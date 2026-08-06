"""Persist HH OAuth tokens under legacy data dir (audit M3).

Env (HH_ACCESS_TOKEN / HH_REFRESH_TOKEN) wins for bootstrap; after refresh
we write ``hh_oauth.json`` so rotated tokens survive process restart.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings

TOKEN_FILENAME = "hh_oauth.json"


def _token_path() -> Path:
    return get_settings().resolved_legacy_data_dir() / TOKEN_FILENAME


def _read_file() -> dict[str, Any]:
    path = _token_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_hh_tokens(
    *,
    access_token: str,
    refresh_token: str | None = None,
) -> Path:
    """Write access (+ optional refresh). Keeps previous refresh if not passed."""
    access = (access_token or "").strip()
    if not access:
        raise ValueError("empty access_token")
    prev = _read_file()
    refresh = (refresh_token or "").strip() or str(prev.get("refresh_token") or "").strip()
    payload = {
        "access_token": access,
        "refresh_token": refresh,
        "saved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def get_hh_access_token(settings: Settings | None = None) -> str:
    """Prefer persisted file (rotated after refresh); fall back to env."""
    file_tok = str(_read_file().get("access_token") or "").strip()
    if file_tok:
        return file_tok
    s = settings or get_settings()
    return (s.hh_access_token or "").strip()


def get_hh_refresh_token(settings: Settings | None = None) -> str:
    file_tok = str(_read_file().get("refresh_token") or "").strip()
    if file_tok:
        return file_tok
    s = settings or get_settings()
    return (s.hh_refresh_token or "").strip()


def apply_tokens_to_settings(
    settings: Settings,
    *,
    access_token: str,
    refresh_token: str | None = None,
) -> None:
    """Update in-memory Settings (lru_cached) so later HhClient() sees new tokens."""
    access = (access_token or "").strip()
    if access:
        settings.hh_access_token = access
    if refresh_token is not None:
        refresh = (refresh_token or "").strip()
        if refresh:
            settings.hh_refresh_token = refresh
