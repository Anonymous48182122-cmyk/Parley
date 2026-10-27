"""
A durable copy of each analysis, kept in Supabase (table parley_jobs, see sql/parley_jobs.sql).

Runs live in the server's memory, and the free host restarts whenever a new version goes live or it
wakes from sleep, which used to wipe a run in the middle of someone reading it. Writing each run here
as it progresses lets the page pick it up again after a restart.

Best effort and optional: when the table does not exist or Supabase cannot be reached, every call here
quietly does nothing for a few minutes and the app works exactly as before, from memory and disk.
"""

import json
import logging
import time

log = logging.getLogger("parley.jobs")

TABLE = "parley_jobs"
MAX_AGE_HOURS = 48
_PAUSE_SECONDS = 600
_paused_until = 0.0


def _client():
    from backend.history import _get_client
    return _get_client()


def _guard(action, fn, default=None):
    global _paused_until
    if time.time() < _paused_until:
        return default
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        _paused_until = time.time() + _PAUSE_SECONDS
        log.warning("job store %s failed, pausing it for %d minutes: %.200s", action, _PAUSE_SECONDS // 60, exc)
        return default


def save(ticker, job_json):
    def go():
        _client().table(TABLE).upsert({"ticker": ticker.upper(), "job": json.loads(job_json),
                                       "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}).execute()
    _guard("save", go)


def load(ticker):
    """The saved job for a ticker if it is younger than MAX_AGE_HOURS, else None."""
    def go():
        rows = _client().table(TABLE).select("job,updated_at").eq("ticker", ticker.upper()).limit(1).execute().data
        if not rows:
            return None
        saved = time.mktime(time.strptime(rows[0]["updated_at"][:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
        return rows[0]["job"] if (time.time() - saved) / 3600 < MAX_AGE_HOURS else None
    return _guard("load", go)


def delete(ticker):
    _guard("delete", lambda: _client().table(TABLE).delete().eq("ticker", ticker.upper()).execute())


def prune():
    """Removes runs past their useful life, so the table stays small."""
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3 * 24 * 3600))
    _guard("prune", lambda: _client().table(TABLE).delete().lt("updated_at", cutoff).execute())
