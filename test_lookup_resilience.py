"""A company that is listed must never be reported as "not found" because one source had a bad moment.

Screener can lack a page, or have a page with no figures yet, for a company that listed this week (Jio Platforms
was one). The lookup then asks Screener's search by company name, then falls back to Yahoo's statements and
prices, and only gives up when nothing at all can be found. A listed company that still fails says so truthfully.
"""

import pytest
import requests

import orchestrator.analyze as analyze
from backend import jobs
from data.search import _is_derivative


def boom(*_a, **_k):
    raise ValueError("Screener.in has no page for ticker JPL (status 404)")


def test_a_differently_named_page_is_found_by_company_name(monkeypatch):
    seen = []

    def fetch(ticker):
        seen.append(ticker)
        if ticker == "JPL":
            raise ValueError("Screener.in has no page for ticker JPL (status 404)")
        return {"ticker": ticker, "name": "Jio Platforms Ltd", "market": "India"}

    monkeypatch.setattr(analyze.bse_fetcher, "fetch", fetch)
    monkeypatch.setattr(analyze, "_screener_slug_by_name", lambda t: "JIOPLATFORMS")
    found = analyze.fetch_india("JPL")
    assert seen == ["JPL", "JIOPLATFORMS"]
    assert found["ticker"] == "JPL"  # the page is under another name, the company keeps the one the person picked


def test_yahoo_is_the_fallback_when_screener_has_nothing(monkeypatch):
    monkeypatch.setattr(analyze.bse_fetcher, "fetch", boom)
    monkeypatch.setattr(analyze, "_screener_slug_by_name", lambda t: None)
    monkeypatch.setattr(analyze, "india_skeleton", lambda t: {"ticker": t, "market": "India", "price": 1369.0})
    assert analyze.fetch_india("JPL")["price"] == 1369.0


def test_a_connection_failure_takes_the_same_road(monkeypatch):
    def down(_t):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(analyze.bse_fetcher, "fetch", down)
    monkeypatch.setattr(analyze, "_screener_slug_by_name", lambda t: None)
    monkeypatch.setattr(analyze, "india_skeleton", lambda t: {"ticker": t, "market": "India", "price": 10.0})
    assert analyze.fetch_india("ABC")["price"] == 10.0


def test_the_original_error_is_raised_when_nothing_is_found(monkeypatch):
    monkeypatch.setattr(analyze.bse_fetcher, "fetch", boom)
    monkeypatch.setattr(analyze, "_screener_slug_by_name", lambda t: None)
    monkeypatch.setattr(analyze, "india_skeleton", lambda t: {"ticker": t, "market": "India", "price": None})
    with pytest.raises(ValueError, match="no page"):
        analyze.fetch_india("ZZZZ")


def test_an_unspecified_market_also_falls_back(monkeypatch):
    def no_edgar(_t):
        raise ValueError("Ticker JPL not found in SEC company_tickers.json")

    monkeypatch.setattr(analyze.edgar_fetcher, "fetch", no_edgar)
    monkeypatch.setattr(analyze, "fetch_india", lambda t: (_ for _ in ()).throw(ValueError("stop here")))
    with pytest.raises(ValueError, match="stop here"):
        analyze.fetch_financials("JPL")  # it reached the Indian lookup after the SEC said no


def test_hong_kong_warrants_are_not_companies():
    assert _is_derivative("29843.HK", "JPLENOV@EC2611B")
    assert _is_derivative("14633.HK", "something")
    assert not _is_derivative("0700.HK", "Tencent Holdings Limited")
    assert not _is_derivative("09988.HK", "Alibaba Group Holding Limited")
    assert not _is_derivative("7203.T", "Toyota Motor Corporation")


def test_a_listed_company_is_never_called_not_found(monkeypatch):
    monkeypatch.setattr(jobs, "_is_listed", lambda t: True)
    job = {}
    jobs._fail_data(job, ValueError("Screener.in has no page for ticker JPL (status 404)"), "JPL")
    assert job["status"] == "error"
    assert "could not find" not in job["error"].lower()
    assert "listed" in job["error"]
    assert job.get("error_kind") != "not_found"


def test_a_typo_is_still_not_found_with_suggestions(monkeypatch):
    monkeypatch.setattr(jobs, "_is_listed", lambda t: False)
    import data.search as search

    monkeypatch.setattr(search, "search_tickers", lambda q, limit=5: [{"ticker": "JPM", "name": "JPMorgan", "market": "US"}])
    job = {}
    jobs._fail_data(job, ValueError("Screener.in has no page for ticker JPX (status 404)"), "JPX")
    assert job["error_kind"] == "not_found"
    assert job["suggestions"][0]["ticker"] == "JPM"


