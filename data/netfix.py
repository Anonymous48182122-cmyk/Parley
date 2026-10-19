"""
Network settings for the outbound data fetches.

On the cloud host some sites (Screener.in) resolve to an IPv6 address the host has no
route to, so every request died with "[Errno 101] Network is unreachable" even though the
site was up. Restricting name resolution to IPv4 makes those requests connect normally.
Importing this module applies the setting once for the whole process.
"""

import socket

import urllib3.util.connection as _urllib3_connection

_urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
