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
from data.technicals import compute_technicals

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


_PERIOD_LONG = re.compile(r"^(\w{3} \d{4})(\d{1,2})m$")


def _period_key(header):
    """Screener glues a long fiscal period's length onto the label ("Mar 202615m"
    is a 15-month year) in the profit-and-loss table only; the balance-sheet and
    cash-flow tables call the same period plain "Mar 2026". Matching on this key
    is what lets the three tables line up."""
    m = _PERIOD_LONG.match(header)
    return m.group(1) if m else header


def _period_label(header):
    m = _PERIOD_LONG.match(header)
    return f"{m.group(1)} ({m.group(2)} months)" if m else header


def _at(values, idx):
    if values is None or idx is None or idx >= len(values):
        return None
    return values[idx]


def _table(soup, section_id):
    table = _find_section_table(soup, section_id)
    return parse_generic_table(table) if table is not None else ([], {})


def _build_annual_rows(soup, max_years=10):
    """Returns (fiscal_year_rows, ttm_row, latest_year_detail).

    The three statements are matched by period label, never by column position.
    They used to be matched by position, and the profit-and-loss table has a
    trailing "TTM" column the other two lack, so the "latest" row (TTM) found no
    balance-sheet or cash-flow entry and every Indian stock showed N/A for both,
    even though Screener publishes them (including a Free Cash Flow row).
    TTM is returned separately: it only has income-statement figures."""
    pl_h, pl = _table(soup, "profit-loss")
    bs_h, bs = _table(soup, "balance-sheet")
    cf_h, cf = _table(soup, "cash-flow")

    sales = _row(pl, "Sales", "Revenue")
    if not sales:
        return [], None, {}

    bs_idx = {_period_key(h): i for i, h in enumerate(bs_h)}
    cf_idx = {_period_key(h): i for i, h in enumerate(cf_h)}
    op, net_p, eps = _row(pl, "Operating Profit"), _row(pl, "Net Profit"), _row(pl, "EPS in Rs")
    payout = _row(pl, "Dividend Payout %")
    eq_cap, reserves = _row(bs, "Equity Capital"), _row(bs, "Reserves")
    borrowings, assets = _row(bs, "Borrowings"), _row(bs, "Total Assets", "Total Liabilities")
    ocf_row, fcf_row = _row(cf, "Cash from Operating Activity"), _row(cf, "Free Cash Flow")

    def build(i, header):
        key = _period_key(header)
        b, c = bs_idx.get(key), cf_idx.get(key)
        ec, rs = _at(eq_cap, b), _at(reserves, b)
        equity = ((ec or 0) + (rs or 0)) if (ec is not None or rs is not None) else None
        net, ocf, fcf, pay = _at(net_p, i), _at(ocf_row, c), _at(fcf_row, c), _at(payout, i)
        row = {
            "period": _period_label(header),
            "revenue": _at(sales, i),
            "gross_profit": None,
            "operating_income": _at(op, i),
            "net_income": net,
            "rnd": None,
            "eps_diluted": _at(eps, i),
            "total_assets": _at(assets, b),
            "total_equity": equity,
            "total_debt": _at(borrowings, b),
            # Screener has no cash line. It used to be filled from the
            # "Investments" row, which is not cash (it is 0 for IGIL) and told
            # agents the company held none.
            "cash": None,
            "operating_cash_flow": ocf,
            # Screener's Free Cash Flow is operating cash flow minus fixed-asset
            # purchases, so capex is recoverable from the two.
            "capex": (ocf - fcf) if (ocf is not None and fcf is not None) else None,
            "dividends": round(net * pay / 100, 1) if (net is not None and pay is not None) else None,
            "shares_outstanding": None,
        }
        compute_derived(row)
        if fcf is not None:
            row["fcf"] = fcf
        return row

    fiscal = [(i, h) for i, h in enumerate(pl_h) if h != "TTM"][-max_years:]
    rows = [build(i, h) for i, h in fiscal]
    ttm = build(pl_h.index("TTM"), "TTM") if "TTM" in pl_h else None

    detail = {}
    if bs_h:
        last = len(bs_h) - 1
        detail["period"] = _period_label(bs_h[last])
        detail["balance_sheet"] = {k: _at(v, last) for k, v in bs.items() if _at(v, last) is not None}
    if cf_h:
        last = len(cf_h) - 1
        detail["cash_flow"] = {k: _at(v, last) for k, v in cf.items() if _at(v, last) is not None}
    return rows, ttm, detail


def _quarters(soup, n=6):
    headers, rows = _table(soup, "quarters")
    sales = _row(rows, "Sales", "Revenue")
    if not sales:
        return []
    op, opm = _row(rows, "Operating Profit"), _row(rows, "OPM %")
    net, eps = _row(rows, "Net Profit"), _row(rows, "EPS in Rs")
    start = max(0, len(headers) - n)
    return [
        {
            "period": headers[i],
            "sales": _at(sales, i),
            "operating_profit": _at(op, i),
            "opm": _at(opm, i),
            "net_profit": _at(net, i),
            "eps": _at(eps, i),
        }
        for i in range(start, len(headers))
    ]


