"""
SEC EDGAR XBRL fetcher for US-listed companies. Free, no auth, 10 req/sec
rate limit. Resolves ticker -> CIK via the static company_tickers.json file,
then pulls companyfacts and extracts up to 10 years of annual (10-K) figures
with tag-synonym fallback lists, since companies use different XBRL tags for
the same concept.
"""

import time
from datetime import date

import requests

from data.common import cached_fetch, compute_derived, format_for_agents

CONTACT_EMAIL = "dhruvadvani102654njr10@gmail.com"
HEADERS = {"User-Agent": f"InvestmentCommittee research tool ({CONTACT_EMAIL})"}

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

_MIN_REQUEST_INTERVAL = 0.11  # stays under SEC's 10 req/sec limit
_last_request_time = 0.0

# XBRL tag synonym fallback lists — every metric needs one since filers vary.
TAG_FALLBACKS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "rnd": ["ResearchAndDevelopmentExpense"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "total_assets": ["Assets"],
    "total_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "total_debt": [
        "DebtLongtermAndShorttermCombinedAmount",
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForCapitalImprovements"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "shares_outstanding": ["CommonStockSharesOutstanding"],
}


def _throttled_get(url):
    global _last_request_time
    wait = _MIN_REQUEST_INTERVAL - (time.time() - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    response = requests.get(url, headers=HEADERS, timeout=20)
    _last_request_time = time.time()
    response.raise_for_status()
    return response


def get_ticker_map():
    def fetch():
        return _throttled_get(TICKER_MAP_URL).json()

    return cached_fetch("us_ticker_map", ttl_hours=24 * 7, fetch_fn=fetch)


def resolve_cik(ticker):
    ticker_map = get_ticker_map()
    ticker_upper = ticker.upper()
    for entry in ticker_map.values():
        if entry["ticker"] == ticker_upper:
            return str(entry["cik_str"]).zfill(10), entry["title"]
    raise ValueError(f"Ticker {ticker} not found in SEC company_tickers.json")


def fetch_company_facts(cik):
    def fetch():
        return _throttled_get(COMPANYFACTS_URL.format(cik=cik)).json()

    return cached_fetch(f"us_facts_{cik}", ttl_hours=24, fetch_fn=fetch)


def _is_annual_duration(start, end):
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return 350 <= days <= 380


def _extract_series(facts, tags):
    """Return (unit, [{"end": date, "val": number}, ...]) for the first tag with 10-K data."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        node = us_gaap.get(tag)
        if not node:
            continue
        units = node.get("units", {})
        unit_key = "USD" if "USD" in units else next(iter(units), None)
        if not unit_key:
            continue
        candidates = []
        for item in units[unit_key]:
            if item.get("form") != "10-K":
                continue
            if item.get("start") and not _is_annual_duration(item["start"], item["end"]):
                continue
            candidates.append(item)
        if not candidates:
            continue
        by_end = {}
        for item in candidates:
            key = item["end"]
            if key not in by_end or item["filed"] > by_end[key]["filed"]:
                by_end[key] = item
        series = sorted(by_end.values(), key=lambda i: i["end"])
        if series:
            return unit_key, {item["end"]: item["val"] for item in series}
    return None, {}


def _build_annual_rows(facts, max_years=10):
    series_by_metric = {metric: _extract_series(facts, tags)[1] for metric, tags in TAG_FALLBACKS.items()}

    anchor = series_by_metric.get("revenue") or series_by_metric.get("net_income") or {}
    end_dates = sorted(anchor.keys())[-max_years:]

    rows = []
    for end_date in end_dates:
        row = {"period": end_date}
        for metric, series in series_by_metric.items():
            row[metric] = series.get(end_date)
        rows.append(compute_derived(row))
    return rows


def fetch(ticker):
    cik, company_name = resolve_cik(ticker)
    facts = fetch_company_facts(cik)
    return {
        "ticker": ticker.upper(),
        "name": company_name,
        "market": "US",
        "currency": "USD",
        "unit_label": "USD",
        "sector": "N/A",
        "price": None,
        "market_cap": None,
        "annual": _build_annual_rows(facts),
        "ratios": {},
        "shareholding": [],
        "qualitative": "",
    }


def fetch_and_format(ticker):
    return format_for_agents(fetch(ticker))
