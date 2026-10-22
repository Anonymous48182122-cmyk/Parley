"""
Diversified groups: companies whose value is a sum of very different businesses.

A single peer median is meaningless for them. Reliance Industries trades on a P/E of about 22
while its refining peers (IOC, BPCL) trade near 6 to 8, because refining is a cyclical
commodity business, but most of Reliance's value comes from Jio and Retail, which are valued like
a telecom company and a consumer business. An agent that compares the group to the refiners
concludes it is "overvalued", which is the wrong conclusion drawn from the wrong comparison.

This module holds (1) a short, factual description of what each well known group is made of, so
agents value segment by segment instead of against one peer set, and (2) for Reliance, a real
comparator for each segment whose current figures are fetched like any other stock's.
"""

# The descriptions are deliberately plain, long established facts about each group, not
# estimates, and never contain figures that change (revenue shares, valuations).
DIVERSIFIED_GROUPS = {
    "RELIANCE": (
        "Reliance Industries is a diversified group, not an oil refiner. Its businesses are oil to "
        "chemicals (refining and petrochemicals), oil and gas production, Reliance Retail, digital "
        "services and telecom (Jio Platforms), media, and new energy. The market values these very "
        "differently: refining is cyclical and trades on low multiples, while telecom and retail "
        "are valued as growth and consumer businesses."
    ),
    "ADANIENT": (
        "Adani Enterprises is the incubator of the Adani group, not one industry. It builds and "
        "holds young infrastructure businesses (airports, roads, mining and resources, data "
        "centres, new energy manufacturing) alongside a trading business, and spins them out once "
        "they mature, so its consolidated numbers mix businesses at very different stages."
    ),
    "LT": (
        "Larsen and Toubro is a conglomerate: engineering and construction, infrastructure "
        "development, heavy engineering and defence, technology and IT services (through listed "
        "subsidiaries), and financial services. It is valued by its order book and by the worth "
        "of its listed subsidiaries, not on a single industry multiple."
    ),
    "GRASIM": (
        "Grasim is a holding company with operating businesses: viscose and chemicals, paints, "
        "and a large stake in UltraTech Cement. A large share of its value is that cement stake, "
        "so it is usually judged as a sum of its parts, often at a holding company discount."
    ),
    "BAJAJFINSV": (
        "Bajaj Finserv is a holding company whose value is mainly its stakes in Bajaj Finance "
        "(lending) and Bajaj Allianz (general and life insurance), so it is judged on those "
        "stakes and not on a single industry multiple."
    ),
    "ITC": (
        "ITC is a diversified group: cigarettes (the main profit source), packaged foods and "
        "personal care, agri business, and paper and packaging. Cigarettes fund the growth of "
        "the newer consumer businesses, so no single peer set describes it."
    ),
    "BRK-B": (
        "Berkshire Hathaway is a conglomerate: insurance and reinsurance (GEICO and others) that "
        "generate investable float, the BNSF railroad, regulated utilities and energy, a wide "
        "range of manufacturing and service businesses, and a very large portfolio of listed "
        "shares and cash. It is judged on book value growth and owner earnings, not a peer median."
    ),
    "AMZN": (
        "Amazon is a group of very different businesses: online retail and marketplace, Amazon "
        "Web Services (cloud), advertising, and subscriptions. The cloud and advertising "
        "businesses earn most of the profit, while retail earns thin margins, so a single "
        "retail peer multiple misleads."
    ),
    "GOOGL": (
        "Alphabet is a group: search and advertising (the main profit source), YouTube, Google "
        "Cloud, and long term bets such as Waymo. It should not be compared to one industry's "
        "average multiple."
    ),
}
DIVERSIFIED_GROUPS["GOOG"] = DIVERSIFIED_GROUPS["GOOGL"]
DIVERSIFIED_GROUPS["BRK.B"] = DIVERSIFIED_GROUPS["BRK-B"]

