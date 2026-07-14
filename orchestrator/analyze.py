"""
Auto-detects whether a ticker is US (SEC EDGAR) or India (Screener.in) and
routes to the matching fetcher. Both fetchers return the same normalized
schema (see data/common.py), so downstream code never needs to know which
market it came from.
"""

from data.common import format_for_agents
from data.india import bse_fetcher
from data.us import edgar_fetcher


def fetch_financials(ticker, market=None):
    if market == "US":
        return edgar_fetcher.fetch(ticker)
    if market == "India":
        return bse_fetcher.fetch(ticker)

    try:
        return edgar_fetcher.fetch(ticker)
    except ValueError:
        return bse_fetcher.fetch(ticker)


def fetch_and_format(ticker, market=None):
    return format_for_agents(fetch_financials(ticker, market=market))
