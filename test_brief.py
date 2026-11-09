"""The plain words brief: parsing is strict about what it keeps, and the prompt names every member."""

import json

from agents.brief import parse_brief, prompt_for

NAMES = {"buffett": "Warren Buffett", "simons": "Jim Simons"}
KEYS = ["buffett", "simons"]


def good(**over):
    data = {
        "headline": "A fine company, but the price is high, so the committee would wait.",
        "for": ["Customers keep coming back", "It earns a lot of cash", "Little debt", "A fourth reason"],
        "against": ["The price is high"],
        "change_mind": "A fall to about 85 dollars would bring buyers in.",
        "members": {"buffett": "Great brand, wrong price.", "simons": "The numbers do not favour it.", "ghost": "not on the committee"},
    }
    data.update(over)
    return json.dumps(data)


def test_parses_and_bounds():
    brief = parse_brief("```json\n" + good() + "\n```", KEYS)
    assert brief["headline"].startswith("A fine company")
    assert len(brief["for"]) == 3  # a fourth reason is dropped
    assert brief["against"] == ["The price is high"]
    assert set(brief["members"]) == {"buffett", "simons"}  # only members who sat on this committee


def test_dashes_are_replaced():
    brief = parse_brief(good(headline="Solid — but pricey"), KEYS)
    assert "—" not in brief["headline"]


def test_unusable_answers_give_none():
    assert parse_brief("", KEYS) is None
    assert parse_brief("no json here", KEYS) is None
    assert parse_brief("{not json}", KEYS) is None
    assert parse_brief(good(headline=""), KEYS) is None
    assert parse_brief("[1, 2]", KEYS) is None


def test_missing_parts_are_tolerated():
    brief = parse_brief(json.dumps({"headline": "Plain."}), KEYS)
    assert brief == {"headline": "Plain.", "for": [], "against": [], "change_mind": None, "members": {}}


def test_prompt_names_every_member_and_their_call():
    stage1 = {"buffett": "Great.\n\n## Verdict\nI would buy.", "simons": "No.\n\n## Verdict\nI would sell."}
    stances = {"buffett": {"final": "buy"}, "simons": {"final": "sell"}}
    text = prompt_for("KO", "HOLD", 6, "The memo.", stage1, stances, NAMES)
    assert '"buffett": "..."' in text and '"simons": "..."' in text
    assert "buffett: Warren Buffett, ended on BUY" in text
    assert "simons: Jim Simons, ended on SELL" in text
    assert "The memo." in text and "HOLD" in text
