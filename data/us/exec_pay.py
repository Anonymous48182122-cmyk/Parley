"""
Executive pay for US companies, straight from the SEC.

Since 2023 every proxy statement (form DEF 14A) carries a "pay versus performance" table tagged in
machine readable form: total pay for the chief executive (the SEC calls the role "PEO") for each of
the last five years, the pay actually realised, and the average for the other named executives. That is the
free, official source for what a company pays its top people, so it is read here rather than guessed.

Best effort like every fetcher in data/: any failure returns {} and the analysis carries on without it.
Companies that do not file a proxy statement (foreign filers, new listings) simply return {}.
"""

import html
import re

from data.common import cached_fetch
from data.us import edgar_fetcher

EXEC_PAY_TTL_HOURS = 24 * 7  # a proxy statement is filed once a year

_TAG = re.compile(r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>", re.S)
_NAME = re.compile(r"<ix:nonNumeric\b[^>]*name=\"ecd:PeoName\"[^>]*>(.*?)</ix:nonNumeric>", re.S)
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_CONTEXT = re.compile(r'<xbrli:context\s[^>]*?id="([^"]+)"[^>]*>(.*?)</xbrli:context>', re.S)
_END = re.compile(r"<xbrli:(?:endDate|instant)>\s*(\d{4}-\d{2}-\d{2})\s*</xbrli:(?:endDate|instant)>")

_FIELDS = {
    "ecd:PeoTotalCompAmt": "ceo_total",
    "ecd:PeoActuallyPaidCompAmt": "ceo_paid",
    "ecd:NonPeoNeoAvgTotalCompAmt": "others_avg_total",
    "ecd:NonPeoNeoAvgCompActuallyPaidAmt": "others_avg_paid",
}


def _latest_proxy(cik):
    cik10 = str(cik).zfill(10)
    sub = edgar_fetcher._throttled_get(f"https://data.sec.gov/submissions/CIK{cik10}.json").json()
    recent = sub["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == "DEF 14A":
            acc = recent["accessionNumber"][i].replace("-", "")
            doc = recent["primaryDocument"][i]
            return recent["filingDate"][i], f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
    raise ValueError("no proxy statement found")


def _period_ends(text):
    """Each filing defines its own reporting periods (context ids are anything from a date label to
    "c-1"), so the period end comes from the context definition and not from the id."""
    ends = {}
    for ctx_id, body in _CONTEXT.findall(text):
        m = _END.search(body)
        if m:
            ends[ctx_id] = m.group(1)
    return ends


def _parse(text):
    years = {}
    ends = _period_ends(text)
    for attrs, body in _TAG.findall(text):
        a = dict(_ATTR.findall(attrs))
        field = _FIELDS.get(a.get("name"))
        if not field:
            continue
        ctx = a.get("contextRef", "")
        dates = [ends[ctx]] if ctx in ends else _DATE.findall(ctx)
        raw = re.sub(r"<[^>]+>", "", body).replace(",", "").strip()
        if not dates or not re.fullmatch(r"-?\d+(\.\d+)?", raw):
            continue
        value = float(raw) * (10 ** int(a.get("scale", "0") or 0))
        if a.get("sign") == "-":
            value = -value
        row = years.setdefault(dates[-1], {})
        row.setdefault(field, value)  # first one wins: the current executive is listed first
    names = [html.unescape(re.sub(r"<[^>]+>", "", n)).strip() for n in _NAME.findall(text)]
    return years, [n for n in names if n]


def _fetch(ticker):
    cik, _ = edgar_fetcher.resolve_cik(ticker)
    filed, url = _latest_proxy(cik)
    years, names = _parse(edgar_fetcher._throttled_get(url).text)
    rows = [{"period_end": end, **vals} for end, vals in sorted(years.items(), reverse=True) if vals.get("ceo_total")]
    if not rows:
        raise ValueError("no tagged executive pay in the proxy statement")
    return {"filed": filed, "ceo_name": names[0] if names else None, "years": rows[:5]}


def fetch_exec_pay(ticker):
    """{"filed": "2026-01-08", "ceo_name": "Mr. Cook", "years": [{"period_end", "ceo_total", ...}]} or {}."""
    try:
        return cached_fetch(f"exec_pay_{ticker.upper().replace('-', '.')}", EXEC_PAY_TTL_HOURS, lambda: _fetch(ticker))
    except Exception:
        return {}
