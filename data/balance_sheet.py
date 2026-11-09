"""
The balance sheet, read for the kind of company it belongs to.

A bank's debt is its raw material, a supermarket's negative working capital is a strength, and a utility
carries debt that would sink a software company. So the same ratios cannot judge them all. Each company is
given a sector profile, and each profile lists the metrics that matter for it in order of importance, with
a weight for each (the weights add up to 100) and plain rule of thumb ranges.

The card shows three levels of the same reading:
- Basic: the few metrics that carry about 60% of what matters for this kind of company;
- Advanced: enough more to reach about 75%, with five year trends, what the company owns and owes, and a
  note on how to read this sector;
- Pro: everything the data allows, with the formulas, the year by year table, the red and green flags, and
  a plain list of what the free data does NOT show.

Everything is computed from the statements already fetched, with no model involved, so nothing is invented.
The weights are shared out over the metrics the data actually allows, so "about 60%" always means 60% of
what this company's data lets us read, and what we cannot read is listed rather than hidden.
"""

import re

BASIC_TARGET = 60
ADVANCED_TARGET = 75


def _n(x):
    try:
        v = float(str(x).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None
    return v if v == v else None


# ---------------------------------------------------------------------------------------------
# Which kind of company
# ---------------------------------------------------------------------------------------------

def _has(text, words):
    return any(w in text for w in words)


def classify(financials):
    kind = f"{financials.get('sector') or ''} {(financials.get('ratios') or {}).get('Industry') or ''}".lower()
    if _has(kind, ("bank", "insurance", "credit services", "capital markets", "asset management", "mortgage", "nbfc",
                   "lending", "financial", "finance")):
        return "bank"
    if _has(kind, ("real estate", "realty", "reit")):
        return "real_estate"
    if _has(kind, ("utilit", "telecom", "infrastructure", "power generation", "gas distribution", "pipeline")):
        return "regulated_infra"
    if _has(kind, ("healthcare", "pharma", "biotech", "drug", "hospital", "medical", "diagnostic")):
        return "healthcare"
    if _has(kind, ("auto", "industrial", "basic materials", "materials", "energy", "oil", "gas", "chemical", "metal",
                   "mining", "steel", "engineering", "construction", "machinery", "shipping", "airline", "aerospace",
                   "capital goods", "transport", "cement", "paper")):
        return "industrial"
    if _has(kind, ("technology", "software", "semiconductor", "internet", "it services", "information technology",
                   "communication", "media", "electronic")):
        return "tech"
    if _has(kind, ("consumer", "retail", "food", "beverage", "household", "restaurant", "apparel", "fmcg", "tobacco",
                   "personal products", "packaged")):
        return "consumer"
    return "default"


# metric id -> weight, in no particular order (the order shown comes from the weights)
PROFILES = {
    "bank": {
        "label": "bank or lender",
        "how": "A bank borrows to lend, so its debt is raw material, not a warning. Read how much it has borrowed "
               "against its own money (leverage), how stable its funding is (customer deposits), and whether it earns "
               "a fair return on shareholders' money. Bad loans decide everything, and they are listed below as not in our data.",
        "weights": {"leverage": 24, "deposit_share": 18, "roe": 18, "roa": 12, "pb_vs_roe": 12, "earnings_stability": 8, "borrowings_share": 8},
        "missing": [("Gross and net bad loans", "The share of loans that are not being repaid. It is the first number to check for any lender."),
                    ("Capital adequacy ratio", "How much loss the bank can absorb before depositors are at risk."),
                    ("Net interest margin", "The gap between what it earns on loans and pays on deposits."),
                    ("Low cost deposit share", "How much of its funding is cheap current and savings money.")],
    },
    "tech": {
        "label": "technology company",
        "how": "Technology companies need little physical capital, so the best sign is cash: more cash than debt, profit that "
               "turns into cash, and customers who pay promptly. Watch for goodwill, which piles up when a company buys "
               "its growth, and for generous stock pay that hides the real cost.",
        "weights": {"net_debt_years": 22, "returns_on_capital": 18, "cash_conversion": 16, "goodwill_share": 12, "receivable_days": 12,
                    "current_ratio": 10, "interest_cover": 6, "capex_intensity": 4},
        "missing": [("Deferred revenue", "Customers' prepayments, a sign of locked in demand.")],
    },
    "consumer": {
        "label": "consumer or retail company",
        "how": "Strong consumer businesses are often paid by customers before they pay their suppliers, so a negative working "
               "capital cycle is a strength. Watch how long stock sits unsold, and for leases, which are debt in disguise for shops.",
        "weights": {"cash_cycle": 20, "inventory_days": 16, "net_debt_years": 18, "returns_on_capital": 16, "interest_cover": 10,
                    "payable_days": 8, "cash_conversion": 8, "debt_to_equity": 4},
        "missing": [("Lease obligations", "Rent commitments for shops and warehouses, which work like debt.")],
    },
    "industrial": {
        "label": "industrial or cyclical company",
        "how": "Cyclical companies earn well in good years and badly in bad ones, so judge debt against normal earnings, not "
               "the best year. Check that interest is comfortably covered, that stock and receivables are not swelling, "
               "and that capital spending is not eating all the cash.",
        "weights": {"net_debt_years": 24, "interest_cover": 18, "cash_cycle": 12, "inventory_days": 12, "receivable_days": 10,
                    "capex_intensity": 10, "returns_on_capital": 8, "current_ratio": 6},
        "missing": [("Debt maturity", "When the borrowings fall due, which decides whether a bad year becomes a crisis.")],
    },
    "regulated_infra": {
        "label": "regulated utility, telecom or infrastructure company",
        "how": "These businesses hold a lot of debt on purpose, because their income is steady and regulated, so debt alone "
               "is not a warning. What matters is whether earnings cover the interest comfortably and how long the "
               "borrowings take to repay.",
        "weights": {"net_debt_years": 26, "interest_cover": 24, "debt_to_equity": 16, "capex_intensity": 14, "returns_on_capital": 10,
                    "current_ratio": 6, "cash_conversion": 4},
        "missing": [("Debt maturity", "When the borrowings fall due and at what rates."),
                    ("Regulated asset base", "The value regulators let the company earn a return on.")],
    },
    "real_estate": {
        "label": "real estate company",
        "how": "Property companies live on borrowed money and unsold stock. Read debt against equity, whether interest is "
               "covered, and how much of the balance sheet is stock that has not sold.",
        "weights": {"debt_to_equity": 24, "net_debt_years": 20, "interest_cover": 20, "inventory_days": 16, "current_ratio": 10, "returns_on_capital": 10},
        "missing": [("Customer advances", "Money buyers paid before delivery, which funds the projects."),
                    ("Unsold inventory value", "The value of finished property that has not sold.")],
    },
    "healthcare": {
        "label": "healthcare company",
        "how": "Pharma and healthcare companies should hold cash, turn profit into cash, and not have bought most of their "
               "growth (goodwill). Check how long they wait for payment and how much stock they carry.",
        "weights": {"net_debt_years": 20, "goodwill_share": 16, "cash_conversion": 14, "receivable_days": 14, "inventory_days": 12,
                    "returns_on_capital": 12, "current_ratio": 12},
        "missing": [("Research pipeline value", "Drugs in development are not on the balance sheet at all.")],
    },
    "default": {
        "label": "company",
        "how": "Start with whether it can repay what it owes (debt against earnings and interest cover), then whether it earns a "
               "good return on the money tied up in it and whether profit turns into cash.",
        "weights": {"net_debt_years": 24, "interest_cover": 18, "current_ratio": 14, "debt_to_equity": 14, "returns_on_capital": 12,
                    "cash_conversion": 10, "equity_ratio": 8},
        "missing": [("Debt maturity", "When the borrowings fall due.")],
    },
}

# ranges that differ from the common ones, by profile: metric -> (good limit, watch limit)
RANGE_OVERRIDES = {
    "regulated_infra": {"net_debt_years": (4.0, 6.5), "debt_to_equity": (1.5, 3.0), "interest_cover": (3.0, 2.0),
                        "returns_on_capital": (8.0, 5.0)},
    "tech": {"receivable_days": (75.0, 100.0)},
    "real_estate": {"net_debt_years": (4.0, 7.0), "debt_to_equity": (0.8, 1.5)},
    "industrial": {"net_debt_years": (2.0, 4.0)},
    "bank": {"leverage": (10.0, 14.0)},
}


# ---------------------------------------------------------------------------------------------
# Plain helpers
# ---------------------------------------------------------------------------------------------

def _money(v, unit):
    if v is None:
        return "not known"
    unit = str(unit or "")
    sign = "-" if v < 0 else ""
    v = abs(v)
    if "Cr" in unit:
        return f"{sign}₹{v:,.0f} Cr"
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹", "CNY": "CN¥", "HKD": "HK$", "CHF": "CHF ",
           "KRW": "₩", "CAD": "C$", "AUD": "A$"}.get(unit[:3].upper(), unit[:3].upper() + " ")
    for cut, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if v >= cut:
            return f"{sign}{sym}{v / cut:,.2f}{suffix}"
    return f"{sign}{sym}{v:,.0f}"


