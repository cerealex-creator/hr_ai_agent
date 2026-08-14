"""Auto-advance interview_scheduled → interview_done after meeting start + offset (MSK)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.candidate_write import set_stage
from app.services.messaging.reminders import _now as reminder_now
from app.services.messaging.reminders import parse_interview_datetime

logger = logging.getLogger(__name__)

AUTO_ADVANCE_NOTE = "авто после начала собеседования"
FROM_STAGE = "interview_scheduled"
TO_STAGE = "interview_done"


def _advance_offset() -> timedelta:
    minutes = get_settings().interview_auto_advance_minutes
    return timedelta(minutes=max(0, minutes))


def _has_meeting(payload: dict[str, Any]) -> bool:
    return bool(str(payload.get("office_interview_date") or "").strip()) and bool(
        str(payload.get("office_interview_time") or "").strip()
    )


def should_auto_advance(payload: dict[str, Any], *, now: datetime | None = None) -> bool:
    """True when meeting start (Europe/Moscow) + offset has passed."""
    if not _has_meeting(payload):
        return False
    start = parse_interview_datetime(
        payload.get("office_interview_date"),
        payload.get("office_interview_time"),
    )
    if start is None:
        return False
    now = reminder_now(now)
    return now >= start + _advance_offset()


def run_interview_auto_advance_tick(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Advance candidates stuck on interview_scheduled past meeting start + offset."""
    now = reminder_now(now)
    stats = {"checked": 0, "advanced": 0, "skipped": 0, "errors": 0}

    candidates = list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.hr_stage == FROM_STAGE).limit(500)
        ).all()
    )

    for cand in candidates:
        payload = dict(cand.payload or {})
        if not _has_meeting(payload):
            stats["skipped"] += 1
            continue

        vacancy = db.get(models.Vacancy, cand.vacancy_id)
        if not vacancy or not vacancy.active:
            stats["skipped"] += 1
            continue

        stats["checked"] += 1
        if not should_auto_advance(payload, now=now):
            stats["skipped"] += 1
            continue

        try:
            set_stage(
                db,
                cand,
                hr_stage=TO_STAGE,
                note=AUTO_ADVANCE_NOTE,
            )
            stats["advanced"] += 1
            logger.info(
                "interview auto-advance: candidate=%s vacancy=%s",
                cand.id,
                cand.vacancy_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "interview auto-advance failed: candidate=%s: %s",
                cand.id,
                exc,
            )
            db.rollback()
            stats["errors"] += 1

    return stats
