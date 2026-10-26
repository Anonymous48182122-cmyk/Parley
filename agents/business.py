"""
The business model side of a Parley run: what the company really is, how it makes money, who runs it,
and how each committee member rates the business itself (apart from the share price).

Pure functions only (prompt text, parsing, the quote picker); the model calls live in runner.py.

Two things come from the models and one from the data:
- every committee member adds a short scorecard to their first pass (a 1 to 10 rating of the business
  model plus The Great, The Bad and The Gruesome), which is split off here so the rest of the
  pipeline keeps reading the plain write up;
- one extra call writes the "business card": a plain English story of the business as JSON;
- the money flow and management facts are computed from the figures, never written by a model.
"""

import json
import re

SCORECARD_INSTRUCTION = """

After your Verdict, finish with this scorecard on its own, using exactly these four labels and nothing
else around it. It rates the BUSINESS (the machine that makes the money), not the share price, so a
wonderful business can score high even if you would not buy it today. Each line is one plain sentence
of at most 18 words, in your own voice, with no dashes. Any figure you quote must come from the data.

BUSINESS MODEL SCORE: <a whole number from 1 to 10>/10
THE GREAT: <the best thing about how this business makes money>
THE BAD: <its real weakness or risk>
THE GRUESOME: <the thing that could really hurt or kill it, or "Nothing that scares me" if truly nothing>
"""

_BLOCK = re.compile(r"\n[\s*#_>-]*BUSINESS MODEL SCORE\b.*\Z", re.S | re.I)
_SCORE = re.compile(r"BUSINESS MODEL SCORE\W*(\d{1,2})(?:\s*(?:/|out of)\s*10)?", re.I)


def _line(block, label):
    m = re.search(rf"{label}\W*[:\-]\s*(.+)", block, re.I)
    if not m:
        return None
    text = re.sub(r"[*_`#]+", "", m.group(1)).strip()
    text = text.split("\n")[0].strip()
    return text[:240] or None


def split_scorecard(text):
    """(write up without the scorecard, {"score", "great", "bad", "gruesome"} or None)."""
    if not text:
        return text, None
    m = _BLOCK.search(text)
    if not m:
        return text, None
    block, clean = m.group(0), text[:m.start()].rstrip()
    score = _SCORE.search(block)
    if not score:
        return clean, None
    value = int(score.group(1))
    if not 1 <= value <= 10:
        return clean, None
    card = {"score": value, "great": _line(block, "THE GREAT"), "bad": _line(block, "THE BAD"),
            "gruesome": _line(block, "THE GRUESOME")}
    return clean, card


# ---------------------------------------------------------------------------------------------
# The business card
# ---------------------------------------------------------------------------------------------

CARD_SYSTEM = """You explain businesses to curious people who have never read an annual report. You are
vivid, concrete and a little witty, never boring and never jargon heavy. You teach: after reading you,
a smart teenager could explain how this company makes its money. Short sentences. No dashes of any kind.
You only state facts and figures that appear in the data you are given; for how the business works you
may use what is plainly common knowledge about the company, but never invent a number, a name or a date."""

