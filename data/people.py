"""
Who runs a company and who started it, from Wikidata.

Two public sources, both free and edited by people. Wikipedia's infobox lists the company's key people
and founders and is usually updated within days of a change of chief executive (Apple's new one took
over on 1 September 2026; the proxy statement still names the old one). Wikidata is the second source:
it records for most sizeable companies the current
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
PEOPLE_TTL_HOURS = 24 * 3  # who runs a company changes rarely, but a new chief executive should show within days

_COMPANY_WORDS = re.compile(r"compan|corporation|conglomerate|multinational|bank|firm|enterprise|group|retailer|manufactur|"
                            r"airline|insurer|brand|holding|provider|developer|producer|platform|maker", re.I)
_SUFFIX = re.compile(r"\b(inc|corp|corporation|ltd|limited|plc|n\.?v\.?|s\.?a\.?|ag|co|company|holdings?|group|class [a-c]|"
                     r"common stock|ordinary shares)\b\.?,?", re.I)


def _get(params, host=API):
    for attempt in range(3):
        response = requests.get(host, params={**params, "format": "json"}, headers=HEADERS, timeout=12)
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


_LINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")
_CEO_WORDS = re.compile(r"\bceo\b|chief executive", re.I)
_ROLE_WORDS = re.compile(r"chair|president|ceo|chief|officer|executive|director|board|vice|founder", re.I)
_FORMER = re.compile(r"former|until|\bto \d{4}|ex-", re.I)


def _infobox_field(wikitext, names):
    """The text of an infobox field such as key_people, up to the next field."""
    for name in names:
        m = re.search(rf"\|\s*{name}\s*=(.*?)(?=\n\s*\|\s*[a-z_0-9 ]+=|\n\}}\}})", wikitext, re.S | re.I)
        if m:
            return m.group(1)
    return ""


def _wikipedia(title):
    """Current chief executive and founders from the article's infobox; empty when it has none."""
    data = _get({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "rvsection": 0,
                 "titles": title, "redirects": 1}, host="https://en.wikipedia.org/w/api.php")
    pages = (data.get("query") or {}).get("pages") or {}
    page = next(iter(pages.values()), {})
    text = (((page.get("revisions") or [{}])[0].get("slots") or {}).get("main") or {}).get("*") or ""
    ceo, founders = [], []
    for chunk in re.split(r"\n\*|<br\s*/?>|\{\{!\}\}|\|(?=\s*\[\[)", _infobox_field(text, ["key_people", "key_person"])):
        if _CEO_WORDS.search(chunk) and not _FORMER.search(chunk):
            for target, label in _LINK.findall(chunk):
                # the first link that reads as a person's name, not a job title ("Chairman", "CEO")
                if len(target.split()) >= 2 and not _ROLE_WORDS.search(target):
                    ceo.append((label or target).strip())
                    break
    for target, label in _LINK.findall(_infobox_field(text, ["founders", "founder"])):
        if not re.search(r"\bcompany\b|\binc\b", target, re.I):
            founders.append((label or target).strip())
    return {"ceo": ceo[:1], "founders": founders[:5]}


def _fetch(name):
    query = _search_name(name)
    if not query:
        return {"ceo": [], "founders": []}
    hits = _get({"action": "wbsearchentities", "search": query, "language": "en", "type": "item", "limit": 6}).get("search", [])
    company = next((h for h in hits if _COMPANY_WORDS.search(h.get("description") or "")), None)
    if not company:
        return {"ceo": [], "founders": []}
    entity = _get({"action": "wbgetentities", "ids": company["id"], "props": "claims|sitelinks"})["entities"][company["id"]]
    claims = entity.get("claims") or {}
    wiki = {"ceo": [], "founders": []}
    title = ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")
    if title:
        try:
            wiki = _wikipedia(title)
        except Exception:
            pass
    ceo_ids, founder_ids = _current(claims, "P169")[:2], _current(claims, "P112")[:5]
    ids = list(dict.fromkeys(ceo_ids + founder_ids))
    if not ids:
        return {"ceo": wiki["ceo"], "founders": wiki["founders"], "entity": company["id"]}
    labels = _get({"action": "wbgetentities", "ids": "|".join(ids), "props": "labels", "languages": "en"})["entities"]

    def name_of(i):
        return ((labels.get(i) or {}).get("labels") or {}).get("en", {}).get("value")

    # Wikipedia first for the chief executive, because it moves faster; Wikidata fills in what it lacks
    ceo = wiki["ceo"] or [n for n in map(name_of, ceo_ids) if n]
    founders = list(wiki["founders"])
    for n in map(name_of, founder_ids):
        if n and not any(n.split()[-1].lower() == f.split()[-1].lower() for f in founders):
            founders.append(n)
    return {"ceo": ceo, "founders": founders[:5], "entity": company["id"], "from_wikipedia": bool(wiki["ceo"])}


def fetch_people(company_name):
    """{"ceo": [names], "founders": [names]}; empty lists when Wikidata has nothing or cannot be reached."""
    if not company_name:
        return {"ceo": [], "founders": []}
    key = "people_" + re.sub(r"[^a-z0-9]+", "_", company_name.lower())[:60]
    try:
        return cached_fetch(key, PEOPLE_TTL_HOURS, lambda: _fetch(company_name))
    except Exception:
        return {"ceo": [], "founders": []}
