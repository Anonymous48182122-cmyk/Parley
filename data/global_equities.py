"""
Companies listed on exchanges outside the US and India (Tokyo, London, Frankfurt, Hong Kong, Seoul, Zurich...).

There is no filing library like SEC EDGAR for these, so the figures come from Yahoo Finance: its annual and
quarterly statements and its daily price history, both of which still answer a cloud server (only its
company profile page is refused). That is thinner than a US or Indian analysis (no filing text, no
shareholding pattern, no peer table) and the data block says so plainly instead of pretending.

The traps this module exists to handle:
- the currency the company reports in is often not the one its shares trade in (Tencent reports in yuan and
  trades in Hong Kong dollars; HSBC reports in dollars and trades in pence), so the reporting currency is read
  from Yahoo's timeseries endpoint, which states it, and the market cap is converted into it so ratios divide
  like by like;
- London, Johannesburg and Tel Aviv quote prices in a hundredth of the main unit (pence, cents, agorot);
- a day with no trading leaves a blank at the end of the price history.

Best effort like every fetcher in data/: a failure leaves a gap, and the page shows what it could get.
"""

import time

import requests

from data.common import cached_fetch
from data.countries import COUNTRY_NAMES, SUBUNIT_CURRENCIES, country_of_symbol
from data.technicals import compute_technicals

_HEADERS = {"User-Agent": "Mozilla/5.0"}
META_TTL_HOURS = 24 * 7
FX_TTL_HOURS = 6


def _timeseries_currency(symbol, kind):
    now = int(time.time())
    r = requests.get(f"https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}",
                     params={"type": kind, "period1": now - 4 * 366 * 86400, "period2": now}, headers=_HEADERS, timeout=12)
    r.raise_for_status()
    result = (r.json().get("timeseries") or {}).get("result") or []
    values = (result[0].get(kind) or []) if result else []
    return values[-1].get("currencyCode") if values else None


def financial_currency(symbol):
    """The currency a company's statements are in, as Yahoo states it (None when it will not say)."""
    def fetch():
        for kind in ("annualTotalRevenue", "annualNetIncome", "annualTotalAssets"):
            code = _timeseries_currency(symbol, kind)
            if code:
                return code
        raise ValueError(f"no reporting currency for {symbol}")
    try:
        return cached_fetch(f"fincur_{symbol.upper()}", META_TTL_HOURS, fetch)
    except Exception:
        return None


def fx_rate(frm, to):
    """How many `to` one `frm` buys (1 when they are the same; None when Yahoo has no such pair)."""
    if not frm or not to:
        return None
    if frm == to:
        return 1.0

    def fetch():
        import yfinance as yf
        closes = yf.Ticker(f"{frm}{to}=X").history(period="5d")["Close"].dropna()
        if not len(closes):
            raise ValueError("no rate")
        return float(closes.iloc[-1])
    try:
        return cached_fetch(f"fx_{frm}_{to}", FX_TTL_HOURS, fetch)
    except Exception:
        return None


def symbol_meta(symbol):
    """Name, exchange, sector and industry for a Yahoo symbol, from Yahoo's search (the profile page is blocked)."""
    def fetch():
        r = requests.get("https://query2.finance.yahoo.com/v1/finance/search",
                         params={"q": symbol, "quotesCount": 8, "newsCount": 0, "listsCount": 0}, headers=_HEADERS, timeout=12)
        r.raise_for_status()
        for q in r.json().get("quotes", []):
            if (q.get("symbol") or "").upper() == symbol.upper():
                return {"name": q.get("longname") or q.get("shortname"), "exchange": q.get("exchDisp"),
                        "sector": q.get("sectorDisp") or q.get("sector"), "industry": q.get("industryDisp") or q.get("industry")}
        raise ValueError("symbol not in search results")
    try:
        return cached_fetch(f"gmeta_{symbol.upper()}", META_TTL_HOURS, fetch)
    except Exception:
        return {}


