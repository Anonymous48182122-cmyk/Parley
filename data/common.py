"""
Shared normalized schema, disk cache, and agent-facing text formatter used by
both the US (EDGAR) and India (Screener/NSE) fetchers. Every fetcher returns
data in the same shape so agents read one consistent format regardless of
market — see format_for_agents below.
"""

import json
import statistics
from datetime import datetime
import time
from pathlib import Path

from data.groups import group_note
from data.technicals import describe_technicals

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

FINANCIALS_TTL_HOURS = 24


def cached_fetch(cache_key, ttl_hours, fetch_fn):
    """Return fetch_fn()'s JSON-serializable result, cached on disk for ttl_hours."""
    path = CACHE_DIR / f"{cache_key}.json"
    if path.exists():
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours < ttl_hours:
            return json.loads(path.read_text(encoding="utf-8"))
    result = fetch_fn()
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def is_data_sparse(data):
    """True if there's essentially nothing to analyse — no price/market cap and
    no annual row with even the core P&L figures. Typical of a freshly listed
    or freshly demerged entity that hasn't filed a standalone year yet."""
    annual = data.get("annual") or []
    if not annual:
        return True
    latest = annual[-1]
    core_fields = ("revenue", "net_income", "total_assets")
    return all(latest.get(field) is None for field in core_fields)


def _pct(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return round(100 * numerator / denominator, 1)


def compute_derived(row):
    """Add margin/FCF/ROIC-approx fields to one annual row in place, returns it."""
    revenue = row.get("revenue")
    row["gross_margin"] = _pct(row.get("gross_profit"), revenue)
    row["operating_margin"] = _pct(row.get("operating_income"), revenue)
    row["net_margin"] = _pct(row.get("net_income"), revenue)

    ocf, capex = row.get("operating_cash_flow"), row.get("capex")
    row["fcf"] = (ocf - capex) if (ocf is not None and capex is not None) else None

    op_income, debt, equity, cash = (
        row.get("operating_income"),
        row.get("total_debt"),
        row.get("total_equity"),
        row.get("cash"),
    )
    invested_capital = None
    if debt is not None and equity is not None:
        invested_capital = debt + equity - (cash or 0)
    if op_income is not None and invested_capital:
        row["roic_approx"] = round(100 * (op_income * 0.79) / invested_capital, 1)
    else:
        row["roic_approx"] = None
    return row


def _fmt(value, suffix=""):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:,.1f}{suffix}"
    return f"{value:,}{suffix}"


def _compact(value, unit_label):
    """Short human units for the trend table — full-precision raw figures would
    burn prompt tokens on digits no analyst reads."""
    if value is None:
        return "N/A"
    if not str(unit_label).endswith("Cr."):
        for cutoff, suffix in ((1e9, "B"), (1e6, "M")):
            if abs(value) >= cutoff:
                return f"{value / cutoff:,.2f}{suffix}"
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.1f}"


def _year_by_year(annual, unit_label, max_rows=8):
    """A compact period-by-period table so agents can judge consistency,
    inflection points and cyclicality — the latest-year snapshot plus one CAGR
    can't show a business that swung from loss to profit or back."""
    rows = annual[-max_rows:]
    if len(rows) < 3:
        return []
    out = ["", f"Year-by-year (oldest to latest; {unit_label}):",
           "Period | Revenue | Rev YoY | Op margin | Net margin | FCF | Diluted EPS"]
    prev_rev = annual[-max_rows - 1].get("revenue") if len(annual) > max_rows else None
    for row in rows:
        rev = row.get("revenue")
        yoy = None
        # A trailing-twelve-months row (Screener appends one) overlaps the last
        # fiscal year, so "growth" against it would be a misleading comparison.
        if rev is not None and prev_rev and str(row.get("period")).upper() != "TTM":
            yoy = round(100 * (rev - prev_rev) / abs(prev_rev), 1)
        prev_rev = rev
        out.append(
            f"{row.get('period')} | {_compact(rev, unit_label)} | {_fmt(yoy, '%')} | "
            f"{_fmt(row.get('operating_margin'), '%')} | {_fmt(row.get('net_margin'), '%')} | "
            f"{_compact(row.get('fcf'), unit_label)} | {_fmt(row.get('eps_diluted'))}"
        )
    return out


