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

# Annual report forms: 10-K for domestic filers, 20-F / 40-F for foreign private
# issuers (Alibaba, Sony, Shopify). Filtering to 10-K alone returned nothing at
# all for those companies.
ANNUAL_FORMS = ("10-K", "20-F", "40-F")

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
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
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
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForCapitalImprovements",
    ],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "shares_outstanding": ["CommonStockSharesOutstanding"],
}

# Foreign private issuers that report under IFRS (Novo Nordisk, TSMC, SAP,
# AstraZeneca, Toyota) publish their 20-F figures under the ifrs-full taxonomy
# instead of us-gaap, so none of the tags above match them. Same concepts,
# different names. Tried after the us-gaap tags.
IFRS_TAG_FALLBACKS = {
    "revenue": ["Revenue", "RevenueFromContractsWithCustomers"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["ProfitLossFromOperatingActivities", "OperatingProfitLoss"],
    "net_income": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "rnd": ["ResearchAndDevelopmentExpense"],
    "eps_diluted": ["DilutedEarningsLossPerShare", "BasicAndDilutedEarningsLossPerShare", "BasicEarningsLossPerShare"],
    "total_assets": ["Assets"],
    "total_equity": ["EquityAttributableToOwnersOfParent", "Equity"],
    "total_debt": ["Borrowings"],
    "cash": ["CashAndCashEquivalents"],
    "operating_cash_flow": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": [
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
        "PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets",
    ],
    "dividends": ["DividendsPaidClassifiedAsFinancingActivities", "DividendsPaid"],
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


def fetch_sic_description(ticker):
    """The SEC's industry label for the company ("Fire, Marine & Casualty Insurance"),
    or None. Used as the sector when no market-data source has one."""
    try:
        cik, _ = resolve_cik(ticker)
        data = cached_fetch(
            f"sec_submissions_{str(cik).zfill(10)}", 24 * 7,
            lambda: _throttled_get(f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json").json())
        return (data.get("sicDescription") or "").strip() or None
    except Exception:
        return None


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


def _pick_unit(units, preferred):
    """The unit to read from one tag. The company's reporting currency when the
    tag has it (IFRS filers also publish USD convenience translations, and a
    mixed series would be nonsense), else USD, else whatever the tag has."""
    if preferred:
        for candidate in (preferred, f"{preferred}/shares"):
            if candidate in units:
                return candidate
    if "USD" in units:
        return "USD"
    return next(iter(units), None)


def _reporting_unit(facts):
    """The currency the annual statements are actually in: whichever currency has
    the most annual-report revenue / net income facts. None when there are none."""
    counts = {}
    for taxonomy, tags in (("us-gaap", TAG_FALLBACKS["revenue"] + TAG_FALLBACKS["net_income"]),
                           ("ifrs-full", IFRS_TAG_FALLBACKS["revenue"] + IFRS_TAG_FALLBACKS["net_income"])):
        node_map = facts.get("facts", {}).get(taxonomy, {})
        for tag in tags:
            for unit, items in (node_map.get(tag, {}).get("units", {})).items():
                if "/" in unit or unit in ("shares", "pure"):
                    continue
                n = sum(1 for i in items if i.get("form") in ANNUAL_FORMS)
                if n:
                    counts[unit] = counts.get(unit, 0) + n
    return max(counts, key=counts.get) if counts else None


def _extract_series(facts, tags, ifrs_tags=(), unit=None):
    """Merge annual-report entries (10-K / 20-F / 40-F) across ALL fallback tags — not
    just the first one with any data. Companies sometimes rename which XBRL
    tag they report a concept under (e.g. NVIDIA moved revenue from
    RevenueFromContractWithCustomerExcludingAssessedTax to plain Revenues
    around FY2022); stopping at the first populated tag silently locks onto
    whichever tag happened to be listed first, which can be one the company
    has since abandoned — missing every filing since the switch and making
    "the latest annual figures" quietly several years stale. For a period
    reported under more than one tag, whichever was filed most recently wins.
    `ifrs_tags` are read from the ifrs-full taxonomy the same way."""
    all_facts = facts.get("facts", {})
    unit_key = None
    by_end = {}
    for taxonomy, tag_list in (("us-gaap", tags), ("ifrs-full", ifrs_tags)):
        node_map = all_facts.get(taxonomy, {})
        for tag in tag_list:
            node = node_map.get(tag)
            if not node:
                continue
            units = node.get("units", {})
            tag_unit = _pick_unit(units, unit)
            if not tag_unit:
                continue
            for item in units[tag_unit]:
                if item.get("form") not in ANNUAL_FORMS:
                    continue
                if item.get("start") and not _is_annual_duration(item["start"], item["end"]):
                    continue
                key = item["end"]
                if key not in by_end or item["filed"] > by_end[key]["filed"]:
                    by_end[key] = item
                    unit_key = tag_unit
    if not by_end:
        return None, {}
    series = sorted(by_end.values(), key=lambda i: i["end"])
    return unit_key, {item["end"]: item["val"] for item in series}


# Companies that report debt as several line items (convertible notes, bank loans,
# bonds) have no single total tag, so the pieces are added up.
DEBT_COMPONENTS = ["ConvertibleDebtNoncurrent", "ConvertibleDebtCurrent", "LongTermLoansFromBank",
                   "SeniorLongTermNotes", "SeniorNotesCurrent", "ShortTermBorrowings"]
IFRS_DEBT_COMPONENTS = ["LongtermBorrowings", "CurrentPortionOfLongtermBorrowings", "ShorttermBorrowings",
                        "NoncurrentPortionOfNoncurrentBondsIssued",
                        "CurrentBondsIssuedAndCurrentPortionOfNoncurrentBondsIssued"]


def _summed_debt(facts, unit):
    totals = {}
    for tag in DEBT_COMPONENTS:
        for end, val in _extract_series(facts, [tag], (), unit)[1].items():
            totals[end] = totals.get(end, 0) + val
    for tag in IFRS_DEBT_COMPONENTS:
        for end, val in _extract_series(facts, [], [tag], unit)[1].items():
            totals[end] = totals.get(end, 0) + val
    return totals


def _build_annual_rows(facts, max_years=10):
    unit = _reporting_unit(facts)
    series_by_metric = {
        metric: _extract_series(facts, tags, IFRS_TAG_FALLBACKS.get(metric, ()), unit)[1]
        for metric, tags in TAG_FALLBACKS.items()
    }

    if not series_by_metric.get("total_debt"):
        series_by_metric["total_debt"] = _summed_debt(facts, unit)

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
    # Foreign filers report in their own currency (Alibaba in CNY). Assuming USD
    # would label yuan as dollars, so take the unit the filing actually used.
    unit = _reporting_unit(facts) or "USD"
    foreign = unit != "USD"
    return {
        "ticker": ticker.upper(),
        "name": company_name,
        "market": "US",
        "currency": unit,
        "unit_label": unit,
        **({"market_cap_unit": "USD", "price_currency": "USD"} if foreign else {}),
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
