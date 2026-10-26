"""
One place for every request to Screener.in.

The cloud host that runs the backend is refused by Screener at the network level (TCP connection
refused, checked with /health/net), so a direct request cannot work from there. When the direct
connection fails, the same page is fetched through a small relay (api/screener.js on the Vercel
frontend), which runs on a different network. Locally, and anywhere Screener is reachable, the
direct request is used and the relay is never touched.

Set SCREENER_RELAY_URL to point at another relay, or to "off" to disable it.
"""

import hashlib
import os
import time
from urllib.parse import urlparse

import requests

import data.netfix  # noqa: F401  (IPv4-only name resolution)

RELAY_URL = os.environ.get("SCREENER_RELAY_URL", "https://parley-amber.vercel.app/api/screener")
_SKIP_DIRECT_SECONDS = 600  # after a refused direct connection, go straight to the relay for a while
_direct_blocked_until = 0.0


def relay_key():
    """The key the relay expects. Set SCREENER_RELAY_KEY explicitly, or leave it and it is derived
    from the backend's own SUPABASE_JWT_SECRET, which the Vercel side is given the same derived
    value of. The secret itself never leaves the backend and nothing here is committed."""
    explicit = os.environ.get("SCREENER_RELAY_KEY")
    if explicit:
        return explicit
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        return None
    return hashlib.sha256(f"parley-screener-relay:{secret}".encode()).hexdigest()


def _relay_target(url):
    parts = urlparse(url)
    path = parts.path
    while "//" in path:  # the standalone page URL is built with an empty segment (/company/X//)
        path = path.replace("//", "/")
    return path + (f"?{parts.query}" if parts.query else "")


def relay_bse_list(timeout=60):
    """The BSE's equity list, fetched through the relay, for a host the BSE refuses."""
    if not RELAY_URL or RELAY_URL.lower() == "off":
        raise requests.exceptions.ConnectionError("no relay configured")
    key = relay_key()
    response = requests.get(RELAY_URL, params={"bse": "list"}, headers={"X-Relay-Key": key} if key else None, timeout=timeout)
    response.raise_for_status()
    return response.json()


def screener_get(url, headers=None, params=None, timeout=20):
    """requests.get for a www.screener.in URL, falling back to the relay when it cannot connect."""
    global _direct_blocked_until
    if time.time() >= _direct_blocked_until:
        try:
            return requests.get(url, headers=headers, params=params, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if not RELAY_URL or RELAY_URL.lower() == "off":
                raise
            _direct_blocked_until = time.time() + _SKIP_DIRECT_SECONDS
            direct_error = exc
    else:
        direct_error = None

    if not RELAY_URL or RELAY_URL.lower() == "off":
        raise requests.exceptions.ConnectionError("Screener unreachable and no relay configured")
    prepared = requests.Request("GET", url, params=params).prepare()
    try:
        key = relay_key()
        return requests.get(
            RELAY_URL,
            params={"u": _relay_target(prepared.url)},
            headers={"X-Relay-Key": key} if key else None,
            timeout=timeout + 15,
        )
    except requests.exceptions.RequestException:
        if direct_error is not None:
            raise direct_error
        raise