def _format_peers(peers, own_pe, unit_label, own_cap=None, is_group=False):
    """Peer table for the agent prompt, plus the median peer P/E next to the
    company's own — the single number that turns "P/E 40" into "expensive
    versus a peer median of 22". That number only means something when the peers
    really are comparable, so it is withheld for a diversified group (whose peers
    describe one segment) and flagged when the company dwarfs its peers."""
    if not peers:
        return []
    peer_caps = [p["market_cap"] for p in peers if p.get("market_cap")]
    typical = statistics.median(peer_caps) if len(peer_caps) >= 2 else None
    ratio = (own_cap / typical) if (own_cap and typical) else None
    much_larger = ratio is not None and ratio >= 3

    if is_group:
        header = ("Peer comparison (these companies resemble only ONE part of this group; "
                  "they are NOT a fair yardstick for the whole company):")
    elif much_larger:
        header = (f"Peer comparison (same-industry companies, but this company is about {ratio:.0f} "
                  "times larger than the typical peer here, so treat their multiples as a loose reference only):")
    else:
        header = "Peer comparison (same-industry companies of comparable size):"
    lines = ["", header]
    for peer in peers:
        parts = []
        if peer.get("pe") is not None:
            fwd = f" (fwd {peer['forward_pe']})" if peer.get("forward_pe") is not None else ""
            parts.append(f"P/E {peer['pe']}{fwd}")
        cap_unit = "" if unit_label == "USD" else " Cr"
        parts.append(f"mkt cap {_compact(peer.get('market_cap'), unit_label)}{cap_unit}")
        for key, label in (
            ("roce", "ROCE"), ("roe", "ROE"), ("operating_margin", "op margin"),
            ("revenue_growth", "revenue growth"), ("sales_growth", "latest-qtr sales growth"),
            ("profit_growth", "latest-qtr profit growth"), ("dividend_yield", "div yield"),
        ):
            if peer.get(key) is not None:
                parts.append(f"{label} {peer[key]}%")
        lines.append(f"- {peer['name']}: " + ", ".join(parts))
    peer_pes = [p["pe"] for p in peers if p.get("pe") and p["pe"] > 0]
    if is_group:
        lines.append("No single peer median is given: a group is valued by its parts, not by one industry's multiple.")
    elif len(peer_pes) >= 2:
        median = round(statistics.median(peer_pes), 1)
        own = f"{own_pe}" if own_pe is not None else "N/A"
        caveat = " Loose reference only, the peers are much smaller." if much_larger else ""
        lines.append(f"Peer median P/E: {median} (this company: {own}).{caveat}")
    return lines


def _format_segment_comps(comps, own_pe):
    """One current data point per segment of a diversified group, so agents can reason about the
    parts with real figures instead of one misleading peer median."""
    if not comps:
        return []
    lines = ["", "Segment reference points (what the market pays for each kind of business inside this group; "
                 "rough proxies, not like for like):"]
    for c in comps:
        parts = []
        if c.get("pe") is not None:
            parts.append(f"P/E {c['pe']}")
        if c.get("roce") is not None:
            parts.append(f"ROCE {c['roce']}%")
        if c.get("operating_margin") is not None:
            parts.append(f"op margin {c['operating_margin']}%")
        if c.get("market_cap") is not None:
            if c.get("unit") == "USD":
                parts.append(f"mkt cap {_compact(c['market_cap'], 'USD')}")
            else:
                parts.append(f"mkt cap {_compact(c['market_cap'], 'INR Cr.')} Cr")
        lines.append(f"- {c['segment']}: {c['name']}" + (" (" + ", ".join(parts) + ")" if parts else ""))
    lines.append(f"Compare these spreads with this company's own P/E ({own_pe if own_pe is not None else 'N/A'}): "
                 "a blended multiple between the segment multiples is what you would expect.")
    return lines


def _detail_value(value, detail, unit_label):
    """Detail rows with their own currency (Nasdaq's, in full dollars) are shortened to B/M;
    Screener's, already in crores, print as they are."""
    return _compact(value, detail["currency"]) if detail.get("currency") else _fmt(value)