def _band(value, good, watch, higher_is_better=True):
    """'good', 'watch' or 'bad' for a value against two limits."""
    if value is None:
        return "unknown"
    if higher_is_better:
        return "good" if value >= good else "watch" if value >= watch else "bad"
    return "good" if value <= good else "watch" if value <= watch else "bad"


class _Ctx:
    def __init__(self, f):
        self.f = f
        self.annual = [r for r in (f.get("annual") or []) if r]
        self.latest = self.annual[-1] if self.annual else {}
        self.ratios = f.get("ratios") or {}
        self.unit = str(f.get("unit_label") or "")
        self.market = f.get("market")
        detail = (f.get("balance_detail") or {}).get("balance_sheet") or {}
        self.detail = {str(k).lower(): _n(v) for k, v in detail.items()} if isinstance(detail, dict) else {}
        self.profile = classify(f)
        self.ranges = RANGE_OVERRIDES.get(self.profile, {})

    def d(self, *needles):
        for needle in needles:
            for key, value in self.detail.items():
                if needle in key and value is not None:
                    return value
        return None

    def r(self, *keys):
        for k in keys:
            v = _n(self.ratios.get(k))
            if v is not None:
                return v
        return None

    def limits(self, metric, default):
        return self.ranges.get(metric, default)

    def series(self, fn):
        """[{period, value}] of a function of each annual row, skipping years it cannot compute."""
        out = []
        for row in self.annual[-5:]:
            try:
                v = fn(row)
            except Exception:
                v = None
            if v is not None:
                out.append({"period": str(row.get("period")), "value": round(v, 2)})
        return out