def _trading_currency(stock, symbol):
    """(main currency, divisor) for the price: GBp becomes GBP with 100, and so on."""
    code = None
    try:
        code = (stock.history_metadata or {}).get("currency")
    except Exception:
        pass
    if not code:
        try:
            code = stock.fast_info.get("currency")
        except Exception:
            code = None
    if code in SUBUNIT_CURRENCIES:
        return SUBUNIT_CURRENCIES[code]
    return code, 1


def global_skeleton(symbol):
    """The starting point for a non US, non Indian company: price, price action and identity. The statements
    are filled in afterwards by complete_with_yahoo, and finish_global then settles the currencies."""
    import yfinance as yf

    symbol = symbol.upper()
    iso = country_of_symbol(symbol)
    stock = yf.Ticker(symbol)
    closes = stock.history(period="14mo")["Close"].dropna()
    if not len(closes):
        raise ValueError(f"No price data found for {symbol}")
    ccy, divisor = _trading_currency(stock, symbol)
    series = [(str(d.date()), float(c) / divisor) for d, c in closes.items()]
    meta = symbol_meta(symbol)

    market_cap = None
    try:
        cap = stock.fast_info.get("marketCap")
        market_cap = float(cap) / divisor if cap else None
    except Exception:
        pass

    f = {
        "ticker": symbol, "name": meta.get("name") or symbol, "market": "Global", "country": iso,
        "exchange": meta.get("exchange"),
        "listing": f"{COUNTRY_NAMES.get(iso, iso)}" + (f" ({meta['exchange']})" if meta.get("exchange") else ""),
        "currency": ccy, "unit_label": ccy, "price_currency": ccy,
        "sector": meta.get("sector") or "N/A", "price": round(series[-1][1], 2), "market_cap": market_cap,
        "annual": [], "ratios": {"Industry": meta["industry"]} if meta.get("industry") else {}, "shareholding": [],
        "technicals": compute_technicals(series),
        "qualitative": "Figures for this company come from Yahoo Finance's annual statements and price history only. "
                       "There is no filing text, shareholding pattern or peer table for it, so judge the business from "
                       "the numbers and from what you know of the sector, saying which is which.",
    }
    f.setdefault("data_sources", []).append(
        f"listed in {f['listing']}; statements and prices from Yahoo Finance, prices in {ccy}")
    return f


def finish_global(financials):
    """After the statements are in: put market cap in the statements' currency so price based ratios divide like
    by like, estimating it from price and share count if Yahoo gave none."""
    try:
        statement_ccy = financials.get("unit_label")
        trading_ccy = financials.get("price_currency") or financials.get("currency")
        cap = financials.get("market_cap")
        if cap is None and financials.get("price"):
            shares = next((r.get("shares_avg") for r in reversed(financials.get("annual") or []) if r.get("shares_avg")), None)
            if shares:
                cap = financials["price"] * shares
                financials.setdefault("data_sources", []).append(
                    "market cap estimated as price x diluted share count (Yahoo gave none)")
        if cap is None:
            return financials
        if statement_ccy and trading_ccy and statement_ccy != trading_ccy:
            rate = fx_rate(trading_ccy, statement_ccy)
            if rate:
                financials["market_cap"] = cap * rate
                financials["market_cap_unit"] = statement_ccy
                financials.setdefault("data_sources", []).append(
                    f"shares trade in {trading_ccy} but the company reports in {statement_ccy}; market cap converted at "
                    f"1 {trading_ccy} = {rate:,.4f} {statement_ccy} so the ratios compare like with like")
            else:
                financials["market_cap"] = cap
                financials["market_cap_unit"] = trading_ccy  # no rate: ratios that need both currencies are skipped
        else:
            financials["market_cap"] = cap
            financials["market_cap_unit"] = statement_ccy or trading_ccy
    except Exception:
        pass
    return financials