def _capital_allocation(annual, unit_label):
    """What management does with the cash: buybacks, dividends, stock comp, and
    whether the share count is shrinking or being diluted."""
    if not annual:
        return []
    latest = annual[-1]
    parts = []
    for key, label in (("buybacks", "share buybacks"), ("dividends", "dividends paid"), ("sbc", "stock-based compensation")):
        if latest.get(key) is not None:
            parts.append(f"{label} {_fmt(latest[key])}")
    shares = [(r.get("period"), r.get("shares_avg")) for r in annual[-5:] if r.get("shares_avg")]
    if len(shares) >= 2:
        first, last = shares[0][1], shares[-1][1]
        parts.append(
            f"diluted share count {last / 1e6:,.0f}M vs {first / 1e6:,.0f}M at {shares[0][0]} "
            f"({100 * (last - first) / first:+.1f}%, {'buying back / shrinking' if last < first else 'diluting'})"
        )
    return ["", f"Capital allocation (latest fiscal year, {unit_label}):", "- " + "; ".join(parts)] if parts else []


def _pay_amount(value):
    if value is None:
        return "n/a"
    if abs(value) >= 1e9:
        return f"${value / 1e9:,.1f}B"
    return f"${value / 1e6:,.1f}M"


def _pay_lines(pay, net_income=None):
    """What the company pays its chief executive and other top executives, from its SEC proxy
    statement. Total pay counts stock awards at their grant date value, which is why a single
    multi year award can dwarf everything else (Tesla's 2025 award), so that is said every time."""
    years = [y for y in pay.get("years", []) if y.get("ceo_total")]
    if not years:
        return []
    latest = years[0]
    try:
        label = datetime.strptime(latest["period_end"], "%Y-%m-%d").strftime("%b %Y")
    except ValueError:
        label = latest["period_end"]
    earlier = ", ".join(_pay_amount(y["ceo_total"]) for y in years[1:4])
    parts = [f"the chief executive's total pay was {_pay_amount(latest['ceo_total'])} for the year to {label}"
             + (f" (earlier years: {earlier})" if earlier else "")]
    if latest.get("ceo_paid") is not None:
        parts.append(f"pay actually realised, after share price moves, was {_pay_amount(latest['ceo_paid'])}")
    if latest.get("others_avg_total") is not None:
        parts.append(f"the other named executives averaged {_pay_amount(latest['others_avg_total'])}")
    line = f"- Executive pay (SEC proxy statement filed {pay.get('filed')}): " + "; ".join(parts) + "."
    out = [line]
    if net_income and net_income > 0 and latest["ceo_total"] / net_income >= 0.001:
        out.append(f"- That chief executive pay is {latest['ceo_total'] / net_income * 100:.2f}% of the company's latest annual net income.")
    out.append("- Total pay counts stock awards at their value when granted, so it can sit far above what is paid in cash in a year.")
    return out


def _management_lines(gov, net_income=None):
    out = []
    officers = gov.get("officers")
    if officers:
        out.append("- Executive pay: " + "; ".join(
            f"{o.get('name')} ({o.get('title')}) {_compact(o['pay'], 'USD')}" for o in officers))
    if gov.get("exec_pay"):
        out += _pay_lines(gov["exec_pay"], net_income)
    ins = gov.get("insiders_6m")
    if ins:
        def n(v):
            return "n/a" if v is None else f"{v:,.0f}"
        net = ins.get("net_pct")
        out.append(
            f"- Insider trading, last 6 months: {n(ins.get('buy_trans'))} purchases ({n(ins.get('buy_shares'))} shares) "
            f"vs {n(ins.get('sell_trans'))} sales ({n(ins.get('sell_shares'))} shares)"
            + (f"; net {net * 100:+.2f}% of insider holdings" if net is not None else "")
        )
    nq = gov.get("insiders_nasdaq")
    if nq:
        def n(v):
            return "n/a" if v is None else f"{v:,.0f}"
        out.append(
            "- Insider trading (Form 4 filings): last 3 months "
            f"{n(nq['buys']['3m'])} open-market buys ({n(nq['shares_bought']['3m'])} shares) vs "
            f"{n(nq['sells']['3m'])} sales ({n(nq['shares_sold']['3m'])} shares); last 12 months "
            f"{n(nq['buys']['12m'])} buys vs {n(nq['sells']['12m'])} sales ({n(nq['shares_sold']['12m'])} shares sold). "
            "Many sales are scheduled plans, so purchases carry more signal than sales."
        )
        recent = [
            f"{t['who']} ({t['relation']}) {str(t['type']).lower()} {n(t['shares'])} shares on {t['date']}"
            for t in nq.get("recent", [])[:4]
        ]
        if recent:
            out.append("- Latest insider filings: " + "; ".join(recent))
    return ["", "Management and insiders:"] + out if out else []