def _net_debt(row):
    d, c = _n(row.get("total_debt")), _n(row.get("cash"))
    return None if d is None or c is None else d - c


def _years_of_profit(row):
    nd, op = _net_debt(row), _n(row.get("operating_income"))
    if nd is None or op is None:
        return None
    if nd <= 0:
        return min(nd / abs(op), 0) if op else None  # negative: net cash
    return nd / op if op > 0 else None


# ---------------------------------------------------------------------------------------------
# The metrics. Each returns {"display", "status", "explain", "formula", "trend"} or None.
# ---------------------------------------------------------------------------------------------

def m_net_debt_years(c):
    row = c.latest
    nd, op = _net_debt(row), _n(row.get("operating_income"))
    if nd is None:
        return None
    unit = c.unit
    trend = c.series(lambda r: (lambda x: None if x is None else round(x, 2))(_years_of_profit(r)))
    formula = "(Total debt minus cash) divided by operating income. Below zero means more cash than debt."
    if nd <= 0:
        return {"display": f"Net cash {_money(-nd, unit)}", "status": "good", "trend": trend, "formula": formula,
                "explain": f"It holds {_money(row.get('cash'), unit)} in cash against {_money(row.get('total_debt'), unit)} of debt, "
                           "so it could repay every borrowing today and still have money left."}
    if op is None or op <= 0:
        return {"display": f"Net debt {_money(nd, unit)}, no operating profit", "status": "bad", "trend": trend, "formula": formula,
                "explain": f"It owes {_money(nd, unit)} more than it holds in cash and is not earning an operating profit to pay it down."}
    years = nd / op
    good, watch = c.limits("net_debt_years", (2.0, 4.0))
    return {"display": f"{years:.1f} years of operating profit", "status": _band(years, good, watch, higher_is_better=False),
            "trend": trend, "formula": formula,
            "explain": f"Net debt is {_money(nd, unit)}, which this year's operating profit would repay in about {years:.1f} years. "
                       f"Under {good:g} years is comfortable for this kind of company, over {watch:g} is stretched."}


def m_interest_cover(c):
    op, interest = _n(c.latest.get("operating_income")), _n(c.latest.get("interest_expense"))
    if op is None or not interest or interest <= 0:
        return None
    cover = op / interest
    good, watch = c.limits("interest_cover", (6.0, 3.0))
    trend = c.series(lambda r: (_n(r.get("operating_income")) / _n(r.get("interest_expense")))
                     if _n(r.get("interest_expense")) and _n(r.get("operating_income")) is not None else None)
    return {"display": f"{cover:.1f} times", "status": _band(cover, good, watch), "trend": trend,
            "formula": "Operating income divided by interest paid.",
            "explain": f"Operating profit covers the interest bill {cover:.1f} times. Above {good:g} is comfortable, below {watch:g} "
                       "leaves little room for a bad year." if cover > 0 else "Operating profit does not cover the interest bill."}


