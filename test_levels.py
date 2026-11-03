from agents.levels import price_levels

NAMES = {"buffett": "Warren Buffett", "bezos": "Jeff Bezos", "lynch": "Peter Lynch", "simons": "Jim Simons"}


def test_prices_in_verdicts_become_levels_with_distance_and_side():
    stage1 = {
        "buffett": "Moat\nStrong.\nVerdict\nI would pass at today's price of 168.70 but buy if the price drops to 120.",
        "bezos": "Verdict\nI would buy at $168.70, but reconsider if the share price rises above $190.",
        "lynch": "Verdict\nPass because the P/E of 37.5 is too rich; I would buy below 100 once the PEG nears 1.",
    }
    out = price_levels(stage1, 168.7, NAMES)
    assert [(l["price"], l["side"]) for l in out] == [(190.0, "above"), (120.0, "below"), (100.0, "below")]
    assert out[0]["who"] == ["Jeff Bezos"] and out[1]["pct"] == -28.9


def test_ratios_years_percentages_and_far_off_numbers_are_not_prices():
    stage1 = {"buffett": "Verdict\nI would buy if the P/E fell to 20, growth hit 25%, margins reached 30 percent, "
                         "in 2027, or the stock touched 12 on a collapse."}
    assert price_levels(stage1, 100.0, NAMES) == []


def test_two_members_naming_the_same_price_share_one_row():
    stage1 = {"buffett": "Verdict\nI would buy below 90.", "lynch": "Verdict\nOnly if the price falls to 90 would I buy."}
    out = price_levels(stage1, 168.0, NAMES)
    assert len(out) == 1 and out[0]["who"] == ["Warren Buffett", "Peter Lynch"]


def test_no_price_or_a_bad_price_gives_nothing():
    assert price_levels({"buffett": "Verdict\nI would buy at 120."}, None, NAMES) == []
    assert price_levels({"buffett": "Verdict\nPass."}, 100, NAMES) == []
