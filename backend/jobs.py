"""
In-memory job store + 48hr on-disk analysis cache, backing the async
job/polling API. A background thread runs the full committee pipeline and
calls back into `_update` after every stage1 analysis, debate turn, and the
CIO memo, so GET /analysis/{ticker} always reflects live progress.
"""

import json
import threading
import time

from agents.prompts import AGENTS, DEBATE_TURN_PLAN
from agents.runner import AgentCallError, run_committee
from data.common import CACHE_DIR, format_for_agents
from orchestrator.analyze import fetch_financials

ANALYSIS_TTL_HOURS = 48
TOTAL_STEPS = len(AGENTS) + len(DEBATE_TURN_PLAN) + 1  # stage1 + debate + CIO

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


def _new_job(ticker_key, market):
    return {
        "ticker": ticker_key,
        "market": market,
        "status": "running",
        "data_text": None,
        "stage1": {},
        "debate": [],
        "user_chat": [],
        "cio_memo": None,
        "current_stage": "fetching_data",
        "error": None,
        "started_at": time.time(),
        "completed_at": None,
    }


def start_analysis(ticker, market=None, force=False):
    ticker_key = ticker.upper()

    if not force:
        cached = _load_cached(ticker_key)
        if cached:
            with _lock:
                _jobs[ticker_key] = cached
            return cached

    with _lock:
        existing = _jobs.get(ticker_key)
        if existing and existing["status"] == "running":
            return existing
        job = _new_job(ticker_key, market)
        _jobs[ticker_key] = job

    thread = threading.Thread(target=_run_job, args=(ticker_key, market), daemon=True)
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
        elif event_type == "stage_start":
            job["current_stage"] = payload["stage"]


def _run_job(ticker_key, market):
    try:
        financials = fetch_financials(ticker_key, market=market)
        data_text = format_for_agents(financials)
        with _lock:
            job = _jobs[ticker_key]
            job["market"] = financials.get("market")
            job["data_text"] = data_text
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
        run_committee(ticker_key, data_text, on_update=on_update)
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
    completed = len(job["stage1"]) + len(job["debate"]) + (1 if job.get("cio_memo") else 0)
    return round(completed / TOTAL_STEPS, 3)