def m_current_ratio(c):
    tca, tcl = c.d("total current assets"), c.d("total current liabilities")
    value = tca / tcl if tca and tcl else c.r("Current Ratio")
    if value is None:
        return None
    if c.profile in ("consumer",) and value < 1:
        status = "watch"
    else:
        status = _band(value, 1.5, 1.0)
    return {"display": f"{value:.2f}", "status": status, "trend": None,
            "formula": "Current assets divided by current liabilities.",
            "explain": f"For every 1 it owes within a year it holds {value:.2f} in cash, stock and money owed to it. "
                       "Above 1.5 is comfortable; under 1 is not a problem on its own for a business paid before it pays."}


def m_debt_to_equity(c):
    d, e = _n(c.latest.get("total_debt")), _n(c.latest.get("total_equity"))
    if d is None or not e or e <= 0:
        return None
    value = d / e
    good, watch = c.limits("debt_to_equity", (0.5, 1.5))
    trend = c.series(lambda r: (_n(r.get("total_debt")) / _n(r.get("total_equity")))
                     if _n(r.get("total_debt")) is not None and _n(r.get("total_equity")) and _n(r.get("total_equity")) > 0 else None)
    return {"display": f"{value:.2f} times", "status": _band(value, good, watch, higher_is_better=False), "trend": trend,
            "formula": "Borrowings divided by shareholders' equity.",
            "explain": f"It has borrowed {value:.2f} for every 1 of shareholders' money. Under {good:g} is conservative, over {watch:g} is heavy."}


def m_equity_ratio(c):
    e, a = _n(c.latest.get("total_equity")), _n(c.latest.get("total_assets"))
    if e is None or not a:
        return None
    value = 100 * e / a
    trend = c.series(lambda r: 100 * _n(r.get("total_equity")) / _n(r.get("total_assets"))
                     if _n(r.get("total_equity")) is not None and _n(r.get("total_assets")) else None)
    return {"display": f"{value:.0f}% owned", "status": _band(value, 50, 30), "trend": trend,
            "formula": "Shareholders' equity divided by total assets.",
            "explain": f"Shareholders own {value:.0f}% of everything the company holds; the rest is owed to others."}


def m_receivable_days(c):
    days = c.r("Debtor Days")
    if days is None:
        rec, rev = c.d("receivable"), _n(c.latest.get("revenue"))
        days = 365 * rec / rev if rec is not None and rev else None
    if days is None:
        return None
    good, watch = c.limits("receivable_days", (60.0, 90.0))
    return {"display": f"{days:.0f} days", "status": _band(days, good, watch, higher_is_better=False), "trend": None,
            "formula": "Money owed by customers divided by sales, times 365.",
            "explain": f"Customers take about {days:.0f} days to pay. Under {good:g} is quick for this kind of company; over {watch:g} "
                       "means cash is tied up waiting, and a rising number is an early warning."}


def _cogs(c):
    rev, gp = _n(c.latest.get("revenue")), _n(c.latest.get("gross_profit"))
    return rev - gp if rev is not None and gp is not None else None


def m_inventory_days(c):
    days = c.r("Inventory Days")
    if days is None:
        inv, cogs = c.d("inventory"), _cogs(c)
        days = 365 * inv / cogs if inv is not None and cogs else None
    if days is None:
        return None
    return {"display": f"{days:.0f} days", "status": "unknown" if c.profile != "real_estate" else _band(days, 400, 800, False),
            "trend": None, "formula": "Stock held divided by the cost of goods sold, times 365.",
            "explain": f"Stock sits for about {days:.0f} days before it sells. There is no universal good number: compare it with the "
                       "same company a few years ago, because rising stock days often come before a write down."}


def m_payable_days(c):
    days = c.r("Days Payable")
    if days is None:
        pay, cogs = c.d("accounts payable", "payable"), _cogs(c)
        days = 365 * pay / cogs if pay is not None and cogs else None
        if days is not None and days > 150:
            return None  # the payables line often includes accrued expenses, which overstates what is owed to suppliers
    if days is None:
        return None
    return {"display": f"{days:.0f} days", "status": "unknown", "trend": None,
            "formula": "Money owed to suppliers divided by the cost of goods sold, times 365.",
            "explain": f"It takes about {days:.0f} days to pay suppliers. Paying slowly can mean strong bargaining power, but "
                       "very long days with falling sales can mean it is stretching to stay afloat."}


