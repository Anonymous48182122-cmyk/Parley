"""
Price-action statistics from a daily closing-price series, shared by both
markets: India gets its series from Screener's chart API (same host the
fundamentals come from, so it works wherever Screener does), the US from
yfinance. Pure arithmetic on a list of (date, close) pairs, no network.

Why this exists: agents like Sperandeo (trend) and Simons (momentum, volatility)
were asked to reason about price action with nothing but a single price and a
52-week range, and the committee page had no range to show at all.
"""

import math
from statistics import pstdev


def _pct(new, old):
    if not old:
        return None
    return round(100 * (new - old) / old, 1)


def _mean(values):
    return sum(values) / len(values) if values else None


def compute_technicals(series):
    """series: list of (iso_date, close) sorted oldest to newest. Returns a flat
    dict of rounded numbers (None where there isn't enough history), or {} if the
    series is too short to say anything useful."""
    closes = [float(c) for _, c in series if c is not None]
    if len(closes) < 20:
        return {}

    last = closes[-1]
    year = closes[-252:]  # roughly one trading year
    high, low = max(year), min(year)

    def back(n):
        return closes[-1 - n] if len(closes) > n else None

    dma50 = _mean(closes[-50:]) if len(closes) >= 50 else None
    dma200 = _mean(closes[-200:]) if len(closes) >= 200 else None

    daily = [closes[i] / closes[i - 1] - 1 for i in range(1, len(year)) if year[i - 1]]
    vol = round(100 * pstdev(daily) * math.sqrt(252), 1) if len(daily) > 20 else None

    peak, max_dd = year[0], 0.0
    for c in year:
        peak = max(peak, c)
        max_dd = min(max_dd, c / peak - 1)

    span = high - low
    return {
        "last": round(last, 2),
        "high_52w": round(high, 2),
        "low_52w": round(low, 2),
        "pct_below_high": _pct(last, high),
        "pct_above_low": _pct(last, low),
        "range_position": round(100 * (last - low) / span) if span else None,
        "dma50": round(dma50, 2) if dma50 else None,
        "dma200": round(dma200, 2) if dma200 else None,
        "vs_dma50": _pct(last, dma50) if dma50 else None,
        "vs_dma200": _pct(last, dma200) if dma200 else None,
        "ret_1m": _pct(last, back(21)),
        "ret_3m": _pct(last, back(63)),
        "ret_6m": _pct(last, back(126)),
        "ret_1y": _pct(last, back(251)) if len(closes) > 251 else None,
        "volatility_1y": vol,
        "max_drawdown_1y": round(100 * max_dd, 1),
        "days_of_history": len(closes),
    }


def describe_technicals(t, currency=""):
    """Compact text lines for the agent-facing data block."""
    if not t:
        return []
    cur = f" {currency}" if currency else ""
    lines = ["", "Price action (daily closes):"]
    lines.append(
        f"- 52-week range: {t['low_52w']} to {t['high_52w']}{cur}; last {t['last']}, "
        f"{abs(t['pct_below_high'])}% below the high and {t['pct_above_low']}% above the low "
        f"(sits {t['range_position']}% of the way up the range)"
        if t.get("pct_below_high") is not None and t.get("range_position") is not None
        else f"- 52-week range: {t['low_52w']} to {t['high_52w']}{cur}"
    )
    avgs = []
    if t.get("dma50"):
        avgs.append(f"50-day average {t['dma50']} (price {t['vs_dma50']:+}% vs it)")
    if t.get("dma200"):
        avgs.append(f"200-day average {t['dma200']} (price {t['vs_dma200']:+}% vs it)")
    if avgs:
        lines.append("- " + "; ".join(avgs))
    rets = [f"{label} {t[key]:+}%" for label, key in
            (("1M", "ret_1m"), ("3M", "ret_3m"), ("6M", "ret_6m"), ("1Y", "ret_1y")) if t.get(key) is not None]
    if rets:
        lines.append("- Price return: " + ", ".join(rets))
    risk = []
    if t.get("volatility_1y") is not None:
        risk.append(f"annualised volatility {t['volatility_1y']}%")
    if t.get("max_drawdown_1y") is not None:
        risk.append(f"worst peak-to-trough fall over the year {t['max_drawdown_1y']}%")
    if risk:
        lines.append("- Risk: " + ", ".join(risk))
    return lines
