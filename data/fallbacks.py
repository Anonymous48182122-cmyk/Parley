"""
Yahoo-independent gap fillers.

Yahoo Finance answers cloud/datacenter IPs (where the live backend runs) with
empty data, so everything that depended on it vanished in production: price,
market cap, sector, ratios, price action, and the statements of companies whose
SEC filings are patchy. These helpers run after the Yahoo steps and fill only
what is still missing, from Nasdaq's public API (US) and from the statements the
agents already have (every market). Each is best-effort and never raises.
"""

from statistics import mean

from data.nasdaq_data import (fetch_nasdaq_annual, fetch_nasdaq_history, fetch_nasdaq_quarterly,
                              fetch_nasdaq_quote, fetch_nasdaq_universe)
from data.technicals import compute_technicals
from data.yahoo_fundamentals import apply_statement_rows


def _note(financials, text):
    notes = financials.setdefault("data_sources", [])
    if text not in notes:
        notes.append(text)


def _note_exchange_rate(financials, usd_rows):
    """A company that reports in yen or euros but trades in dollars: Nasdaq publishes the
    same years converted to USD, so the ratio of the two revenues is the rate in use.
    Handing agents that number lets them compare the dollar share price with local-currency
    statements instead of saying a conversion is not provided."""
    from data.yahoo_fundamentals import period_date
    try:
        native = financials["annual"][-1]
        d = period_date(native.get("period"))
        match = next((r for r in usd_rows if d and period_date(r["period"]) and
                      abs((period_date(r["period"]) - d).days) <= 50), None)
        if match and native.get("revenue") and match.get("revenue"):
            rate = native["revenue"] / match["revenue"]
            code = financials.get("unit_label")
            _note(financials, f"exchange rate implied by the filings: 1 USD = {rate:,.2f} {code} "
                              f"(use it to compare the USD share price and market cap with the {code} statements)")
    except Exception:
        pass


def complete_with_nasdaq(financials):
    """US only: fill statement gaps (or replace empty statements) from Nasdaq."""
    if financials.get("market") != "US":
        return financials
    try:
        data = fetch_nasdaq_annual(financials["ticker"])
        if data.get("detail") and not financials.get("balance_detail"):
            financials["balance_detail"] = data["detail"]
        native = str(financials.get("unit_label") or "")
        if native and native != "USD" and financials.get("annual"):
            _note_exchange_rate(financials, data.get("rows") or [])
        return apply_statement_rows(financials, data.get("rows") or [], data.get("currency"), "Nasdaq")
    except Exception:
        return financials


def _beta(stock_series, market_series):
    """Beta of daily returns against the market over the dates both have."""
    m = {d: c for d, c in market_series}
    pairs = [(d, c) for d, c in stock_series if d in m]
    if len(pairs) < 120:
        return None
    sr = [pairs[i][1] / pairs[i - 1][1] - 1 for i in range(1, len(pairs)) if pairs[i - 1][1]]
    mr = [m[pairs[i][0]] / m[pairs[i - 1][0]] - 1 for i in range(1, len(pairs)) if m[pairs[i - 1][0]]]
    n = min(len(sr), len(mr))
    sr, mr = sr[-n:], mr[-n:]
    mm, sm = mean(mr), mean(sr)
    var = sum((x - mm) ** 2 for x in mr)
    if var == 0:
        return None
    return round(sum((x - mm) * (y - sm) for x, y in zip(mr, sr)) / var, 2)


