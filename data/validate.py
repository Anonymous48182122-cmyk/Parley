"""
Last line of defence against wrong figures.

Several independent sources (SEC filings, Screener, Yahoo, Nasdaq) are merged into
one data block, and any of them can be stale, in a different unit or currency, or
simply wrong for one company. A wrong number is worse than a missing one: agents
build arguments on it and the user sees it on the stock card. This module runs on the
finished data and

  1. drops values that are impossible (a 300% dividend yield, a gross margin over 100%),
  2. cross-checks the headline ratios against the statements the agents also see and
     replaces a ratio that disagrees badly with the one the statements imply, and
  3. records every change in `data_sources`, so the data notes say what was corrected.

It never raises: a validator that can break an analysis is worse than none.
"""

import math


def _num(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if isinstance(value, bool) or (isinstance(value, float) and math.isnan(value)) else float(value)
    try:
        return float(str(value).replace("%", "").replace(",", "").strip())
    except ValueError:
        return None


# (ratio key, lowest plausible, highest plausible). Outside this a figure is a data
# error, not a bold company.
_BOUNDS = {
    "Dividend Yield": (0, 25),
    "Gross Margin": (-500, 100),
    "Operating Margin": (-5000, 100),
    "Net Profit Margin": (-5000, 100),
    "Beta": (-2, 5),
    "Beta (1Y vs S&P 500)": (-2, 5),
    "P/E Ratio (Trailing)": (0, 3000),
    "P/E Ratio (Forward)": (0, 3000),
    "P/E Ratio": (0, 3000),
    "Return on Equity": (-2000, 2000),
    "Return on Assets": (-500, 100),
    "Debt to Equity": (0, 20000),  # percent; negative means negative equity, which says nothing
    "Price to Book": (0, 1000),
}


def _same_unit(financials):
    """Whether market cap and the statements are in one currency, so they can be divided."""
    unit = str(financials.get("unit_label") or "")
    market = financials.get("market")
    return (market == "US" and unit == "USD") or (market == "India" and "Cr" in unit)


def _earnings_and_equity(financials):
    """Trailing-twelve-month net income when there is one, and the last fiscal year's, plus equity."""
    annual = financials.get("annual") or []
    last = annual[-1] if annual else {}
    ttm = financials.get("ttm") or {}
    return _num(ttm.get("net_income")), _num(last.get("net_income")), _num(last.get("total_equity"))


def validate_financials(financials):
    try:
        _validate(financials)
    except Exception:
        pass
    return financials


def _validate(financials):
    ratios = financials.get("ratios") or {}
    fixes = []

    # 1. impossible values
    for key, (low, high) in _BOUNDS.items():
        value = _num(ratios.get(key))
        if value is not None and not (low <= value <= high):
            fixes.append(f"dropped {key} ({ratios[key]}): outside any plausible range")
            del ratios[key]

    # 2. P/E against the statements
    mcap = _num(financials.get("market_cap"))
    ttm_ni, fy_ni, equity = _earnings_and_equity(financials)
    if mcap and _same_unit(financials):
        key = "P/E Ratio (Trailing)" if "P/E Ratio (Trailing)" in ratios else ("P/E Ratio" if "P/E Ratio" in ratios else None)
        pe = _num(ratios.get(key)) if key else None
        # trailing-twelve-month earnings are a fair check at 50%; last fiscal year's can be a year
        # stale for a fast-growing company (a real P/E may be half of it), so only a 3x gap counts
        if ttm_ni and ttm_ni > 0:
            implied, tolerance = mcap / ttm_ni, 0.5
        elif fy_ni and fy_ni > 0:
            implied, tolerance = mcap / fy_ni, 2.0
        else:
            implied = tolerance = None
        if pe and implied and not (1 / (1 + tolerance) <= implied / pe <= 1 + tolerance):
            best = round(implied, 2)
            fixes.append(f"{key} {pe} disagreed with market cap / earnings ({best}); using {best}")
            ratios[key] = best

    # 3. a ratio built on equity means nothing when equity is zero or negative
    if equity is not None and equity <= 0:
        for key in ("Debt to Equity", "Return on Equity"):
            if key in ratios:
                del ratios[key]
                fixes.append(f"dropped {key}: equity is zero or negative, so the ratio is meaningless")

    # 4. the 52-week range against the daily closes the technicals are built from
    tech = financials.get("technicals") or {}
    for key, tkey in (("52-Week High", "high_52w"), ("52-Week Low", "low_52w")):
        a, b = _num(ratios.get(key)), _num(tech.get(tkey))
        if a and b and abs(a / b - 1) > 0.15:
            del ratios[key]
            fixes.append(f"dropped {key} ({a}): differs from the price history ({b}) by more than 15%")

    # 5. price against market cap order of magnitude (a price in rupees under a dollar label etc.)
    price = _num(financials.get("price"))
    last_close = _num(tech.get("last"))
    if price and last_close and abs(price / last_close - 1) > 0.5:
        fixes.append(f"price {price} disagrees with the last daily close {last_close}; using the close")
        financials["price"] = last_close

    # 6. peers
    for peer in financials.get("peers") or []:
        for field, low, high in (("pe", 0, 1500), ("forward_pe", 0, 1500), ("roe", -1000, 1000),
                                 ("operating_margin", -5000, 100), ("revenue_growth", -100, 10000)):
            value = _num(peer.get(field))
            if value is not None and not (low <= value <= high):
                peer[field] = None

    if fixes:
        notes = financials.setdefault("data_sources", [])
        notes += [f"data check: {f}" for f in fixes if f"data check: {f}" not in notes]
    return financials
