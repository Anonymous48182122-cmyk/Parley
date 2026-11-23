"""
Does every listed company resolve to figures? A sweep over a random sample of the ticker index (or the tickers
given on the command line) that runs the same first step an analysis runs, and lists the ones that fail.

    python scripts/check_lookup.py                 # 30 Indian and 20 US tickers at random
    python scripts/check_lookup.py JPL AZAD KO     # these tickers
    python scripts/check_lookup.py --india 80 --us 40 --seed 7

A failure here is a company a person could pick from search and get an error for. Run it after changing anything
in the data layer, and now and then against the live lists.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.analyze import fetch_india  # noqa: E402
from data.us import edgar_fetcher  # noqa: E402


def check(ticker, market):
    try:
        if market == "India":
            d = fetch_india(ticker)
            return bool(d.get("price") or d.get("annual")), d.get("name")
        d = edgar_fetcher.fetch(ticker)
        return bool(d.get("annual")), d.get("name")
    except Exception as exc:  # report, never stop the sweep
        return False, f"{type(exc).__name__}: {str(exc)[:90]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--india", type=int, default=30)
    ap.add_argument("--us", type=int, default=20)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    index = json.loads((Path(__file__).resolve().parent.parent / "frontend" / "public" / "ticker-index.json").read_text(encoding="utf-8"))
    rng = random.Random(args.seed)
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        picks = [(r[0], r[2]) for r in index if r[0].upper() in wanted and r[2] in ("India", "US")]
    else:
        india = [r for r in index if r[2] == "India"]
        us = [r for r in index if r[2] == "US"]
        picks = [(r[0], r[2]) for r in rng.sample(india, min(args.india, len(india)))] + \
                [(r[0], r[2]) for r in rng.sample(us, min(args.us, len(us)))]

    failed = []
    for ticker, market in picks:
        ok, note = check(ticker, market)
        print(f"{'ok  ' if ok else 'FAIL'} {market:5} {ticker:14} {note}", flush=True)
        if not ok:
            failed.append((ticker, market, note))
        time.sleep(1.0)
    print(f"\n{len(picks) - len(failed)} of {len(picks)} resolved")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