def fill_market_gaps(financials):
    """US only: fill price, market cap, sector, 52-week range, analyst target,
    business description and price action from Nasdaq where Yahoo gave none."""
    if financials.get("market") != "US":
        return financials
    ticker = financials["ticker"]
    try:
        q = fetch_nasdaq_quote(ticker)
        if not q:
            return financials
        ratios = financials.setdefault("ratios", {})
        used = False

        if financials.get("price") is None and q.get("price") is not None:
            financials["price"], used = q["price"], True
        if financials.get("market_cap") is None and q.get("market_cap") is not None:
            financials["market_cap"], used = q["market_cap"], True
        if financials.get("sector") in (None, "N/A") and q.get("sector"):
            financials["sector"], used = q["sector"], True

        def put(key, value):
            if value is not None and ratios.get(key) in (None, ""):
                ratios[key] = value

        if financials.get("sector") in (None, "N/A") or not q.get("industry"):
            # the stock list carries a sector and industry even where the profile has none (BRK-B)
            sym = ticker.upper().replace("-", ".")
            row = next((u for u in fetch_nasdaq_universe() if u["symbol"].upper() == sym), None)
            if row:
                if financials.get("sector") in (None, "N/A") and row.get("sector"):
                    financials["sector"], used = row["sector"], True
                q = {**q, "industry": q.get("industry") or row.get("industry")}

        if financials.get("sector") in (None, "N/A"):
            from data.us.edgar_fetcher import fetch_sic_description
            sic = fetch_sic_description(ticker)
            if sic:
                financials["sector"], used = sic, True

        if q.get("eps_surprises") and not financials.get("eps_surprises"):
            financials["eps_surprises"] = q["eps_surprises"]
        if q.get("eps_estimates") and not financials.get("eps_estimates"):
            financials["eps_estimates"] = q["eps_estimates"]

        put("Industry", q.get("industry"))
        put("52-Week High", q.get("high_52w"))
        put("52-Week Low", q.get("low_52w"))
        put("Analyst Mean Target Price", q.get("target"))
        if q.get("dividend_yield") is not None:
            put("Dividend Yield", f"{q['dividend_yield']}%")
        put("P/E Ratio (Trailing)", q.get("pe"))
        if not financials.get("business_summary") and q.get("description"):
            text = q["description"]
            financials["business_summary"] = text if len(text) <= 650 else text[:650].rstrip() + "..."

        # forward P/E only when the per-share EPS and the ADR price are on the same basis,
        # which shows up as the market cap / net income P/E agreeing with price / EPS
        fwd, price = q.get("forward_eps"), financials.get("price")
        latest = (financials.get("annual") or [{}])[-1]
        mcap, ni, eps = financials.get("market_cap"), latest.get("net_income"), latest.get("eps_diluted")
        if fwd and fwd > 0 and price and financials.get("unit_label") == "USD":
            consistent = bool(mcap and ni and ni > 0 and eps and eps > 0
                              and abs((price / eps) / (mcap / ni) - 1) < 0.2)
            if consistent:
                put("P/E Ratio (Forward)", round(price / fwd, 2))

        if not financials.get("technicals"):
            history = fetch_nasdaq_history(ticker)
            tech = compute_technicals([(d, c) for d, c in history]) if history else {}
            if tech:
                financials["technicals"], used = tech, True
                spy = fetch_nasdaq_history("SPY", "etf")
                beta = _beta(history, spy) if spy else None
                if beta is not None and ratios.get("Beta") in (None, "") and ratios.get("Beta (1Y vs S&P 500)") is None:
                    ratios["Beta (1Y vs S&P 500)"] = beta
                    _note(financials, "Beta is against the S&P 500 (SPY) over about a year of daily returns")
        if used:
            _note(financials, "price, market cap and sector from Nasdaq (Yahoo Finance was unavailable)")
    except Exception:
        pass
    return financials


def _pct(value):
    return f"{round(value * 100, 2)}%"


def _money_text(value):
    for cutoff, suffix in ((1e9, "B"), (1e6, "M")):
        if abs(value) >= cutoff:
            return f"{value / cutoff:,.2f}{suffix}"
    return f"{value:,.0f}"


_MONEY_FIELDS = ("revenue", "gross_profit", "operating_income", "net_income",
                 "total_assets", "total_equity", "total_debt", "cash")


def _consecutive(rows, period_date):
    dates = [period_date(r["period"]) for r in rows]
    return None not in dates and all(60 <= (b - a).days <= 125 for a, b in zip(dates, dates[1:]))


