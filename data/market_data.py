"""
Market/valuation data — price, market cap, P/E, dividend yield, beta,
debt-to-equity, and similar — via yfinance. This is the one layer neither
SEC EDGAR (fundamentals-only XBRL filings, no live market data by design)
nor Screener's scraped tables reliably cover for every field. Free, no API
key, and covers both US and India tickers (NSE via the .NS suffix) through
one uniform interface.

Best-effort like every other fetcher in data/: a missing individual field
becomes None silently, and a total failure returns {} rather than raising,
so a flaky Yahoo response degrades the analysis rather than failing it.
"""

import yfinance as yf

from data.common import cached_fetch

MARKET_DATA_TTL_HOURS = 1  # price/market cap are live — much shorter than fundamentals


def _yf_symbol(ticker, market):
    return f"{ticker.upper()}.NS" if market == "India" else ticker.upper()


def _round(value, digits=2):
    return None if value is None else round(value, digits)


def _pct(value):
    # returnOnEquity/returnOnAssets/profitMargins come back as decimal
    # fractions (0.276 = 27.6%) — unlike dividendYield, which yfinance
    # already reports as a percentage number (5.98 = 5.98%), verified
    # against known high-yield tickers before writing this.
    return None if value is None else f"{round(value * 100, 2)}%"


def _india_crores(value):
    # Screener (bse_fetcher.py) reports market cap in crores (1 Cr = 10^7),
    # matching the app's "INR Cr." unit_label for India — but yfinance
    # always returns market cap in raw rupees regardless of market. Only
    # used as a fallback when Screener's own value is missing (rare, since
    # Screener usually has it), but without this conversion a fallback
    # would show a number ~10 million times too large under a label that
    # says crores.
    return None if value is None else round(value / 1e7, 2)


def _fetch(ticker, market):
    symbol = _yf_symbol(ticker, market)
    info = yf.Ticker(symbol).info or {}

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    market_cap = info.get("marketCap")
    if market == "India":
        market_cap = _india_crores(market_cap)

    sector = info.get("sector")
    industry = info.get("industry")

    dividend_yield = info.get("dividendYield")
    ratios = {
        "P/E Ratio (Trailing)": _round(info.get("trailingPE")),
        "P/E Ratio (Forward)": _round(info.get("forwardPE")),
        "PEG Ratio": _round(info.get("pegRatio")),
        "Dividend Yield": None if dividend_yield is None else f"{_round(dividend_yield)}%",
        "52-Week High": _round(info.get("fiftyTwoWeekHigh")),
        "52-Week Low": _round(info.get("fiftyTwoWeekLow")),
        "Beta": _round(info.get("beta")),
        "Debt to Equity": _round(info.get("debtToEquity")),
        "Current Ratio": _round(info.get("currentRatio")),
        "Return on Equity": _pct(info.get("returnOnEquity")),
        "Return on Assets": _pct(info.get("returnOnAssets")),
        "Net Profit Margin": _pct(info.get("profitMargins")),
        "Book Value per Share": _round(info.get("bookValue")),
        "Industry": industry,
    }
    ratios = {k: v for k, v in ratios.items() if v is not None}

    return {"price": price, "market_cap": market_cap, "sector": sector, "ratios": ratios}


def fetch_market_data(ticker, market):
    """Returns {"price": ..., "market_cap": ..., "ratios": {...}}, or {} on
    total failure — callers should treat {} as "no market data available"
    rather than an error."""
    try:
        cache_key = f"market_{market}_{ticker.upper()}"
        return cached_fetch(cache_key, MARKET_DATA_TTL_HOURS, lambda: _fetch(ticker, market))
    except Exception:
        return {}
