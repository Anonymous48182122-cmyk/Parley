from agents.stances import final_stances, parse_stance, positions_table
from agents.prompts import CIO_PROMPT_TEMPLATE, DEBATE_TURN_TEMPLATE


def test_negations_and_verdict_section():
    assert parse_stance("**Verdict:** I would not buy at this price") == "pass"
    assert parse_stance("Verdict: Sell, the negative cash flow") == "sell"
    assert parse_stance("") == "unclear"


def test_a_changed_mind_is_reported_with_the_final_call_first():
    stage1 = {"thiel": "Verdict: Buy", "buffett": "Verdict: Pass"}
    turns = [("thiel", "I am changing my call from Buy to Sell.\nVerdict: Sell"), ("buffett", "only prose")]
    f = final_stances(stage1, turns)
    assert f["thiel"] == {"opening": "buy", "final": "sell", "changed": True}
    assert f["buffett"]["changed"] is False
    table = positions_table(stage1, turns, {"thiel": "Peter Thiel", "buffett": "Warren Buffett"})
    assert "Peter Thiel: FINAL SELL" in table and "opened as Buy" in table


def test_templates_still_format():
    CIO_PROMPT_TEMPLATE.format(ticker="X", transcript="t", stage1_analyses="s", data="d", positions="p")
    assert "Verdict: Buy" in DEBATE_TURN_TEMPLATE