def m_cash_cycle(c):
    value = c.r("Cash Conversion Cycle", "Working Capital Days")
    if value is None:
        rec, inv, pay, cogs, rev = c.d("receivable"), c.d("inventory"), c.d("accounts payable", "payable"), _cogs(c), _n(c.latest.get("revenue"))
        if None in (rec, inv, pay) or not cogs or not rev:
            return None
        if 365 * pay / cogs > 150:
            return None  # payables that include accrued expenses would make the cycle look far better than it is
        value = 365 * rec / rev + 365 * inv / cogs - 365 * pay / cogs
    status = "good" if value <= 30 else "watch" if value <= 90 else "bad"
    return {"display": f"{value:.0f} days", "status": status, "trend": None,
            "formula": "Days of stock plus days customers take to pay, minus days it takes to pay suppliers.",
            "explain": ("Negative means customers and suppliers fund the business: it is paid before it has to pay. A strength."
                        if value < 0 else f"Cash is tied up for about {value:.0f} days between paying for goods and being paid. "
                        "The shorter, the better, and a rising number is a warning.")}


def m_goodwill_share(c):
    intang, a = c.d("intangible", "goodwill"), _n(c.latest.get("total_assets"))
    if intang is None or not a:
        return None
    value = 100 * intang / a
    return {"display": f"{value:.0f}% of assets", "status": _band(value, 15, 35, higher_is_better=False), "trend": None,
            "formula": "Goodwill and intangible assets divided by total assets.",
            "explain": f"{value:.0f}% of what the company owns is goodwill and other intangibles, mostly the price paid for past "
                       "acquisitions. High numbers mean growth was bought, and a write down can erase equity."}


def m_returns_on_capital(c):
    values = [_n(r.get("roic_approx")) for r in c.annual[-5:] if _n(r.get("roic_approx")) is not None]
    if not values:
        return None
    latest = values[-1]
    avg = sum(values) / len(values)
    good, watch = c.limits("returns_on_capital", (15.0, 8.0))
    return {"display": f"{latest:.0f}%, average {avg:.0f}%", "status": _band(latest, good, watch),
            "trend": c.series(lambda r: _n(r.get("roic_approx"))),
            "formula": "Operating profit after tax divided by the capital tied up in the business (approximation).",
            "explain": f"Each 100 of capital earns about {latest:.0f} a year. Above {good:g} shows a real advantage; below {watch:g} "
                       "usually means the business earns less than it costs to fund."}


def m_cash_conversion(c):
    ni, cfo = _n(c.latest.get("net_income")), _n(c.latest.get("operating_cash_flow"))
    if not ni or ni <= 0 or cfo is None:
        return None
    value = cfo / ni
    return {"display": f"{value:.2f} times profit", "status": _band(value, 1.0, 0.7),
            "trend": c.series(lambda r: _n(r.get("operating_cash_flow")) / _n(r.get("net_income"))
                              if _n(r.get("net_income")) and _n(r.get("net_income")) > 0 and _n(r.get("operating_cash_flow")) is not None else None),
            "formula": "Cash from operations divided by net income.",
            "explain": f"Every 1 of reported profit brought in {value:.2f} of cash. Around or above 1 means profit is real; "
                       "well below 1 means it is sitting in receivables or stock."}


def m_capex_intensity(c):
    capex, cfo = _n(c.latest.get("capex")), _n(c.latest.get("operating_cash_flow"))
    if not capex or not cfo or cfo <= 0:
        return None
    value = 100 * abs(capex) / cfo
    return {"display": f"{value:.0f}% of operating cash", "status": _band(value, 50, 85, higher_is_better=False),
            "trend": c.series(lambda r: 100 * abs(_n(r.get("capex"))) / _n(r.get("operating_cash_flow"))
                              if _n(r.get("capex")) and _n(r.get("operating_cash_flow")) and _n(r.get("operating_cash_flow")) > 0 else None),
            "formula": "Capital spending divided by cash from operations.",
            "explain": f"{value:.0f}% of the cash the business makes goes back into plant and equipment. Above 85% leaves "
                       "little for debt repayment, dividends or growth."}


# --- lenders ---------------------------------------------------------------------------------

def m_leverage(c):
    a, e = _n(c.latest.get("total_assets")), _n(c.latest.get("total_equity"))
    if not a or not e or e <= 0:
        return None
    value = a / e
    good, watch = c.limits("leverage", (10.0, 14.0))
    return {"display": f"{value:.1f} times", "status": _band(value, good, watch, higher_is_better=False),
            "trend": c.series(lambda r: _n(r.get("total_assets")) / _n(r.get("total_equity"))
                              if _n(r.get("total_assets")) and _n(r.get("total_equity")) and _n(r.get("total_equity")) > 0 else None),
            "formula": "Total assets divided by shareholders' equity.",
            "explain": f"The bank holds {value:.1f} of assets for every 1 of its own money. Banks run at 8 to 12 times; "
                       f"above {watch:g} means a small loss on its loans can wipe out the equity."}


