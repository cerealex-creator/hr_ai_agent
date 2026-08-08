"""Per-user candidate intake channel preferences."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models

DEFAULT_CANDIDATE_INTAKE: dict[str, bool] = {
    "manual": True,
    "file_upload": True,
    "file_link": False,
    "disk_public_sync": False,
    "disk_inbox": False,
}
CANDIDATE_INTAKE_CORE = frozenset({"manual", "file_upload"})
CANDIDATE_INTAKE_OPTIONAL = frozenset({"file_link", "disk_public_sync", "disk_inbox"})
CANDIDATE_INTAKE_KEYS = tuple(DEFAULT_CANDIDATE_INTAKE.keys())
CANDIDATE_INTAKE_LABELS: dict[str, str] = {
    "manual": "Вручную",
    "file_upload": "Из файла",
    "file_link": "По ссылке на файл",
    "disk_public_sync": "Синхронизация с папкой вакансии",
    "disk_inbox": "Роутинг из inbox",
}


def ensure_candidate_intake_column(db: Session) -> None:
    """Idempotent local bootstrap when Alembic lag / lock."""
    db.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS candidate_intake "
            "JSONB NOT NULL DEFAULT '{}'::jsonb"
        )
    )
    db.commit()


def normalize_candidate_intake(raw: Any) -> dict[str, bool]:
    base = {k: bool(v) for k, v in DEFAULT_CANDIDATE_INTAKE.items()}
    if isinstance(raw, dict):
        for key in CANDIDATE_INTAKE_OPTIONAL:
            if key in raw:
                base[key] = bool(raw.get(key))
    for key in CANDIDATE_INTAKE_CORE:
        base[key] = True
    return base


def get_user_candidate_intake(db: Session, user_id: uuid.UUID) -> dict[str, bool]:
    user = db.get(models.User, user_id)
    if not user:
        raise LookupError("User not found")
    return normalize_candidate_intake(getattr(user, "candidate_intake", None) or {})


def set_user_candidate_intake(
    db: Session, user_id: uuid.UUID, patch: dict[str, Any] | None
) -> dict[str, bool]:
    user = db.get(models.User, user_id)
    if not user:
        raise LookupError("User not found")
    cur = normalize_candidate_intake(getattr(user, "candidate_intake", None) or {})
    if isinstance(patch, dict):
        for key in CANDIDATE_INTAKE_OPTIONAL:
            if key in patch:
                cur[key] = bool(patch.get(key))
    for key in CANDIDATE_INTAKE_CORE:
        cur[key] = True
    user.candidate_intake = cur
    flag_modified(user, "candidate_intake")
    db.flush()
    return cur


def effective_candidate_intake(*, is_owner: bool, stored: dict[str, bool] | None = None) -> dict[str, bool]:
    """Admin always has every channel; others use personal defaults/settings."""
    if is_owner:
        return {k: True for k in CANDIDATE_INTAKE_KEYS}
    return normalize_candidate_intake(stored)


def require_candidate_intake_channel(channel: str, *, is_owner: bool, stored: dict[str, bool] | None) -> None:
    flags = effective_candidate_intake(is_owner=is_owner, stored=stored)
    if not flags.get(channel):
        label = CANDIDATE_INTAKE_LABELS.get(channel, channel)
        raise ValueError(
            f"Канал «{label}» отключён в настройках способов добавления кандидатов."
        )
