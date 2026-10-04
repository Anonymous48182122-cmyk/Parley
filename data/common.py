"""
Shared normalized schema, disk cache, and agent-facing text formatter used by
both the US (EDGAR) and India (Screener/NSE) fetchers. Every fetcher returns
data in the same shape so agents read one consistent format regardless of
market — see format_for_agents below.
"""

import json
import statistics
import time
from pathlib import Path

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
    if unit_label == "USD":
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


def _format_peers(peers, own_pe, unit_label):
    """Peer table for the agent prompt, plus the median peer P/E next to the
    company's own — the single number that turns "P/E 40" into "expensive
    versus a peer median of 22"."""
    if not peers:
        return []
    lines = ["", "Peer comparison (same-industry companies of comparable size):"]
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
    if len(peer_pes) >= 2:
        median = round(statistics.median(peer_pes), 1)
        own = f"{own_pe}" if own_pe is not None else "N/A"
        lines.append(f"Peer median P/E: {median} (this company: {own})")
    return lines


def format_for_agents(data):
    """Render the normalized schema into the text block every agent prompt reads."""
    annual = data.get("annual", [])
    latest = annual[-1] if annual else {}
    prior = annual[-2] if len(annual) > 1 else {}
    currency = data.get("currency", "")
    unit_label = data.get("unit_label", currency)

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
        f"Market cap: {_fmt(data.get('market_cap'))} {unit_label} | "
        f"Share price: {_fmt(data.get('price'))} {currency}",
        "",
        f"Income statement (period ending {latest.get('period', 'N/A')}, {unit_label}):",
        f"- Revenue: {_fmt(latest.get('revenue'))} "
        f"(prior period {_fmt(prior.get('revenue'))})",
        f"- Gross profit: {_fmt(latest.get('gross_profit'))} "
        f"(gross margin {_fmt(latest.get('gross_margin'), '%')})",
        f"- Operating income: {_fmt(latest.get('operating_income'))} "
        f"(operating margin {_fmt(latest.get('operating_margin'), '%')})",
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

    if len(annual) > 1:
        first = annual[0]
        years = len(annual) - 1
        rev_first, rev_last = first.get("revenue"), latest.get("revenue")
        cagr = None
        if rev_first and rev_last and rev_first > 0 and years > 0:
            cagr = round(100 * ((rev_last / rev_first) ** (1 / years) - 1), 1)
        lines += [
            "",
            f"Multi-year trend ({first.get('period')} to {latest.get('period')}, "
            f"{len(annual)} periods):",
            f"- Revenue CAGR: {_fmt(cagr, '%') if cagr is not None else 'N/A'}",
        ]
        lines += _year_by_year(annual, unit_label)

    ratios = data.get("ratios") or {}
    if ratios:
        lines.append("")
        lines.append("Additional ratios:")
        for key, value in ratios.items():
            lines.append(f"- {key}: {value}")

    own_pe = ratios.get("P/E Ratio (Trailing)", ratios.get("P/E Ratio"))
    lines += _format_peers(data.get("peers"), own_pe, unit_label)

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
