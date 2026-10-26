"""
Saves the BSE's list of every listed equity to data/bse_snapshot.json.

The BSE refuses the cloud hosts the backend runs on, so the backend cannot always fetch the list
itself. It keeps this snapshot as the fallback (and Screener's live search covers anything listed
since). Run by hand or by .github/workflows/refresh-bse-list.yml; fails loudly when the BSE
answers with anything but a full list, so a bad snapshot is never written.
"""

import json
import pathlib
import sys

import requests

URL = ("https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
       "?Group=&Scripcode=&industry=&segment=Equity&status=Active")
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "bse_snapshot.json"


def main():
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/"}, timeout=60)
    response.raise_for_status()
    rows = [{"code": str(r["SCRIP_CD"]).strip(), "symbol": (r.get("scrip_id") or "").strip(),
             "name": (r.get("Issuer_Name") or r.get("Scrip_Name") or "").strip(), "isin": (r.get("ISIN_NUMBER") or "").strip()}
            for r in response.json() if r.get("SCRIP_CD")]
    if len(rows) < 3000:
        sys.exit(f"BSE returned only {len(rows)} companies; keeping the old snapshot")
    OUT.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    print(f"saved {len(rows)} companies to {OUT}")


if __name__ == "__main__":
    main()