# One comparator per segment, for the well known groups. Each is a loose proxy for what the market
# pays for that kind of business, picked as the clearest listed pure play, never a like for like peer.
SEGMENT_COMPARATORS = {
    "RELIANCE": [
        ("Telecom and digital (Jio)", "BHARTIARTL"),
        ("Retail", "DMART"),
        ("Fashion retail", "TRENT"),
        ("Oil and gas production", "ONGC"),
        ("Refining and marketing", "IOC"),
    ],
    "ADANIENT": [
        ("Airports", "GMRAIRPORT"),
        ("Roads and highways", "IRB"),
        ("Mining and resources", "COALINDIA"),
        ("Solar manufacturing", "WAAREEENER"),
    ],
    "LT": [
        ("Engineering and construction", "KEC"),
        ("IT and technology services", "INFY"),
        ("Defence and aerospace", "HAL"),
        ("Financial services", "CHOLAFIN"),
    ],
    "GRASIM": [
        ("Cement (through UltraTech)", "ULTRACEMCO"),
        ("Paints", "ASIANPAINT"),
        ("Chemicals (caustic soda)", "GUJALKALI"),
    ],
    "BAJAJFINSV": [
        ("Lending (Bajaj Finance)", "BAJFINANCE"),
        ("Life insurance", "SBILIFE"),
        ("General insurance", "ICICIGI"),
    ],
    "ITC": [
        ("Cigarettes", "GODFRYPHLP"),
        ("Packaged foods and personal care", "HINDUNILVR"),
        ("Paper and packaging", "JKPAPER"),
    ],
    "AMZN": [
        ("Online retail", "WMT"),
        ("Cloud computing", "MSFT"),
        ("Digital advertising", "META"),
    ],
    "GOOGL": [
        ("Digital advertising", "META"),
        ("Cloud and software", "MSFT"),
    ],
    "BRK-B": [
        ("Property and casualty insurance", "CB"),
        ("Railroads", "UNP"),
        ("Regulated utilities", "NEE"),
    ],
}
SEGMENT_COMPARATORS["GOOG"] = SEGMENT_COMPARATORS["GOOGL"]
SEGMENT_COMPARATORS["BRK.B"] = SEGMENT_COMPARATORS["BRK-B"]


def group_note(ticker):
    """What kind of group this is, or None for an ordinary company."""
    return DIVERSIFIED_GROUPS.get((ticker or "").upper())


def _india_comp(comp):
    from data.india import bse_fetcher  # local: only the India path needs it

    f = bse_fetcher.fetch(comp, _allow_parent_lookup=False)
    ratios = f.get("ratios") or {}
    return {"name": f.get("name") or comp, "pe": ratios.get("P/E Ratio"), "roce": ratios.get("ROCE"),
            "market_cap": f.get("market_cap"), "unit": "INR Cr."}


def _us_comp(symbol):
    """P/E on trailing twelve month earnings (last fiscal year when the quarters are unavailable),
    market cap and operating margin, from Nasdaq's public data."""
    from data.nasdaq_data import fetch_nasdaq_annual, fetch_nasdaq_quarterly, fetch_nasdaq_quote
    from data.yahoo_fundamentals import period_date

    q = fetch_nasdaq_quote(symbol)
    mcap = q.get("market_cap")
    if not mcap:
        raise ValueError(f"no quote for {symbol}")
    rows = (fetch_nasdaq_quarterly(symbol).get("rows") or [])[-4:]
    dates = [period_date(r["period"]) for r in rows]
    consecutive = len(rows) == 4 and None not in dates and all(60 <= (b - a).days <= 125 for a, b in zip(dates, dates[1:]))
    if not consecutive:
        rows = (fetch_nasdaq_annual(symbol).get("rows") or [])[-1:]
    ni = sum(r.get("net_income") or 0 for r in rows) if rows else None
    rev = sum(r.get("revenue") or 0 for r in rows) if rows else None
    op = sum(r.get("operating_income") or 0 for r in rows) if rows else None
    return {"name": q.get("name") or symbol, "pe": round(mcap / ni, 1) if ni and ni > 0 else None,
            "operating_margin": round(op / rev * 100, 1) if rev and op else None,
            "market_cap": mcap, "unit": "USD"}


def fetch_segment_comps(ticker, market):
    """Current P/E and size for each segment comparator, or [] when there is none or nothing could
    be fetched. Best effort, like every fetcher in data/: never raises."""
    pairs = SEGMENT_COMPARATORS.get((ticker or "").upper())
    if not pairs:
        return []
    out = []
    for segment, comp in pairs:
        try:
            data = _india_comp(comp) if market == "India" else _us_comp(comp)
            out.append({"segment": segment, "ticker": comp, **data})
        except Exception:
            continue
    return out
