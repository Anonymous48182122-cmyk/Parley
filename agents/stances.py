"""
Where each agent stands: Buy, Pass, Sell, or unclear.

A mirror of frontend/src/stance.js (keep the two in step). Agents end their writing with a
"Verdict" in plain prose, so this reads the text after the last "Verdict" and takes the first clear
call, understanding simple negations ("I would not buy" is a pass).

An agent has two calls on record: the one from its first pass and the one it ended its debate turn
with. The final one is what counts, and the CIO is told both so a changed mind is never reported as
the old call.
"""

import re

_CALL = re.compile(r"\b(strong buy|buy|accumulate|pass|sell|avoid|stay away|hold off|hold|wait)\b")
_NEGATION_BEFORE = re.compile(
    r"\b(not|never|no|don't|do not|won't|wouldn't|would not|cannot|can't|isn't|is not)\s+(a |an |to |really |be a )?$"
)
_NEGATION_AFTER = re.compile(
    r"^\W*(is|are|would be)\s+(not|n't)\s+(warranted|justified|earned|supported)|^\W*isn't\s+(warranted|justified)"
)

LABELS = {"buy": "Buy", "pass": "Pass", "sell": "Sell", "unclear": "Undecided"}


def _classify(segment):
    for m in _CALL.finditer(segment):
        word = m.group(1)
        before = segment[max(0, m.start() - 18):m.start()]
        after = segment[m.end():m.end() + 30]
        buy_like = word in ("buy", "strong buy", "accumulate")
        negated = bool(_NEGATION_BEFORE.search(before) or _NEGATION_AFTER.search(after))
        if buy_like:
            return "pass" if negated else "buy"
        if negated:
            continue  # "not a sell" says nothing about what they will do
        if word in ("sell", "avoid"):
            return "sell"
        return "pass"  # pass, hold, hold off, wait, stay away
    return None


def parse_stance(text):
    """'buy', 'pass', 'sell' or 'unclear'."""
    if not text:
        return "unclear"
    lower = re.sub(r"\s+", " ", re.sub(r"[*#_`]+", " ", text.lower()))
    at = lower.rfind("verdict")
    if at != -1:
        tail = re.sub(r"^[\s:|>\-]+", "", lower[at + len("verdict"):])[:700]
        found = _classify(tail)
        if found:
            return found
    return _classify(lower[-500:]) or "unclear"


def final_stances(stage1, turns):
    """{agent: {"opening", "final", "changed"}}. The final call is the verdict on the agent's last
    debate turn that states one, and falls back to the opening call when it states none."""
    last_turn = {}
    for agent, text in turns:
        if parse_stance(text) != "unclear":
            last_turn[agent] = parse_stance(text)
    out = {}
    for agent, text in stage1.items():
        opening = parse_stance(text)
        final = last_turn.get(agent, opening)
        out[agent] = {"opening": opening, "final": final, "changed": final != opening and opening != "unclear"}
    return out


def fallback_summary(stage1, turns, names):
    """(memo, verdict, conviction) worked out from the committee's final calls alone, for when the CIO's
    models cannot be reached. It is plainly an automatic summary with low conviction, never a pretence
    of the CIO's own judgement. BUY needs most of the room to say buy; SELL needs a real bear camp;
    anything else is HOLD, matching how the CIO prompt defines the three."""
    stances = final_stances(stage1, turns)
    groups = {"buy": [], "pass": [], "sell": [], "unclear": []}
    for agent, s in stances.items():
        groups[s["final"]].append(names.get(agent, agent))
    decided = len(groups["buy"]) + len(groups["pass"]) + len(groups["sell"])
    verdict = "HOLD"
    if decided:
        if len(groups["buy"]) / decided > 0.5:
            verdict = "BUY"
        elif len(groups["sell"]) / decided >= 0.35:
            verdict = "SELL"
    moved = [(names.get(a, a), LABELS[s["opening"]], LABELS[s["final"]]) for a, s in stances.items() if s["changed"]]

    def line(title, who):
        return f"{title} ({len(who)}): {', '.join(who)}." if who else f"{title}: nobody."

    parts = [
        "This is an automatic summary. The CIO's models were busy, so it only counts where each member ended up. "
        "Use the button above to ask the CIO again.",
        "Where the committee landed",
        line("Buy", groups["buy"]), line("Pass", groups["pass"]), line("Sell", groups["sell"]),
    ]
    if groups["unclear"]:
        parts.append(line("Undecided", groups["unclear"]))
    if moved:
        parts.append("Changed their mind during the debate: " + "; ".join(f"{n} went from {a} to {b}" for n, a, b in moved) + ".")
    memo = "\n\n".join(parts)
    return f"VERDICT: {verdict} | CONVICTION: 3/10\n\n" + memo, verdict, 3


def positions_table(stage1, turns, names):
    """Plain lines for the CIO prompt: each agent's opening and final call."""
    lines = []
    for agent, s in final_stances(stage1, turns).items():
        name = names.get(agent, agent)
        if s["changed"]:
            lines.append(f"- {name}: FINAL {LABELS[s['final']].upper()} (changed their mind during the debate; opened as {LABELS[s['opening']]})")
        else:
            lines.append(f"- {name}: FINAL {LABELS[s['final']].upper()} (same call as their first pass)")
    return "\n".join(lines)
