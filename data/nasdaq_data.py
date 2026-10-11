"""
Nasdaq's public quote API as a second source for US stocks.

Yahoo Finance (via yfinance) is the main source for price, market cap, ratios,
price history and gap-filling statements, but it is an unofficial API and
answers cloud/datacenter IPs (Render) with empty data. Without it a US stock
loses its price, market cap, sector and price action, and any company whose
SEC filings are patchy (Exxon) loses its statements too. Nasdaq publishes the
same things over a plain JSON API that works without cookies or keys, and covers
NYSE-listed names as well.

Best-effort like every fetcher in data/: any failure returns "no extra data",
never an exception. India has no equivalent here (Screener already provides it).
"""

import re
import time
from datetime import date, datetime, timedelta

import requests

from data.common import cached_fetch

NASDAQ_TTL_HOURS = 1
NASDAQ_STATEMENTS_TTL_HOURS = 24
BASE = "https://api.nasdaq.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def _get(path, params=None, retries=2):
    last = None
    for attempt in range(retries):
        try:
            resp = requests.get(f"{BASE}/{path}", params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            body = resp.json()
            if body.get("data") is not None:
                return body["data"]
            last = ValueError(f"Nasdaq returned no data for {path}")
        except Exception as e:  # network, HTTP error or non-JSON body
            last = e
        time.sleep(1.0 + attempt)
    raise last


def _sym(ticker):
    """Nasdaq writes share classes with a dot (BRK.B); Yahoo and our callers use a hyphen."""
    return ticker.upper().replace("-", ".")


def _num(text):
    """'$1,234.50', '-$920,000', '12.5%', '--', 'N/A' -> float or None."""
    if text is None:
        return None
    s = str(text).strip()
    if not s or s.upper() in ("N/A", "NA", "--", "-"):
        return None
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"[^0-9.]", "", s)
    if not s or s == ".":
        return None
    value = float(s)
    return -value if neg else value


def _summary_value(summary, key):
    node = (summary or {}).get(key)
    return node.get("value") if isinstance(node, dict) else None


# ---- quote / profile -------------------------------------------------------

def _fetch_quote(ticker):
    symbol = _sym(ticker)
    summary = _get(f"quote/{symbol}/summary", {"assetclass": "stocks"}).get("summaryData") or {}
    market_cap = _num(_summary_value(summary, "MarketCap"))

    price = None
    try:
        info = _get(f"quote/{symbol}/info", {"assetclass": "stocks"})
        price = _num(((info or {}).get("primaryData") or {}).get("lastSalePrice"))
    except Exception:
        pass
    if price is None:
        price = _num(_summary_value(summary, "PreviousClose"))
    if price is None and market_cap is None:
        raise ValueError(f"Nasdaq has no quote for {symbol}")

    high = low = None
    rng = _summary_value(summary, "FiftTwoWeekHighLow")  # "$64.16/$35.12"
    if rng and "/" in str(rng):
        a, b = str(rng).split("/", 1)
        high, low = _num(a), _num(b)

    sector = _summary_value(summary, "Sector")
    industry = _summary_value(summary, "Industry")
    description = None
    try:
        profile = _get(f"company/{symbol}/company-profile")
        sector = sector if sector not in (None, "N/A") else _summary_value(profile, "Sector")
        industry = industry if industry not in (None, "N/A") else _summary_value(profile, "Industry")
        description = _summary_value(profile, "CompanyDescription")
    except Exception:
        pass

    dividend_yield = pe = annual_dividend = forward_eps = None
    try:
        div = _get(f"quote/{symbol}/dividends", {"assetclass": "stocks"})
        dividend_yield = _num(div.get("yield"))
        annual_dividend = _num(div.get("annualizedDividend"))
        pe = _num(next((h.get("value") for h in div.get("dividendHeaderValues", [])
                        if h.get("label") == "P/E Ratio"), None))
    except Exception:
        pass
    estimates = []
    try:
        rows = ((_get(f"analyst/{symbol}/earnings-forecast").get("yearlyForecast") or {}).get("rows")) or []
        # the first fiscal year still in the future is the forward estimate
        forward_eps = _num(rows[0].get("consensusEPSForecast")) if rows else None
        estimates = [{"year": r.get("fiscalEnd"), "eps": r.get("consensusEPSForecast"),
                      "analysts": r.get("noOfEstimates")} for r in rows[:3]]
    except Exception:
        pass
    surprises = []
    try:
        for r in (_get(f"quote/{symbol}/eps").get("earningsPerShare") or []):
            if r.get("type") == "PreviousQuarter" and r.get("consensus") is not None:
                surprises.append({"period": r.get("period"), "actual": r.get("earnings"),
                                  "consensus": r.get("consensus")})
    except Exception:
        pass

    return {
        "price": price,
        "market_cap": market_cap,
        "dividend_yield": dividend_yield,
        "annual_dividend": annual_dividend,
        "pe": pe,
        "forward_eps": forward_eps,
        "eps_estimates": estimates,
        "eps_surprises": surprises[-4:],
        "sector": sector if sector not in (None, "N/A", "") else None,
        "industry": industry if industry not in (None, "N/A", "") else None,
        "high_52w": high,
        "low_52w": low,
        "target": _num(_summary_value(summary, "OneYrTarget")),
        "avg_volume": _num(_summary_value(summary, "AverageVolume")),
        "description": (description or "").strip() or None,
    }


