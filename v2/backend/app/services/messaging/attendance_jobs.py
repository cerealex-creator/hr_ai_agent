"""Queue morning attendance DMs into reminder tick marks + immediate send."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.messaging.attendance import (
    attendance_keyboard,
    build_morning_attendance_message,
    should_send_morning_attendance,
)
from app.services.messaging.client_apply import ensure_tg_callback_id
from app.services.messaging.reminders import _mark, _now
from app.services.messaging.telegram_provider import send_html_message

logger = logging.getLogger(__name__)


def collect_and_queue_morning_jobs(db: Session, now: datetime | None = None) -> int:
    """Send morning attendance prompts to HR and mark candidates."""
    settings = get_settings()
    hr_chat = (settings.telegram_hr_user_id or "").strip()
    if not hr_chat:
        return 0
    now = _now(now)
    if now.weekday() >= 5:
        return 0

    sent = 0
    vacancies = {v.id: v for v in db.scalars(select(models.Vacancy)).all()}
    for cand in db.scalars(select(models.Candidate)).all():
        if not should_send_morning_attendance(cand, now):
            continue
        vac = vacancies.get(cand.vacancy_id)
        if not vac:
            continue
        cid = ensure_tg_callback_id(cand)
        repeat = str((cand.payload or {}).get("interview_attendance_morning_date") or "") == now.date().isoformat()
        text = build_morning_attendance_message(cand, vac.title or "", repeat=repeat)
        ok, msg, _ = send_html_message(hr_chat, text, reply_markup=attendance_keyboard(cid))
        if not ok:
            logger.warning("morning attendance failed %s: %s", cand.id, msg)
            continue
        _mark(
            cand,
            "attendance_morning",
            marked_at=now.isoformat(),
            marked_date=now.date().isoformat(),
        )
        sent += 1
    if sent:
        db.commit()
    return sent
