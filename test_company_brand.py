"""A company's web address and logo file are read from Wikidata claims, skipping withdrawn values."""

from data.people import _brand


def claim(value, rank="normal"):
    return {"rank": rank, "mainsnak": {"datavalue": {"value": value}}}


def test_domain_and_logo_are_found():
    claims = {
        "P856": [claim("https://www.coca-colacompany.com/")],
        "P154": [claim("The Coca-Cola Company (2020).svg")],
    }
    assert _brand(claims) == {"domain": "coca-colacompany.com", "logo": "The Coca-Cola Company (2020).svg"}


def test_small_icon_is_preferred_over_the_wordmark():
    claims = {"P8972": [claim("Apple icon.svg")], "P154": [claim("Apple wordmark.svg")]}
    assert _brand(claims)["logo"] == "Apple icon.svg"


def test_withdrawn_values_are_skipped():
    claims = {"P856": [claim("http://old.example.com", "deprecated"), claim("https://WWW.Example.com/en/home")]}
    assert _brand(claims) == {"domain": "example.com", "logo": None}


def test_nothing_known_gives_empty_values():
    assert _brand({}) == {"domain": None, "logo": None}


from bs4 import BeautifulSoup

from data.brand import _best_icon, _logo_from_json_ld, host_of, same_site


def test_host_of_reads_plain_addresses_only():
    assert host_of("http://www.azad.in") == "azad.in"
    assert host_of("https://WWW2.Example.co.in/about?x=1") == "example.co.in"
    assert host_of("example.com") == "example.com"
    assert host_of("https://www.bseindia.com/stock/x") is None  # an exchange page is not the company's site
    assert host_of("http://127.0.0.1:8000") is None
    assert host_of("") is None and host_of(None) is None


def test_same_site_accepts_subdomains_only():
    assert same_site("ril.com", "ril.com")
    assert same_site("investors.ril.com", "ril.com")
    assert not same_site("ril.com", "rilx.com")
    assert not same_site(None, "ril.com")


def test_json_ld_logo_is_found_even_when_nested():
    html = '<script type="application/ld+json">{"@graph":[{"@type":"Organization","logo":{"url":"/img/logo.png"}}]}</script>'
    assert _logo_from_json_ld(BeautifulSoup(html, "lxml"), "https://acme.com/") == "https://acme.com/img/logo.png"
    assert _logo_from_json_ld(BeautifulSoup("<p>x</p>", "lxml"), "https://acme.com/") is None


def test_best_icon_prefers_apple_touch_then_size():
    html = ('<link rel="icon" href="/f16.png" sizes="16x16"><link rel="icon" href="/f64.png" sizes="64x64">'
            '<link rel="apple-touch-icon" href="/apple.png" sizes="180x180">')
    assert _best_icon(BeautifulSoup(html, "lxml"), "https://acme.com/") == "https://acme.com/apple.png"
    html = '<link rel="icon" href="/f16.png" sizes="16x16"><link rel="shortcut icon" href="/fav.ico">'
    assert _best_icon(BeautifulSoup(html, "lxml"), "https://acme.com/") == "https://acme.com/f16.png"
    assert _best_icon(BeautifulSoup("<p>none</p>", "lxml"), "https://acme.com/") is None