def _four_quarters(financials, period_date):
    """The last four consecutive quarters in US dollars, and where they came from.

    Nasdaq first (already dollars). Many foreign filers have none there, so Yahoo's quarterly
    statements are used, in the company's own currency, and converted at today's exchange rate,
    which is the rate the dollar price and market cap are quoted at."""
    from data.yahoo_fundamentals import fetch_fx_rate, fetch_yahoo_quarterly

    rows = (fetch_nasdaq_quarterly(financials["ticker"]).get("rows") or [])[-4:]
    if len(rows) == 4 and _consecutive(rows, period_date):
        return rows, "Nasdaq"

    data = fetch_yahoo_quarterly(financials["ticker"], financials.get("market"))
    ylist = (data.get("rows") or [])[-4:]
    if len(ylist) < 4 or not _consecutive(ylist, period_date):
        return None, None
    # the filings' own currency is the reliable one: Yahoo's .info, where its financial currency
    # lives, is exactly what the cloud host cannot read
    unit = str(financials.get("unit_label") or "")
    code = unit if (len(unit) == 3 and unit.isalpha()) else (data.get("currency") or "USD")
    fx = fetch_fx_rate(code)
    if not fx:
        return None, None
    usd = []
    for r in ylist:
        out = dict(r)
        for key in _MONEY_FIELDS:
            if out.get(key) is not None:
                out[key] = out[key] / fx
        usd.append(out)
    return usd, f"Yahoo quarterly statements converted from {code} at {fx:,.2f} per USD"


def _quarterly_ratios(financials, put):
    """US: the ratios as they are quoted, on trailing-twelve-month earnings and the latest
    quarter's balance sheet, from Nasdaq's quarterly statements. (The annual figures lag by
    up to a year: Eli Lilly's fiscal-year debt/equity read 160 while the latest quarter is 162,
    and its P/E on last year's earnings read 54 against 42 on the trailing twelve months.)"""
    from data.yahoo_fundamentals import period_date

    rows, source = _four_quarters(financials, period_date)
    if not rows:
        return False

    def total(key):
        vals = [r.get(key) for r in rows]
        return None if any(v is None for v in vals) else sum(vals)

    ni, rev, op, gp = total("net_income"), total("revenue"), total("operating_income"), total("gross_profit")
    if source != "Nasdaq":
        # Yahoo's quarterly figures can be restated by spin-offs and discontinued operations (Sony's
        # four quarters sum to a loss in a year it earned over a trillion yen). When the trailing year
        # contradicts the fiscal year's sign, the quarterly series is not to be trusted.
        recent = [r.get("net_income") for r in (financials.get("annual") or [])[-2:] if r.get("net_income")]
        if ni is not None and any((ni > 0) != (v > 0) for v in recent):
            return False  # either of the last two fiscal years says the opposite (restated years too)
    now = rows[-1]
    eq, assets, debt, cash = now.get("total_equity"), now.get("total_assets"), now.get("total_debt"), now.get("cash")
    mcap, price = financials.get("market_cap"), financials.get("price")
    lender = any(w in str(financials.get("sector") or "").lower() for w in ("financ", "bank", "insur"))

    # return on equity is earnings over the AVERAGE equity of the period (the first and last
    # quarter-end here), which is how it is quoted; the latest equity alone understates it
    # for a company whose equity grew through the year
    first_eq = rows[0].get("total_equity")
    avg_eq = (eq + first_eq) / 2 if (eq and first_eq and first_eq > 0) else eq
    if ni is not None and avg_eq and avg_eq > 0:
        put("Return on Equity", f"{round(ni / avg_eq * 100, 2)}%")
    if ni is not None and assets:
        put("Return on Assets", f"{round(ni / assets * 100, 2)}%")
    if ni is not None and rev:
        put("Net Profit Margin", f"{round(ni / rev * 100, 2)}%")
    if gp is not None and rev and not lender:
        put("Gross Margin", f"{round(gp / rev * 100, 2)}%")
    if op is not None and rev:
        put("Operating Margin", f"{round(op / rev * 100, 2)}%")
    if debt is not None and eq and eq > 0 and not lender:
        put("Debt to Equity", round(debt / eq * 100, 2))
    if mcap and ni and ni > 0:
        put("P/E Ratio (Trailing)", round(mcap / ni, 2))
    if mcap and eq and eq > 0:
        put("Price to Book", round(mcap / eq, 2))
        if price:
            put("Book Value per Share", round(eq / (mcap / price), 2))
    if cash is not None:
        put("Cash & Equivalents (latest quarter)", _money_text(cash))
    if debt is not None:
        put("Total Debt (latest quarter)", _money_text(debt))

    # a trailing-twelve-month block for the agents, when the statements are in dollars too
    if str(financials.get("unit_label")) == "USD" and not financials.get("ttm") and rev:
        shares = (mcap / price) if (mcap and price) else None
        financials["ttm"] = {
            "revenue": rev, "operating_income": op, "net_income": ni,
            "operating_margin": round(op / rev * 100, 1) if op is not None else None,
            "net_margin": round(ni / rev * 100, 1) if ni is not None else None,
            "eps_diluted": round(ni / shares, 2) if (ni is not None and shares) else None,
        }
    _note(financials, f"P/E, ROE and margins use trailing-twelve-month earnings and debt, equity and cash use the "
                      f"balance sheet at {rows[-1]['period']} (latest quarter), from {source}")
    return True