def _proxy_note(row):
    note = row.get("operating_income_proxy")
    return f" [{note} shown: this company does not report an operating income line]" if note else ""


_FINANCIAL_WORDS = ("financial", "bank", "insurance", "credit services", "capital markets",
                    "asset management", "mortgage", "nbfc", "lending")


def _derived_metrics(data, latest, ttm, cap_unit, unit_label):
    """Valuation figures computed here from numbers already in the block, so a
    missing ready-made ratio is never a reason an agent can't value the company.
    Skipped when market cap and the statements are in different currencies."""
    out = []
    kind = f"{data.get('sector') or ''} {(data.get('ratios') or {}).get('Industry') or ''}".lower()
    interest, op = latest.get("interest_expense"), latest.get("operating_income")
    if interest and interest > 0 and op is not None and not any(w in kind for w in _FINANCIAL_WORDS):
        out.append(f"- Interest coverage (operating income / interest expense): {op / interest:.1f}x"
                   + (" (operating loss: interest is not covered by operations)" if op < 0 else ""))
    market_cap = data.get("market_cap")
    if not market_cap or cap_unit != unit_label:
        return (["", "Derived valuation metrics (computed from the figures above):"] + out) if out else []
    revenue = (ttm or {}).get("revenue") or latest.get("revenue")
    if revenue and revenue > 0:
        out.append(f"- Price/Sales: {market_cap / revenue:.2f}" + (" (TTM revenue)" if (ttm or {}).get("revenue") else ""))
    equity = latest.get("total_equity")
    if equity and equity > 0:
        out.append(f"- Price/Book: {market_cap / equity:.2f}")
    fcf = latest.get("fcf")
    if fcf is not None:
        out.append(f"- Free cash flow yield: {100 * fcf / market_cap:.1f}% (latest fiscal year FCF / market cap)")
    debt, cash = latest.get("total_debt"), latest.get("cash")
    if debt is not None and cash is not None:
        out.append(f"- Net debt (debt minus cash): {_fmt(round(debt - cash, 1))} {unit_label}")
    return ["", "Derived valuation metrics (computed from the figures above):"] + out if out else []