CARD_PROMPT = """Write the business card for {ticker} as one JSON object and nothing else (no markdown fence).

Use exactly these keys:
{{
 "one_breath": "what this company is, in one sentence of at most 25 words",
 "analogy": "a vivid everyday comparison that makes the business model click, starting with 'Think of it as'",
 "customer": "who actually pays the company, and what they are really buying, in one or two sentences",
 "engines": [ {{"name": "a revenue engine, 1 to 3 words", "how": "how it earns money, one short sentence"}} ],
 "moat": {{"type": "one of: Brand, Network effect, Cost advantage, Switching costs, Scale, Regulation or licence, Patents or technology, Nothing special",
           "story": "why customers stay, or why rivals cannot copy it, in one or two sentences",
           "strength": a whole number 1 to 10}},
 "great": "the single most impressive thing about the business model, one or two sentences",
 "bad": "its most real weakness, one or two sentences",
 "gruesome": "the thing that could really hurt it, one or two sentences",
 "people": {{"ceo": "the current chief executive's full name, or null if you are not sure",
             "founders": ["full names of the founders, only the ones you are certain of; an empty list for a company with no famous founders"]}},
 "management": {{"story": "two sentences on who runs it: are they the founders still in charge or hired professionals, and what is notable about how they run it. Do NOT mention pay, share sales or ownership percentages"}},
 "ask_yourself": "one sharp question a student of business should ask about this company"
}}

Rules: 2 to 4 engines. Every number must come from the data below, and do not name a currency unless the
data does. Names of people must be ones you are certain of or that the data gives; never guess a name.
If the data is thin, say so in plain words rather than guessing.

Data:
{data}
"""


def _text(value, limit):
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", value).strip().replace("—", ",").replace("–", ",")
    return value[:limit] or None


def parse_card(raw):
    """The model's JSON, cleaned and bounded. None when it is not usable."""
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        card = json.loads(raw[start:end + 1])
    except ValueError:
        return None
    if not isinstance(card, dict) or not _text(card.get("one_breath"), 400):
        return None

    moat = card.get("moat") if isinstance(card.get("moat"), dict) else {}
    try:
        strength = max(1, min(10, int(moat.get("strength"))))
    except (TypeError, ValueError):
        strength = None
    mgmt = card.get("management") if isinstance(card.get("management"), dict) else {}
    people = card.get("people") if isinstance(card.get("people"), dict) else {}
    founders = [_text(n, 60) for n in (people.get("founders") or [])[:4] if isinstance(n, str)]

    engines = []
    for e in (card.get("engines") or [])[:4]:
        if isinstance(e, dict) and _text(e.get("name"), 40):
            engines.append({"name": _text(e.get("name"), 40), "how": _text(e.get("how"), 200)})
    signals = []
    for s in (mgmt.get("signals") or [])[:4]:
        if isinstance(s, dict) and _text(s.get("text"), 120):
            signals.append({"good": bool(s.get("good")), "text": _text(s.get("text"), 120)})

    return {
        "one_breath": _text(card.get("one_breath"), 400),
        "analogy": _text(card.get("analogy"), 300),
        "customer": _text(card.get("customer"), 400),
        "engines": engines,
        "moat": {"type": _text(moat.get("type"), 40), "story": _text(moat.get("story"), 400), "strength": strength},
        "great": _text(card.get("great"), 400),
        "bad": _text(card.get("bad"), 400),
        "gruesome": _text(card.get("gruesome"), 400),
        "management": {"story": _text(mgmt.get("story"), 600), "signals": signals},
        "people": {"ceo": _text(people.get("ceo"), 60), "founders": [n for n in founders if n]},
        "ask_yourself": _text(card.get("ask_yourself"), 300),
    }


# ---------------------------------------------------------------------------------------------
# Real lines that fit the business in front of you
# ---------------------------------------------------------------------------------------------

