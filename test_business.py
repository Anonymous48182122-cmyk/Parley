from agents.business import management_facts, money_flow, parse_card, pick_wisdom, split_scorecard

WRITE_UP = """Moat\nStrong.\n\nVerdict\nPass at this price.\n\nBUSINESS MODEL SCORE: 8/10
THE GREAT: **A brand that sets its own price.**
THE BAD: Volumes are capped.
THE GRUESOME: Nothing that scares me
"""


def test_scorecard_is_split_off_and_the_write_up_keeps_its_verdict():
    clean, card = split_scorecard(WRITE_UP)
    assert "BUSINESS MODEL" not in clean and clean.rstrip().endswith("Pass at this price.")
    assert card == {"score": 8, "great": "A brand that sets its own price.", "bad": "Volumes are capped.",
                    "gruesome": "Nothing that scares me"}


def test_a_write_up_without_a_scorecard_or_with_a_wild_score_is_left_alone():
    assert split_scorecard("Verdict: Buy") == ("Verdict: Buy", None)
    clean, card = split_scorecard("Verdict: Buy\nBUSINESS MODEL SCORE: 14/10\nTHE GREAT: x")
    assert card is None and "SCORE" not in clean


def test_business_card_json_is_cleaned_and_bounded():
    raw = '```json\n{"one_breath": "It sells cars — fast ones.", "moat": {"type": "Brand", "strength": 14}, ' \
          '"engines": [{"name": "Cars", "how": "Sells them."}], "management": {"story": "Fine.", "signals": ' \
          '[{"good": true, "text": "Pay is small"}]}}\n```'
    card = parse_card(raw)
    assert card["one_breath"] == "It sells cars , fast ones."
    assert card["moat"]["strength"] == 10 and card["engines"][0]["name"] == "Cars"
    assert parse_card("not json") is None and parse_card('{"one_breath": ""}') is None


def test_money_flow_uses_percent_of_sales_and_prefers_the_trailing_year():
    fin = {"ttm": {"revenue": 200.0, "operating_income": 60.0, "net_income": 40.0},
           "annual": [{"period": "2025", "revenue": 100.0, "gross_margin": 50.0}]}
    flow = money_flow(fin)
    assert flow["operating"] == 30.0 and flow["net"] == 20.0 and flow["gross"] == 50.0
    assert money_flow({"annual": []}) is None


def test_wisdom_follows_the_numbers():
    assert pick_wisdom({"Debt to Equity": 2.4})["who"] == "Warren Buffett"
    assert "tide" in pick_wisdom({"Debt to Equity": 240})["quote"]  # a percentage is read as a multiple
    assert "do not lose money" in pick_wisdom({"Net Profit Margin": -3})["quote"]
    assert pick_wisdom({})["quote"]


def test_management_facts_leave_out_what_is_unknown():
    assert management_facts({}, "USD") is None
    fin = {"governance": {"officers": [{"name": "Mr. A  B", "title": "CEO", "pay": 5}]},
           "shareholding": [{"period": "Mar 2026", "promoters": 50.4}]}
    facts = management_facts(fin, "INR")
    assert facts["officers"][0]["name"] == "Mr. A B" and facts["promoters"]["now"] == 50.4
