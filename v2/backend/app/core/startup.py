"""Startup validation (D5 production hardening)."""
from __future__ import annotations

import logging

from app.core.config import Settings

logger = logging.getLogger("hr_api.startup")

_WEAK_JWT = frozenset(
    {
        "",
        "dev-change-me-hr-v2-jwt-secret-min-32b",
        "change-me-long-random",
        "change-me-now",
        "secret",
        "changeme",
        "jwt-secret",
        "your-secret-here",
    }
)


def validate_startup_settings(settings: Settings) -> None:
    """Fail-fast when APP_ENV=production and auth/cookie config is unsafe."""
    env = (settings.app_env or "").strip().lower()
    if env != "production":
        return

    secret = (settings.jwt_secret or "").strip()
    secret_l = secret.lower()
    if len(secret) < 32 or secret_l in _WEAK_JWT or "change-me" in secret_l or "changeme" in secret_l:
        raise RuntimeError(
            "APP_ENV=production: set a strong JWT_SECRET "
            "(≥32 characters, not a default/placeholder)."
        )

    if not settings.auth_cookie_secure:
        raise RuntimeError(
            "APP_ENV=production: AUTH_COOKIE_SECURE must be true (serve UI over HTTPS)."
        )

    same = (settings.auth_cookie_samesite or "lax").strip().lower()
    if same not in {"lax", "strict", "none"}:
        raise RuntimeError("APP_ENV=production: AUTH_COOKIE_SAMESITE must be lax|strict|none")
    if same == "none" and not settings.auth_cookie_secure:
        raise RuntimeError("AUTH_COOKIE_SAMESITE=none requires AUTH_COOKIE_SECURE=true")

    logger.info("production startup checks OK (JWT + cookie secure)")
