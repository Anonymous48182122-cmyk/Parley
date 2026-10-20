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

# One comparator per segment, for groups where that is practical. Each is a loose proxy for what
# the market pays for that kind of business, not a like for like peer.
SEGMENT_COMPARATORS = {
    "RELIANCE": [
        ("Telecom and digital (Jio)", "BHARTIARTL"),
        ("Retail", "DMART"),
        ("Fashion retail", "TRENT"),
        ("Oil and gas production", "ONGC"),
        ("Refining and marketing", "IOC"),
    ],
}


def group_note(ticker):
    """What kind of group this is, or None for an ordinary company."""
    return DIVERSIFIED_GROUPS.get((ticker or "").upper())


def fetch_segment_comps(ticker, market):
    """Current P/E, ROCE and size for each segment comparator, or [] when there is none or
    nothing could be fetched. Best effort, like every fetcher in data/: never raises."""
    pairs = SEGMENT_COMPARATORS.get((ticker or "").upper())
    if not pairs or market != "India":
        return []
    from data.india import bse_fetcher  # local: only the India path needs it

    out = []
    for segment, comp in pairs:
        try:
            f = bse_fetcher.fetch(comp, _allow_parent_lookup=False)
            ratios = f.get("ratios") or {}
            out.append({
                "segment": segment,
                "name": f.get("name") or comp,
                "ticker": comp,
                "pe": ratios.get("P/E Ratio"),
                "roce": ratios.get("ROCE"),
                "market_cap": f.get("market_cap"),
            })
        except Exception:
            continue
    return out
