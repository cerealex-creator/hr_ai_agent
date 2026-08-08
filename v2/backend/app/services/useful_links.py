"""Per-user useful launcher links (custom buttons only; presets are UI-only)."""
from __future__ import annotations

import re
import uuid
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db import models

_MAX_CUSTOM = 20
_LABEL_MAX = 64
_URL_MAX = 2048


def _normalize_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise ValueError("URL обязателен")
    if len(url) > _URL_MAX:
        raise ValueError("URL слишком длинный")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL должен начинаться с http:// или https://")
    return url


def _normalize_label(raw: str) -> str:
    label = re.sub(r"\s+", " ", (raw or "").strip())
    if not label:
        raise ValueError("Название обязательно")
    if len(label) > _LABEL_MAX:
        raise ValueError(f"Название длиннее {_LABEL_MAX} символов")
    return label


def clean_useful_links(items: list[Any]) -> list[dict[str, str]]:
    if not isinstance(items, list):
        raise ValueError("items должен быть списком")
    if len(items) > _MAX_CUSTOM:
        raise ValueError(f"Не больше {_MAX_CUSTOM} своих кнопок")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError("Каждая ссылка — объект {id, label, url}")
        link_id = str(raw.get("id") or "").strip() or str(uuid.uuid4())
        if link_id in seen:
            raise ValueError("Дублируется id ссылки")
        seen.add(link_id)
        out.append(
            {
                "id": link_id,
                "label": _normalize_label(str(raw.get("label") or "")),
                "url": _normalize_url(str(raw.get("url") or "")),
            }
        )
    return out


def get_user_useful_links(db: Session, user_id: uuid.UUID) -> list[dict[str, str]]:
    row = db.get(models.User, user_id)
    if not row:
        return []
    raw = row.useful_links if isinstance(row.useful_links, list) else []
    try:
        return clean_useful_links(raw)
    except ValueError:
        return []


def set_user_useful_links(
    db: Session, user_id: uuid.UUID, items: list[Any]
) -> list[dict[str, str]]:
    row = db.get(models.User, user_id)
    if not row:
        raise LookupError("user not found")
    cleaned = clean_useful_links(items)
    row.useful_links = cleaned
    db.add(row)
    db.flush()
    return cleaned
