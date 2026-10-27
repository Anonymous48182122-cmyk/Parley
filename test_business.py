from agents.business import management_facts, money_flow, parse_card, pick_wisdom, split_scorecard, wisdom_features

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


def test_the_most_apt_quote_wins_whoever_said_it():
    pick = lambda **kw: pick_wisdom(wisdom_features(**kw))
    assert "tide" in pick(ratios={"Debt to Equity": 2.4})["quote"]
    assert "tide" in pick(ratios={"Debt to Equity": 240})["quote"]  # a percentage is read as a multiple
    assert "stop digging" in pick(ratios={"Net Profit Margin": -3, "Debt to Equity": 1.2})["quote"]
    assert pick(ratios={"P/E Ratio (Trailing)": 80})["who"] in ("John Templeton", "Oscar Wilde")
    assert pick(ratios={"Operating Margin": 40}, card={"moat": {"type": "Network effect", "strength": 9}})["who"] == "Peter Thiel"
    assert pick(ratios={}, card={"moat": {"type": "Brand", "strength": 8}})["who"] in ("Jeff Bezos", "Warren Buffett")
    insiders = {"insiders": {"buys": 1, "sells": 30}}
    assert pick(ratios={}, management=insiders)["who"] == "Charlie Munger"
    assert pick(ratios={}, market="India", card=None)["quote"]  # nothing special falls back to a general line


def test_different_companies_do_not_all_get_the_same_line():
    f = wisdom_features({})
    assert len({pick_wisdom(f, t)["quote"] for t in ("AAPL", "MSFT", "KO", "RACE", "ABNB", "NVDA")}) > 1


def test_management_facts_leave_out_what_is_unknown():
    assert management_facts({}, "USD") is None
    fin = {"governance": {"officers": [{"name": "Mr. A  B", "title": "CEO", "pay": 5}]},
           "shareholding": [{"period": "Mar 2026", "promoters": 50.4}]}
    facts = management_facts(fin, "INR")
    assert facts["officers"][0]["name"] == "Mr. A B" and facts["promoters"]["now"] == 50.4


def test_leaders_name_the_chief_executive_and_merge_the_same_person():
    fin = {"price": 100.0, "governance": {
        "exec_pay": {"ceo_name": "Brian Chesky", "years": [{"period_end": "2025-12-31", "ceo_total": 242122.0, "ceo_paid": -89e6}]},
        "officers": [{"name": "Mr. Brian Chesky", "title": "Co-Founder, CEO", "pay": 242122},
                     {"name": "Mr. Nathan Blecharczyk", "title": "Co-Founder", "pay": 1310067}],
        "insiders_nasdaq": {"recent": [{"who": "Blecharczyk Nathan", "relation": "Officer", "held": 38259.0, "type": "Sell",
                                        "shares": 100.0, "date": "10/12/2026"},
                                       {"who": "Bernstein David C", "relation": "Officer", "held": 45655.0, "type": "Sell",
                                        "shares": 1369.0, "date": "10/15/2026"}]}}}
    leaders = management_facts(fin, "USD")["leaders"]
    names = [l["name"] for l in leaders]
    assert names == ["Brian Chesky", "Nathan Blecharczyk", "David C Bernstein"]
    assert leaders[0]["ceo"] and leaders[1]["held"] == 38259.0 and leaders[1]["held_value"] == 3825900


def test_a_surname_only_chief_executive_gets_the_full_name_and_degrees_are_dropped():
    from agents.business import clean_name
    assert clean_name("Mr. Alexander C. Karp J.D.") == "Alexander C. Karp"
    assert clean_name("Dr. Jane Roe, Ph.D.") == "Jane Roe"
    fin = {"price": 10.0, "governance": {
        "exec_pay": {"ceo_name": "Mr. Karp", "years": [{"period_end": "2025-12-31", "ceo_total": 1.0}]},
        "insiders_nasdaq": {"recent": [{"who": "Karp Alexander C", "relation": "Officer", "held": 5.0}]}}}
    leaders = management_facts(fin, "USD")["leaders"]
    assert leaders[0]["name"] == "Alexander C Karp" and leaders[0]["ceo"]


