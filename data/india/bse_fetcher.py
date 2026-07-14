"""
India fetcher: Screener.in (public HTML pages) for price, market cap, 10yr
P&L / balance sheet / cash flow / ratios, and shareholding pattern trend.

Screener.in already surfaces price, market cap, and the promoter/FII/DII/
public shareholding trend directly on the company page, so this fetcher does
not depend on NSE's session-cookie-gated APIs at all — those are known to be
fragile for scripted access, and everything the committee needs is already
here in one reliably reachable page.
"""

import csv
import io
import re
import time

import requests
from bs4 import BeautifulSoup

from data.common import cached_fetch, compute_derived, format_for_agents, is_data_sparse

# Manually curated: freshly demerged/spun-off tickers that have little or no
# standalone history on Screener yet, mapped to the parent whose overall
# financials are a reasonable stand-in until the new entity files its own
# first full year. Extend this as new demergers come up — there's no reliable
# way to detect "X was demerged from Y" automatically from Screener's HTML.
DEMERGER_PARENT_MAP = {
    "VOGL": "VEDL",  # Vedanta Oil & Gas Ltd, demerged from Vedanta Ltd
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

BASE_URL = "https://www.screener.in/company/{ticker}/{statement_type}/"
_REQUEST_DELAY_SECONDS = 0.5

# Static, non-session-gated list of every NSE-listed equity (symbol + full
# company name) — used to power ticker/company-name search, not financials.
NSE_EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def get_symbol_list():
    def fetch():
        response = requests.get(NSE_EQUITY_LIST_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        reader = csv.DictReader(io.StringIO(response.text))
        rows = []
        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip()
            name = (row.get("NAME OF COMPANY") or "").strip()
            if symbol and name:
                rows.append({"symbol": symbol, "name": name})
        return rows

    return cached_fetch("in_equity_list", ttl_hours=24 * 7, fetch_fn=fetch)


def _get_html(ticker, statement_type):
    time.sleep(_REQUEST_DELAY_SECONDS)
    url = BASE_URL.format(ticker=ticker.upper(), statement_type=statement_type)
    response = requests.get(url, headers=HEADERS, timeout=20)
    return response


def fetch_screener_html(ticker):
    """Consolidated figures first, falling back to standalone if unavailable."""
    response = _get_html(ticker, "consolidated")
    if response.status_code == 200:
        return response.text, "consolidated"
    response = _get_html(ticker, "")
    if response.status_code == 200:
        return response.text, "standalone"
    raise ValueError(f"Screener.in has no page for ticker {ticker} (status {response.status_code})")


def parse_number(text):
    if text is None:
        return None
    cleaned = text.strip().replace(",", "").replace("₹", "").replace("%", "").replace("Cr.", "").strip()
    if cleaned in ("", "-"):
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if cleaned in ("", "-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_top_ratios(soup):
    ul = soup.find("ul", id="top-ratios")
    if not ul:
        return {}
    result = {}
    for li in ul.find_all("li", recursive=False):
        name_span = li.find("span", class_="name")
        number_span = li.find("span", class_="number")
        if not name_span or not number_span:
            continue
        name = name_span.get_text(strip=True)
        result[name] = parse_number(number_span.get_text(strip=True))
    return result


def _clean_label(label):
    return re.sub(r"\s*\+\s*$", "", label).strip()


def parse_generic_table(table):
    thead = table.find("thead")
    tbody = table.find("tbody")
    if thead is None or tbody is None:
        return [], {}
    headers = [th.get_text(strip=True) for th in thead.find_all("th")][1:]
    rows = {}
    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        label = _clean_label(tds[0].get_text(strip=True))
        values = [parse_number(td.get_text(strip=True)) for td in tds[1:]]
        rows[label] = values
    return headers, rows


def _find_section_table(soup, section_id):
    section = soup.find(id=section_id)
    if not section:
        return None
    return section.find("table", class_="data-table")


SHAREHOLDING_CATEGORIES = ("promoters", "fiis", "diis", "government", "public", "others")


def parse_shareholding(soup):
    container = soup.find(id="quarterly-shp")
    if not container:
        return []
    table = container.find("table", class_="data-table")
    if table is None:
        return []
    headers, rows = parse_generic_table(table)
    result = []
    for i, period in enumerate(headers):
        entry = {"period": period}
        for label, values in rows.items():
            key = label.lower().replace(" ", "_")
            if key not in SHAREHOLDING_CATEGORIES:
                continue
            if i < len(values):
                entry[key] = values[i]
        result.append(entry)
    return result


def _row(rows, *candidates):
    for candidate in candidates:
        if candidate in rows:
            return rows[candidate]
    for label, values in rows.items():
        if any(candidate.lower() in label.lower() for candidate in candidates):
            return values
    return None


def _build_annual_rows(soup, max_years=10):
    pl_table = _find_section_table(soup, "profit-loss")
    bs_table = _find_section_table(soup, "balance-sheet")
    cf_table = _find_section_table(soup, "cash-flow")

    pl_headers, pl_rows = parse_generic_table(pl_table) if pl_table is not None else ([], {})
    _, bs_rows = parse_generic_table(bs_table) if bs_table is not None else ([], {})
    _, cf_rows = parse_generic_table(cf_table) if cf_table is not None else ([], {})

    sales = _row(pl_rows, "Sales", "Revenue")
    if not sales:
        return []

    periods = pl_headers[-max_years:]
    offset = len(pl_headers) - len(periods)

    equity_capital = _row(bs_rows, "Equity Capital")
    reserves = _row(bs_rows, "Reserves")
    borrowings = _row(bs_rows, "Borrowings")
    total_assets = _row(bs_rows, "Total Assets", "Total Liabilities")
    cash_row = _row(bs_rows, "Cash & Bank", "Cash Equivalents", "Investments")

    ocf = _row(cf_rows, "Cash from Operating Activity")

    rows = []
    for i, period in enumerate(periods):
        idx = offset + i
        revenue = sales[idx] if idx < len(sales) else None
        equity = None
        if equity_capital and reserves and idx < len(equity_capital) and idx < len(reserves):
            ec, rs = equity_capital[idx], reserves[idx]
            if ec is not None or rs is not None:
                equity = (ec or 0) + (rs or 0)
        row = {
            "period": period,
            "revenue": revenue,
            "gross_profit": None,
            "operating_income": (_row(pl_rows, "Operating Profit") or [None] * len(periods))[idx]
            if _row(pl_rows, "Operating Profit") and idx < len(_row(pl_rows, "Operating Profit"))
            else None,
            "net_income": (_row(pl_rows, "Net Profit") or [None] * len(periods))[idx]
            if _row(pl_rows, "Net Profit") and idx < len(_row(pl_rows, "Net Profit"))
            else None,
            "rnd": None,
            "eps_diluted": (_row(pl_rows, "EPS in Rs") or [None] * len(periods))[idx]
            if _row(pl_rows, "EPS in Rs") and idx < len(_row(pl_rows, "EPS in Rs"))
            else None,
            "total_assets": total_assets[idx] if total_assets and idx < len(total_assets) else None,
            "total_equity": equity,
            "total_debt": borrowings[idx] if borrowings and idx < len(borrowings) else None,
            "cash": cash_row[idx] if cash_row and idx < len(cash_row) else None,
            "operating_cash_flow": ocf[idx] if ocf and idx < len(ocf) else None,
            "capex": None,
            "dividends": None,
            "shares_outstanding": None,
        }
        rows.append(compute_derived(row))
    return rows


def _parse(html):
    soup = BeautifulSoup(html, "lxml")
    name_tag = soup.find("h1")
    name = name_tag.get_text(strip=True) if name_tag else None
    top_ratios = parse_top_ratios(soup)

    ratios_table = _find_section_table(soup, "ratios")
    _, ratios_rows = parse_generic_table(ratios_table) if ratios_table is not None else ([], {})
    ratios = {label: values[-1] for label, values in ratios_rows.items() if values and values[-1] is not None}
    ratios.update({k: v for k, v in top_ratios.items() if k in ("ROCE", "ROE") and v is not None})

    return {
        "name": name,
        "price": top_ratios.get("Current Price"),
        "market_cap": top_ratios.get("Market Cap"),
        "annual": _build_annual_rows(soup),
        "ratios": ratios,
        "shareholding": parse_shareholding(soup),
    }


def fetch(ticker, _allow_parent_lookup=True):
    def do_fetch():
        html, statement_type = fetch_screener_html(ticker)
        parsed = _parse(html)
        parsed["statement_type"] = statement_type
        return parsed

    ticker_upper = ticker.upper()
    parsed = cached_fetch(f"in_screener_{ticker_upper}", ttl_hours=24, fetch_fn=do_fetch)
    result = {
        "ticker": ticker_upper,
        "name": parsed.get("name") or ticker_upper,
        "market": "India",
        "currency": "INR",
        "unit_label": "INR Cr.",
        "sector": "N/A",
        "price": parsed.get("price"),
        "market_cap": parsed.get("market_cap"),
        "annual": parsed.get("annual", []),
        "ratios": parsed.get("ratios", {}),
        "shareholding": parsed.get("shareholding", []),
        "qualitative": f"Figures are {parsed.get('statement_type', 'consolidated')} per Screener.in.",
    }

    parent_ticker = DEMERGER_PARENT_MAP.get(ticker_upper)
    if _allow_parent_lookup and parent_ticker and is_data_sparse(result):
        try:
            result["parent_context"] = fetch(parent_ticker, _allow_parent_lookup=False)
        except Exception:
            pass  # parent lookup is a nice-to-have; don't fail the main fetch over it
    return result


def fetch_and_format(ticker):
    return format_for_agents(fetch(ticker))
