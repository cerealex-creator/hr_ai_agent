"""Исходящие HTTP-запросы только через IPv4 (на Timeweb IPv6 до Telegram часто недоступен)."""

import socket

import requests

_applied = False
_session: requests.Session | None = None


def force_requests_ipv4() -> None:
    global _applied
    if _applied:
        return
    family = lambda: socket.AF_INET
    try:
        import urllib3.util.connection as urllib3_connection

        urllib3_connection.allowed_gai_family = family
    except Exception:
        pass
    try:
        from urllib3.util import connection as urllib3_connection2

        urllib3_connection2.allowed_gai_family = family
    except Exception:
        pass
    _applied = True


def get_requests_session() -> requests.Session:
    global _session
    force_requests_ipv4()
    if _session is None:
        _session = requests.Session()
    return _session


force_requests_ipv4()
