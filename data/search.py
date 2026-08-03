"""
Ticker/company-name search-as-you-type, combining SEC's full US ticker list
with NSE's full equity list. Both are large (10k+ / 2k+ rows) and change
rarely, so on top of their day(s)-long disk cache we keep a short in-process
memo too, so a burst of keystrokes doesn't re-read the cache file each time.

A first-letter prefix index is built once per memo refresh and reused across
every search in that window — without it, every keystroke re-scans the full
~12k-entry combined list, and since the frontend used to leave stale
in-flight requests running, overlapping searches would pile up and compete
for Render's free-tier CPU, making each subsequent keystroke slower than the
last. Indexing turns each search into an O(candidates for that letter) scan
instead of O(everything), so it stays fast regardless of request load.
"""

import time
from collections import defaultdict

from data.india.bse_fetcher import get_symbol_list
from data.us.edgar_fetcher import get_ticker_map

_MEMO_TTL_SECONDS = 600
_memo = {}
_index_cache = {"entries_id": None, "index": None}


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


def _build_all_entries():
    """Flattens both US and India sources into one normalized
    (ticker, name, payload) list, built once per memo refresh."""
    entries = []
    seen = set()

    us_map = _memoized("us_map", get_ticker_map)
    for entry in us_map.values():
        ticker, name = entry["ticker"].upper(), entry["title"].upper()
        key = ("US", ticker)
        if key in seen:
            continue
        seen.add(key)
        entries.append((ticker, name, {"ticker": entry["ticker"], "name": entry["title"], "market": "US"}))

    in_list = _memoized("in_list", get_symbol_list)
    for entry in in_list:
        ticker, name = entry["symbol"].upper(), entry["name"].upper()
        key = ("India", ticker)
        if key in seen:
            continue
        seen.add(key)
        entries.append((ticker, name, {"ticker": entry["symbol"], "name": entry["name"], "market": "India"}))

    return entries


def _build_prefix_index(entries):
    """Buckets entries by the first letter of their ticker AND of their
    name, so a query only scans candidates that could plausibly prefix-match
    it, instead of the full combined list."""
    index = defaultdict(list)
    for ticker, name, payload in entries:
        if ticker:
            index[ticker[0]].append((ticker, name, payload))
        if name and (not ticker or name[0] != ticker[0]):
            index[name[0]].append((ticker, name, payload))
    return index


def _get_index(entries):
    # Rebuild only when the underlying (memoized, TTL-bound) entries list
    # itself was rebuilt — cheap identity check, avoids re-indexing ~12k
    # entries on every request when nothing has actually changed.
    if _index_cache["entries_id"] != id(entries):
        _index_cache["index"] = _build_prefix_index(entries)
        _index_cache["entries_id"] = id(entries)
    return _index_cache["index"]


def search_tickers(query, limit=8):
    query = (query or "").strip().upper()
    if not query:
        return []

    entries = _memoized("all_entries", _build_all_entries)
    index = _get_index(entries)

    scored = []
    seen_keys = set()
    for ticker, name, payload in index.get(query[0], []):
        score = _score(query, ticker, name)
        if score is None:
            continue
        key = (payload["market"], ticker)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        scored.append((score, len(ticker), payload))

    # The indexed pass only catches matches at the very start of the ticker
    # or name (scores 0-2). A full scan for substring-anywhere matches
    # (scores 3-4) is much more expensive, so it only runs on the rare
    # occasion the fast path didn't already fill the result limit.
    if len(scored) < limit:
        for ticker, name, payload in entries:
            key = (payload["market"], ticker)
            if key in seen_keys:
                continue
            score = _score(query, ticker, name)
            if score is None or score < 3:
                continue
            seen_keys.add(key)
            scored.append((score, len(ticker), payload))

    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:limit]]
