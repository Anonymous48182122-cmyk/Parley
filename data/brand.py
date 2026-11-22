"""
A company's logo, for any stock, large or small.

Wikidata only knows the big names, so the logo is found in layers and the page uses the best one it can load:

1. The company's own website. It comes from the source that already holds the company's exact record: the
   exchange page on Screener for an Indian company, the SEC's filing index for a US one (Wikidata for the rest).
   A website taken from the company's own record is never a guess.
2. The logo Wikidata holds for the company (the big names), but only when Wikidata's website agrees with the one
   above, so a similar sounding company can never lend its logo.
3. The pictures the website itself offers: the logo it declares for search engines (schema.org JSON-LD) and its
   best app icon. Read once from the home page and kept for a week.
4. The page then falls back to the site's favicon, and last to the company's initials.

Everything is best effort and cached. Any failure returns less, never an error.
"""

import ipaddress
import json
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from data.common import cached_fetch
from data.people import fetch_people

SITE_TTL_HOURS = 24 * 7
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en",
}
_SKIP_HOSTS = ("bseindia.com", "nseindia.com", "screener.in", "sec.gov", "linkedin.com", "twitter.com", "facebook.com")


def host_of(url):
    """'https://www.Azad.in/about' -> 'azad.in'. None for anything that is not a plain web address."""
    if not isinstance(url, str) or not url.strip():
        return None
    text = url.strip()
    if "://" not in text:
        text = "https://" + text
    host = (urlparse(text).hostname or "").lower()
    host = re.sub(r"^www\d?\.", "", host)
    if not host or "." not in host or any(host == h or host.endswith("." + h) for h in _SKIP_HOSTS):
        return None
    try:
        ipaddress.ip_address(host)
        return None  # a raw address is never a company's public site
    except ValueError:
        return host


def same_site(a, b):
    """True when two hosts belong to one company's site: equal, or one is a sub domain of the other."""
    if not a or not b:
        return False
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def _first_size(sizes):
    m = re.search(r"(\d+)\s*x\s*(\d+)", sizes or "")
    return int(m.group(1)) if m else None


def _logo_from_json_ld(soup, base):
    """The logo a site declares for search engines (schema.org Organization logo), the best picture of the brand."""
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                logo = node.get("logo")
                if isinstance(logo, dict):
                    logo = logo.get("url") or logo.get("contentUrl")
                if isinstance(logo, str) and logo.strip():
                    return urljoin(base, logo.strip())
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return None


def _best_icon(soup, base):
    """The largest app icon the page links: Apple touch icons first, then sized or vector icons."""
    best, best_score = None, -1
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" not in rel or "mask" in rel:
            continue
        href = link["href"].strip()
        if not href or href.startswith("data:"):
            continue
        size = _first_size(link.get("sizes"))
        if "apple-touch-icon" in rel:
            score = 200 + (size or 180) / 10
        elif href.lower().split("?")[0].endswith(".svg") or "svg" in (link.get("type") or ""):
            score = 150
        else:
            score = size or 16
        if score > best_score:
            best, best_score = urljoin(base, href), score
    return best


def _scrape_site(domain):
    for host in (domain, "www." + domain):
        try:
            response = requests.get(f"https://{host}/", headers=_HEADERS, timeout=8, allow_redirects=True)
        except requests.RequestException:
            continue
        if response.status_code != 200 or "html" not in (response.headers.get("content-type") or "").lower():
            continue
        final = host_of(response.url)
        if not final:
            continue  # redirected somewhere that is not a company site
        soup = BeautifulSoup(response.text[:400000], "lxml")
        icon = _best_icon(soup, response.url) or urljoin(response.url, "/favicon.ico")
        return {"logo": _logo_from_json_ld(soup, response.url), "icon": icon}
    return {"logo": None, "icon": None}


def site_pictures(domain):
    """{"logo": url or None, "icon": url or None} read from the site's home page; cached a week."""
    if not domain:
        return {"logo": None, "icon": None}
    key = "site_pics_" + re.sub(r"[^a-z0-9]+", "_", domain)[:60]
    try:
        found = cached_fetch(key, SITE_TTL_HOURS, lambda: _scrape_site(domain))
    except Exception:
        return {"logo": None, "icon": None}
    # a picture over plain http would be blocked on an https page
    return {k: (re.sub(r"^http://", "https://", v) if isinstance(v, str) else None) for k, v in found.items()}


def find_brand(name, website=None):
    """{"domain", "logo", "site_logo", "site_icon"}: whatever is known about how to draw this company's logo."""
    own = host_of(website)
    people = fetch_people(name) if name else {}
    wd_domain = host_of(people.get("domain"))
    wd_logo = people.get("logo")
    if own and wd_domain and not same_site(own, wd_domain):
        wd_logo = None  # Wikidata means a different company with a similar name
    domain = own or wd_domain
    pictures = site_pictures(domain)
    return {"domain": domain, "logo": wd_logo, "site_logo": pictures["logo"], "site_icon": pictures["icon"]}


def website_from_sec(ticker):
    """The company's own web address from its SEC filing index, or None. Many small filers leave it blank."""
    try:
        from data.us.edgar_fetcher import _throttled_get, resolve_cik

        cik, _ = resolve_cik(ticker)
        data = cached_fetch(
            f"sec_submissions_{str(cik).zfill(10)}", 24 * 7,
            lambda: _throttled_get(f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json").json())
        return (data.get("website") or "").strip() or None
    except Exception:
        return None


def website_from_nasdaq(ticker):
    """The company's web address from the Nasdaq profile (it lists one for most US companies), or None."""
    try:
        from data.nasdaq_data import _get, _summary_value

        profile = _get(f"company/{ticker}/company-profile")
        value = _summary_value(profile, "CompanyUrl")
        return (value or "").strip() or None
    except Exception:
        return None


def website_for_us(ticker):
    """The SEC's record first, then Nasdaq's, since many small filers leave the SEC field blank."""
    return website_from_sec(ticker) or website_from_nasdaq(ticker)