def derive_ratios(financials):
    """Fill ratio gaps from the statements the agents already have. Uses the last
    fiscal year, so P/E and yield describe that year and not the trailing twelve months."""
    try:
        annual = financials.get("annual") or []
        if not annual:
            return financials
        last = annual[-1]
        ratios = financials.setdefault("ratios", {})
        derived = []

        # Screener names some of these differently; never shadow what it already gave
        aliases = {"Return on Equity": ("ROE",), "P/E Ratio (Trailing)": ("P/E Ratio",)}

        def put(key, value):
            taken = any(ratios.get(k) not in (None, "") for k in (key, *aliases.get(key, ())))
            if value is not None and not taken:
                ratios[key] = value
                derived.append(key)

        if financials.get("market") == "US" and financials.get("market_cap"):
            try:
                _quarterly_ratios(financials, put)
            except Exception:
                pass

        ni, eq, rev = last.get("net_income"), last.get("total_equity"), last.get("revenue")
        assets, debt = last.get("total_assets"), last.get("total_debt")

        if ni is not None and eq and eq > 0:
            put("Return on Equity", _pct(ni / eq))
        if ni is not None and assets:
            put("Return on Assets", _pct(ni / assets))
        # gross margin and debt/equity say nothing useful about a bank or insurer
        lender = any(w in str(financials.get("sector") or "").lower() for w in ("financ", "bank", "insur"))
        if ni is not None and rev:
            put("Net Profit Margin", _pct(ni / rev))
        if not lender and last.get("gross_profit") is not None and rev:
            put("Gross Margin", _pct(last["gross_profit"] / rev))
        if last.get("operating_income") is not None and rev and not last.get("operating_income_proxy"):
            put("Operating Margin", _pct(last["operating_income"] / rev))
        if not lender and debt is not None and eq and eq > 0:
            put("Debt to Equity", round(debt / eq * 100, 2))  # percent, the way Yahoo reports it

        # price-based ratios need price and statements in the same currency
        mcap = financials.get("market_cap")
        unit = str(financials.get("unit_label") or "")
        same_ccy = (financials.get("market") == "US" and unit == "USD") or \
                   (financials.get("market") == "India" and "Cr" in unit)
        if mcap and same_ccy:
            if ni and ni > 0:
                put("P/E Ratio (Trailing)", round(mcap / ni, 2))
            div = last.get("dividends")
            if div and div > 0:
                put("Dividend Yield", f"{round(div / mcap * 100, 2)}%")
            if eq and eq > 0:
                put("Price to Book", round(mcap / eq, 2))
                if financials.get("price"):
                    put("Book Value per Share", round(eq / (mcap / financials["price"]), 2))
            nq = fetch_nasdaq_quote(financials["ticker"]) if financials.get("market") == "US" else {}
            if nq.get("annual_dividend") and financials.get("price") and last.get("dividends") is None:
                last["dividends"] = round(nq["annual_dividend"] * mcap / financials["price"], 2)
                _note(financials, "dividends paid estimated as annual dividend per share x current share count")

        elif mcap and financials.get("market") == "US":
            # an ADR reporting in yen or euros: Nasdaq's dollar-converted statements make P/E possible
            usd = (fetch_nasdaq_annual(financials["ticker"]).get("rows") or [{}])[-1].get("net_income")
            if usd and usd > 0:
                put("P/E Ratio (Trailing)", round(mcap / usd, 2))

        price = financials.get("price")
        if last.get("eps_diluted") is None and ni and mcap and price and same_ccy and financials.get("market") == "US":
            # no reported EPS in the filing data: net income over today's share count
            # (market cap / price), good enough to size earnings per share
            last["eps_diluted"] = round(ni / (mcap / price), 2)
            last["eps_proxy"] = True
            _note(financials, "latest EPS estimated as net income / current shares (market cap / price)")

        if derived:
            _note(financials, "some ratios (" + ", ".join(derived[:6]) + ") computed from the last fiscal year's statements")
    except Exception:
        pass
    return financials
