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
from data.fallbacks import complete_with_nasdaq, derive_ratios, fill_market_gaps, finish_india_skeleton, india_skeleton
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


def fetch_financials(ticker, market=None):
    if market == "US":
        financials = edgar_fetcher.fetch(ticker)
    elif market == "India":
        try:
            financials = bse_fetcher.fetch(ticker)
        except requests.exceptions.RequestException:
            # Screener unreachable (not "no such company", which is a ValueError): carry on with Yahoo
            financials = india_skeleton(ticker)
    else:
        try:
            financials = edgar_fetcher.fetch(ticker)
        except ValueError:
            financials = bse_fetcher.fetch(ticker)

    financials = complete_with_yahoo(financials)
    if not financials.get("annual") and financials.get("qualitative", "").startswith("Screener.in could not"):
        raise ValueError(f"Could not reach Screener.in or Yahoo Finance for {ticker}; try again shortly")
    if financials.get("qualitative", "").startswith("Screener.in could not"):
        financials = finish_india_skeleton(financials)
    financials = add_latest_quarter_balance(financials)
    financials = complete_with_nasdaq(financials)  # Yahoo is empty from cloud IPs; Nasdaq is the backup
    financials = _merge_market_data(financials)
    financials = fill_market_gaps(financials)
    financials = derive_ratios(financials)
    financials["peers"] = fetch_peers(
        financials["ticker"],
        financials.get("market"),
        own_name=financials.get("name"),
        own_market_cap=financials.get("market_cap"),
    )
    return validate_financials(financials)  # last: drop impossible values, flag disagreements


def fetch_and_format(ticker, market=None):
    return format_for_agents(fetch_financials(ticker, market=market))
