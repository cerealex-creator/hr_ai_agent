"""Notify HR about client-scheduled meetings (Telegram DM + confirm button)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.messaging.attendance import build_hr_confirm_message, hr_confirm_keyboard
from app.services.messaging.client_apply import ensure_tg_callback_id
from app.services.messaging.telegram_provider import send_html_message

logger = logging.getLogger(__name__)


def notify_hr_meeting_pending(db: Session, candidate: models.Candidate) -> bool:
    """Send HR a Telegram message to confirm the meeting. Returns True if sent."""
    from app.services.messaging.providers.registry import telegram_hr_notify_allowed

    if not telegram_hr_notify_allowed():
        return False
    settings = get_settings()
    hr_chat = (settings.telegram_hr_user_id or "").strip()
    if not hr_chat:
        return False
    vac = db.get(models.Vacancy, candidate.vacancy_id)
    try:
        cid = ensure_tg_callback_id(candidate)
        db.commit()
        ok, msg, _ = send_html_message(
            hr_chat,
            build_hr_confirm_message(candidate, vac.title if vac else ""),
            reply_markup=hr_confirm_keyboard(cid),
        )
        if not ok:
            logger.warning("HR meeting notify failed for %s: %s", candidate.id, msg)
        return bool(ok)
    except Exception as exc:  # noqa: BLE001
        logger.warning("HR meeting notify error for %s: %s", candidate.id, exc)
        return False
