"""
In-memory job store + 48hr on-disk analysis cache, backing the async
job/polling API. A background thread runs the full committee pipeline and
calls back into `_update` after every stage1 analysis, debate turn, and the
CIO memo, so GET /analysis/{ticker} always reflects live progress.
"""

import json
import threading
import time

from agents.prompts import AGENTS, DEFAULT_AGENTS, MIN_AGENTS, build_debate_turn_plan
from agents.runner import AgentCallError, run_committee
from data.common import CACHE_DIR, format_for_agents
from orchestrator.analyze import fetch_financials

ANALYSIS_TTL_HOURS = 48


def normalize_agents(agent_keys):
    """Validates a requested committee against the known roster, falling back
    to the default 9 on anything unusable (empty, unknown keys, too few)
    rather than 400ing — a bad/stale agent list shouldn't block the whole
    analysis. Returns (agent_keys, warning_or_None)."""
    if not agent_keys:
        return DEFAULT_AGENTS, None
    known = [key for key in agent_keys if key in AGENTS]
    # de-dupe while preserving the user's chosen order
    seen = set()
    known = [key for key in known if not (key in seen or seen.add(key))]
    if len(known) < MIN_AGENTS:
        return DEFAULT_AGENTS, f"Need at least {MIN_AGENTS} valid agents; using the default committee."
    return known, None

_jobs = {}
_lock = threading.Lock()


def _cache_path(ticker):
    return CACHE_DIR / f"analysis_{ticker.upper()}.json"


def _load_cached(ticker):
    path = _cache_path(ticker)
    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours >= ANALYSIS_TTL_HOURS:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(ticker, job):
    try:
        _cache_path(ticker).write_text(json.dumps(job), encoding="utf-8")
    except OSError:
        pass  # caching is best-effort; a failed write shouldn't fail the request


def get_job(ticker):
    with _lock:
        return _jobs.get(ticker.upper())


def record_chat(ticker, entry):
    """Appends a user Q&A exchange to the job and re-persists the on-disk
    cache, so a page refresh doesn't lose the conversation within the
    48hr cache window — unlike cross-exam, which is frontend-only state."""
    ticker_key = ticker.upper()
    with _lock:
        job = _jobs.get(ticker_key)
        if not job:
            return None
        job["user_chat"].append(entry)
        _save_cache(ticker_key, job)
        return job


def clear_cache(ticker):
    ticker_key = ticker.upper()
    path = _cache_path(ticker_key)
    if path.exists():
        path.unlink()
    with _lock:
        _jobs.pop(ticker_key, None)


def _new_job(ticker_key, market, agent_keys):
    return {
        "ticker": ticker_key,
        "market": market,
        "agents": agent_keys,
        # The debate's actual speaking order for this roster — the frontend's
        # "X is weighing in" indicator reads this instead of assuming a fixed
        # script, since the turn plan is generated fresh per roster.
        "turn_plan": [agent_key for _, agent_key, _ in build_debate_turn_plan(agent_keys)],
        "status": "running",
        "data_text": None,
        "market_data": None,
        "stage1": {},
        "debate": [],
        "user_chat": [],
        "cio_memo": None,
        "verdict": None,
        "conviction": None,
        "current_stage": "fetching_data",
        "error": None,
        "started_at": time.time(),
        "completed_at": None,
    }


def start_analysis(ticker, market=None, agents=None, force=False):
    ticker_key = ticker.upper()
    agent_keys, agent_warning = normalize_agents(agents)
    # No committee specified (a direct link, or a page refresh that lost the
    # picker's router state) means "whatever is already running or cached for
    # this ticker" — not "the default nine". Treating it as the default would
    # replace a user's custom-committee debate with a fresh default one every
    # time they refreshed the page.
    unspecified = not agents

    def same_committee(job):
        return unspecified or job.get("agents") == agent_keys

    if not force:
        cached = _load_cached(ticker_key)
        # Otherwise only reuse the cache for the same committee — a different
        # explicit selection must actually run the debate it asked for rather
        # than silently returning an earlier one.
        if cached and same_committee(cached):
            # Caches written before committee selection existed have no
            # roster; their first-pass keys are the committee that ran.
            cached.setdefault("agents", list(cached.get("stage1", {})))
            with _lock:
                _jobs[ticker_key] = cached
            return cached

    with _lock:
        existing = _jobs.get(ticker_key)
        if existing and existing["status"] == "running" and same_committee(existing):
            return existing
        job = _new_job(ticker_key, market, agent_keys)
        if agent_warning:
            job["agent_warning"] = agent_warning
        _jobs[ticker_key] = job

    thread = threading.Thread(target=_run_job, args=(ticker_key, market, agent_keys), daemon=True)
    thread.start()
    return job


def _update(ticker_key, event_type, payload):
    with _lock:
        job = _jobs[ticker_key]
        if event_type == "stage1":
            job["stage1"][payload["agent"]] = payload["text"]
        elif event_type == "debate_turn":
            job["debate"].append(payload)
        elif event_type == "cio":
            job["cio_memo"] = payload["text"]
            job["verdict"] = payload.get("verdict")
            job["conviction"] = payload.get("conviction")
        elif event_type == "stage_start":
            job["current_stage"] = payload["stage"]


def _run_job(ticker_key, market, agent_keys):
    try:
        financials = fetch_financials(ticker_key, market=market)
        data_text = format_for_agents(financials)
        with _lock:
            job = _jobs[ticker_key]
            job["market"] = financials.get("market")
            job["data_text"] = data_text
            # Structured subset for the frontend's price/range visual — the
            # rest of `financials` (annual rows, shareholding, qualitative
            # text) is only ever needed as the prose already baked into
            # data_text, not as separate UI state.
            job["market_data"] = {
                "price": financials.get("price"),
                "market_cap": financials.get("market_cap"),
                "currency": financials.get("currency"),
                "unit_label": financials.get("unit_label"),
                "sector": financials.get("sector"),
                "ratios": financials.get("ratios", {}),
            }
    except ValueError as exc:
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "error"
            job["error"] = f"Could not fetch financial data: {exc}"
            job["completed_at"] = time.time()
        return
    except Exception as exc:
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "error"
            job["error"] = f"Unexpected error fetching data: {exc}"
            job["completed_at"] = time.time()
        return

    def on_update(event_type, payload):
        _update(ticker_key, event_type, payload)

    try:
        run_committee(ticker_key, data_text, agent_keys=agent_keys, on_update=on_update)
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "complete"
            job["completed_at"] = time.time()
            _save_cache(ticker_key, job)
    except AgentCallError as exc:
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "error"
            job["error"] = str(exc)
            job["completed_at"] = time.time()
    except Exception as exc:
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "error"
            job["error"] = f"Unexpected error during committee run: {exc}"
            job["completed_at"] = time.time()


def progress_fraction(job):
    total_steps = len(job.get("agents") or DEFAULT_AGENTS) + len(job.get("turn_plan") or []) + 1
    completed = len(job["stage1"]) + len(job["debate"]) + (1 if job.get("cio_memo") else 0)
    return round(completed / total_steps, 3)
