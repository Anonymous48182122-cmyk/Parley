"""
Generates frontend/public/ticker-index.json — the full US (SEC) + India (NSE)
ticker/company-name list, minified for client-side search. Run this whenever
the underlying lists should be refreshed (they change slowly — new listings,
delistings — so periodic manual regeneration is fine, same cadence as the
day/week-scale disk caches data/us and data/india already use).

Run from the repo root: python scripts/generate_ticker_index.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.search import _build_all_entries

OUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "public" / "ticker-index.json"


def build_entries():
    """The same list the server searches: SEC and Nasdaq for the US, NSE and BSE for India."""
    return [[p["ticker"], p["name"], p["market"]] for _, _, p in _build_all_entries()]


def main():
    entries = build_entries()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(entries, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
