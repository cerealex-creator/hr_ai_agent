"""Signed decision tokens for Bitrix task description links."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from app.services.app_settings import get_bitrix, set_bitrix

OUR_STATUSES = frozenset({"ready", "think", "reject", "offer"})
STATUS_LABELS = {
    "ready": "Встреча",
    "think": "Подумать",
    "reject": "Отказ",
    "offer": "Оффер",
}
STATUS_ICONS = {
    "ready": "🟢",
    "think": "🟡",
    "reject": "🔴",
    "offer": "🟣",
}
# Tokens valid long enough for a hiring cycle.
DEFAULT_TTL_SEC = 60 * 60 * 24 * 60  # 60 days


def ensure_decide_secret() -> str:
    cfg = get_bitrix()
    existing = str(cfg.get("decide_secret") or "").strip()
    if existing:
        return existing
    secret = secrets.token_urlsafe(32)
    set_bitrix({"decide_secret": secret})
    return secret


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def make_decide_token(
    *,
    candidate_id: str,
    status_key: str,
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> str:
    if status_key not in OUR_STATUSES:
        raise ValueError(f"bad status: {status_key}")
    secret = ensure_decide_secret()
    payload = {
        "c": str(candidate_id),
        "s": status_key,
        "e": int(time.time()) + max(3600, ttl_sec),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64url(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def parse_decide_token(token: str) -> dict[str, Any]:
    raw = (token or "").strip()
    if "." not in raw:
        raise ValueError("invalid token")
    body, sig = raw.rsplit(".", 1)
    secret = ensure_decide_secret()
    expect = _b64url(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expect, sig):
        raise ValueError("bad signature")
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("bad payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("bad payload")
    cid = str(payload.get("c") or "").strip()
    status = str(payload.get("s") or "").strip()
    exp = int(payload.get("e") or 0)
    if not cid or status not in OUR_STATUSES:
        raise ValueError("bad claims")
    if exp and exp < int(time.time()):
        raise ValueError("token expired")
    return {"candidate_id": cid, "status_key": status, "exp": exp}


def public_api_base() -> str:
    return str(get_bitrix().get("public_api_base") or "").strip().rstrip("/")


def build_decide_url(*, candidate_id: str, status_key: str) -> str | None:
    base = public_api_base()
    if not base:
        return None
    token = make_decide_token(candidate_id=candidate_id, status_key=status_key)
    return f"{base}/integrations/bitrix/decide?{urlencode({'t': token})}"
