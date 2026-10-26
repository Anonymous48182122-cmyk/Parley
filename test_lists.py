from backend import jobs
from data import fallbacks, search


def test_not_found_message_and_kind():
    exc = ValueError("Ticker POAHF not found in SEC company_tickers.json")
    job = {}
    jobs._fail_data(job, exc, "POAHF")
    assert job["error_kind"] == "not_found" and job["status"] == "error"
    assert "over the counter" in job["error"] and "retry" not in job["error"].lower()


def test_other_data_failures_are_not_reported_as_not_found():
    job = {}
    jobs._fail_data(job, ValueError("no usable annual rows"), "AAPL")
    assert "error_kind" not in job


def test_refresh_is_rate_limited():
    search._last_refresh["at"] = 0.0
    assert search.may_refresh_lists() is True
    assert search.may_refresh_lists() is False


def test_market_cap_disagreement_uses_the_other_source(monkeypatch):
    monkeypatch.setattr(fallbacks, "_yahoo_market_cap", lambda t: 69.4e9)
    f = {}
    assert fallbacks.checked_market_cap("RACE", 92.6e9, f) == 69.4e9
    assert any("two sources disagreed" in n for n in f["data_sources"])
    assert fallbacks.checked_market_cap("RACE", 70.0e9, {}) == 70.0e9
    monkeypatch.setattr(fallbacks, "_yahoo_market_cap", lambda t: None)
    assert fallbacks.checked_market_cap("RACE", 92.6e9, {}) == 92.6e9
