"""
The prices at which committee members say their answer would change.

Every first pass ends with a Verdict sentence that names the price or fact that would change the
answer ("I would buy if the price dropped to 120"). This reads those sentences and pulls out the
prices, so the page can show a price ladder: how far the stock would have to move before each member
turns. Worked out by plain pattern matching, never by a model, and anything doubtful is left out.
"""

import re

_NUMBER = re.compile(
    r"(?<![\w.,])(?:[$₹€£]|USD\s|INR\s|Rs\.?\s?)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?!\d)(?!\s*(?:%|x\b|×|times\b|percent\b|years?\b|yrs?\b|billion|million|trillion|crore|cr\b|lakh|bn\b|m\b|k\b|days?\b|months?\b))",
    re.I)
_CUE = re.compile(r"\b(below|under|above|over|beneath|drop|drops|dropped|fall|falls|fell|decline|declines|reach|reaches|"
                  r"near|toward|towards|exceed|exceeds|rise|rises|rose|at|to|if|until|once|when)\b", re.I)
_ACTION = re.compile(r"\b(buy|sell|reconsider|turn|change|swing|flip|enter|accumulate|add|exit|trim|pass|hold|"
                     r"interested|attractive|position|switch|revisit|move)\b", re.I)
_NOT_A_PRICE = re.compile(r"(p/e|pe ratio|multiple|peg|ev/|p/b|price[- ]to|ratio|yield|margin|growth|roic|roe|"
                          r"eps|earnings per share|\bq[1-4]\b)\s*(of|at|near|to|below|above|under|over|from|=|:)?\s*$", re.I)
_DISPLAY_SUFFIX = re.compile(r"\b(52[- ]week|200[- ]day)\b", re.I)


def _verdict_text(text):
    lower = (text or "").lower()
    at = lower.rfind("verdict")
    return (text[at:] if at != -1 else (text or "")[-500:])[:800]


def _sentences(text):
    return [s for s in re.split(r"(?<=[.;!?])\s+|\n+", text) if s.strip()]


def price_levels(stage1, price, names):
    """[{"price", "pct", "side", "who": [names]}] sorted from the highest price down, one entry per
    distinct price, where `pct` is how far the price is from today's (negative means below it)."""
    try:
        price = float(price)
    except (TypeError, ValueError):
        return []
    if price <= 0:
        return []
    found = {}
    for agent, text in (stage1 or {}).items():
        for sentence in _sentences(_verdict_text(text)):
            if not _ACTION.search(sentence):
                continue
            for m in _NUMBER.finditer(sentence):
                try:
                    value = float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
                # a trigger price is rarely more than 60% below or 150% above today's, and a figure outside that is
                # nearly always something else (a ratio, a year, a day count)
                if not (0.4 * price <= value <= 2.5 * price) or abs(value / price - 1) < 0.02:
                    continue
                before = sentence[max(0, m.start() - 45):m.start()]
                if not _CUE.search(before) or _NOT_A_PRICE.search(before[-22:]):
                    continue
                if value == int(value) and 1990 <= value <= 2100 and not m.group(0)[0] in "$₹€£":
                    continue  # a year
                key = round(value, 2)
                who = found.setdefault(key, [])
                name = names.get(agent, agent)
                if name not in who:
                    who.append(name)
    out = []
    for value, who in sorted(found.items(), reverse=True):
        out.append({"price": value, "pct": round(100 * (value / price - 1), 1),
                    "side": "below" if value < price else "above", "who": who})
    return out