def m_deposit_share(c):
    deposits, a = c.d("deposit"), _n(c.latest.get("total_assets"))
    if deposits is None or not a:
        return None
    value = 100 * deposits / a
    return {"display": f"{value:.0f}% of assets", "status": _band(value, 60, 40), "trend": None,
            "formula": "Customer deposits divided by total assets.",
            "explain": f"Customers' deposits fund {value:.0f}% of the balance sheet. Deposits are the stable, cheap funding; "
                       "a bank that leans on market borrowing instead is more exposed when credit tightens."}


def m_borrowings_share(c):
    b, a = c.d("borrowing"), _n(c.latest.get("total_assets"))
    if b is None or not a:
        return None
    value = 100 * b / a
    return {"display": f"{value:.0f}% of assets", "status": _band(value, 15, 30, higher_is_better=False), "trend": None,
            "formula": "Borrowings from markets and other lenders divided by total assets.",
            "explain": f"{value:.0f}% of the balance sheet is funded by borrowing rather than deposits. It costs more and can "
                       "dry up in a crisis, so lower is safer."}


def m_roe(c):
    ni, e = _n(c.latest.get("net_income")), _n(c.latest.get("total_equity"))
    if ni is None or not e or e <= 0:
        return None
    value = 100 * ni / e
    return {"display": f"{value:.1f}%", "status": _band(value, 12, 8),
            "trend": c.series(lambda r: 100 * _n(r.get("net_income")) / _n(r.get("total_equity"))
                              if _n(r.get("net_income")) is not None and _n(r.get("total_equity")) and _n(r.get("total_equity")) > 0 else None),
            "formula": "Net income divided by shareholders' equity.",
            "explain": f"Shareholders' money earned {value:.1f}% this year. A lender earning below about 10% is not paying for "
                       "the risk it takes."}


def m_roa(c):
    ni, a = _n(c.latest.get("net_income")), _n(c.latest.get("total_assets"))
    if ni is None or not a:
        return None
    value = 100 * ni / a
    return {"display": f"{value:.2f}%", "status": _band(value, 1.0, 0.6),
            "trend": c.series(lambda r: 100 * _n(r.get("net_income")) / _n(r.get("total_assets"))
                              if _n(r.get("net_income")) is not None and _n(r.get("total_assets")) else None),
            "formula": "Net income divided by total assets.",
            "explain": f"Each 100 of assets earned {value:.2f}. A healthy lender earns about 1 or more; much lower means thin margins or credit costs."}


def m_pb_vs_roe(c):
    pb, roe = c.r("Price to Book"), None
    ni, e = _n(c.latest.get("net_income")), _n(c.latest.get("total_equity"))
    if ni is not None and e and e > 0:
        roe = 100 * ni / e
    if pb is None or roe is None:
        return None
    fair = roe / 12.0  # at a 12% required return, a lender earning its ROE all year is worth ROE/12 times book
    status = "good" if pb <= fair * 0.9 else "watch" if pb <= fair * 1.25 else "bad"
    return {"display": f"{pb:.1f}x book for {roe:.0f}% return", "status": "unknown", "trend": None,
            "formula": "Price to book compared with return on equity divided by a 12% required return (a rough yardstick).",
            "explain": f"The market pays {pb:.1f} times book value. A lender earning {roe:.0f}% on its equity is worth roughly "
                       f"{fair:.1f} times book at a 12% required return, so this looks "
                       f"{'cheap' if status == 'good' else 'about fair' if status == 'watch' else 'expensive'} on that yardstick. "
                       "This is a price question, not a safety one, so it does not count towards the verdict."}


def m_earnings_stability(c):
    values = [_n(r.get("net_income")) for r in c.annual[-5:]]
    values = [v for v in values if v is not None]
    if len(values) < 4:
        return None
    ups = sum(1 for a, b in zip(values, values[1:]) if b > a)
    losses = sum(1 for v in values if v < 0)
    status = "bad" if losses else "good" if ups >= len(values) - 2 else "watch"
    return {"display": f"{ups} of {len(values) - 1} years higher", "status": status, "trend": c.series(lambda r: _n(r.get("net_income"))),
            "formula": "How many of the last years' profits were higher than the year before, and whether any were losses.",
            "explain": "Steady, rising profit is the best evidence of careful lending; a lossmaking year is a serious warning."
            if not losses else "At least one year in the last five was a loss, which is a serious warning for a lender."}


