"""
The plain words layer of a Parley run: what the committee decided, said so that someone with no finance
background can take it in within a minute.

One extra call, made after the CIO has ruled, writes it as JSON: a headline, the three best reasons for and
against, what would change the committee's mind, and one short line for each member. Everything it states
must come from the memo and the members' own words, so it only retells; it never adds a new opinion.

Pure functions only (prompt text, input gathering, parsing); the model call lives in runner.py. The page
builds its own fallback from the scorecards and the votes when this call fails, so a missing brief only
means plainer wording, never an empty screen.
"""

import json
import re

BRIEF_SYSTEM = """You turn an investment committee's decision into plain words for someone who has never
studied finance and has under a minute. Short, concrete sentences, everyday words, no jargon: if a finance
word is unavoidable, explain it in a few plain words right there. No dashes of any kind. You only retell what
the memo and the members said; never add a new opinion, a new number, or advice to buy or sell."""

BRIEF_PROMPT = """The committee has finished looking at {ticker}. Its ruling is {verdict} with conviction {conviction} out of 10.

Write the plain words version as one JSON object and nothing else (no markdown fence).

Use exactly these keys:
{{
 "headline": "the whole decision in one sentence of at most 22 words, a beginner could repeat it to a friend",
 "for": ["the three strongest reasons to like it, each at most 16 words"],
 "against": ["the three strongest reasons to worry, each at most 16 words"],
 "change_mind": "what would make the committee change its call, one sentence of at most 24 words",
 "members": {{ {member_keys} }}
}}

For "members", give every key below exactly one short line (at most 14 words) in plain words, in that member's
own voice, saying why they landed where they did. The keys and the call each member ended on:
{members}

Rules: only use numbers that appear in the text below. No finance jargon without a few plain words of
explanation. Never tell the reader to buy or sell; say what the committee thinks.

The CIO's memo:
{memo}

What each member said at the end of their first pass:
{closing}
"""


def _clean(value, limit):
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", value).strip().replace("—", ",").replace("–", ",")
    value = re.sub(r"^[\"'“]+|[\"'”]+$", "", value).strip()
    return value[:limit] or None


def closing_words(stage1, names, per_agent=260):
    """Each member's own last words: the end of their first pass, where the verdict lives."""
    lines = []
    for agent, text in stage1.items():
        tail = re.sub(r"[*#_`]+", "", text or "").strip()
        tail = re.sub(r"\s+", " ", tail)
        lines.append(f"- {names.get(agent, agent)}: {tail[-per_agent:]}")
    return "\n".join(lines)


def prompt_for(ticker, verdict, conviction, memo, stage1, stances, names, memo_chars=3800):
    keys = list(stage1.keys())
    calls = "\n".join(f"- {k}: {names.get(k, k)}, ended on {stances.get(k, {}).get('final', 'unclear').upper()}" for k in keys)
    member_keys = ", ".join(f'"{k}": "..."' for k in keys)
    clipped = re.sub(r"\n{3,}", "\n\n", memo or "")[:memo_chars]
    return BRIEF_PROMPT.format(
        ticker=ticker, verdict=verdict or "HOLD", conviction=conviction if conviction is not None else "unknown",
        member_keys=member_keys, members=calls, memo=clipped, closing=closing_words(stage1, names),
    )


def parse_brief(raw, agent_keys):
    """The model's JSON, cleaned and bounded. None when there is no usable headline."""
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    headline = _clean(data.get("headline"), 220)
    if not headline:
        return None

    def reasons(key):
        out = []
        for item in (data.get(key) or [])[:4]:
            text = _clean(item, 160)
            if text:
                out.append(text)
        return out[:3]

    members = {}
    raw_members = data.get("members") if isinstance(data.get("members"), dict) else {}
    for key in agent_keys:
        line = _clean(raw_members.get(key), 140)
        if line:
            members[key] = line
    return {
        "headline": headline,
        "for": reasons("for"),
        "against": reasons("against"),
        "change_mind": _clean(data.get("change_mind"), 240),
        "members": members,
    }
