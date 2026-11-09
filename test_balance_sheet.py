from data.balance_sheet import agent_lines, build, classify


def _rows(n=5, **over):
    rows = []
    for i in range(n):
        row = {"period": str(2021 + i), "revenue": 1000 + 100 * i, "operating_income": 200 + 20 * i, "net_income": 150 + 10 * i,
               "total_assets": 2000 + 100 * i, "total_equity": 900 + 80 * i, "total_debt": 300, "cash": 500, "interest_expense": 20,
               "operating_cash_flow": 220 + 10 * i, "capex": 60, "roic_approx": 18.0, "gross_profit": 600 + 50 * i}
        row.update(over)
        rows.append(row)
    return rows


def _fin(sector="Technology", **kw):
    base = {"market": "US", "unit_label": "USD", "sector": sector, "annual": _rows(), "ratios": {"Industry": "Software"},
            "balance_detail": {"balance_sheet": {"Net Receivables": 120.0, "Total Current Assets": 1200.0,
                                                 "Total Current Liabilities": 600.0, "Intangible Assets": 100.0}}}
    base.update(kw)
    return base


def test_the_kind_of_company_comes_from_its_sector_and_industry():
    assert classify({"sector": "Financial Services", "ratios": {"Industry": "Private Sector Bank"}}) == "bank"
    assert classify({"sector": "Utilities", "ratios": {}}) == "regulated_infra"
    assert classify({"sector": "Consumer Cyclical", "ratios": {"Industry": "Auto Manufacturers"}}) == "industrial"
    assert classify({"sector": "Technology", "ratios": {}}) == "tech"
    assert classify({"sector": "Consumer Defensive", "ratios": {}}) == "consumer"
    assert classify({"sector": "N/A", "ratios": {}}) == "default"


def test_levels_cover_about_60_and_75_percent_and_pro_has_everything():
    r = build(_fin())
    metrics = r["metrics"]
    basic = [m for m in metrics if m["level"] == "basic"]
    advanced = [m for m in metrics if m["level"] == "advanced"]
    pro = [m for m in metrics if m["level"] == "pro"]
    assert len(basic) >= 3 and advanced and pro
    assert abs(sum(m["weight"] for m in basic) - 60) <= 15
    assert sum(m["weight"] for m in metrics) == 100.0 or abs(sum(m["weight"] for m in metrics) - 100) < 0.5
    assert r["coverage"]["basic"] < r["coverage"]["advanced"] < r["coverage"]["pro"] == 100


def test_net_cash_is_strong_and_a_stretched_company_is_weak():
    strong = build(_fin(annual=_rows(cash=900)))
    assert next(m for m in strong["metrics"] if m["id"] == "net_debt_years")["display"].startswith("Net cash")
    assert strong["verdict"]["tone"] == "strong"
    weak = build(_fin(sector="Industrials", annual=_rows(total_debt=4000, cash=100, operating_income=200, interest_expense=400)))
    assert weak["verdict"]["tone"] == "weak"


def test_a_bank_is_judged_on_leverage_and_funding_not_on_debt_and_cash_flow():
    f = _fin(sector="Financial Services", market="India", unit_label="INR Cr.",
             annual=_rows(total_assets=10000, total_equity=1000, net_income=130),
             balance_detail={"balance_sheet": {"Deposits": 6800.0, "Borrowing": 1200.0, "Investments": 2500.0}})
    r = build(f)
    ids = {m["id"] for m in r["metrics"]}
    assert {"leverage", "deposit_share", "roe", "roa"} <= ids and "net_debt_years" not in ids and "cash_conversion" not in ids
    assert next(m for m in r["metrics"] if m["id"] == "leverage")["display"] == "10.0 times"
    assert any("bad loans" in x["label"].lower() for x in r["missing"])
    assert [x["label"] for x in r["composition"]["funding"]][:2] == ["Customer deposits", "Borrowings"]
    assert "not meaningful" in "\n".join(agent_lines(r))


def test_price_against_return_is_shown_but_never_counts_towards_the_verdict():
    f = _fin(sector="Financial Services", annual=_rows(total_assets=10000, total_equity=1000, net_income=150),
             ratios={"Industry": "Banks", "Price to Book": 9.0})
    m = next(x for x in build(f)["metrics"] if x["id"] == "pb_vs_roe")
    assert m["status"] == "unknown"


def test_nothing_to_read_gives_none_and_the_agents_get_plain_lines():
    assert build({"annual": [], "ratios": {}}) is None
    lines = agent_lines(build(_fin()))
    assert lines[1].startswith("Balance sheet reading") and any("Debt against earnings" in l for l in lines)