METRICS = {
    "net_debt_years": ("Debt against earnings", m_net_debt_years), "interest_cover": ("Interest cover", m_interest_cover),
    "current_ratio": ("Short term cover", m_current_ratio), "debt_to_equity": ("Debt against equity", m_debt_to_equity),
    "equity_ratio": ("Share owned by shareholders", m_equity_ratio), "receivable_days": ("Days to be paid", m_receivable_days),
    "inventory_days": ("Days of stock", m_inventory_days), "payable_days": ("Days to pay suppliers", m_payable_days),
    "cash_cycle": ("Cash cycle", m_cash_cycle), "goodwill_share": ("Goodwill and intangibles", m_goodwill_share),
    "returns_on_capital": ("Return on capital", m_returns_on_capital), "cash_conversion": ("Profit turned into cash", m_cash_conversion),
    "capex_intensity": ("Capital spending", m_capex_intensity), "leverage": ("Leverage", m_leverage),
    "deposit_share": ("Deposit funding", m_deposit_share), "borrowings_share": ("Market borrowing", m_borrowings_share),
    "roe": ("Return on equity", m_roe), "roa": ("Return on assets", m_roa), "pb_vs_roe": ("Price against return", m_pb_vs_roe),
    "earnings_stability": ("Earnings stability", m_earnings_stability),
}


# ---------------------------------------------------------------------------------------------
# What it owns and owes, year by year, and the whole picture
# ---------------------------------------------------------------------------------------------

def _composition(c):
    a = _n(c.latest.get("total_assets"))
    if not a:
        return None
    unit = c.unit
    assets, funding = [], []

    def add(bucket, label, v):
        if v is not None and v > 0:
            bucket.append({"label": label, "value": v, "share": round(100 * v / a, 1)})

    if c.profile == "bank":
        if c.d("deposit") is not None:
            add(funding, "Customer deposits", c.d("deposit"))
            add(funding, "Borrowings", c.d("borrowing"))
        else:
            add(funding, "Long term borrowings", c.d("long-term debt"))
        add(funding, "Shareholders' equity", _n(c.latest.get("total_equity")))
        add(assets, "Investments", c.d("investments"))
        add(assets, "Fixed assets", c.d("fixed assets"))
    else:
        add(assets, "Cash", _n(c.latest.get("cash")))
        add(assets, "Money owed by customers", c.d("receivable"))
        add(assets, "Stock", c.d("inventory"))
        add(assets, "Goodwill and intangibles", c.d("intangible", "goodwill"))
        add(assets, "Investments", c.d("investments"))
        add(assets, "Fixed assets", c.d("fixed assets"))
        add(funding, "Debt", _n(c.latest.get("total_debt")))
        add(funding, "Shareholders' equity", _n(c.latest.get("total_equity")))
        add(funding, "Owed to suppliers", c.d("accounts payable", "payable"))
    for bucket in (assets, funding):
        known = sum(x["value"] for x in bucket)
        if known < a * 0.999:
            if c.profile == "bank":
                rest = ("Loans and other assets" if bucket is assets
                        else "Other liabilities" if c.d("deposit") is not None else "Deposits and other liabilities")
            else:
                rest = "Everything else"
            bucket.append({"label": rest, "value": a - known, "share": round(100 * (a - known) / a, 1)})
        elif known > a * 1.001:  # items that overlap (equity and debt shown with payables) are shown as they are, scaled to fit
            for x in bucket:
                x["share"] = round(100 * x["value"] / known, 1)
    return {"total": a, "assets": assets, "funding": funding, "unit": unit}


def _years_table(c):
    rows = c.annual[-5:]
    if not rows:
        return None
    lines = [("Total assets", "total_assets"), ("Shareholders' equity", "total_equity"), ("Total debt", "total_debt"), ("Cash", "cash"),
             ("Revenue", "revenue"), ("Operating income", "operating_income"), ("Net income", "net_income"),
             ("Cash from operations", "operating_cash_flow"), ("Capital spending", "capex")]
    if c.profile == "bank":
        lines = [x for x in lines if x[1] in ("total_assets", "total_equity", "revenue", "net_income")]
    out = []
    for label, key in lines:
        values = [_n(r.get(key)) for r in rows]
        if any(v is not None for v in values):
            out.append({"label": label, "values": values})
    return {"periods": [str(r.get("period")) for r in rows], "rows": out}


def _detail_lines(c):
    a = _n(c.latest.get("total_assets"))
    out = []
    for key, value in c.detail.items():
        if value is None:
            continue
        out.append({"label": key.title() if key.islower() else key, "value": value,
                    "share": round(100 * value / a, 1) if a else None})
    return out


def _a(label):
    return "an" if label[:1].lower() in "aeiou" else "a"


