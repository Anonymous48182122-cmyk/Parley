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
 "management": {{"story": "two or three sentences on who runs it and whether their incentives look aligned, using ONLY the management and ownership facts in the data; say plainly what is not known",
                 "signals": [ {{"good": true or false, "text": "a short fact based signal, at most 12 words"}} ]}},
 "ask_yourself": "one sharp question a student of business should ask about this company"
}}

Rules: 2 to 4 engines, 2 to 4 signals. Every number must come from the data below, and do not name a
currency unless the data does. For management, mention insider buying or selling, pay or ownership ONLY
if the data literally contains it; when it does not, say that is not known instead of saying "zero".
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
        "ask_yourself": _text(card.get("ask_yourself"), 300),
    }


# ---------------------------------------------------------------------------------------------
# Real lines that fit the business in front of you
# ---------------------------------------------------------------------------------------------

_WISDOM = {
    "debt": ("Only when the tide goes out do you discover who has been swimming naked.", "Warren Buffett",
             "This company carries a lot of debt, so the tide matters."),
    "moat": ("In business, I look for economic castles protected by unbreachable moats.", "Warren Buffett",
             "Margins this strong usually mean something protects them."),
    "quality": ("It is far better to buy a wonderful company at a fair price than a fair company at a wonderful price.",
                "Warren Buffett", "The business looks strong. The price is the only open question."),
    "pricey": ("Price is what you pay. Value is what you get.", "Warren Buffett",
               "The market is asking a lot for this business."),
    "thin": ("Invert, always invert.", "Charlie Munger",
             "Margins are thin here, so ask first how this business could fail."),
    "loss": ("The first rule of investing is do not lose money.", "Warren Buffett",
             "The company is not making a profit today."),
    "growth": ("Know what you own, and know why you own it.", "Peter Lynch",
               "Fast growth is only a story until you can explain where it comes from."),
    "default": ("Risk comes from not knowing what you are doing.", "Warren Buffett",
                "Which is why the business comes before the price."),
}


def _num(x):
    try:
        return float(str(x).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def pick_wisdom(ratios, net_margin=None):
    """A real, short line from a famous investor that fits this company's numbers, with why it fits."""
    ratios = ratios or {}
    de = _num(ratios.get("Debt to Equity"))
    op = _num(ratios.get("Operating Margin"))
    pe = _num(ratios.get("P/E Ratio (Trailing)"))
    growth = _num(ratios.get("Revenue Growth (YoY, latest quarter)"))
    net = net_margin if net_margin is not None else _num(ratios.get("Net Profit Margin"))
    # the debt to equity ratio arrives either as a multiple or as a percentage
    if de is not None and de > 5:
        de = de / 100
    if net is not None and net < 0:
        key = "loss"
    elif de is not None and de >= 1.5:
        key = "debt"
    elif op is not None and op >= 25 and pe is not None and pe >= 35:
        key = "pricey"
    elif op is not None and op >= 25:
        key = "moat"
    elif op is not None and 0 < op < 8:
        key = "thin"
    elif growth is not None and growth >= 25:
        key = "growth"
    elif op is not None and op >= 15:
        key = "quality"
    else:
        key = "default"
    quote, who, why = _WISDOM[key]
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


def management_facts(financials, currency):
    """Officers, chief executive pay and the ownership signals that show whose money is on the line."""
    gov = financials.get("governance") or {}
    out = {"currency": currency}
    officers = [o for o in (gov.get("officers") or []) if o.get("name")][:4]
    if officers:
        out["officers"] = [{"name": o["name"].replace("  ", " ").strip(), "title": o.get("title"), "pay": o.get("pay")}
                           for o in officers]
    pay = gov.get("exec_pay") or {}
    years = [y for y in pay.get("years", []) if y.get("ceo_total")]
    if years:
        net = _num((financials.get("ttm") or {}).get("net_income")) or _num(((financials.get("annual") or [{}])[-1]).get("net_income"))
        out["ceo_pay"] = {"latest": years[0]["ceo_total"], "year": years[0]["period_end"][:4],
                          "earlier": [y["ceo_total"] for y in years[1:4]],
                          "pct_of_profit": round(100 * years[0]["ceo_total"] / net, 4) if net and net > 0 and currency == "USD" else None}
    ins = gov.get("insiders_6m")
    if ins:
        out["insiders"] = {"buys": int(ins.get("buy_trans") or 0), "sells": int(ins.get("sell_trans") or 0)}
    holding = financials.get("shareholding") or []
    if holding and holding[-1].get("promoters") is not None:
        latest = holding[-1]
        back = holding[-5] if len(holding) >= 5 else holding[0]
        out["promoters"] = {"now": latest["promoters"], "year_ago": back.get("promoters"), "period": latest.get("period")}
    return out if len(out) > 1 else None
