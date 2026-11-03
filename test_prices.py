from fastapi.testclient import TestClient

import backend.main as app_main
from data import prices


def test_the_prices_endpoint_parses_items_and_leaves_unknowns_null(monkeypatch):
    monkeypatch.setattr(prices, "latest_price", lambda t, m: {"AAPL": 331.2, "TCS": 2499.1}.get(t))
    out = TestClient(app_main.app).get("/prices", params={"items": "aapl:US, TCS:india ,ZZZ:US,"}).json()
    assert out == {"AAPL:US": 331.2, "TCS:India": 2499.1, "ZZZ:US": None}


def test_latest_price_is_cached_and_failures_become_none(monkeypatch):
    calls = []

    def fake_us(t):
        calls.append(t)
        raise RuntimeError("down")
    monkeypatch.setattr(prices, "_us_price", fake_us)
    prices._CACHE.clear()
    assert prices.latest_price("ABC", "US") is None and prices.latest_price("ABC", "US") is None
    assert calls == ["ABC"]  # the second call came from the cache, even though the first found nothing
