"""Per-user notification preferences (recruiter personal Telegram + channels)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models

# Align with admin digest: Tue 18:00, Fri 15:00 (Europe/Moscow) — see reminders.DIGEST_SCHEDULE
DEFAULT_TELEGRAM_PERIOD = "digest_admin"
DEFAULT_TELEGRAM_TEXT = (
    "📊 Сводка по вакансиям\n\n"
    "Краткая сводка по активным вакансиям и статусам кандидатов у заказчика "
    "(ждёт / подумать / встреча). Расписание по умолчанию — как у дайджеста бота: "
    "вторник 18:00 и пятница 15:00 (Europe/Moscow)."
)

DEFAULT_NOTIFY_PREFS: dict[str, Any] = {
    # Opt-in: user enables calendar in settings and completes OAuth.
    "google_calendar_enabled": False,
    "telegram_enabled": False,
    "telegram_chat_id": "",
    "telegram_period": DEFAULT_TELEGRAM_PERIOD,
    "telegram_text": DEFAULT_TELEGRAM_TEXT,
}


def ensure_notify_prefs_column(db: Session) -> None:
    """Idempotent local bootstrap when Alembic lag / lock."""
    db.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_prefs "
            "JSONB NOT NULL DEFAULT '{}'::jsonb"
        )
    )
    db.commit()


def normalize_notify_prefs(raw: Any) -> dict[str, Any]:
    base = dict(DEFAULT_NOTIFY_PREFS)
    if isinstance(raw, dict):
        if "google_calendar_enabled" in raw:
            base["google_calendar_enabled"] = bool(raw["google_calendar_enabled"])
        if "telegram_enabled" in raw:
            base["telegram_enabled"] = bool(raw["telegram_enabled"])
        if "telegram_chat_id" in raw and raw["telegram_chat_id"] is not None:
            base["telegram_chat_id"] = str(raw["telegram_chat_id"]).strip()
        if "telegram_period" in raw and raw["telegram_period"]:
            base["telegram_period"] = str(raw["telegram_period"]).strip()
        if "telegram_text" in raw and raw["telegram_text"] is not None:
            base["telegram_text"] = str(raw["telegram_text"])
    return base


def get_user_notify_prefs(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    user = db.get(models.User, user_id)
    if not user:
        raise LookupError("User not found")
    return normalize_notify_prefs(getattr(user, "notify_prefs", None) or {})


def set_user_notify_prefs(db: Session, user_id: uuid.UUID, patch: dict[str, Any]) -> dict[str, Any]:
    user = db.get(models.User, user_id)
    if not user:
        raise LookupError("User not found")
    current = normalize_notify_prefs(getattr(user, "notify_prefs", None) or {})
    merged = normalize_notify_prefs({**current, **(patch or {})})
    if merged["telegram_enabled"] and not (merged["telegram_chat_id"] or "").strip():
        # Allow saving enabled=false or chat_id alone; enabling without chat is a warning in UI
        pass
    user.notify_prefs = merged
    flag_modified(user, "notify_prefs")
    db.flush()
    return merged