def _growth(soup):
    """Screener's compounded-growth boxes: sales/profit CAGR, price CAGR, ROE."""
    out = {}
    for table in soup.select("table.ranges-table"):
        title_cell = table.find("th")
        if not title_cell:
            continue
        values = {}
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) >= 2:
                value = parse_number(tds[1].get_text(strip=True))
                if value is not None:
                    values[tds[0].get_text(strip=True).rstrip(":")] = value
        if values:
            out[title_cell.get_text(strip=True)] = values
    return out


def _bullets(soup, css_class, limit=4):
    return [li.get_text(" ", strip=True) for li in soup.select(f".{css_class} li")][:limit]


def _about(soup, limit=650):
    node = soup.select_one(".company-profile .about")
    if not node:
        return None
    text = re.sub(r"\[\d+\]", "", node.get_text(" ", strip=True)).strip()
    return text[:limit].rstrip() + ("..." if len(text) > limit else "")


def _high_low(soup):
    """The "High / Low" box on Screener's summary strip holds two numbers. The
    generic top-ratios parser mangles it (it concatenates both into one), so it
    was skipped and no India stock had a 52-week range from Screener."""
    ul = soup.find("ul", id="top-ratios")
    if not ul:
        return None, None
    for li in ul.find_all("li", recursive=False):
        name = li.find("span", class_="name")
        if name and "high" in name.get_text(strip=True).lower():
            nums = [parse_number(s.get_text(strip=True)) for s in li.find_all("span", class_="number")]
            if len(nums) >= 2 and None not in nums[:2]:
                return nums[0], nums[1]
    return None, None


def _price_series(html, statement_type):
    """About 14 months of daily closes from Screener's own chart endpoint (the
    same host the fundamentals come from, so it works wherever Screener does)."""
    match = re.search(r'data-company-id="(\d+)"', html)
    if not match:
        return []
    flag = "true" if statement_type == "consolidated" else "false"
    url = (
        f"https://www.screener.in/api/company/{match.group(1)}/chart/"
        f"?q=Price-DMA50-DMA200-Volume&days=400&consolidated={flag}"
    )
    response = requests.get(url, headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"}, timeout=20)
    response.raise_for_status()
    for dataset in response.json().get("datasets", []):
        if dataset.get("metric") == "Price":
            return [(day, float(value)) for day, value in dataset.get("values", [])]
    return []


def _parse(html):
    soup = BeautifulSoup(html, "lxml")
    name_tag = soup.find("h1")
    name = name_tag.get_text(strip=True) if name_tag else None
    top_ratios = parse_top_ratios(soup)

    ratios_table = _find_section_table(soup, "ratios")
    _, ratios_rows = parse_generic_table(ratios_table) if ratios_table is not None else ([], {})
    ratios = {label: values[-1] for label, values in ratios_rows.items() if values and values[-1] is not None}
    ratios.update({k: v for k, v in top_ratios.items() if k in ("ROCE", "ROE") and v is not None})
    # top_ratios already has these parsed (parse_top_ratios captures every
    # label on Screener's summary strip) — they were previously computed and
    # then silently thrown away here rather than passed through.
    for label, key, suffix in (
        ("Stock P/E", "P/E Ratio", ""),
        ("Dividend Yield", "Dividend Yield", "%"),
        ("Book Value", "Book Value per Share", ""),
    ):
        value = top_ratios.get(label)
        if value is not None:
            ratios[key] = f"{value}{suffix}" if suffix else value

    high, low = _high_low(soup)
    if high is not None:
        ratios["52-Week High"] = high
        ratios["52-Week Low"] = low

    annual, ttm, detail = _build_annual_rows(soup)
    return {
        "name": name,
        "price": top_ratios.get("Current Price"),
        "market_cap": top_ratios.get("Market Cap"),
        "annual": annual,
        "ttm": ttm,
        "balance_detail": detail,
        "quarters": _quarters(soup),
        "growth": _growth(soup),
        "pros": _bullets(soup, "pros"),
        "cons": _bullets(soup, "cons"),
        "about": _about(soup),
        "ratios": ratios,
        "shareholding": parse_shareholding(soup),
    }


def fetch(ticker, _allow_parent_lookup=True):
    def do_fetch():
        html, statement_type = fetch_screener_html(ticker)
        parsed = _parse(html)
        parsed["statement_type"] = statement_type
        try:
            parsed["technicals"] = compute_technicals(_price_series(html, statement_type))
        except Exception:
            parsed["technicals"] = {}  # price history is a bonus; never fail the fetch over it
        return parsed

    ticker_upper = ticker.upper()
    parsed = cached_fetch(f"in_screener_v2_{ticker_upper}", ttl_hours=24, fetch_fn=do_fetch)
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
        "ttm": parsed.get("ttm"),
        "balance_detail": parsed.get("balance_detail") or {},
        "quarters": parsed.get("quarters") or [],
        "growth": parsed.get("growth") or {},
        "pros": parsed.get("pros") or [],
        "cons": parsed.get("cons") or [],
        "business_summary": parsed.get("about"),
        "technicals": parsed.get("technicals") or {},
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