def _data_notes(data, latest, ttm, ratios, cap_unit, unit_label):
    """Plain statements of what is not available and what to use instead. The
    point is that an agent should work around a gap, not decline to opine."""
    notes = []
    kind = f"{data.get('sector') or ''} {ratios.get('Industry') or ''}".lower()
    is_financial = any(word in kind for word in _FINANCIAL_WORDS)
    if is_financial:
        notes.append(
            "This is a financial company. Operating margin, free cash flow, capex and debt-to-equity "
            "do not mean what they do for an industrial business (deposits, float or borrowing ARE its "
            "raw material). Judge it on return on equity, book value and price-to-book, earnings "
            "growth and consistency, and balance sheet scale instead. Asset quality (NPAs), "
            "capital adequacy and net interest margin are not in our data; infer them from return on "
            "equity, price-to-book, leverage (assets relative to equity) and earnings consistency, and "
            "say that you are inferring."
        )
    net = (ttm or latest).get("net_income")
    if net is not None and net < 0:
        notes.append(
            "Net income is negative, so P/E is not meaningful. Value it on price/sales, price/book, "
            "cash burn against cash on hand, and the path to profitability."
        )
    if data.get("market") == "India" and not data.get("governance"):
        notes.append(
            "Board composition and executive pay are not in our data for Indian companies. "
            "Use the promoter and institutional holding trend shown below as the governance signal."
        )
    group = group_note(data.get("ticker"))
    if group:
        notes.append(group + " Value it segment by segment, with the segment reference points if they are "
                     "given, and do not judge it against a single peer median.")
    if "Debt to Equity" in ratios:
        notes.append(
            "Debt to equity counts borrowings (short and long term debt) only. Figures that also include "
            "lease liabilities, such as Yahoo's, run higher."
        )
    if latest.get("operating_income_proxy"):
        notes.append("No operating income line is reported by this company; pre-tax income is shown in its place.")
    if unit_label not in ("USD", "INR Cr.") and cap_unit != unit_label:
        notes.append(
            f"Financial statements are reported in {unit_label}, while the share price and market cap are in "
            f"{cap_unit}. Ratios and margins are unit-free and comparable; compare amounts only within "
            "the same currency. Per-share figures such as book value are per US-listed share (ADS), the "
            "unit the dollar price is quoted in; one ADS can be several ordinary shares."
        )
    have = lambda key: latest.get(key) is not None
    yahoo = lambda key: ratios.get(key) not in (None, "")
    missing = []
    for label, ok in (
        ("revenue", have("revenue")),
        ("net income", have("net_income")),
        ("total debt", have("total_debt") or yahoo("Total Debt (latest quarter, Yahoo)") or yahoo("Total Debt (latest quarter)")),
        ("cash", have("cash") or yahoo("Cash & Equivalents (latest quarter, Yahoo)") or yahoo("Cash & Equivalents (latest quarter)")),
        ("operating cash flow", have("operating_cash_flow") or yahoo("Operating Cash Flow (TTM, Yahoo)")),
    ):
        if not ok:
            missing.append(label)
    if not is_financial:
        if not (have("fcf") or yahoo("Free Cash Flow (TTM, Yahoo)")):
            missing.append("free cash flow")
        if not have("capex"):
            missing.append("capex")
    if missing:
        notes.append(
            "Not available from our data sources for this company: " + ", ".join(missing) + ". "
            "That is a gap in our feed, not a fact about the business. Work from the figures that ARE shown, "
            "derive what you need (for example free cash flow = operating cash flow minus capex; "
            "net debt = debt minus cash), say plainly where you are assuming, and still give your view."
        )
    # where figures came from or were estimated (exchange rate, computed ratios, derived EPS)
    notes += [n for n in data.get("data_sources") or [] if n not in notes and "gaps filled" not in n]
    return ["", "DATA NOTES:"] + [f"- {n}" for n in notes] if notes else []


