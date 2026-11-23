"""
Auto-detects whether a ticker is US (SEC EDGAR) or India (Screener.in) and
routes to the matching fetcher. Both fetchers return the same normalized
schema (see data/common.py), so downstream code never needs to know which
market it came from.
"""

import requests

from data.common import format_for_agents
from data.india import bse_fetcher
from data.market_data import fetch_market_data
from data.peers import fetch_peers
from data.groups import fetch_segment_comps
from data.countries import is_global_symbol
from data.fallbacks import complete_with_nasdaq, derive_ratios, fill_market_gaps, finish_india_skeleton, india_skeleton
from data.global_equities import finish_global, global_skeleton
from data.validate import validate_financials
from data.yahoo_fundamentals import add_latest_quarter_balance, complete_with_yahoo
from data.us import edgar_fetcher


def _merge_market_data(financials):
    """SEC EDGAR has no price/market data at all (fundamentals-only by
    design), and Screener's own numbers don't cover beta, debt-to-equity,
    current ratio, ROA, or net margin reliably — yfinance fills whatever's
    missing for both markets. Screener's own already-parsed values win on
    a literal key collision (they're India-report-convention-tuned);
    everything else from both sources coexists in the ratios dict."""
    market_data = fetch_market_data(financials["ticker"], financials.get("market"))
    if not market_data:
        return financials

    if financials.get("price") is None:
        financials["price"] = market_data.get("price")
    if financials.get("market_cap") is None:
        financials["market_cap"] = market_data.get("market_cap")
    if financials.get("sector") in (None, "N/A") and market_data.get("sector"):
        financials["sector"] = market_data["sector"]

    # Price action and the business description: keep whatever the primary source
    # already supplied (Screener's own series for India), else use Yahoo's.
    for key in ("technicals", "business_summary", "governance"):
        if not financials.get(key) and market_data.get(key):
            financials[key] = market_data[key]

    merged_ratios = {**market_data.get("ratios", {}), **(financials.get("ratios") or {})}
    financials["ratios"] = merged_ratios
    return financials


def _listed_name(ticker):
    """The company's full name from the NSE or BSE list, or None."""
    try:
        from data.india.bse_fetcher import get_bse_list, get_symbol_list

        want = ticker.upper()
        return (next((r["name"] for r in get_symbol_list() if r["symbol"].upper() == want), None)
                or next((r["name"] for r in get_bse_list() if r["symbol"].upper() == want), None))
    except Exception:
        return None


def _screener_slug_by_name(ticker):
    """The name Screener files a listed company under, found by asking its own search for the company's name (our
    lists know the name for every NSE and BSE ticker). Covers the case where the short name on the exchange list is
    not the name Screener's page is under. None when nothing sensible comes back."""
    try:
        from data.search import _screener_matches_live

        name = _listed_name(ticker)
        if not name:
            return None
        return next((m["ticker"] for m in _screener_matches_live(name, 3) if m.get("ticker")), None)
    except Exception:
        return None


def fetch_india(ticker):
    """An Indian company's figures. Screener first. When its page is missing, blank (a company that listed this week
    has a page before it has any figures) or unreachable, ask Screener's search for the right page by company name,
    and when that fails too fall back to Yahoo's statements and price history, so a company that exists on the
    exchange gets an analysis rather than an error. Raises the original error only when nothing at all can be found."""
    try:
        return bse_fetcher.fetch(ticker)
    except (requests.exceptions.RequestException, ValueError) as first:
        slug = _screener_slug_by_name(ticker)
        if slug and slug.upper() != ticker.upper():
            try:
                found = bse_fetcher.fetch(slug)
                found["ticker"] = ticker.upper()
                return found
            except (requests.exceptions.RequestException, ValueError):
                pass
        skeleton = india_skeleton(ticker)
        if skeleton.get("price") is None:
            raise first
        skeleton["name"] = _listed_name(ticker) or skeleton.get("name")
        return skeleton


def fetch_financials(ticker, market=None):
    if market is None and is_global_symbol(ticker):
        market = "Global"  # 7203.T, SAP.DE, 0700.HK: the exchange suffix says where it trades
    if market == "Global":
        financials = global_skeleton(ticker)
    elif market == "US":
        financials = edgar_fetcher.fetch(ticker)
    elif market == "India":
        financials = fetch_india(ticker)
    else:
        try:
            financials = edgar_fetcher.fetch(ticker)
        except ValueError:
            financials = fetch_india(ticker)

    financials = complete_with_yahoo(financials)
    if not financials.get("annual") and financials.get("qualitative", "").startswith("Screener.in could not"):
        raise ValueError(f"Could not reach Screener.in or Yahoo Finance for {ticker}; try again shortly")
    if financials.get("qualitative", "").startswith("Screener.in could not"):
        financials = finish_india_skeleton(financials)
    financials = add_latest_quarter_balance(financials)
    if financials.get("market") == "Global":
        if not financials.get("annual"):
            raise ValueError(f"No financial statements found for {ticker}")
        financials = finish_global(financials)
    financials = complete_with_nasdaq(financials)  # Yahoo is empty from cloud IPs; Nasdaq is the backup
    financials = _merge_market_data(financials)
    financials = fill_market_gaps(financials)
    if not financials.get("annual") and financials.get("price") is None:
        # nothing to read at all (a blank cheque company, a fund, a symbol that stopped trading): say so before the committee is convened
        raise ValueError(f"No financial statements or prices found for {ticker}")
    financials = derive_ratios(financials)
    financials["peers"] = fetch_peers(
        financials["ticker"],
        financials.get("market"),
        own_name=financials.get("name"),
        own_market_cap=financials.get("market_cap"),
    )
    financials["segment_comps"] = fetch_segment_comps(financials["ticker"], financials.get("market"))
    return validate_financials(financials)  # last: drop impossible values, flag disagreements


def fetch_and_format(ticker, market=None):
    return format_for_agents(fetch_financials(ticker, market=market))
