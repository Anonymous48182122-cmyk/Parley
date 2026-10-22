from data.common import _pay_lines
from data.us.exec_pay import _parse

PROXY = """
<xbrli:context id="c-1"><xbrli:period><xbrli:startDate>2024-10-01</xbrli:startDate><xbrli:endDate>2025-09-27</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c-2"><xbrli:period><xbrli:startDate>2023-10-01</xbrli:startDate><xbrli:endDate>2024-09-28</xbrli:endDate></xbrli:period></xbrli:context>
<ix:nonFraction name="ecd:PeoTotalCompAmt" contextRef="c-1" scale="6" unitRef="usd">74.3</ix:nonFraction>
<ix:nonFraction name="ecd:PeoTotalCompAmt" contextRef="c-2" scale="6" unitRef="usd">74.6</ix:nonFraction>
<ix:nonFraction name="ecd:PeoTotalCompAmt" contextRef="c-2" scale="6" unitRef="usd">1.0</ix:nonFraction>
<ix:nonFraction name="ecd:PeoActuallyPaidCompAmt" contextRef="c-1" unitRef="usd">108,400,000</ix:nonFraction>
"""


def test_parse_reads_scale_and_period_from_context_and_first_value_wins():
    years, _ = _parse(PROXY)
    assert years["2025-09-27"]["ceo_total"] == 74.3e6
    assert years["2024-09-28"]["ceo_total"] == 74.6e6
    assert years["2025-09-27"]["ceo_paid"] == 108.4e6


def test_pay_lines_say_how_total_pay_is_counted_and_skip_missing_pay():
    pay = {"filed": "2026-01-08", "years": [{"period_end": "2025-09-27", "ceo_total": 74.3e6, "ceo_paid": 108.4e6}]}
    text = "\n".join(_pay_lines(pay, 100e9))
    assert "$74.3M" in text and "$108.4M" in text and "granted" in text
    assert _pay_lines({"filed": "x", "years": []}) == []
