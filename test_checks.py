from agents import prompts
from data.checks import framework_check_lines


def _rows(n=6, **over):
    rows = []
    for i in range(n):
        g = 1.1 ** i
        row = {"period": str(2020 + i), "revenue": 100 * g, "net_income": 20 * g, "operating_income": 30 * g,
               "operating_cash_flow": 24 * g, "fcf": 20 * g, "capex": 4 * g, "total_assets": 200 * g, "total_debt": 50,
               "cash": 80, "gross_margin": 40 + i, "operating_margin": 30 + i * 0.5, "eps_diluted": 2 * g,
               "shares_avg": 100 - i, "dividends": 5, "buybacks": 5, "sbc": 2 * g}
        row.update(over)
        rows.append(row)
    return rows


def _data(**over):
    base = {"market": "US", "unit_label": "USD", "market_cap": 1000.0, "market_cap_unit": "USD", "price": 50.0,
            "sector": "Technology", "ratios": {"P/E Ratio (Trailing)": 25, "Book Value per Share": 10.0},
            "ttm": {"eps_diluted": 2.5}, "annual": _rows()}
    base.update(over)
    return base


def test_the_checks_compute_the_standard_tests():
    text = "\n".join(framework_check_lines(_data()))
    assert "Revenue growth over 5 years: 10.0% a year" in text
    assert "a steady stalwart" in text                      # earnings growth of 10% a year
    assert "Share count over 5 years: -1.0% a year" in text and "buybacks outweigh" in text
    assert "Net debt" not in text and "net cash" in text   # cash 80 against debt 50
    assert "Graham number" in text and "22.5" in text
    assert "Piotroski" in text and "Rule of 40" in text
    assert "my assumed figure" in text                      # the bond yield is labelled as not from the data


def test_a_bank_does_not_get_misleading_industrial_tests():
    text = "\n".join(framework_check_lines(_data(sector="Financial Services")))
    assert "Gross margin" not in text and "Piotroski" not in text and "Net debt" not in text


def test_insane_margins_and_missing_history_are_left_out():
    rows = _rows()
    rows[0]["gross_margin"], rows[0]["operating_margin"] = 503.5, 626.6
    text = "\n".join(framework_check_lines(_data(annual=rows)))
    assert "503" not in text and "626" not in text
    assert framework_check_lines({"annual": [_rows(1)[0]]}) == []


def test_every_agent_carries_its_tests_and_one_style_note():
    for key in prompts.AGENTS:
        text = prompts.SYSTEM_PROMPTS[key]
        assert "Your own tests" in text and "Framework checks" in text, key
        assert text.count("How to write your answer") == 1, key


def test_debate_and_first_pass_prompts_still_format_and_ask_for_something_new():
    prompts.DEBATE_TURN_TEMPLATE.format(agent="a", ticker="t", roster="r", data="d", own_position="p",
                                        transcript="x", instruction="i")
    assert "Add something new each turn" in prompts.DEBATE_TURN_TEMPLATE
    assert "change your answer" in prompts.STAGE1_PROMPT_TEMPLATE


def test_first_pass_asks_for_plain_headers_and_a_data_reminder_and_the_cio_gathers_price_levels():
    assert "plain text (no bullet, no bold" in prompts.STAGE1_PROMPT_TEMPLATE
    assert "my rough estimate" in prompts.STAGE1_PROMPT_TEMPLATE
    assert "7. Price Levels" in prompts.CIO_PROMPT_TEMPLATE and "Framework checks" in prompts.CIO_PROMPT_TEMPLATE