def _verdict(metrics, label):
    scored = [m for m in metrics if m["status"] in ("good", "watch", "bad")]
    if not scored:
        return {"tone": "unknown", "text": "There is not enough data to read this balance sheet."}
    total = sum(m["weight"] for m in scored)
    good = sum(m["weight"] for m in scored if m["status"] == "good") / total
    bad = sum(m["weight"] for m in scored if m["status"] == "bad") / total
    heavy_bad = [m for m in scored if m["status"] == "bad" and m["weight"] >= 15]
    best = max((m for m in scored if m["status"] == "good"), key=lambda m: m["weight"], default=None)
    worst = max((m for m in scored if m["status"] == "bad"), key=lambda m: m["weight"], default=None)
    if heavy_bad or bad >= 0.3:
        tone, head = "weak", f"A stretched balance sheet for {_a(label)} {label}."
    elif good >= 0.65 and not worst:
        tone, head = "strong", f"A strong balance sheet for {_a(label)} {label}."
    else:
        tone, head = "mixed", f"A mixed balance sheet for {_a(label)} {label}."
    parts = [head]
    if best:
        parts.append(f"Strongest: {best['label'].lower()} ({best['display']}).")
    if worst:
        parts.append(f"Weakest: {worst['label'].lower()} ({worst['display']}).")
    return {"tone": tone, "text": " ".join(parts)}


def build(financials):
    """The whole balance sheet reading for a company, or None when there is nothing to read."""
    try:
        c = _Ctx(financials)
        if not c.annual or not _n(c.latest.get("total_assets")) and not c.detail:
            return None
        profile = PROFILES[c.profile]
        metrics = []
        for metric_id, weight in profile["weights"].items():
            label, fn = METRICS[metric_id]
            try:
                got = fn(c)
            except Exception:
                got = None
            if got:
                metrics.append({"id": metric_id, "label": label, "weight": weight, **got})
        if not metrics:
            return None
        total = sum(m["weight"] for m in metrics)
        for m in metrics:
            m["weight"] = round(100 * m["weight"] / total, 1)
        metrics.sort(key=lambda m: -m["weight"])

        # each level takes metrics, most important first, for as long as that brings the total closer to its target
        # (60% for Basic, 75% for Advanced), so the levels sit near their targets instead of overshooting them
        running, level_of = 0.0, {}
        stage = "basic"
        for i, m in enumerate(metrics):
            target = BASIC_TARGET if stage == "basic" else ADVANCED_TARGET if stage == "advanced" else None
            if stage != "pro" and i >= (3 if stage == "basic" else 0) and abs(running + m["weight"] - target) > abs(running - target):
                stage = "advanced" if stage == "basic" else "pro"
                if stage == "advanced" and abs(running + m["weight"] - ADVANCED_TARGET) > abs(running - ADVANCED_TARGET):
                    stage = "pro"
            level_of[m["id"]] = stage
            running += m["weight"]
        # Advanced must add something to Basic whenever anything is left, or the tab would show the same thing
        if "advanced" not in level_of.values():
            first_pro = next((m for m in metrics if level_of[m["id"]] == "pro"), None)
            if first_pro:
                level_of[first_pro["id"]] = "advanced"
        for m in metrics:
            m["level"] = level_of[m["id"]]
        basic_cov = round(sum(m["weight"] for m in metrics if m["level"] == "basic"))
        adv_cov = round(sum(m["weight"] for m in metrics if m["level"] in ("basic", "advanced")))

        flags = {"red": [m["label"] for m in metrics if m["status"] == "bad"],
                 "green": [m["label"] for m in metrics if m["status"] == "good"]}
        return {
            "profile": c.profile, "label": profile["label"], "how_to_read": profile["how"],
            "verdict": _verdict(metrics, profile["label"]), "metrics": metrics,
            "coverage": {"basic": basic_cov, "advanced": adv_cov, "pro": 100},
            "composition": _composition(c), "years": _years_table(c), "detail": _detail_lines(c),
            "missing": [{"label": a, "why": b} for a, b in profile["missing"]], "flags": flags,
            "unit": c.unit, "period": str(c.latest.get("period")),
        }
    except Exception:
        return None


def agent_lines(reading):
    """A few plain lines for the agents' data block, so they judge the balance sheet by its own sector's tests."""
    if not reading:
        return []
    lines = ["", f"Balance sheet reading (sector profile: {reading['label']}; rules of thumb, computed from the figures above):",
             f"- {reading['verdict']['text']}"]
    for m in reading["metrics"]:
        if m["level"] != "pro" or m["status"] == "bad":
            lines.append(f"- {m['label']}: {m['display']} ({m['status']})")
    if reading["profile"] == "bank":
        lines.append("- For a bank or lender, debt and operating cash flow are not meaningful: judge leverage, funding, returns "
                     "and, where given, bad loans. Bad loans and capital adequacy are not in this data, so say what you cannot see.")
    return lines
