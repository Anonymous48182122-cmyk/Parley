"""Tests for data/validate.py: impossible values are dropped, a ratio that contradicts the
statements is corrected, and the validator never raises. Run: python test_validate.py"""

from data.validate import validate_financials


def base(**over):
    f = {
        "ticker": "TEST", "market": "US", "unit_label": "USD", "market_cap": 1_000_000_000.0, "price": 100.0,
        "annual": [{"net_income": 25_000_000.0, "total_equity": 200_000_000.0, "total_debt": 100_000_000.0}],
        "ratios": {}, "technicals": {}, "peers": [],
    }
    f.update(over)
    return f


def notes(f):
    return " | ".join(f.get("data_sources", []))


def test_impossible_values_dropped():
    f = base(ratios={"Dividend Yield": "300%", "Gross Margin": "250%", "Beta": 40, "P/E Ratio (Trailing)": 38.0})
    validate_financials(f)
    assert "Dividend Yield" not in f["ratios"] and "Gross Margin" not in f["ratios"] and "Beta" not in f["ratios"]
    assert f["ratios"]["P/E Ratio (Trailing)"] == 38.0
    assert "dropped Dividend Yield" in notes(f)


def test_pe_contradicting_statements_is_corrected():
    # market cap / net income = 40, but the ratio says 150
    f = base(ratios={"P/E Ratio (Trailing)": 150.0})
    validate_financials(f)
    assert f["ratios"]["P/E Ratio (Trailing)"] == 40.0
    assert "disagreed" in notes(f)


def test_pe_half_of_a_stale_fiscal_year_is_left_alone():
    # earnings doubled since the fiscal year, so a real P/E of 21 against an implied 40 is fine
    f = base(ratios={"P/E Ratio (Trailing)": 21.0})
    validate_financials(f)
    assert f["ratios"]["P/E Ratio (Trailing)"] == 21.0


def test_pe_consistent_is_untouched():
    f = base(ratios={"P/E Ratio (Trailing)": 38.0})
    validate_financials(f)
    assert f["ratios"]["P/E Ratio (Trailing)"] == 38.0 and not f.get("data_sources")


def test_pe_checked_against_ttm_when_present():
    # the trailing year gives 20x, so a ratio of 21 is right and one of 40 is not
    f = base(ratios={"P/E Ratio (Trailing)": 21.0}, ttm={"net_income": 50_000_000.0})
    validate_financials(f)
    assert f["ratios"]["P/E Ratio (Trailing)"] == 21.0
    g = base(ratios={"P/E Ratio (Trailing)": 40.0}, ttm={"net_income": 50_000_000.0})
    validate_financials(g)
    assert g["ratios"]["P/E Ratio (Trailing)"] == 20.0


def test_negative_equity_drops_equity_ratios():
    f = base(ratios={"Debt to Equity": -250.0, "Return on Equity": "-90%"})
    f["annual"][0]["total_equity"] = -5_000_000.0
    validate_financials(f)
    assert "Debt to Equity" not in f["ratios"] and "Return on Equity" not in f["ratios"]


def test_52_week_range_conflicting_with_history_is_dropped():
    f = base(ratios={"52-Week High": 300.0, "52-Week Low": 80.0},
             technicals={"high_52w": 120.0, "low_52w": 79.0, "last": 100.0})
    validate_financials(f)
    assert "52-Week High" not in f["ratios"] and f["ratios"]["52-Week Low"] == 80.0


def test_price_far_from_last_close_uses_close():
    f = base(price=8300.0, technicals={"last": 100.0})
    validate_financials(f)
    assert f["price"] == 100.0


def test_foreign_currency_statements_skip_the_pe_check():
    # statements in yen, market cap in dollars: dividing them would be nonsense
    f = base(unit_label="JPY", ratios={"P/E Ratio (Trailing)": 15.0})
    validate_financials(f)
    assert f["ratios"]["P/E Ratio (Trailing)"] == 15.0


def test_peers_with_absurd_values_are_blanked():
    f = base(peers=[{"ticker": "X", "pe": 99999, "roe": 5000, "operating_margin": 20}])
    validate_financials(f)
    assert f["peers"][0]["pe"] is None and f["peers"][0]["roe"] is None and f["peers"][0]["operating_margin"] == 20


def test_never_raises_on_garbage():
    for junk in ({}, {"ratios": None}, {"ratios": {"P/E Ratio (Trailing)": "abc"}, "annual": None},
                 {"annual": [None], "market": "US"}, {"ratios": {"Beta": object()}}):
        validate_financials(junk)


if __name__ == "__main__":
    tests = [(n, fn) for n, fn in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"{len(tests)} passed")