def format_for_agents(data):
    """Render the normalized schema into the text block every agent prompt reads."""
    annual = data.get("annual", [])
    latest = annual[-1] if annual else {}
    prior = annual[-2] if len(annual) > 1 else {}
    currency = data.get("currency", "")
    unit_label = data.get("unit_label", currency)
    cap_unit = data.get("market_cap_unit", unit_label)  # market cap can be USD while statements are TWD, DKK...
    price_ccy = data.get("price_currency", currency)

    # SEC's total-debt tag is missing for some filers (e.g. Plug Power), which
    # rendered as "N/A" right next to a debt-to-equity ratio of 176% — and an
    # agent read the N/A as "no debt". When debt isn't directly reported but a
    # debt-to-equity ratio and equity are, derive the figure and say so.
    total_debt_text = _fmt(latest.get("total_debt"))
    if latest.get("total_debt") is None:
        de = (data.get("ratios") or {}).get("Debt to Equity")
        equity = latest.get("total_equity")
        if isinstance(de, (int, float)) and equity:
            total_debt_text = (
                f"~{_fmt(round(equity * de / 100))} (derived from debt-to-equity "
                f"{de}% x total equity; not directly reported)"
            )

    lines = [
        f"Company: {data.get('name', data['ticker'])} ({data['ticker']}), "
        f"{data.get('market', '')} listed, {data.get('sector', 'Sector N/A')}",
        f"Market cap: {_fmt(data.get('market_cap'))} {cap_unit} | "
        f"Share price: {_fmt(data.get('price'))} {price_ccy}",
        "",
        f"Income statement (period ending {latest.get('period', 'N/A')}, {unit_label}):",
        f"- Revenue: {_fmt(latest.get('revenue'))} "
        f"(prior period {_fmt(prior.get('revenue'))})",
        f"- Gross profit: {_fmt(latest.get('gross_profit'))} "
        f"(gross margin {_fmt(latest.get('gross_margin'), '%')})",
        f"- Operating income: {_fmt(latest.get('operating_income'))} "
        f"(operating margin {_fmt(latest.get('operating_margin'), '%')}){_proxy_note(latest)}",
        f"- Net income: {_fmt(latest.get('net_income'))} "
        f"(net margin {_fmt(latest.get('net_margin'), '%')})",
        f"- R&D spend: {_fmt(latest.get('rnd'))}",
        f"- EPS (diluted): {_fmt(latest.get('eps_diluted'))} "
        f"(prior period {_fmt(prior.get('eps_diluted'))})",
        "",
        "Balance sheet:",
        f"- Total assets: {_fmt(latest.get('total_assets'))}",
        f"- Total equity: {_fmt(latest.get('total_equity'))}",
        f"- Total debt: {total_debt_text}",
        f"- Cash & equivalents: {_fmt(latest.get('cash'))}",
        "",
        "Cash flow:",
        f"- Operating cash flow: {_fmt(latest.get('operating_cash_flow'))}",
        f"- Capex: {_fmt(latest.get('capex'))}",
        f"- Free cash flow: {_fmt(latest.get('fcf'))}",
        f"- Dividends paid: {_fmt(latest.get('dividends'))}",
        f"- Approx. ROIC: {_fmt(latest.get('roic_approx'), '%')}",
        "(N/A means the figure was not available from the data source. It never means zero.)",
    ]

    # Optional lines that are simply empty add noise, not information: a block
    # full of N/A made agents comment on "a feed riddled with N/A" even when the
    # missing item (R&D at a bank, gross profit where none is reported) was
    # never applicable. Core lines stay visible so a real gap is still explicit.
    droppable = ["- R&D spend: N/A", "- Gross profit: N/A", "- Dividends paid: N/A", "- Approx. ROIC: N/A"]
    kind_text = f"{data.get('sector') or ''} {(data.get('ratios') or {}).get('Industry') or ''}".lower()
    if any(word in kind_text for word in _FINANCIAL_WORDS):
        droppable += ["- Capex: N/A", "- Free cash flow: N/A"]
    lines = [line for line in lines if not line.startswith(tuple(droppable))]

    if data.get("business_summary"):
        lines[2:2] = ["", "Business: " + data["business_summary"]]

    ttm = data.get("ttm")
    if ttm:
        lines += [
            "",
            f"Trailing twelve months (TTM, income statement only, {unit_label}):",
            f"- Revenue {_fmt(ttm.get('revenue'))}, operating income {_fmt(ttm.get('operating_income'))} "
            f"(margin {_fmt(ttm.get('operating_margin'), '%')}), net income {_fmt(ttm.get('net_income'))} "
            f"(margin {_fmt(ttm.get('net_margin'), '%')}), EPS {_fmt(ttm.get('eps_diluted'))}",
        ]

    detail = data.get("balance_detail") or {}
    if detail.get("balance_sheet"):
        lines += [
            "",
            f"Balance sheet detail ({detail.get('period')}, {detail.get('currency') or unit_label}):",
            "- " + "; ".join(f"{k} {_detail_value(v, detail, unit_label)}" for k, v in detail["balance_sheet"].items()),
        ]
    if detail.get("cash_flow"):
        lines += [
            "",
            f"Cash flow detail (same period, {detail.get('currency') or unit_label}; CFO/OP is the percent of operating profit that became cash):",
            "- " + "; ".join(f"{k} {_detail_value(v, detail, unit_label)}" for k, v in detail["cash_flow"].items()),
        ]

    if len(annual) > 1:
        # Use the first and last years that actually HAVE revenue: a half-empty
        # oldest year (Yahoo's fifth column) used to make this print N/A.
        with_rev = [(i, r) for i, r in enumerate(annual) if r.get("revenue")]
        first = with_rev[0][1] if with_rev else annual[0]
        years = (with_rev[-1][0] - with_rev[0][0]) if len(with_rev) >= 2 else 0
        rev_first = first.get("revenue")
        rev_last = with_rev[-1][1].get("revenue") if with_rev else latest.get("revenue")
        cagr = None
        if rev_first and rev_last and rev_first > 0 and years > 0:
            cagr = round(100 * ((rev_last / rev_first) ** (1 / years) - 1), 1)
        lines += [
            "",
            f"Multi-year trend ({first.get('period')} to {latest.get('period')}, "
            f"{len(annual)} periods):",
            f"- Revenue CAGR: {_fmt(cagr, '%') if cagr is not None else 'N/A'}",
        ]
        lines += _year_by_year(annual + ([ttm] if ttm else []), unit_label)

    quarters = data.get("quarters") or []
    if quarters:
        has_npa = any(q.get("gnpa") is not None for q in quarters)
        lines += ["", f"Recent quarters ({unit_label}):",
                  "Quarter | Sales | Op profit | OPM % | Net profit | EPS" + (" | Gross NPA % | Net NPA %" if has_npa else "")]
        for q in quarters:
            lines.append(
                f"{q.get('period')} | {_compact(q.get('sales'), unit_label)} | "
                f"{_compact(q.get('operating_profit'), unit_label)} | {_fmt(q.get('opm'), '%')} | "
                f"{_compact(q.get('net_profit'), unit_label)} | {_fmt(q.get('eps'))}"
                + (f" | {_fmt(q.get('gnpa'))} | {_fmt(q.get('nnpa'))}" if has_npa else "")
            )

    surprises = data.get("eps_surprises") or []
    if surprises:
        parts = []
        for s in surprises:
            actual, cons = s.get("actual"), s.get("consensus")
            if actual is None or not cons:
                continue
            gap = (actual - cons) / abs(cons) * 100
            parts.append(f"{s.get('period')}: EPS {actual} vs {cons} expected ({'beat' if gap >= 0 else 'miss'} {abs(gap):.1f}%)")
        if parts:
            lines += ["", "Recent quarterly earnings vs analyst consensus (per share, USD):", "- " + "; ".join(parts)]
    estimates = data.get("eps_estimates") or []
    if estimates:
        lines += ["- Analyst consensus EPS for coming fiscal years: " + "; ".join(
            f"{e.get('year')} {e.get('eps')} ({e.get('analysts')} analysts)" for e in estimates)]

    growth = data.get("growth") or {}
    if growth:
        lines += ["", "Growth and returns:"]
        for title, vals in growth.items():
            lines.append(f"- {title}: " + ", ".join(f"{k} {v}%" for k, v in vals.items()))

    ratios = data.get("ratios") or {}
    if ratios:
        lines.append("")
        lines.append("Additional ratios:")
        for key, value in ratios.items():
            if key == "Debt to Equity" and isinstance(value, (int, float)):
                lines.append(f"- {key}: {value} (a percent: {value / 100:.2f}x total debt to equity)")
            else:
                lines.append(f"- {key}: {value}")

    own_pe = ratios.get("P/E Ratio (Trailing)", ratios.get("P/E Ratio"))
    lines += _format_peers(data.get("peers"), own_pe, cap_unit, own_cap=data.get("market_cap"),
                           is_group=bool(group_note(data.get("ticker"))))
    lines += _format_segment_comps(data.get("segment_comps"), own_pe)

    lines += describe_technicals(data.get("technicals"), currency)

    pros, cons = data.get("pros") or [], data.get("cons") or []
    if pros or cons:
        lines += ["", "Screener's automated checklist:"]
        lines += [f"- Pro: {x}" for x in pros[:3]] + [f"- Con: {x}" for x in cons[:3]]

    lines += _capital_allocation(annual, unit_label)
    lines += _management_lines(
        data.get("governance") or {},
        latest.get("net_income") if str(unit_label) == "USD" else None,
    )
    lines += _derived_metrics(data, latest, ttm, cap_unit, unit_label)
    lines += _data_notes(data, latest, ttm, ratios, cap_unit, unit_label)

    shareholding = data.get("shareholding") or []
    if shareholding:
        lines.append("")
        lines.append("Shareholding pattern trend (most recent periods):")
        for row in shareholding:
            parts = ", ".join(
                f"{k.replace('_', ' ').title()} {v}%"
                for k, v in row.items()
                if k != "period" and v is not None
            )
            lines.append(f"- {row.get('period')}: {parts}")

    qualitative = data.get("qualitative")
    if qualitative:
        lines.append("")
        lines.append("Qualitative:")
        lines.append(qualitative)

    parent_context = data.get("parent_context")
    if parent_context:
        lines.append("")
        lines.append(
            f"Parent company context ({parent_context['name']}, {parent_context['ticker']}) — "
            f"{data['ticker']} has little or no standalone financial history yet, so this is the "
            f"PARENT's own overall financials, provided as pre-demerger/pre-listing baseline context, "
            f"NOT {data['ticker']}'s own numbers. Reason with this as an informed proxy, not a fact "
            f"about {data['ticker']} itself:"
        )
        lines.append(format_for_agents(parent_context))

    return "\n".join(lines)
