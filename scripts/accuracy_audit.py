"""Compare the ratios Parley produces WITHOUT Yahoo (as on the live server) against Yahoo's own.

Prices, market caps, P/E and the 52-week range should agree within about 15%. Known definitional
differences are not errors: Yahoo's debt/equity includes lease liabilities, its operating margin is
the latest quarter's (ours is trailing twelve months) and its ROE uses a slightly different average.

Run from the repo root:  python scripts/accuracy_audit.py [TICKER[:India] ...]
Tickers default to US; add :India for Indian stocks (compared with Yahoo's .NS listing).
"""
import os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import yfinance as yf

ARGS = sys.argv[1:] or ["AAPL", "MSFT", "NVDA", "XOM", "KO", "JNJ", "LLY", "JPM", "V", "PG", "HD", "CVX", "PFE",
                           "WMT", "COST", "AMD", "NFLX", "DIS", "BA", "CAT", "MCD", "NKE", "UNH", "TSLA", "GOOGL"]

TARGETS = [(a.split(":")[0], a.split(":")[1] if ":" in a else "US") for a in ARGS]
TICKERS = [t for t, _ in TARGETS]
MARKET = dict(TARGETS)

# Yahoo's values first, while Yahoo still works
truth = {}
for t in TICKERS:
    try:
        i = yf.Ticker(t + ".NS" if MARKET[t] == "India" else t).info
        truth[t] = {"pe": i.get("trailingPE"), "roe": i.get("returnOnEquity"), "de": i.get("debtToEquity"),
                    "om": i.get("operatingMargins"), "pm": i.get("profitMargins"),
                    "price": i.get("currentPrice") or i.get("regularMarketPrice"), "cap": i.get("marketCap"),
                    "hi": i.get("fiftyTwoWeekHigh"), "lo": i.get("fiftyTwoWeekLow"), "bv": i.get("bookValue")}
    except Exception as e:
        print("no Yahoo values for", t, e)

# then reproduce what the cloud host sees: Yahoo's quote data (.info) comes back empty while its
# price history and statements still work (checked with GET /health/sources on the live server)
import data.common as common

_RealTicker = yf.Ticker


class _NoInfoTicker(_RealTicker):
    @property
    def info(self):
        raise RuntimeError("Yahoo .info blocked (simulated)")


class _Blocked:
    def __init__(self, *a, **k):
        raise RuntimeError("Yahoo blocked (simulated)")


yf.Ticker = _NoInfoTicker
for name in ("Sector", "Industry", "Search", "Lookup"):
    if hasattr(yf, name):
        setattr(yf, name, _Blocked)
src, tmp = common.CACHE_DIR, tempfile.mkdtemp(prefix="accuracy_cache_")
for f in os.listdir(src):
    if not f.startswith(("yfund_", "market_v", "peers_", "nasdaq_", "analysis_")):
        shutil.copy(os.path.join(src, f), tmp)
common.CACHE_DIR = type(src)(tmp)

from orchestrator.analyze import fetch_financials


def num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace("%", "").replace(",", ""))
    except ValueError:
        return None


for t in TICKERS:
    if t not in truth:
        continue
    f = fetch_financials(t, MARKET[t])
    r, y = f["ratios"], truth[t]
    if MARKET[t] == "India" and y["cap"]:
        y["cap"] /= 1e7  # Yahoo reports rupees, Screener crores
    ours = {"pe": num(r.get("P/E Ratio (Trailing)", r.get("P/E Ratio"))), "roe": num(r.get("Return on Equity", r.get("ROE"))),
            "de": num(r.get("Debt to Equity")), "om": num(r.get("Operating Margin")),
            "pm": num(r.get("Net Profit Margin")), "price": f.get("price"), "cap": f.get("market_cap"),
            "hi": num(r.get("52-Week High")), "lo": num(r.get("52-Week Low")), "bv": num(r.get("Book Value per Share"))}
    for k in ("roe", "om", "pm"):
        if y[k] is not None:
            y[k] *= 100
    bad = []
    for k, a in ours.items():
        b = y[k]
        if b is None:
            continue
        if a is None:
            bad.append(f"{k}: missing (yahoo {b:.4g})")
        elif b and abs(a / b - 1) > 0.15 and abs(a - b) > 1:
            bad.append(f"{k}: ours {a:.4g} vs yahoo {b:.4g}")
    print(f"{t:6s}", "OK" if not bad else " | ".join(bad), flush=True)