from data.search import instrument_kind


def test_funds_warrants_units_and_rights_are_not_offered_as_companies():
    us = {"PSQL", "NEWC", "KO"}
    assert instrument_kind("CPSEETF", "CPSE ETF", "India", us) == "fund"
    assert instrument_kind("NIFTYJBLK", "Jio BlackRock Mutual Fund", "India", us) == "fund"
    assert instrument_kind("SPY", "SPDR S&P 500 ETF TRUST", "US", us) == "fund"
    assert instrument_kind("PSQLW", "Pasqal Holding SA", "US", us) == "warrant"
    assert instrument_kind("FTRA-UN", "FutureCorp Space Acquisition 1", "US", us) == "unit"
    assert instrument_kind("COPR-WT", "Idaho Copper Corp", "US", us) == "warrant"
    assert instrument_kind("OLAELEC-RE", "Ola Electric Mobility Limited", "India", us) == "right"


def test_real_companies_are_never_dropped():
    us = {"GROW", "KO", "BRK-A"}
    for ticker, name, market in [
        ("KO", "COCA COLA CO", "US"), ("BRK-B", "BERKSHIRE HATHAWAY INC", "US"), ("BF-B", "BROWN FORMAN CORP", "US"),
        ("RELIANCE", "Reliance Industries Ltd", "India"), ("JPL", "Jio Platforms Limited", "India"),
        ("AZAD", "Azad Engineering Ltd", "India"),
        # an Indian ticker that happens to look like a US warrant (GROW + W) is still a company
        ("GROWW", "Billionbrains Garage Ventures Limited", "India"),
        ("BEESCO", "Bees Knees Ltd", "India"),  # a name containing "Bees" is not a fund
        ("XYZ-BE", "Some Trade To Trade Ltd", "India"),
    ]:
        assert instrument_kind(ticker, name, market, us) is None, ticker


def test_preferred_series_and_spac_shells():
    assert instrument_kind("GAB-PH", "Gabelli Equity Trust Preferred", "US", set()) == "preferred"
    assert instrument_kind("BRK-B", "BERKSHIRE HATHAWAY INC", "US", set()) is None


def test_a_spac_shell_gets_its_own_plain_message():
    text = jobs.friendly_error(ValueError("EVOX is a blank check company (SPAC) with no business or statements yet"), "EVOX", "data")
    assert "blank check" in text and "could not find" not in text.lower()


from data.search import is_otc_foreign


def test_over_the_counter_foreign_lines_are_dropped_but_exchange_listed_adrs_stay():
    listed = {f"T{i}" for i in range(1500)} | {"RYAAY", "KO"}
    assert is_otc_foreign("DTEGY", "US", listed)  # Deutsche Telekom's OTC ADR
    assert is_otc_foreign("RTNTF", "US", listed)  # Rio Tinto's OTC ordinary share
    assert not is_otc_foreign("RYAAY", "US", listed)  # Ryanair's ADR is listed on Nasdaq
    assert not is_otc_foreign("KO", "US", listed)
    assert not is_otc_foreign("DTEGY", "India", listed)
    assert not is_otc_foreign("DTEGY", "US", {"KO"})  # a failed exchange list never empties the search


def test_live_search_matches_are_held_to_the_same_rule(monkeypatch):
    import data.search as search

    monkeypatch.setattr(search, "_screener_matches", lambda q, n: [
        {"ticker": "CPSEETF", "name": "CPSE ETF", "market": "India", "country": "IN"},
        {"ticker": "CPSE", "name": "CPSE Industries Ltd", "market": "India", "country": "IN"},
    ])
    monkeypatch.setattr(search, "_yahoo_global_matches", lambda q, n: [])
    monkeypatch.setattr(search, "_build_all_entries", lambda: [])
    monkeypatch.setattr(search, "_memoized", lambda key, fn: fn())
    found = search.search_tickers("CPSE", limit=8)
    assert [m["ticker"] for m in found] == ["CPSE"]


def test_closed_end_funds_go_but_lending_funds_that_are_businesses_stay():
    assert instrument_kind("PDI", "PIMCO Dynamic Income Fund", "US", set()) == "fund"
    assert instrument_kind("ETB", "Eaton Vance Tax-Managed Buy-Write Income Fund", "US", set()) == "fund"
    assert instrument_kind("BXSL", "Blackstone Secured Lending Fund", "US", set()) is None
    assert instrument_kind("MSDL", "Morgan Stanley Direct Lending Fund", "US", set()) is None
    assert instrument_kind("KO", "COCA COLA CO", "US", set()) is None
