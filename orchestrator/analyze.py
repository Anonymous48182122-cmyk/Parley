"""
Auto-detects whether a ticker is US (SEC EDGAR) or India (Screener.in) and
routes to the matching fetcher. Both fetchers return the same normalized
schema (see data/common.py), so downstream code never needs to know which
market it came from.
"""

from data.common import format_for_agents
from data.india import bse_fetcher
from data.market_data import fetch_market_data
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

    merged_ratios = {**market_data.get("ratios", {}), **(financials.get("ratios") or {})}
    financials["ratios"] = merged_ratios
    return financials


def fetch_financials(ticker, market=None):
    if market == "US":
        financials = edgar_fetcher.fetch(ticker)
    elif market == "India":
        financials = bse_fetcher.fetch(ticker)
    else:
        try:
            financials = edgar_fetcher.fetch(ticker)
        except ValueError:
            financials = bse_fetcher.fetch(ticker)

    return _merge_market_data(financials)


def fetch_and_format(ticker, market=None):
    return format_for_agents(fetch_financials(ticker, market=market))
