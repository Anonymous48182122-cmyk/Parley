"""Every member states a buy and a sell price in two fixed lines; they feed The Floor and the price ladder."""

from agents.business import split_scorecard
from agents.levels import price_levels


def write_up(buy, sell):
    return ("Strong brand.\n\n## Verdict\nI would pass for now.\n\n"
            "BUSINESS MODEL SCORE: 8/10\nTHE GREAT: People ask for it.\nTHE BAD: Slow.\nTHE GRUESOME: Sugar rules.\n"
            f"BUY AT OR BELOW: {buy}\nSELL AT OR ABOVE: {sell}\n")


def test_limits_are_read_and_removed_from_the_write_up():
    clean, card = split_scorecard(write_up("$85", "$105.50"))
    assert card["buy_at"] == 85 and card["sell_at"] == 105.5
    assert "BUY AT" not in clean and clean.endswith("I would pass for now.")


def test_rupees_commas_and_words():
    assert split_scorecard(write_up("₹1,200", "Rs. 1,650"))[1]["buy_at"] == 1200
    assert split_scorecard(write_up("about 72", "NONE"))[1]["sell_at"] is None
    assert split_scorecard(write_up("about 72", "NONE"))[1]["buy_at"] == 72


def test_ratios_and_percentages_are_not_prices():
    card = split_scorecard(write_up("15 times earnings", "20%"))[1]
    assert card["buy_at"] is None and card["sell_at"] is None


def test_stated_limits_win_over_the_wording_of_the_verdict():
    stage1 = {"a": "Verdict: I would buy below 70.", "b": "Verdict: I would buy if it fell to 80."}
    levels = price_levels(stage1, 100, {"a": "Ann", "b": "Bo"}, {"a": {"buy_at": 90, "sell_at": 130}})
    assert [(x["price"], x["who"]) for x in levels] == [(130, ["Ann"]), (90, ["Ann"]), (80, ["Bo"])]


def test_wild_or_trivial_limits_are_left_out():
    levels = price_levels({"a": "Verdict: pass."}, 100, {"a": "Ann"}, {"a": {"buy_at": 5, "sell_at": 100.5}})
    assert levels == []
