from data import global_equities, search
from data.countries import country_of_symbol, is_global_symbol, iso_from_name, suffix_of


def test_exchange_suffixes_give_the_country_and_us_share_classes_are_not_mistaken_for_one():
    assert is_global_symbol("7203.T") and country_of_symbol("7203.T") == "JP"
    assert is_global_symbol("SAP.DE") and country_of_symbol("SAP.DE") == "DE"
    assert is_global_symbol("HSBA.L") and country_of_symbol("0005.HK") == "HK"
    assert not is_global_symbol("BRK.B") and not is_global_symbol("BF.B") and not is_global_symbol("AAPL")
    assert not is_global_symbol("TCS.NS")          # India has its own route
    assert country_of_symbol("AAPL") == "US" and suffix_of("RACE.MI") == "MI"


def test_country_names_from_nasdaq_become_codes():
    assert iso_from_name("Taiwan") == "TW" and iso_from_name("United States") == "US"
    assert iso_from_name("Hong Kong") == "HK" and iso_from_name("Nowhereland") is None and iso_from_name(None) is None


def _fin(**over):
    base = {"unit_label": "CNY", "price_currency": "HKD", "currency": "CNY", "market_cap": 1000.0, "price": 10.0, "annual": []}
    base.update(over)
    return base


def test_market_cap_is_converted_into_the_reporting_currency_and_the_rate_is_stated(monkeypatch):
    monkeypatch.setattr(global_equities, "fx_rate", lambda a, b: 0.85)
    f = global_equities.finish_global(_fin())
    assert f["market_cap"] == 850.0 and f["market_cap_unit"] == "CNY"
    assert any("converted at 1 HKD = 0.8500 CNY" in n for n in f["data_sources"])


def test_without_a_rate_the_market_cap_stays_in_the_trading_currency(monkeypatch):
    monkeypatch.setattr(global_equities, "fx_rate", lambda a, b: None)
    f = global_equities.finish_global(_fin())
    assert f["market_cap"] == 1000.0 and f["market_cap_unit"] == "HKD"


def test_same_currency_needs_no_conversion_and_a_missing_cap_is_estimated_from_shares(monkeypatch):
    f = global_equities.finish_global(_fin(unit_label="EUR", price_currency="EUR", market_cap=None,
                                           annual=[{"shares_avg": 50.0}]))
    assert f["market_cap"] == 500.0 and f["market_cap_unit"] == "EUR"


def test_yahoo_search_keeps_main_listings_and_drops_us_minor_venues_and_receipts(monkeypatch):
    quotes = [
        {"symbol": "TM", "quoteType": "EQUITY", "shortname": "TOYOTA"},                       # US: our own lists cover it
        {"symbol": "7203.T", "quoteType": "EQUITY", "longname": "Toyota Motor Corporation", "exchDisp": "Tokyo Stock Exchange"},
        {"symbol": "TOM.F", "quoteType": "EQUITY", "shortname": "TOYOTA MOTOR"},              # Frankfurt secondary venue
        {"symbol": "TSMC34.SA", "quoteType": "EQUITY", "shortname": "TSMC BDR"},              # Brazilian receipt
        {"symbol": "TMH", "quoteType": "ETF", "shortname": "AN ETF"},
    ]

    class Reply:
        def raise_for_status(self): pass
        def json(self): return {"quotes": quotes}

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: Reply())
    out = search._yahoo_global_matches_live("toyota", 8)
    assert [m["ticker"] for m in out] == ["7203.T"]
    assert out[0]["country"] == "JP" and out[0]["market"] == "Global" and out[0]["exchange"] == "Tokyo Stock Exchange"
