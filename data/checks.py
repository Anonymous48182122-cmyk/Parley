"""
Framework checks: the standard tests that each investing method asks for, computed here from the
statements so every agent works from the same correct numbers instead of doing sums in its head.

Graham's number, Piotroski style quality score, accruals, share count change, shareholder yield,
margin trends, the Rule of 40 and a growth profile for Lynch's categories. All of it comes from the
annual rows already in the data block; a test that needs a figure we do not have is simply left out,
and nothing here is ever guessed except the one labelled bond yield.
"""

from math import sqrt

_FINANCIAL_WORDS = ("financial", "bank", "insurance", "credit services", "capital markets",
                    "asset management", "mortgage", "nbfc", "lending")

# A rough long bond yield to set an earnings yield against; not from the data, and said so in the text.
_BOND_YIELD = {"US": 4.3, "India": 6.8}


def _n(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _cagr(first, last, years):
    if first is None or last is None or first <= 0 or last <= 0 or years < 1:
        return None
    return 100 * ((last / first) ** (1 / years) - 1)


def _pct(x, digits=1):
    return f"{x:.{digits}f}%"


def _window(annual, key, positive=False):
    """(first value, last value, years apart) over the longest span of up to five years with both ends known."""
    rows = annual[-6:]
    for i in range(len(rows)):
        for j in range(len(rows) - 1, i, -1):
            a, b = _n(rows[i].get(key)), _n(rows[j].get(key))
            if a is not None and b is not None and (not positive or (a > 0 and b > 0)):
                return a, b, j - i
    return None


def _piotroski(rows):
    """Tests passed out of the tests the data allows, with the ones that failed."""
    if len(rows) < 2:
        return None
    cur, prev = rows[-1], rows[-2]
    tests = []

    def add(name, ok):
        if ok is not None:
            tests.append((name, ok))

    def roa(r):
        ni, ta = _n(r.get("net_income")), _n(r.get("total_assets"))
        return ni / ta if ni is not None and ta else None

    add("profit was positive", None if roa(cur) is None else roa(cur) > 0)
    cfo = _n(cur.get("operating_cash_flow"))
    add("operating cash flow was positive", None if cfo is None else cfo > 0)
    add("return on assets improved", None if roa(cur) is None or roa(prev) is None else roa(cur) > roa(prev))
    ni = _n(cur.get("net_income"))
    add("cash flow beat profit", None if cfo is None or ni is None else cfo > ni)

    def lev(r):
        d, ta = _n(r.get("total_debt")), _n(r.get("total_assets"))
        return d / ta if d is not None and ta else None

    add("debt fell against assets", None if lev(cur) is None or lev(prev) is None else lev(cur) <= lev(prev))
    sc, sp = _n(cur.get("shares_avg")), _n(prev.get("shares_avg"))
    add("no new shares were issued", None if sc is None or sp is None or sp == 0 else sc <= sp * 1.005)
    mc = _n(cur.get("gross_margin")) if _n(cur.get("gross_margin")) is not None else _n(cur.get("operating_margin"))
    mp = _n(prev.get("gross_margin")) if _n(prev.get("gross_margin")) is not None else _n(prev.get("operating_margin"))
    add("margin improved", None if mc is None or mp is None else mc > mp)

    def turn(r):
        rev, ta = _n(r.get("revenue")), _n(r.get("total_assets"))
        return rev / ta if rev is not None and ta else None

    add("sales per unit of assets improved", None if turn(cur) is None or turn(prev) is None else turn(cur) > turn(prev))
    if len(tests) < 5:
        return None
    passed = sum(1 for _, ok in tests if ok)
    failed = [name for name, ok in tests if not ok]
    return passed, len(tests), failed


def framework_check_lines(data):
    """Lines for the data block, or [] when there is nothing to compute from."""
    annual = [r for r in (data.get("annual") or []) if r]
    if len(annual) < 2:
        return []
    latest, prior = annual[-1], annual[-2]
    market = data.get("market")
    unit = str(data.get("unit_label") or "")
    ratios = data.get("ratios") or {}
    ttm = data.get("ttm") or {}
    kind = f"{data.get('sector') or ''} {ratios.get('Industry') or ''}".lower()
    financial = any(w in kind for w in _FINANCIAL_WORDS)
    out = []

    # --- growth ------------------------------------------------------------------------------
    w = _window(annual, "revenue", positive=True)
    if w:
        g = _cagr(w[0], w[1], w[2])
        if g is not None:
            out.append(f"- Revenue growth over {w[2]} years: {_pct(g)} a year (latest year {_pct(100 * (latest['revenue'] / prior['revenue'] - 1))})"
                       if _n(latest.get("revenue")) and _n(prior.get("revenue")) else
                       f"- Revenue growth over {w[2]} years: {_pct(g)} a year")
    e = _window(annual, "eps_diluted", positive=True)
    eps_growth = _cagr(e[0], e[1], e[2]) if e else None
    if eps_growth is not None:
        out.append(f"- Earnings per share growth over {e[2]} years: {_pct(eps_growth)} a year")
    losses = [r.get("period") for r in annual[-6:-1] if _n(r.get("net_income")) is not None and _n(r.get("net_income")) < 0]
    if losses and (_n(latest.get("net_income")) or 0) > 0:
        out.append(f"- Turnaround marker: net income was negative in an earlier year ({', '.join(str(p) for p in losses[:2])}) and is positive now")
    if eps_growth is not None:
        profile = ("a fast grower (20% or more a year)" if eps_growth >= 20 else
                   "a steady stalwart (about 10 to 20% a year)" if eps_growth >= 10 else
                   "a modest grower (about 5 to 10% a year)" if eps_growth >= 5 else "a slow grower (under 5% a year)")
        out.append(f"- Growth profile by earnings: looks like {profile}")

    # --- margins and returns --------------------------------------------------------------------
    # a bank has no gross margin worth reading, and a year with negative or near zero sales gives margins
    # of hundreds of percent, so only sane margins are compared
    for key, label in (("gross_margin", "Gross margin"), ("operating_margin", "Operating margin")):
        if financial and key == "gross_margin":
            continue
        m = _window(annual, key)
        if m and m[2] >= 2 and all(-100 <= v <= 100 for v in m[:2]):
            delta = m[1] - m[0]
            out.append(f"- {label} over {m[2]} years: {_pct(m[0])} to {_pct(m[1])} "
                       f"({'wider' if delta > 0.5 else 'narrower' if delta < -0.5 else 'about flat'}, {delta:+.1f} points)")
    roics = [_n(r.get("roic_approx")) for r in annual[-5:] if _n(r.get("roic_approx")) is not None]
    if len(roics) >= 3 and not financial:
        out.append(f"- Return on invested capital (approx): latest {_pct(roics[-1])}, average of last {len(roics)} years {_pct(sum(roics) / len(roics))}")

    # --- quality of earnings ----------------------------------------------------------------------
    ni, cfo = _n(latest.get("net_income")), _n(latest.get("operating_cash_flow"))
    ta, rev = _n(latest.get("total_assets")), _n(latest.get("revenue"))
    if not financial and ni and ni > 0 and cfo is not None:
        out.append(f"- Operating cash flow / net income: {cfo / ni:.2f}x"
                   + (" (cash earnings run ahead of accounting profit)" if cfo / ni >= 1.1 else
                      " (profit is not fully backed by cash)" if cfo / ni < 0.8 else ""))
    if not financial and ni is not None and cfo is not None and ta:
        accruals = 100 * (ni - cfo) / ta
        out.append(f"- Accruals (net income minus operating cash flow) as % of assets: {accruals:+.1f}%"
                   + (" (high: earnings leaning on non-cash items)" if accruals > 10 else ""))
    fcf, sbc = _n(latest.get("fcf")), _n(latest.get("sbc"))
    if fcf is not None and rev:
        line = f"- Free cash flow margin: {_pct(100 * fcf / rev)}"
        if sbc:
            line += f"; stock compensation is {_pct(100 * sbc / rev)} of revenue, so free cash flow after it is {_pct(100 * (fcf - sbc) / rev)} of revenue"
        out.append(line)

    # --- balance sheet --------------------------------------------------------------------------------
    debt, cash, op = _n(latest.get("total_debt")), _n(latest.get("cash")), _n(latest.get("operating_income"))
    if not financial and debt is not None and cash is not None:
        net = debt - cash
        if net <= 0:
            out.append("- Cash exceeds debt: the company has net cash, so it owes more to no one than it holds")
        elif op and op > 0:
            out.append(f"- Net debt is {net / op:.1f} years of operating income" + (" (heavy)" if net / op > 4 else ""))
        elif op is not None and op <= 0:
            out.append("- Net debt with no operating profit to service it")

    # --- capital allocation -----------------------------------------------------------------------------
    sh = _window(annual, "shares_avg", positive=True)
    if sh and sh[2] >= 2:
        c = _cagr(sh[0], sh[1], sh[2])
        if c is not None:
            out.append(f"- Share count over {sh[2]} years: {c:+.1f}% a year "
                       + ("(shrinking: buybacks outweigh issuance)" if c < -0.5 else "(growing: shareholders are being diluted)" if c > 0.5 else "(flat)"))
    div, bb = _n(latest.get("dividends")), _n(latest.get("buybacks"))
    cap = _n(data.get("market_cap"))
    same_unit = (data.get("market_cap_unit") or unit) == unit
    if cap and same_unit and (div is not None or bb is not None):
        paid = abs(div or 0) + abs(bb or 0)
        if paid:
            out.append(f"- Shareholder yield (dividends plus buybacks / market cap): {_pct(100 * paid / cap)}")
    if div and ni and ni > 0:
        out.append(f"- Dividend payout: {_pct(100 * abs(div) / ni, 0)} of net income")
    capex = _n(latest.get("capex"))
    if capex and cfo and cfo > 0:
        out.append(f"- Reinvestment: capital spending is {_pct(100 * abs(capex) / cfo, 0)} of operating cash flow")

    # --- valuation tests ----------------------------------------------------------------------------------
    price = _n(data.get("price"))
    comparable = (market == "US" and unit == "USD") or market == "India"
    eps = _n(ttm.get("eps_diluted")) if _n(ttm.get("eps_diluted")) is not None else _n(latest.get("eps_diluted"))
    bvps = _n(ratios.get("Book Value per Share"))
    if bvps is None and _n(latest.get("total_equity")) and _n(latest.get("shares_outstanding")):
        bvps = latest["total_equity"] / latest["shares_outstanding"] if unit == "USD" else None
    if comparable and price and eps and eps > 0 and bvps and bvps > 0:
        graham = sqrt(22.5 * eps * bvps)
        out.append(f"- Graham number (square root of 22.5 x earnings per share x book value per share): {graham:,.1f}; "
                   f"price is {price / graham:.2f}x of it" + (" (below it: inside Graham's limit)" if price < graham else " (above it)"))
    pe = _n(ratios.get("P/E Ratio (Trailing)"))
    if pe and pe > 0 and market in _BOND_YIELD:
        ey = 100 / pe
        out.append(f"- Earnings yield (1 / P/E): {_pct(ey)} against a long government bond yield of roughly "
                   f"{_BOND_YIELD[market]}% (my assumed figure, not from the data)")

    # --- composite scores ------------------------------------------------------------------------------------
    if not financial:
        score = _piotroski(annual)
        if score:
            passed, total, failed = score
            out.append(f"- Quality score (Piotroski style): {passed} of {total} tests passed"
                       + (f"; failed: {', '.join(failed)}" if failed else ""))
    growth = _n(ratios.get("Revenue Growth (YoY, latest quarter)"))
    if growth is None and rev and _n(prior.get("revenue")):
        growth = 100 * (rev / prior["revenue"] - 1)
    if growth is not None and fcf is not None and rev:
        out.append(f"- Rule of 40 (revenue growth plus free cash flow margin): {growth + 100 * fcf / rev:.0f}"
                   + (" (healthy: 40 or more)" if growth + 100 * fcf / rev >= 40 else ""))

    if not out:
        return []
    return ["", "Framework checks (computed from the figures above, so use them instead of doing your own sums):"] + out
