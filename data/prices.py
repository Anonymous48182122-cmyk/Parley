"""
Latest share prices for a handful of tickers, for the History page's track record (how a saved call has
done since it was made). US prices come from Nasdaq's public quote, India's from Yahoo's daily history,
which still answers cloud servers when its profile data does not. Cached briefly in memory; anything
unknown is simply None and the page leaves that row out.
"""

import threading
import time

_CACHE = {}
_LOCK = threading.Lock()
_TTL = 1800  # half an hour is fresh enough for "how has it done since I saved it"


def _us_price(ticker):
    # Yahoo's daily history answers in a fraction of a second; Nasdaq's full quote takes ten seconds or more,
    # so it is only the fallback
    try:
        price = _yahoo_price(ticker)
    except Exception:
        price = None
    if price:
        return price
    from data.nasdaq_data import fetch_nasdaq_quote
    quote = fetch_nasdaq_quote(ticker.replace("-", "."))
    return float(quote["price"]) if (quote or {}).get("price") else None


def _yahoo_price(symbol):
    import yfinance as yf
    closes = yf.Ticker(symbol).history(period="5d")["Close"].dropna()
    return float(closes.iloc[-1]) if len(closes) else None


def _india_price(ticker):
    suffixes = (".BO",) if ticker.isdigit() else (".NS", ".BO")
    for suffix in suffixes:
        try:
            price = _yahoo_price(ticker.upper() + suffix)
        except Exception:
            price = None
        if price:
            return price
    return None


def latest_price(ticker, market):
    key = (ticker.upper(), market)
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    try:
        price = _india_price(ticker) if market == "India" else _us_price(ticker)
    except Exception:
        price = None
    with _LOCK:
        _CACHE[key] = (now, price)
    return price
