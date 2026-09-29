"""
Peer comparison — a handful of comparable listed companies with their key
valuation/quality multiples, so agents can judge "cheap or expensive *relative
to what*" instead of reasoning about a P/E in a vacuum.

India: Screener.in's own curated peer table (same-industry, sorted by size).
US: Yahoo's industry constituents, kept only when comparable in size to the
target — Yahoo's raw list is often small-cap noise (AAPL's "peers" include
speaker and remote-control makers), and a bad peer set is worse than none.

Best-effort like the rest of data/: any failure yields [] and the analysis
simply runs without a peer table.
"""

import math
import re
from concurrent.futures import ThreadPoolExecutor

import requests
import yfinance as yf

from data.common import cached_fetch
from data.india.bse_fetcher import HEADERS, parse_number

PEERS_TTL_HOURS = 6
MAX_PEERS = 4

# US peers must be within this band of the target's market cap.
_US_CAP_BAND = (0.2, 5.0)


def _cap_distance(cap, own_cap):
    if not cap or not own_cap or cap <= 0 or own_cap <= 0:
        return float("inf")
    return abs(math.log(cap / own_cap))


# --------------------------------------------------------------------- India

def _screener_warehouse_id(ticker):
    html = requests.get(
        f"https://www.screener.in/company/{ticker.upper()}/consolidated/", headers=HEADERS, timeout=20
    ).text
    match = re.search(r'data-warehouse-id="(\d+)"', html)
    if not match:
        # Standalone-only companies have no consolidated page.
        html = requests.get(
            f"https://www.screener.in/company/{ticker.upper()}/", headers=HEADERS, timeout=20
        ).text
        match = re.search(r'data-warehouse-id="(\d+)"', html)
    return match.group(1) if match else None


def _india_peers(ticker, own_name, own_cap):
    from bs4 import BeautifulSoup  # local: only the India path needs it

    warehouse_id = _screener_warehouse_id(ticker)
    if not warehouse_id:
        return []
    response = requests.get(
        f"https://www.screener.in/api/company/{warehouse_id}/peers/",
        headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
        timeout=20,
    )
    response.raise_for_status()
    table = BeautifulSoup(response.text, "lxml").find("table")
    if table is None:
        return []

    rows = table.find_all("tr")
    header = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    col = {name: i for i, name in enumerate(header)}

    def cell(cells, *names):
        for name in names:
            for label, idx in col.items():
                if label.startswith(name) and idx < len(cells):
                    return parse_number(cells[idx])
        return None

    peers = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 4 or not cells[1]:
            continue
        name = cells[1]
        if name.lower().startswith(("median", "average")):
            continue  # Screener's own summary row, not a company
        market_cap = cell(cells, "Mar Cap")
        is_self = (own_name and name.lower() in own_name.lower()) or (
            own_cap and market_cap and abs(market_cap - own_cap) / own_cap < 0.01
        )
        if is_self or market_cap is None:
            continue
        peers.append({
            "name": name,
            "market_cap": market_cap,
            "pe": cell(cells, "P/E"),
            "roce": cell(cells, "ROCE"),
            "dividend_yield": cell(cells, "Div Yld"),
            "sales_growth": cell(cells, "Qtr Sales Var"),
            "profit_growth": cell(cells, "Qtr Profit Var"),
        })
    peers.sort(key=lambda p: _cap_distance(p["market_cap"], own_cap))
    return peers[:MAX_PEERS]


# ------------------------------------------------------------------------ US

def _pct(value):
    return None if value is None else round(value * 100, 1)


def _us_peer_row(symbol):
    info = yf.Ticker(symbol).info or {}
    if not info.get("marketCap"):
        return None
    return {
        "name": info.get("shortName") or symbol,
        "ticker": symbol,
        "market_cap": info.get("marketCap"),
        "pe": None if info.get("trailingPE") is None else round(info["trailingPE"], 1),
        "forward_pe": None if info.get("forwardPE") is None else round(info["forwardPE"], 1),
        "revenue_growth": _pct(info.get("revenueGrowth")),
        "operating_margin": _pct(info.get("operatingMargins")),
        "roe": _pct(info.get("returnOnEquity")),
    }


def _us_peers(ticker, own_cap):
    info = yf.Ticker(ticker).info or {}
    industry_key = info.get("industryKey")
    if not industry_key:
        return []
    top = yf.Industry(industry_key).top_companies
    if top is None or len(top) == 0:
        return []

    candidates = [s for s in top.index if s.upper() != ticker.upper()][:10]
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = [r for r in pool.map(_safe(_us_peer_row), candidates) if r]

    low, high = _US_CAP_BAND
    if own_cap:
        rows = [r for r in rows if low <= r["market_cap"] / own_cap <= high]
    rows.sort(key=lambda r: _cap_distance(r["market_cap"], own_cap))
    return rows[:MAX_PEERS]


def _safe(fn):
    def wrapped(arg):
        try:
            return fn(arg)
        except Exception:
            return None

    return wrapped


# -------------------------------------------------------------------- public

def fetch_peers(ticker, market, own_name=None, own_market_cap=None):
    """Returns a list of peer dicts (possibly empty). `own_market_cap` must be
    in the same unit the fetcher reported (crores for India, dollars for US)."""

    def fetch():
        if market == "India":
            return _india_peers(ticker, own_name, own_market_cap)
        return _us_peers(ticker, own_market_cap)

    try:
        return cached_fetch(f"peers_{market}_{ticker.upper()}", PEERS_TTL_HOURS, fetch)
    except Exception:
        return []
