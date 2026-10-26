"""
Who runs a company and who started it, from Wikidata.

Wikidata is free, public and edited by people, and it records for most sizeable companies the current
chief executive (property P169) and the founders (P112) with full names. That fills the gap left by the
filings, where the proxy statement often names the chief executive by surname only or not at all, and
the officer lists we can read from the exchanges are refused to the cloud server. Best effort: any
failure returns empty lists and the page falls back to what the filings and the business card say.
"""

import re
import time

import requests

from data.common import cached_fetch

API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "Parley/1.0 (investment committee app; contact via github.com/Anonymous48182122-cmyk/Parley)"}
PEOPLE_TTL_HOURS = 24 * 30  # who runs a company changes rarely

_COMPANY_WORDS = re.compile(r"compan|corporation|conglomerate|multinational|bank|firm|enterprise|group|retailer|manufactur|"
                            r"airline|insurer|brand|holding|provider|developer|producer|platform|maker", re.I)
_SUFFIX = re.compile(r"\b(inc|corp|corporation|ltd|limited|plc|n\.?v\.?|s\.?a\.?|ag|co|company|holdings?|group|class [a-c]|"
                     r"common stock|ordinary shares)\b\.?,?", re.I)


def _get(params):
    for attempt in range(3):
        response = requests.get(API, params={**params, "format": "json"}, headers=HEADERS, timeout=12)
        if response.status_code == 429 and attempt < 2:  # asked to slow down: wait and ask again
            time.sleep(2 * (attempt + 1))
            continue
        response.raise_for_status()
        return response.json()


def _search_name(name):
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", name or "")).strip(" ,.")


def _current(claims, prop):
    """Entity ids of a property's values that have not ended (no end time) and are not deprecated."""
    out = []
    for c in claims.get(prop, []):
        if c.get("rank") == "deprecated" or "P582" in (c.get("qualifiers") or {}):
            continue
        value = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(value, dict) and value.get("id"):
            out.append((0 if c.get("rank") == "preferred" else 1, value["id"]))
    return [i for _, i in sorted(out)]


def _fetch(name):
    query = _search_name(name)
    if not query:
        return {"ceo": [], "founders": []}
    hits = _get({"action": "wbsearchentities", "search": query, "language": "en", "type": "item", "limit": 6}).get("search", [])
    company = next((h for h in hits if _COMPANY_WORDS.search(h.get("description") or "")), None)
    if not company:
        return {"ceo": [], "founders": []}
    entity = _get({"action": "wbgetentities", "ids": company["id"], "props": "claims"})["entities"][company["id"]]
    claims = entity.get("claims") or {}
    ceo_ids, founder_ids = _current(claims, "P169")[:2], _current(claims, "P112")[:5]
    ids = list(dict.fromkeys(ceo_ids + founder_ids))
    if not ids:
        return {"ceo": [], "founders": [], "entity": company["id"]}
    labels = _get({"action": "wbgetentities", "ids": "|".join(ids), "props": "labels", "languages": "en"})["entities"]

    def name_of(i):
        return ((labels.get(i) or {}).get("labels") or {}).get("en", {}).get("value")

    return {"ceo": [n for n in map(name_of, ceo_ids) if n], "founders": [n for n in map(name_of, founder_ids) if n],
            "entity": company["id"]}


def fetch_people(company_name):
    """{"ceo": [names], "founders": [names]}; empty lists when Wikidata has nothing or cannot be reached."""
    if not company_name:
        return {"ceo": [], "founders": []}
    key = "people_" + re.sub(r"[^a-z0-9]+", "_", company_name.lower())[:60]
    try:
        return cached_fetch(key, PEOPLE_TTL_HOURS, lambda: _fetch(company_name))
    except Exception:
        return {"ceo": [], "founders": []}
