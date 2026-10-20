"""One-command health check of the live Parley backend.

Run from the repo root:  python scripts/smoke_prod.py [backend URL]

Checks which outside data sources the server can reach, then starts a small analysis (three agents,
to spare model quota) for a US stock, an Indian stock and a foreign filer, and checks that the stock
card data comes back complete and sensible. Exits with a non-zero status if anything fails.
"""
import json
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://parley-api-mqks.onrender.com").rstrip("/")
failures = []


def call(path, body=None, timeout=90):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(label)


# the first call may wake a sleeping free-tier server
for attempt in range(6):
    try:
        check("server is up", call("/health", timeout=70).get("ok") is True)
        break
    except Exception as exc:  # noqa: BLE001
        print(f"waiting for server ({exc})")
        time.sleep(10)
else:
    check("server is up", False)
    sys.exit(1)

sources = call("/health/sources?ticker=TCS.NS")
for key in ("screener", "yahoo_history", "yahoo_statements"):
    check(f"source reachable: {key}", bool(sources.get(key, {}).get("ok")), sources.get(key, {}).get("error", "")[:90])
us = call("/health/sources?ticker=AAPL")
for key in ("nasdaq_quote", "nasdaq_history", "nasdaq_statements"):
    check(f"source reachable: {key}", bool(us.get(key, {}).get("ok")), us.get(key, {}).get("error", "")[:90])

STOCKS = [("AAPL", "US"), ("RELIANCE", "India"), ("TSM", "US")]
for ticker, market in STOCKS:
    call("/analyze", {"ticker": ticker, "market": market, "agents": ["buffett", "munger", "graham"], "force": True})
for ticker, market in STOCKS:
    md = None
    for _ in range(30):
        job = call(f"/analysis/{ticker}")
        if job.get("status") == "error":
            check(f"{ticker} analysis starts", False, job.get("error", "")[:120])
            break
        md = job.get("market_data")
        if md:
            break
        time.sleep(6)
    if not md:
        continue
    ratios, tech = md.get("ratios") or {}, md.get("technicals") or {}
    check(f"{ticker} price and market cap", bool(md.get("price")) and bool(md.get("market_cap")))
    check(f"{ticker} sector", md.get("sector") not in (None, "N/A", ""), str(md.get("sector")))
    check(f"{ticker} P/E", any(ratios.get(k) for k in ("P/E Ratio (Trailing)", "P/E Ratio")))
    check(f"{ticker} price history", len(tech) > 5 and bool(tech.get("as_of")))
    check(f"{ticker} 52 week range", tech.get("high_52w") is not None or ratios.get("52-Week High") is not None)

print()
print("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED: " + "; ".join(failures))
sys.exit(1 if failures else 0)
