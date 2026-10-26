"""
In-memory job store + 48hr on-disk analysis cache, backing the async
job/polling API. A background thread runs the full committee pipeline and
calls back into `_update` after every stage1 analysis, debate turn, and the
CIO memo, so GET /analysis/{ticker} always reflects live progress.
"""

import json
import logging
import threading
import time

import requests

from agents.prompts import AGENTS, DEFAULT_AGENTS, MIN_AGENTS, build_debate_turn_plan
from agents.business import management_facts, money_flow, pick_wisdom
from agents.runner import AgentCallError, run_committee
from data.common import CACHE_DIR, format_for_agents
from orchestrator.analyze import fetch_financials

ANALYSIS_TTL_HOURS = 48

log = logging.getLogger("parley.jobs")


_NOT_FOUND_WORDS = ("no page for ticker", "not found", "no cik", "could not resolve", "no such")


def _is_not_found(exc, stage):
    return stage == "data" and isinstance(exc, ValueError) and any(k in str(exc).lower() for k in _NOT_FOUND_WORDS)


def not_found_message(ticker):
    text = (f"We could not find {ticker}. Parley covers companies listed on the US exchanges (NYSE and Nasdaq) "
            "and on India's NSE. Please check the spelling, or search by company name.")
    if len(ticker) == 5 and ticker.endswith("F") and ticker.isalpha():
        text += (" A five letter ticker ending in F is usually a foreign share traded over the counter, "
                 "which Parley does not cover yet. Try the company's main stock exchange listing instead.")
    return text


def _fail_data(job, exc, ticker):
    """Marks a run as failed while getting data. A ticker that does not exist gets its own kind of
    failure, with close matches, because trying the same ticker again can never work."""
    job["status"] = "error"
    job["error"] = friendly_error(exc, ticker, "data")
    if _is_not_found(exc, "data"):
        from data.search import search_tickers
        job["error_kind"] = "not_found"
        try:
            job["suggestions"] = [m for m in search_tickers(ticker, limit=5) if m["ticker"].upper() != ticker.upper()][:4]
        except Exception:
            job["suggestions"] = []
    job["completed_at"] = time.time()


def friendly_error(exc, ticker, stage):
    """What the user sees when a run fails: short, plain, and about what to do next. The technical
    detail (connection pool names, model lists) goes to the server log instead of the screen."""
    log.error("analysis of %s failed while %s: %s: %s", ticker, stage, type(exc).__name__, exc)
    text = str(exc).lower()
    if isinstance(exc, AgentCallError):
        return "Our AI models are busy right now. Please try again in a few minutes."
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return "We could not reach one of our data sources just now. This is usually brief. Please try again in a minute."
    if stage == "data" and isinstance(exc, ValueError):
        if _is_not_found(exc, stage):
            return not_found_message(ticker)
        if "could not reach" in text:
            return "We could not reach our data sources for this company. Please try again in a minute."
        return "We could not get financial data for this company right now. It may be newly listed or have no recent filings."
    if stage == "data":
        return "Something went wrong while getting the financial data. Please try again in a minute."
    return "Something went wrong while the committee was working. Please try again."


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
        "scorecards": {},
        "business_card": None,
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


def _business_facts(financials):
    """What the Business Lab draws from the figures themselves: where each 100 of sales goes, who
    runs the company and whose money is on the line, and a real line of investing wisdom that fits."""
    try:
        currency = financials.get("price_currency") or financials.get("currency")
        flow = money_flow(financials)
        net = flow["net"] if flow else None
        return {
            "money_flow": flow,
            "management": management_facts(financials, "INR" if financials.get("market") == "India" else currency),
            "wisdom": pick_wisdom(financials.get("ratios"), net),
        }
    except Exception:
        log.exception("could not build the business facts")
        return None


def _update(ticker_key, event_type, payload):
    with _lock:
        job = _jobs[ticker_key]
        if event_type == "stage1":
            job["stage1"][payload["agent"]] = payload["text"]
            if payload.get("scorecard"):
                job["scorecards"][payload["agent"]] = payload["scorecard"]
        elif event_type == "business_card":
            job["business_card"] = payload.get("card")
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
                # statements can be in a foreign currency (TWD, DKK) while the
                # price and market cap of the US listing are in USD
                "market_cap_unit": financials.get("market_cap_unit") or financials.get("unit_label"),
                "price_currency": financials.get("price_currency") or financials.get("currency"),
                "sector": financials.get("sector"),
                "ratios": financials.get("ratios", {}),
                "technicals": financials.get("technicals") or {},
                "business_facts": _business_facts(financials),
            }
    except ValueError as exc:
        with _lock:
            job = _jobs[ticker_key]
            _fail_data(job, exc, ticker_key)
        return
    except Exception as exc:
        with _lock:
            job = _jobs[ticker_key]
            _fail_data(job, exc, ticker_key)
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
            job["error"] = friendly_error(exc, ticker_key, "committee")
            job["completed_at"] = time.time()
    except Exception as exc:
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "error"
            job["error"] = friendly_error(exc, ticker_key, "committee")
            job["completed_at"] = time.time()


def progress_fraction(job):
    total_steps = len(job.get("agents") or DEFAULT_AGENTS) + len(job.get("turn_plan") or []) + 1
    completed = len(job["stage1"]) + len(job["debate"]) + (1 if job.get("cio_memo") else 0)
    return round(completed / total_steps, 3)