def fetch_nasdaq_quote(ticker):
    """Price, market cap, sector, industry, 52-week range, analyst target; {} on failure."""
    try:
        return cached_fetch(f"nasdaq_quote_{ticker.upper()}", NASDAQ_TTL_HOURS, lambda: _fetch_quote(ticker))
    except Exception:
        return {}


# ---- price history ---------------------------------------------------------

def _fetch_history(ticker, assetclass="stocks"):
    today = date.today()
    data = _get(
        f"quote/{_sym(ticker)}/historical",
        {"assetclass": assetclass, "fromdate": (today - timedelta(days=430)).isoformat(),
         "todate": today.isoformat(), "limit": 400},
    )
    rows = ((data or {}).get("tradesTable") or {}).get("rows") or []
    series = []
    for r in rows:
        close = _num(r.get("close"))
        try:
            day = datetime.strptime(r.get("date", ""), "%m/%d/%Y").date().isoformat()
        except ValueError:
            continue
        if close is not None:
            series.append((day, close))
    if len(series) < 20:
        raise ValueError(f"Nasdaq history too short for {ticker}")
    return sorted(series)


def fetch_nasdaq_history(ticker, assetclass="stocks"):
    """[(iso_date, close)] oldest to newest, about 14 months of daily closes; [] on failure."""
    try:
        return cached_fetch(f"nasdaq_hist_{assetclass}_{ticker.upper()}", NASDAQ_TTL_HOURS,
                            lambda: [list(p) for p in _fetch_history(ticker, assetclass)])
    except Exception:
        return []


# ---- annual statements -----------------------------------------------------

# our field -> (table, Nasdaq row labels in order of preference)
_STATEMENT_MAP = {
    "revenue": ("incomeStatementTable", ["Total Revenue"]),
    "gross_profit": ("incomeStatementTable", ["Gross Profit"]),
    "operating_income": ("incomeStatementTable", ["Operating Income"]),
    "pretax_income": ("incomeStatementTable", ["Earnings Before Tax"]),
    "net_income": ("incomeStatementTable", ["Net Income"]),
    "rnd": ("incomeStatementTable", ["Research and Development"]),
    "interest_expense": ("incomeStatementTable", ["Interest Expense"]),
    "total_assets": ("balanceSheetTable", ["Total Assets"]),
    "total_equity": ("balanceSheetTable", ["Total Equity"]),
    "cash": ("balanceSheetTable", ["Cash and Cash Equivalents"]),
    "operating_cash_flow": ("cashFlowTable", ["Net Cash Flow-Operating"]),
    "capex": ("cashFlowTable", ["Capital Expenditures"]),
    "buybacks": ("cashFlowTable", ["Sale and Purchase of Stock"]),  # net: only an outflow counts as a buyback
}
_ABS = {"capex", "interest_expense"}
_DEBT_ROWS = ("Short-Term Debt / Current Portion of Long-Term Debt", "Long-Term Debt")


def _table_columns(table):
    """{column key: iso date} from a statement table's header row."""
    out = {}
    for key, label in (table.get("headers") or {}).items():
        if key == "value1":
            continue
        try:
            out[key] = datetime.strptime(label, "%m/%d/%Y").date().isoformat()
        except (TypeError, ValueError):
            pass
    return out


