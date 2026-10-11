"""
Yahoo Finance annual statements as a second source for fundamentals.

SEC EDGAR and Screener are the primary sources, but each has holes: EDGAR has
nothing usable for foreign filers (20-F/IFRS: TSMC, Novo Nordisk) and for some
US companies whose annual facts sit under unusual tags (Exxon); it has no
operating income for banks; Screener lacks cash, and has no usable layout for
some financial companies (IRFC). Yahoo publishes income statement, balance
sheet and cash flow for all of these, so it is used to (a) fill individual
missing fields in the latest years and (b) replace the statements entirely when
the primary source returned nothing useful.

Best-effort like every fetcher in data/: any failure returns "no extra data",
never an exception.
"""

import re
from datetime import date, datetime

import yfinance as yf

from data.common import cached_fetch, compute_derived

YAHOO_FUNDAMENTALS_TTL_HOURS = 24

# our field -> (statement, candidate Yahoo row labels, in order of preference)
FIELD_MAP = {
    "revenue": ("income", ["Total Revenue", "Operating Revenue"]),
    "gross_profit": ("income", ["Gross Profit"]),
    "operating_income": ("income", ["Operating Income", "Total Operating Income As Reported"]),
    "pretax_income": ("income", ["Pretax Income"]),
    "net_income": ("income", ["Net Income", "Net Income Common Stockholders"]),
    "eps_diluted": ("income", ["Diluted EPS", "Basic EPS"]),
    "rnd": ("income", ["Research And Development"]),
    "total_assets": ("balance", ["Total Assets"]),
    "total_equity": ("balance", ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]),
    "total_debt": ("balance", ["Total Debt"]),
    "cash": ("balance", ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
    "operating_cash_flow": ("cash", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
    "capex": ("cash", ["Capital Expenditure"]),
    "dividends": ("cash", ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
    "fcf": ("cash", ["Free Cash Flow"]),
    "buybacks": ("cash", ["Repurchase Of Capital Stock", "Common Stock Payments"]),
    "sbc": ("cash", ["Stock Based Compensation"]),
    "shares_avg": ("income", ["Diluted Average Shares", "Basic Average Shares"]),
    "interest_expense": ("income", ["Interest Expense", "Interest Expense Non Operating"]),
}
_ABS_FIELDS = {"capex", "dividends", "buybacks", "interest_expense"}  # Yahoo reports outflows as negative numbers
_PER_SHARE = {"eps_diluted", "shares_avg"}  # not currency amounts: never rescaled

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def _symbol(ticker, market):
    return f"{ticker.upper()}.NS" if market == "India" else ticker.upper()


def period_date(period):
    """ISO date, or Screener-style "Mar 2026" / "Mar 2026 (15 months)", as a date."""
    if not period:
        return None
    text = str(period).strip()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    m = re.match(r"^([A-Za-z]{3})\w*\s+(\d{4})", text)
    if m and m.group(1).lower() in _MONTHS:
        month, year = _MONTHS[m.group(1).lower()], int(m.group(2))
        nxt = date(year + (month == 12), (month % 12) + 1, 1)
        return date.fromordinal(nxt.toordinal() - 1)
    return None


def _cell(df, labels, col):
    # the three statements don't always cover the same years (one may reach a
    # year further back), so a missing column is "no value", not an error
    if df is None or df.empty or col not in df.columns:
        return None
    for label in labels:
        if label in df.index:
            value = df.at[label, col]
            if value == value and value is not None:  # not NaN
                return float(value)
    return None


def _fetch(ticker, market):
    stock = yf.Ticker(_symbol(ticker, market))
    frames = {"income": stock.income_stmt, "balance": stock.balance_sheet, "cash": stock.cashflow}
    if all(f is None or f.empty for f in frames.values()):
        raise ValueError(f"Yahoo returned no statements for {ticker}")

    try:
        currency = (stock.info or {}).get("financialCurrency")
    except Exception:
        currency = None

    scale = 1e7 if market == "India" else 1.0  # raw rupees -> crores, matching Screener's unit
    columns = sorted({c for f in frames.values() if f is not None and not f.empty for c in f.columns})
    rows = []
    for col in columns[-6:]:
        row = {"period": str(col.date())}
        for name, (stmt, labels) in FIELD_MAP.items():
            value = _cell(frames[stmt], labels, col)
            if value is not None:
                if name in _ABS_FIELDS:
                    value = abs(value)
                if name not in _PER_SHARE:
                    value = round(value / scale, 2)
            row[name] = value
        rows.append(row)
    return {"rows": rows, "currency": currency}


def fetch_yahoo_annual(ticker, market):
    """{"rows": [...oldest to newest...], "currency": "TWD"} or {} on any failure."""
    try:
        return cached_fetch(f"yfund_{market}_{ticker.upper()}", YAHOO_FUNDAMENTALS_TTL_HOURS,
                            lambda: _fetch(ticker, market))
    except Exception:
        return {}


_FILL_FIELDS = [f for f in FIELD_MAP if f != "pretax_income"]


def _is_sparse(rows):
    if len(rows) < 2:
        return True
    latest = rows[-1]
    return latest.get("revenue") is None and latest.get("net_income") is None


def _normalise(row):
    """Give a Yahoo row the same shape and derived fields as a primary-source row."""
    out = {k: row.get(k) for k in FIELD_MAP}
    out["period"] = row["period"]
    out.setdefault("shares_outstanding", None)
    out["_pretax"] = row.get("pretax_income")
    fcf = out.pop("fcf", None)
    compute_derived(out)
    if fcf is not None and out.get("fcf") is None:
        out["fcf"] = round(fcf, 2)
    return out


def _same_currency(financials, currency):
    """Whether statements in `currency` can be mixed with the primary source's rows.
    Unknown counts as the same, so the long-standing behaviour is unchanged."""
    if not currency:
        return True
    unit = str(financials.get("unit_label") or "")
    if currency == "INR":
        return "Cr" in unit or "INR" in unit
    return unit.upper().startswith(currency.upper())


def complete_with_yahoo(financials):
    """Fill gaps in `financials["annual"]` from Yahoo, in place. Returns the dict."""
    market = financials.get("market")
    if market not in ("US", "India"):
        return financials
    data = fetch_yahoo_annual(financials["ticker"], market)
    return apply_statement_rows(financials, data.get("rows") or [], data.get("currency"), "Yahoo Finance")


def apply_statement_rows(financials, yrows, currency, source):
    """Fill gaps in `financials["annual"]` from another source's rows, in place.

    Fills only fields the primary source left empty, matching years by fiscal
    year-end date, so a figure the primary source did report is never replaced.
    Falls back to the other source's statements wholesale when the primary one
    gave nothing usable, and appends fiscal years the primary source is missing.
    Rows in a different currency from the primary source are never mixed in."""
    if not yrows:
        return financials

    existing = financials.get("annual") or []
    notes = []

    if _is_sparse(existing):
        usable = [r for r in yrows if r.get("revenue") is not None or r.get("net_income") is not None]
        financials["annual"] = [_normalise(r) for r in (usable or yrows)]
        notes.append(f"statements from {source} (the primary filing source had no usable annual data)")
        statement_ccy = currency
    elif not _same_currency(financials, currency):
        return financials
    else:
        statement_ccy = None  # the primary source's currency stands
        by_date = [(period_date(r["period"]), r) for r in yrows]
        filled = 0
        for row in existing:
            d = period_date(row.get("period"))
            if d is None:
                continue
            match = next((r for yd, r in by_date if yd and abs((yd - d).days) <= 50), None)
            if not match:
                continue
            for field in _FILL_FIELDS:
                if row.get(field) is None and match.get(field) is not None:
                    value = match[field]
                    row[field] = abs(value) if field in _ABS_FIELDS else value
                    filled += 1
            row["_pretax"] = match.get("pretax_income")
            prior_fcf = row.get("fcf")  # compute_derived would reset it when capex is unknown
            compute_derived(row)
            if row.get("fcf") is None:
                if prior_fcf is not None:
                    row["fcf"] = prior_fcf
                elif match.get("fcf") is not None:
                    row["fcf"] = round(match["fcf"], 2)
        # fiscal years that exist at Yahoo but not in the primary source
        known = [period_date(r.get("period")) for r in existing]
        known = [d for d in known if d]
        newest = max(known) if known else None
        for yd, r in by_date:
            if yd and newest and (yd - newest).days > 200 and r.get("revenue") is not None:
                existing.append(_normalise(r))
                filled += 1
        if filled:
            notes.append(f"{filled} gaps filled from {source} statements")

    # banks and some others report no operating income; pre-tax income is the closest figure
    for row in financials.get("annual") or []:
        pretax = row.pop("_pretax", None)
        if row.get("operating_income") is None and pretax is not None:
            row["operating_income"] = pretax
            row["operating_income_proxy"] = "pre-tax income"
            compute_derived(row)

    if statement_ccy and statement_ccy != "INR" and statement_ccy != str(financials.get("unit_label")):
        # the statements are in a different currency than the price/market cap (an ADR priced
        # in USD reporting in yen), so say so instead of labelling yen as dollars
        us = financials.get("market") == "US"
        financials.setdefault("market_cap_unit", "USD" if us else financials.get("unit_label"))
        financials.setdefault("price_currency", "USD" if us else financials.get("currency"))
        financials["unit_label"] = statement_ccy
        financials["currency"] = statement_ccy
    if notes:
        financials.setdefault("data_sources", []).extend(notes)
    return financials
