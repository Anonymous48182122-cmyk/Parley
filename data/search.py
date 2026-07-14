"""
Ticker/company-name search-as-you-type, combining SEC's full US ticker list
with NSE's full equity list. Both are large (10k+ / 2k+ rows) and change
rarely, so on top of their day(s)-long disk cache we keep a short in-process
memo too, so a burst of keystrokes doesn't re-read the cache file each time.
"""

import time

from data.india.bse_fetcher import get_symbol_list
from data.us.edgar_fetcher import get_ticker_map

_MEMO_TTL_SECONDS = 600
_memo = {}


def _memoized(key, fetch_fn):
    entry = _memo.get(key)
    now = time.time()
    if entry and now - entry[0] < _MEMO_TTL_SECONDS:
        return entry[1]
    value = fetch_fn()
    _memo[key] = (now, value)
    return value


def _score(query, ticker, name):
    if ticker == query:
        return 0
    if ticker.startswith(query):
        return 1
    if name.startswith(query):
        return 2
    if query in ticker:
        return 3
    if query in name:
        return 4
    return None


def search_tickers(query, limit=8):
    query = (query or "").strip().upper()
    if not query:
        return []

    scored = []
    seen = set()

    us_map = _memoized("us_map", get_ticker_map)
    for entry in us_map.values():
        ticker, name = entry["ticker"].upper(), entry["title"].upper()
        score = _score(query, ticker, name)
        if score is None:
            continue
        key = ("US", ticker)
        if key in seen:
            continue
        seen.add(key)
        scored.append((score, len(ticker), {"ticker": entry["ticker"], "name": entry["title"], "market": "US"}))

    in_list = _memoized("in_list", get_symbol_list)
    for entry in in_list:
        ticker, name = entry["symbol"].upper(), entry["name"].upper()
        score = _score(query, ticker, name)
        if score is None:
            continue
        key = ("India", ticker)
        if key in seen:
            continue
        seen.add(key)
        scored.append((score, len(ticker), {"ticker": entry["symbol"], "name": entry["name"], "market": "India"}))

    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:limit]]