def test_wikidata_names_the_ceo_and_founders_and_joins_the_same_person():
    fin = {"price": 10.0, "governance": {
        "officers": [{"name": "Mr. Lawrence Edward Page II", "title": "Co-Founder & Director", "pay": 1},
                     {"name": "Mr. Nikhil Meswani", "title": "Executive Director"},
                     {"name": "Mr. Hital Meswani", "title": "Executive Director"}]}}
    people = {"ceo": ["Sundar Pichai"], "founders": ["Larry Page", "Sergey Brin"]}
    leaders = management_facts(fin, "USD", people)["leaders"]
    names = [l["name"] for l in leaders]
    assert names[0] == "Sundar Pichai" and leaders[0]["ceo"]
    assert names.count("Larry Page") == 1 and "Lawrence Edward Page II" not in names
    assert "Sergey Brin" in names and "Nikhil Meswani" in names and "Hital Meswani" in names  # two different people


def test_quotes_come_from_anyone_whose_line_fits_the_situation():
    pick = lambda **kw: pick_wisdom(wisdom_features(**kw))
    assert pick(ratios={}, sector="Energy")["who"] in ("Ecclesiastes", "Howard Marks")
    assert pick(ratios={}, sector="Healthcare", rnd_pct=22)["who"] in ("Louis Pasteur", "Thomas Edison")
    assert pick(ratios={"Revenue Growth (YoY, latest quarter)": -8})["who"] == "John F. Kennedy"
    assert pick(ratios={"P/E Ratio (Trailing)": 9, "Net Profit Margin": 12})["who"] == "Benjamin Graham"
    assert pick(ratios={}, management={"insiders": {"buys": 40, "sells": 3}})["who"] == "Peter Lynch"
    seen = {pick_wisdom(wisdom_features({}), t)["who"] for t in ("A", "B", "C", "D", "E", "F", "G", "H")}
    assert len(seen) >= 3


def test_a_new_chief_executive_replaces_the_one_in_the_old_proxy_statement():
    fin = {"price": 10.0, "governance": {
        "exec_pay": {"ceo_name": "Mr. Cook", "years": [{"period_end": "2025-09-27", "ceo_total": 1.0}]},
        "officers": [{"name": "Mr. Timothy D. Cook", "title": "Executive Chairman of the Board"}]}}
    leaders = management_facts(fin, "USD", {"ceo": ["John Ternus"], "founders": ["Steve Jobs"]})["leaders"]
    ceos = [l["name"] for l in leaders if l.get("ceo")]
    assert ceos == ["John Ternus"]
    assert any(l["name"] == "Steve Jobs" and l["founder"] for l in leaders)


def test_options_vary_and_the_overused_line_needs_a_clear_case():
    from agents.business import pick_wisdom_options
    strong = wisdom_features({"P/E Ratio (Trailing)": 24, "Return on Equity": 30, "Operating Margin": 30, "Debt to Equity": 0.2},
                             scorecards={"a": {"score": 9}, "b": {"score": 9}}, card={"moat": {"type": "Brand", "strength": 9}})
    opts = pick_wisdom_options(strong, "ABC")
    assert len(opts) == 4 and len({o["quote"] for o in opts}) == 4
    assert all("fair price" not in o["quote"] for o in opts[:1])  # not the line every good business gets
    seen = {pick_wisdom_options(strong, t)[0]["quote"] for t in ("AAPL", "KO", "MSFT", "V", "COST", "NVDA", "HD", "PG")}
    assert len(seen) >= 3


def test_situations_bring_their_own_lines():
    pick = lambda **kw: pick_wisdom(wisdom_features(**kw))["who"]
    assert pick(ratios={}, drawdown=45) == "Warren Buffett"
    assert pick(ratios={"P/E Ratio (Trailing)": 40}, near_high=True) in ("German proverb", "John Templeton", "Oscar Wilde")
    assert pick(ratios={"Gross Margin": 82}) in ("Peter Thiel",)
    assert pick(ratios={}, sector="Financial Services") in ("Hyman Minsky", "Warren Buffett", "Benjamin Franklin", "William Shakespeare")
    assert pick(ratios={"Revenue Growth (YoY, latest quarter)": -4, "Net Profit Margin": 8}) in ("Heraclitus", "John F. Kennedy")
