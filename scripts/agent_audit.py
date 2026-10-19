"""Agent-level audit: how often do agents say they lack data? Runs first-pass analyses and scans each
for sentences that complain about missing data (not rhetorical 'lacks a moat' lines). Uses model quota.

Run from the repo root:
    python scripts/agent_audit.py TAG [TICKER:MARKET ...]
Set REALISTIC=1 to reproduce the cloud host: Yahoo's quote data (.info) blocked, its history and
statements still working, with a cache that has no Yahoo-derived entries.
"""
import json, os, re, shutil, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

if os.environ.get("REALISTIC") == "1":
    import yfinance as yf
    import data.common as common

    _Real = yf.Ticker

    class _NoInfo(_Real):
        @property
        def info(self):
            raise RuntimeError("Yahoo .info blocked (simulated)")

    class _Blocked:
        def __init__(self, *a, **k):
            raise RuntimeError("blocked")

    yf.Ticker = _NoInfo
    for n in ("Sector", "Industry", "Search", "Lookup"):
        if hasattr(yf, n):
            setattr(yf, n, _Blocked)
    src, tmp = common.CACHE_DIR, tempfile.mkdtemp(prefix="agent_audit_cache_")
    for f in os.listdir(src):
        if not f.startswith(("yfund_", "yq_", "market_v", "peers_", "nasdaq_", "analysis_", "in_screener", "fx_")):
            shutil.copy(os.path.join(src, f), tmp)
    common.CACHE_DIR = type(src)(tmp)

from orchestrator.analyze import fetch_and_format
from agents import runner

DEFAULT = ["NVO:US", "XOM:US", "JPM:US", "TSM:US", "LLY:US", "BRK-B:US", "RELIANCE:India", "HDFCBANK:India",
           "IRFC:India", "IGIL:India", "TCS:India"]
tag = sys.argv[1] if len(sys.argv) > 1 else "run"
targets = [a.split(":") for a in sys.argv[2:]] or [d.split(":") for d in DEFAULT]
AGENTS = ["buffett", "munger", "graham", "lynch", "damani", "simons", "ackman", "burry"]

# Only phrases about DATA AVAILABILITY, not rhetorical "lacks a moat" / "cannot be optimised".
PATTERNS = [
    r"\bn/a\b(?!\w)",
    r"\b(not|isn[’']t|aren[’']t|wasn[’']t) (been )?(provided|disclosed|available|reported|given|shown|supplied|included|stated|furnished)\b",
    r"\bno (data|figures?|numbers?|information|disclosure|details?) (on|about|for|regarding|is|are|was|were|provided|available)\b",
    r"\bdata (is|are|was|were) (missing|unavailable|absent|not)\b",
    r"\b(data|information|figures?) (feed|set|provided)\b[^.]{0,60}\b(missing|riddled|incomplete|sparse|lacking|blank)\b",
    r"\black of (any )?(data|disclosure|information|visibility|transparency|figures|numbers|detail)\b",
    r"\b(lacks?|lacking|missing|without) (the )?(any )?(necessary |relevant |sufficient |key |critical )?(balance[- ]sheet|cash[- ]flow|financial|income statement|capex|debt|cash|earnings)( data| figures| numbers| statements| information| disclosure)\b",
    r"\b(cannot|can[’']t|unable to|impossible to|not possible to|hard to) (reliably |properly |fully )?(verify|assess|evaluate|analy[sz]e|judge|determine|underwrite|value|calculate|compute|confirm)\b[^.]{0,80}\b(data|figures?|numbers?|disclos|statements?|cash|debt|earnings|capex|balance)\b",
    r"\binsufficient (data|information|disclosure)\b",
    r"\b(too|not) (little|enough) (data|information|history)\b",
    r"\bno (balance[- ]sheet|cash[- ]flow|financial statement|capex|debt|cash) (data|figures?|numbers?|information)\b",
]
RX = [re.compile(p, re.I) for p in PATTERNS]
SENT = re.compile(r"[^.!?\n]+[.!?]?")


def complaints(text):
    return [s.strip()[:260] for s in SENT.findall(text) if any(r.search(s) for r in RX)]


results = {}
for ticker, market in targets:
    try:
        data = fetch_and_format(ticker, market=market)
    except Exception as e:
        print(f"{ticker}: FETCH FAILED {e}")
        continue
    t0 = time.time()
    try:
        s1 = runner.run_stage1_all(ticker, data, agent_keys=AGENTS)
    except Exception as e:
        print(f"{ticker}: stage1 failed {str(e)[:120]}")
        continue
    per = {a: complaints(t) for a, t in s1.items()}
    results[ticker] = {"market": market, "complaints": per, "stage1": s1, "na_in_block": data.count("N/A")}
    n_bad = sum(1 for c in per.values() if c)
    print(f"{ticker:9s} {market:5s} agents with a data complaint: {n_bad}/{len(AGENTS)}  "
          f"(N/A cells in block: {data.count('N/A')})  [{time.time() - t0:.0f}s]", flush=True)

out = os.path.join(tempfile.gettempdir(), f"agent_audit_{tag}.json")
json.dump(results, open(out, "w", encoding="utf-8"))
tot = sum(len(r["complaints"]) for r in results.values())
bad = sum(1 for r in results.values() for c in r["complaints"].values() if c)
print(f"\nTOTAL: {bad}/{tot} first-pass analyses contain a data-deprivation complaint ({100 * bad / max(tot, 1):.0f}%)")
print(f"(full output saved to {out})\n\nCOMPLAINTS:")
for tk, r in results.items():
    for a, cs in r["complaints"].items():
        if cs:
            print(f"  [{tk}/{a}] {cs[0]}")