def _num(x):
    try:
        return float(str(x).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


# Each entry: (fit, quote, who, why it fits). The quotes are real and well attested, from investors,
# founders, writers, scientists and statesmen alike: the pool is "anything apt", not "anything from the
# committee". The fit is a number from 0 up built from the figures, the moat the business card found,
# the committee's average rating, the sector and who owns the shares; the best fit wins.
_CYCLICAL = ("energy", "materials", "industrial", "auto", "semiconductor", "steel", "mining", "airline", "chemical",
             "real estate", "construction", "cyclical", "capital goods", "metals")
_CUSTOMER = ("retail", "consumer", "restaurant", "e-commerce", "apparel", "grocery", "food")


def _candidates(f):
    de, op, net, pe = f.get("de"), f.get("op"), f.get("net"), f.get("pe")
    growth, roe, beta = f.get("growth"), f.get("roe"), f.get("beta")
    moat, strength, avg = (f.get("moat") or "").lower(), f.get("strength"), f.get("avg")
    buys, sells, ceo_pct = f.get("buys") or 0, f.get("sells") or 0, f.get("ceo_pct")
    engines, rnd, sector = f.get("engines"), f.get("rnd_pct"), (f.get("sector") or "").lower()
    out = []

    def add(fit, quote, who, why):
        if fit and fit > 0:
            out.append((fit, quote, who, why))

    # debt and survival
    if de is not None and de >= 1.5:
        extra = min(de - 1.5, 2)
        add(3 + extra, "Only when the tide goes out do you discover who has been swimming naked.", "Warren Buffett",
            "This company carries a lot of debt, so the tide matters.")
        add(2.8 + extra, "Beware of little expenses. A small leak will sink a great ship.", "Benjamin Franklin",
            "Heavy borrowing means small leaks in profit can sink the ship.")
        add(2.6 + extra, "Neither a borrower nor a lender be.", "William Shakespeare",
            "A lot of this company is funded with other people's money.")
    if net is not None and net < 0:
        extra = 0.6 if de and de > 1 else 0
        add(3.5 + extra, "When you are in a hole, stop digging.", "Denis Healey",
            "The company is not making a profit today, so every dollar it burns counts.")
        add(3.0, "The first rule of investing is do not lose money.", "Warren Buffett",
            "A business that loses money has no room for error.")
        if growth is not None and growth >= 25:
            add(3.8, "When something is important enough, you do it even if the odds are not in your favor.",
                "Elon Musk", "Growing fast while losing money is a bet on the future, and bets can go either way.")
            add(3.3, "We are stubborn on vision. We are flexible on details.", "Jeff Bezos",
                "Losses are only worth it when the long plan stays fixed while the details change.")
    # moats, brands, monopolies
    if strength is not None and strength >= 8:
        add(3 + (strength - 8) * 0.3, "I like businesses with economic castles protected by unbreachable moats.",
            "Warren Buffett", "The committee found a moat that rivals will struggle to cross.")
    if "brand" in moat and (strength or 0) >= 7:
        add(3.4, "Your brand is what other people say about you when you are not in the room.", "Jeff Bezos",
            "This business is protected by what customers feel about its name.")
        add(3.1, "It takes twenty years to build a reputation and five minutes to ruin it.", "Warren Buffett",
            "A brand is worth the most and breaks the easiest.")
    if any(w in moat for w in ("network", "scale", "technology", "patent")) and (strength or 0) >= 8 and op is not None and op >= 25:
        add(3.5, "Competition is for losers.", "Peter Thiel",
            "High margins and a hard to copy edge are what a near monopoly looks like.")
    if op is not None and 0 < op < 10:
        add(2.8, "Competition is for losers.", "Peter Thiel", "Thin margins are what competition looks like in numbers.")
        add(2.6, "Invert, always invert.", "Charlie Munger", "Margins are thin, so start by asking how this business could fail.")
        add(2.5, "When a management with a reputation for brilliance tackles a business with a reputation for bad "
                 "economics, it is the reputation of the business that remains intact.", "Warren Buffett",
            "Thin margins say the business, not the managers, sets the result.")
    # quality, time and compounding
    if avg is not None and avg >= 7.5 and pe is not None and pe < 35:
        add(3.6, "It is far better to buy a wonderful company at a fair price than a fair company at a wonderful price.",
            "Warren Buffett", "The committee likes the business, and the price is not extreme.")
    if avg is not None and avg >= 7 and roe is not None and roe >= 20 and (de is None or de < 1) and op is not None and op >= 20:
        add(3.3, "Someone is sitting in the shade today because someone planted a tree a long time ago.",
            "Warren Buffett", "High returns on little debt are how businesses compound over the years.")
        add(3.2, "The first rule of compounding: never interrupt it unnecessarily.", "Charlie Munger",
            "A business that earns this much on its capital rewards patience.")
    if avg is not None and avg >= 7 and pe is not None and pe >= 35:
        add(3.4, "The big money is not in the buying and selling, but in the waiting.", "Charlie Munger",
            "A strong business at a rich price is a case for patience.")
    if avg is not None and avg < 5:
        add(3.0, "Invert, always invert.", "Charlie Munger", "The committee is unimpressed, so start from how this goes wrong.")
        add(2.9, "Time is the friend of the wonderful business, the enemy of the mediocre.", "Warren Buffett",
            "The committee rates this business low, and time is not on its side.")
    # price
    if pe is not None and pe >= 50:
        add(3.4 + min((pe - 50) / 50, 1), "The four most dangerous words in investing are: this time it is different.",
            "John Templeton", "The market is paying a rich price, which only works if the story keeps coming true.")
        add(3.1, "A cynic is a man who knows the price of everything and the value of nothing.", "Oscar Wilde",
            "At this price the question is what the business is really worth.")
    elif pe is not None and pe >= 35:
        add(2.7, "Price is what you pay. Value is what you get.", "Warren Buffett", "The market is asking a lot for this business.")
        add(2.4, "In the short run, the market is a voting machine, but in the long run it is a weighing machine.",
            "Benjamin Graham", "A high price is a vote, and the weighing comes later.")
    if pe is not None and 0 < pe < 14 and (net is None or net > 0):
        add(3.2, "The margin of safety is always dependent on the price paid.", "Benjamin Graham",
            "The price is low next to earnings, which is what a margin of safety looks like.")
    # people and incentives
    if buys >= 5 and buys >= 2 * max(sells, 1):
        add(3.7, "Insiders might sell their shares for any number of reasons, but they buy for only one: they think "
                 "the price will rise.", "Peter Lynch", "Insiders are buying more than they sell.")
    if sells >= 10 and sells >= 3 * max(buys, 1):
        add(3.2, "Show me the incentive and I will show you the outcome.", "Charlie Munger",
            "Insiders have been selling far more than buying, so look at what they are paid to do.")
    if ceo_pct is not None and ceo_pct >= 0.5:
        add(3.0, "Show me the incentive and I will show you the outcome.", "Charlie Munger",
            "The chief executive takes a notable slice of profit, so check what that pay rewards.")
    # risk, change and cycles
    if beta is not None and beta >= 1.4:
        add(2.9, "You cannot predict. You can prepare.", "Howard Marks", "This stock swings harder than the market, so prepare for the swings.")
    if any(w in sector for w in _CYCLICAL):
        add(3.0, "To everything there is a season, and a time to every purpose under the heaven.", "Ecclesiastes",
            "This industry rises and falls in cycles, and the numbers depend on the season.")
        add(2.8, "You cannot predict. You can prepare.", "Howard Marks", "Cyclical businesses reward those who prepare for the downturn.")
    if growth is not None and growth >= 30:
        add(2.2, "He who lives by the crystal ball will eat shattered glass.", "Ray Dalio",
            "Fast growth is a forecast, and forecasts are where investors get hurt.")
    if growth is not None and growth < 0:
        add(3.3, "Change is the law of life. And those who look only to the past or present are certain to miss the future.",
            "John F. Kennedy", "Sales are shrinking, so the question is whether the business can change.")
    if rnd is not None and rnd >= 15:
        add(3.2, "Chance favours the prepared mind.", "Louis Pasteur",
            "This company spends a large share of sales on research, betting that preparation meets discovery.")
        add(2.8, "Genius is one percent inspiration and ninety nine percent perspiration.", "Thomas Edison",
            "Research heavy businesses live on patient, unglamorous work.")
    if any(w in sector for w in _CUSTOMER) and (op is None or op < 15):
        add(2.9, "There is only one boss. The customer. And he can fire everybody in the company from the chairman on down, "
                 "simply by spending his money somewhere else.", "Sam Walton",
            "A business that lives on everyday customers lives or dies by them.")
    if f.get("market") == "India" and growth is not None and growth >= 15:
        add(3.0, "Think big, think fast, think ahead. Ideas are no one's monopoly.", "Dhirubhai Ambani",
            "Fast growth at scale in India is the kind of ambition he built Reliance on.")
    if engines is not None and engines <= 2 and op is not None and op >= 20:
        add(2.6, "Focusing is about saying no.", "Steve Jobs", "The business does a few things and does them very well.")
    # nothing stands out, so any of these fits equally and the company's own seed picks one
    for quote, who, why in (
        ("Know what you own, and know why you own it.", "Peter Lynch", "A business is only worth owning if you can explain how it makes money."),
        ("Behind every stock is a company. Find out what it is doing.", "Peter Lynch", "The numbers are the start, and the business behind them is the story."),
        ("Risk comes from not knowing what you are doing.", "Warren Buffett", "Which is why the business comes before the price."),
        ("It is not supposed to be easy. Anyone who finds it easy is stupid.", "Charlie Munger", "No single number settles this one, so read the whole picture."),
        ("The investor's chief problem, and even his worst enemy, is likely to be himself.", "Benjamin Graham", "A calm look at the business is the best protection against a hasty call."),
        ("Know the enemy and know yourself, and in a hundred battles you will never be in peril.", "Sun Tzu", "Know the business and know your own limits before you buy."),
    ):
        add(1.0, quote, who, why)
    return out


def wisdom_features(ratios, net_margin=None, market=None, management=None, card=None, scorecards=None,
                    sector=None, rnd_pct=None):
    """The few numbers the quote picker looks at, gathered from whatever is known so far."""
    ratios = ratios or {}
    de = _num(ratios.get("Debt to Equity"))
    if de is not None and de > 5:  # arrives either as a multiple or as a percentage
        de = de / 100
    scores = [c["score"] for c in (scorecards or {}).values() if isinstance(c, dict) and c.get("score")]
    ins = (management or {}).get("insiders") or {}
    moat = (card or {}).get("moat") or {}
    return {
        "de": de, "op": _num(ratios.get("Operating Margin")), "pe": _num(ratios.get("P/E Ratio (Trailing)")),
        "net": net_margin if net_margin is not None else _num(ratios.get("Net Profit Margin")),
        "growth": _num(ratios.get("Revenue Growth (YoY, latest quarter)")), "roe": _num(ratios.get("Return on Equity")),
        "beta": _num(ratios.get("Beta")), "market": market, "sector": sector, "rnd_pct": rnd_pct,
        "moat": moat.get("type"), "strength": moat.get("strength"), "engines": len((card or {}).get("engines") or []) or None,
        "avg": sum(scores) / len(scores) if scores else None,
        "buys": ins.get("buys"), "sells": ins.get("sells"),
        "ceo_pct": ((management or {}).get("ceo_pay") or {}).get("pct_of_profit"),
    }


def pick_wisdom(features, seed=""):
    """The single most apt real quote for this business. Ties go to a seeded pick so the same
    company always gets the same line while different companies do not all get the same one."""
    ranked = sorted(_candidates(features), key=lambda c: -c[0])
    top = [c for c in ranked if c[0] >= ranked[0][0] - 0.05]
    _, quote, who, why = top[sum(map(ord, seed)) % len(top)] if top else (0, "", "", "")
    return {"quote": quote, "who": who, "why": why}


# ---------------------------------------------------------------------------------------------
# Facts computed from the figures
# ---------------------------------------------------------------------------------------------

def money_flow(financials):
    """Where each 100 of sales goes, as percentages: gross profit, operating profit, net profit.
    Uses trailing twelve months when there is one, else the last fiscal year."""
    ttm = financials.get("ttm") or {}
    annual = (financials.get("annual") or [{}])[-1]
    row, label = (ttm, "the last twelve months") if ttm.get("revenue") and ttm.get("operating_income") is not None \
        and ttm.get("net_income") is not None else (annual, annual.get("period"))
    revenue = _num(row.get("revenue"))
    if not revenue or revenue <= 0:
        return None
    op, net = _num(row.get("operating_income")), _num(row.get("net_income"))
    if op is None or net is None:
        return None

    def pct(v):
        return None if v is None else round(100 * v / revenue, 1)

    gross = pct(_num(row.get("gross_profit")))
    if gross is None:  # the trailing figures often lack it, so use the last fiscal year's margin
        gross = _num(annual.get("gross_margin"))
    return {"period": label, "gross": gross, "operating": pct(op), "net": pct(net)}


_TITLES = re.compile(r"^(mr|ms|mrs|dr|prof|sir)\.?\s+", re.I)


_CREDENTIALS = re.compile(r"(,?\s+(j\.?d\.?|ph\.?d\.?|m\.?d\.?|m\.?b\.?a\.?|c\.?p\.?a\.?|esq\.?))+\s*$", re.I)


def clean_name(name):
    """A person's name without Mr. or Dr. in front or degrees (J.D., Ph.D., CPA) behind."""
    text = re.sub(r"\s+", " ", _TITLES.sub("", (name or "").strip())).strip()
    return _CREDENTIALS.sub("", text).strip()


def _nasdaq_name(name):
    """Nasdaq lists insiders surname first ("Bernstein David C"); people are shown as "David C Bernstein"."""
    parts = clean_name(name).title().split()
    return " ".join(parts[1:] + parts[:1]) if len(parts) > 1 else " ".join(parts)


_GENERATIONAL = {"jr", "sr", "ii", "iii", "iv", "v"}


def _surname_and_initial(name):
    tokens = [t.strip(".,").lower() for t in name.split() if t.strip(".,")]
    while len(tokens) > 1 and tokens[-1] in _GENERATIONAL:
        tokens.pop()
    return (tokens[-1] if tokens else "", tokens[0][0] if len(tokens) > 1 else "")


def _same_person(a, b):
    """The same surname and, when both names have a first name, the same first initial. That joins
    "Larry Page" and "Lawrence Edward Page II" and keeps Nikhil and Hital Meswani apart."""
    (sa, ia), (sb, ib) = _surname_and_initial(a), _surname_and_initial(b)
    return bool(sa) and sa == sb and (not ia or not ib or ia == ib)


def _leaders(gov, price, ceo_row):
    """The people to name: the chief executive (from the proxy statement), then the officers the
    exchanges list with their pay, then insiders who have recently traded the company's shares."""
    leaders = [ceo_row] if ceo_row else []

    def known(name):
        return any(_same_person(name, l["name"]) for l in leaders)

    for o in (gov.get("officers") or [])[:8]:
        name = clean_name(o.get("name"))
        if not name:
            continue
        is_founder = "founder" in (o.get("title") or "").lower()
        match = next((l for l in leaders if _same_person(name, l["name"])), None)
        if match:
            match["founder"] = match.get("founder") or is_founder
            match.setdefault("title", o.get("title"))
            if len(name.split()) > len(match["name"].split()):
                match["name"] = name  # the proxy statement often gives only a surname ("Karp")
        else:
            leaders.append({"name": name, "role": o.get("title"), "pay": o.get("pay"), "founder": is_founder})

    held = {}
    for r in ((gov.get("insiders_nasdaq") or {}).get("recent") or []):
        name = _nasdaq_name(r.get("who"))
        if name:
            held.setdefault(name, {"name": name, "role": r.get("relation") or "Insider", "trades": []})["trades"].append(r)
    for name, entry in held.items():
        latest = entry["trades"][0]
        match = next((l for l in leaders if _same_person(name, l["name"])), None)
        if match:
            # someone already listed (the chief executive, an officer): add what they hold to that card
            if match.get("held") is None:
                match["held"] = latest.get("held")
            if len(name.split()) > len(match["name"].split()):
                match["name"] = name
            continue
        if len(leaders) >= 6:
            continue
        leaders.append({"name": name, "role": entry["role"], "held": latest.get("held"),
                        "last": {"type": latest.get("type"), "shares": latest.get("shares"), "date": latest.get("date")}})
    for l in leaders:
        if l.get("held") and price:
            l["held_value"] = round(l["held"] * price)
    return leaders[:6]


def _merge_wikidata(leaders, people):
    """Wikidata's chief executive and founders: full names, and a card for anyone not listed yet."""
    def find(name):
        return next((l for l in leaders if _same_person(name, l["name"])), None)

    for i, name in enumerate(people.get("ceo") or []):
        hit = find(name)
        if hit:
            hit["ceo"] = True
            hit["name"] = name  # Wikidata's name is the one the person is known by
        elif i == 0:
            leaders.insert(0, {"name": name, "role": "Chief executive", "ceo": True})
    for name in people.get("founders") or []:
        hit = find(name)
        if hit:
            hit["founder"] = True
            hit["name"] = name
        else:
            leaders.append({"name": name, "role": "Founder", "founder": True})
    return leaders


def management_facts(financials, currency, people=None):
    """Officers, chief executive pay and the ownership signals that show whose money is on the line."""
    gov = financials.get("governance") or {}
    out = {"currency": currency}
    officers = [o for o in (gov.get("officers") or []) if o.get("name")][:4]
    if officers:
        out["officers"] = [{"name": o["name"].replace("  ", " ").strip(), "title": o.get("title"), "pay": o.get("pay")}
                           for o in officers]
    pay = gov.get("exec_pay") or {}
    years = [y for y in pay.get("years", []) if y.get("ceo_total")]
    ceo_row = None
    if years:
        net = _num((financials.get("ttm") or {}).get("net_income")) or _num(((financials.get("annual") or [{}])[-1]).get("net_income"))
        out["ceo_pay"] = {"latest": years[0]["ceo_total"], "year": years[0]["period_end"][:4],
                          "realised": years[0].get("ceo_paid"),
                          "earlier": [y["ceo_total"] for y in years[1:4]],
                          "pct_of_profit": round(100 * years[0]["ceo_total"] / net, 4) if net and net > 0 and currency == "USD" else None}
        if pay.get("ceo_name"):
            ceo_row = {"name": clean_name(pay["ceo_name"]), "role": "Chief executive", "ceo": True,
                       "pay": years[0]["ceo_total"], "realised": years[0].get("ceo_paid"), "year": years[0]["period_end"][:4]}
    leaders = _leaders(gov, _num(financials.get("price")), ceo_row)
    if people:
        leaders = _merge_wikidata(leaders, people)
    if leaders:
        out["leaders"] = leaders
    ins = gov.get("insiders_6m")
    nq = gov.get("insiders_nasdaq")
    if ins:
        out["insiders"] = {"buys": int(ins.get("buy_trans") or 0), "sells": int(ins.get("sell_trans") or 0), "window": "6 months"}
    elif nq and (nq.get("buys") or nq.get("sells")):
        out["insiders"] = {"buys": int((nq.get("buys") or {}).get("12m") or 0),
                           "sells": int((nq.get("sells") or {}).get("12m") or 0), "window": "12 months"}
    holding = financials.get("shareholding") or []
    if holding and holding[-1].get("promoters") is not None:
        latest = holding[-1]
        back = holding[-5] if len(holding) >= 5 else holding[0]
        out["promoters"] = {"now": latest["promoters"], "year_ago": back.get("promoters"), "period": latest.get("period")}
    return out if len(out) > 1 else None
