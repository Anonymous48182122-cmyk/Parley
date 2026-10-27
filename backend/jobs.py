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
from backend import job_store
from agents.business import management_facts, money_flow, pick_wisdom, wisdom_features
from data.people import fetch_people
from agents.runner import AgentCallError, run_cio, run_committee
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


_dirty = set()
_dirty_lock = threading.Lock()
_saver_started = False
_PRUNE_EVERY = 3600


def _touch(ticker_key):
    """Note that a run changed, so the background saver writes it to the durable store soon."""
    global _saver_started
    with _dirty_lock:
        _dirty.add(ticker_key)
        if _saver_started:
            return
        _saver_started = True
    threading.Thread(target=_saver, daemon=True).start()


def _saver():
    last_prune = 0.0
    while True:
        time.sleep(3)
        with _dirty_lock:
            keys = list(_dirty)
            _dirty.clear()
        for key in keys:
            with _lock:
                job = _jobs.get(key)
                text = json.dumps(job) if job else None
            if text:
                job_store.save(key, text)
        if time.time() - last_prune > _PRUNE_EVERY:
            last_prune = time.time()
            job_store.prune()


def _load_durable(ticker_key):
    """A run saved before a restart. One that was still running when the server went down has no thread
    behind it any more, so it is shown as stopped early, with everything it had produced."""
    job = job_store.load(ticker_key)
    if not job:
        return None
    if job.get("status") == "running":
        if not (job.get("stage1") or job.get("debate")):
            return None  # it had produced nothing yet: starting again loses nothing
        job["status"] = "error"
        job["error_kind"] = "interrupted"
        job["error"] = "The server restarted while this was running."
    return job


def _load_cached(ticker):
    path = _cache_path(ticker)
    if not path.exists():
        durable = _load_durable(ticker.upper())
        return durable if durable and durable.get("status") == "complete" else None
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
    key = ticker.upper()
    with _lock:
        job = _jobs.get(key)
    if job:
        return job
    job = _load_durable(key)
    if not job:
        return None
    with _lock:
        return _jobs.setdefault(key, job)


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
    _touch(ticker_key)
    return job


def clear_cache(ticker):
    ticker_key = ticker.upper()
    path = _cache_path(ticker_key)
    if path.exists():
        path.unlink()
    with _lock:
        _jobs.pop(ticker_key, None)
    job_store.delete(ticker_key)


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
        people = fetch_people(financials.get("name"))
        management = management_facts(financials, "INR" if financials.get("market") == "India" else currency, people)
        last = (financials.get("annual") or [{}])[-1]
        rnd = (last.get("rnd") / last["revenue"] * 100) if last.get("rnd") and last.get("revenue") else None
        inputs = {"sector": financials.get("sector"), "rnd_pct": rnd}
        features = wisdom_features(financials.get("ratios"), net, financials.get("market"), management, **inputs)
        return {
            "money_flow": flow,
            "management": management,
            "wisdom": pick_wisdom(features, financials.get("ticker", "")),
            "wisdom_inputs": inputs,
        }
    except Exception:
        log.exception("could not build the business facts")
        return None


def _refresh_wisdom(job):
    """Once the committee has rated the business and the card has named its moat, pick the quote
    again with all of that known, so the line chosen is the most apt one and not just a first guess."""
    try:
        facts = (job.get("market_data") or {}).get("business_facts")
        if not facts:
            return
        features = wisdom_features((job["market_data"] or {}).get("ratios"),
                                   (facts.get("money_flow") or {}).get("net"), job.get("market"),
                                   facts.get("management"), job.get("business_card"), job.get("scorecards"),
                                   **(facts.get("wisdom_inputs") or {}))
        facts["wisdom"] = pick_wisdom(features, job.get("ticker", ""))
    except Exception:
        log.exception("could not refresh the quote")


def _update(ticker_key, event_type, payload):
    with _lock:
        job = _jobs[ticker_key]
        if event_type == "stage1":
            job["stage1"][payload["agent"]] = payload["text"]
            if payload.get("scorecard"):
                job["scorecards"][payload["agent"]] = payload["scorecard"]
        elif event_type == "business_card":
            job["business_card"] = payload.get("card")
            _refresh_wisdom(job)
        elif event_type == "debate_turn":
            job["debate"].append(payload)
        elif event_type == "cio":
            job["cio_memo"] = payload["text"]
            job["verdict"] = payload.get("verdict")
            job["conviction"] = payload.get("conviction")
            job["cio_fallback"] = bool(payload.get("fallback"))
        elif event_type == "stage_start":
            job["current_stage"] = payload["stage"]
    _touch(ticker_key)


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
        _touch(ticker_key)
        return
    except Exception as exc:
        with _lock:
            job = _jobs[ticker_key]
            _fail_data(job, exc, ticker_key)
        _touch(ticker_key)
        return

    _touch(ticker_key)  # the figures are in: keep the run from here on

    def on_update(event_type, payload):
        _update(ticker_key, event_type, payload)

    try:
        run_committee(ticker_key, data_text, agent_keys=agent_keys, on_update=on_update)
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "complete"
            job["completed_at"] = time.time()
            _save_cache(ticker_key, job)
    except Exception as exc:  # AgentCallError and anything unexpected end the run the same way
        with _lock:
            job = _jobs[ticker_key]
            job["status"] = "error"
            job["error"] = friendly_error(exc, ticker_key, "committee")
            job["completed_at"] = time.time()
    _touch(ticker_key)


def retry_cio(ticker):
    """Ask the CIO again for a finished session whose memo was only the automatic summary. Runs in the
    background; the page polls. Returns the job, or None when there is nothing to retry."""
    ticker_key = ticker.upper()
    get_job(ticker_key)  # loads it from the durable store if the server has restarted
    with _lock:
        job = _jobs.get(ticker_key)
        if not job or not job.get("cio_fallback") or job.get("cio_retrying") or not job.get("data_text"):
            return job
        job["cio_retrying"] = True

    def work():
        try:
            turns = [(t["agent"], t["text"]) for t in job["debate"]]
            memo, verdict, conviction = run_cio(ticker_key, job["data_text"], turns, job["stage1"])
            with _lock:
                job["cio_memo"], job["verdict"], job["conviction"] = memo, verdict, conviction
                job["cio_fallback"] = False
                _save_cache(ticker_key, job)
            _touch(ticker_key)
        except Exception:
            log.warning("asking the CIO again for %s failed", ticker_key)
        finally:
            with _lock:
                job["cio_retrying"] = False

    threading.Thread(target=work, daemon=True).start()
    return job


def progress_fraction(job):
    total_steps = len(job.get("agents") or DEFAULT_AGENTS) + len(job.get("turn_plan") or []) + 1
    completed = len(job["stage1"]) + len(job["debate"]) + (1 if job.get("cio_memo") else 0)
    return round(completed / total_steps, 3)
