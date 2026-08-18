"""Public demo showcase constants and login throttling (no DB)."""

from __future__ import annotations

import threading
import time

DEMO_ORG_SLUG = "demo-showcase"
DEMO_ORG_NAME = "Демо: Аврора Ритейл"
DEMO_USER_EMAIL = "demo@hr-toolbox.local"
DEMO_USER_NAME = "Демо-рекрутер"
DEMO_SESSION_HOURS = 4
DEMO_CONTACT = "mailto@alexkrupin.ru"
DEMO_WRITE_DETAIL = (
    "В демо-режиме действия недоступны. "
    f"Для полного доступа напишите: {DEMO_CONTACT}"
)
DEMO_BANNER = f"Это демо-режим. Для полного доступа напишите: {DEMO_CONTACT}"
DEMO_LOGIN_PER_IP_HOUR = 30
DEMO_REFRESH_KEEP = 40
DEMO_LOGIN_RETRY_DETAIL = "Слишком много запросов демо. Подождите немного."

_login_hits: dict[str, list[float]] = {}
_login_lock = threading.Lock()


def demo_login_allowed(ip: str) -> bool:
    """Sliding window: at most DEMO_LOGIN_PER_IP_HOUR demo logins per IP per hour."""
    now = time.time()
    key = (ip or "").strip() or "unknown"
    cutoff = now - 3600
    with _login_lock:
        hits = [t for t in _login_hits.get(key, []) if t >= cutoff]
        if len(hits) >= DEMO_LOGIN_PER_IP_HOUR:
            _login_hits[key] = hits
            return False
        hits.append(now)
        _login_hits[key] = hits
        if len(_login_hits) > 4000:
            stale = [k for k, v in _login_hits.items() if not v or v[-1] < cutoff]
            for k in stale:
                _login_hits.pop(k, None)
        return True