def _fetch_statements(ticker):
    data = _get(f"company/{_sym(ticker)}/financials", {"frequency": 1})
    tables = {k: (data or {}).get(k) or {} for k in ("incomeStatementTable", "balanceSheetTable", "cashFlowTable")}
    columns = _table_columns(tables["incomeStatementTable"]) or _table_columns(tables["balanceSheetTable"])
    if not columns:
        raise ValueError(f"Nasdaq has no statements for {ticker}")

    def cells(table_name, labels):
        by_label = {r.get("value1"): r for r in (tables[table_name].get("rows") or [])}
        for label in labels:
            if label in by_label:
                return by_label[label]
        return None

    rows = []
    for col, iso in sorted(columns.items(), key=lambda kv: kv[1]):
        row = {"period": iso}
        for field, (table_name, labels) in _STATEMENT_MAP.items():
            src = cells(table_name, labels)
            value = _num(src.get(col)) if src else None
            if field == "buybacks":
                value = abs(value) if value is not None and value < 0 else None
            if value is not None:
                value = abs(value) if field in _ABS else value
                value = round(value * 1000, 2)  # Nasdaq reports thousands of dollars
            row[field] = value
        debts = []
        for label in _DEBT_ROWS:
            src = cells("balanceSheetTable", [label])
            debts.append(_num(src.get(col)) if src else None)
        row["total_debt"] = round(sum(d for d in debts if d is not None) * 1000, 2) if any(
            d is not None for d in debts) else None
        rows.append(row)
    rows = [r for r in rows if r.get("revenue") is not None or r.get("net_income") is not None]
    if not rows:
        raise ValueError(f"Nasdaq statements for {ticker} were empty")

    # the latest year's line items that the summary fields leave out (receivables,
    # inventory, current assets and liabilities, goodwill ...), for liquidity questions
    latest_col = max(columns, key=lambda k: columns[k])

    def detail(table_name, labels):
        out = {}
        for label in labels:
            src = cells(table_name, [label])
            value = _num(src.get(latest_col)) if src else None
            if value is not None:
                out[label] = round(value * 1000, 2)
        return out

    balance = detail("balanceSheetTable", [
        "Net Receivables", "Inventory", "Total Current Assets", "Total Current Liabilities", "Accounts Payable",
        "Short-Term Investments", "Goodwill", "Intangible Assets", "Long-Term Investments",
        "Short-Term Debt / Current Portion of Long-Term Debt", "Long-Term Debt", "Total Liabilities"])
    flows = detail("cashFlowTable", [
        "Depreciation", "Net Cash Flows-Investing", "Net Cash Flows-Financing",
        "Sale and Purchase of Stock", "Net Borrowings"])
    return {"rows": rows, "currency": "USD",
            "detail": {"period": columns[latest_col], "currency": "USD",
                       "balance_sheet": balance, "cash_flow": flows}}


def fetch_nasdaq_annual(ticker):
    """{"rows": [...oldest to newest...], "currency": "USD"} or {} on failure.
    Nasdaq converts foreign issuers to US dollars, so currency is always USD."""
    try:
        return cached_fetch(f"nasdaq_fin_{ticker.upper()}", NASDAQ_STATEMENTS_TTL_HOURS,
                            lambda: _fetch_statements(ticker))
    except Exception:
        return {}


# ---- stock universe (for peers) -------------------------------------------

def _fetch_universe():
    data = _get("screener/stocks", {"tableonly": "true", "limit": 10000, "offset": 0, "download": "true"})
    out = []
    for r in (data or {}).get("rows") or []:
        cap = _num(r.get("marketCap"))
        if r.get("symbol") and cap:
            out.append({"symbol": r["symbol"].strip(), "name": (r.get("name") or "").strip(),
                        "cap": cap, "sector": r.get("sector") or None, "industry": r.get("industry") or None})
    if len(out) < 500:
        raise ValueError("Nasdaq screener returned a truncated list")
    return out


def fetch_nasdaq_universe():
    """Every listed US stock with market cap, sector and industry; [] on failure."""
    try:
        return cached_fetch("nasdaq_universe", 24, _fetch_universe)
    except Exception:
        return []
