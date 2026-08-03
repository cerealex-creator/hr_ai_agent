"""Morning attendance ping + HR meeting confirm (Streamlit interview_attendance / client_actions parity)."""

from __future__ import annotations

import html
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.messaging.reminders import (
    _has_meeting,
    _now,
    _payload,
    format_interview_display,
    parse_interview_datetime,
)

MORNING_ATTENDANCE_HOUR = 9
MORNING_ATTENDANCE_MINUTE = 0
MORNING_ATTENDANCE_REPEAT_MIN = 30


def _esc(text: Any) -> str:
    return html.escape(str(text or "").strip())


def attendance_keyboard(callback_id: str) -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Подтверждаю", "callback_data": f"iac:{callback_id}"}],
            [
                {
                    "text": "❌ Отмена собеседования кандидатом",
                    "callback_data": f"iak:{callback_id}",
                }
            ],
            [
                {
                    "text": "⛔ Отмена собеседования Заказчиком",
                    "callback_data": f"icl:{callback_id}",
                }
            ],
        ]
    }


def hr_confirm_keyboard(callback_id: str) -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Подтвердить встречу", "callback_data": f"mhc:{callback_id}"}]
        ]
    }


def build_morning_attendance_message(
    candidate: models.Candidate,
    vacancy_title: str,
    *,
    repeat: bool = False,
) -> str:
    p = _payload(candidate)
    when = format_interview_display(p.get("office_interview_date"), p.get("office_interview_time"))
    fmt_parts = []
    if p.get("remote_interview"):
        fmt_parts.append("удалённо")
    if p.get("office_interview"):
        fmt_parts.append("офис")
    fmt_part = f" ({_esc(', '.join(fmt_parts))})" if fmt_parts else ""
    lines = []
    if repeat:
        lines.append("🔁 <b>Напоминание:</b> ответ по явке ещё не получен.\n")
    lines.extend(
        [
            "<b>☀️ Сегодня собеседование</b>",
            f"👤 <b>{_esc(candidate.name)}</b> · 🏢 {_esc(vacancy_title)}",
            f"🕐 {when}{fmt_part}",
            "",
            "Уточните у кандидата явку на встречу и выберите действие:",
        ]
    )
    return "\n".join(lines)


def build_hr_confirm_message(candidate: models.Candidate, vacancy_title: str) -> str:
    p = _payload(candidate)
    when = format_interview_display(p.get("office_interview_date"), p.get("office_interview_time"))
    return (
        f"<b>📅 Встреча назначена заказчиком</b>\n"
        f"👤 <b>{_esc(candidate.name)}</b> · 🏢 {_esc(vacancy_title)}\n"
        f"🕐 {when}\n\n"
        f"Подтвердите встречу, когда согласуете с кандидатом."
    )


def should_send_morning_attendance(candidate: models.Candidate, now: datetime | None = None) -> bool:
    now = _now(now)
    p = _payload(candidate)
    if not _has_meeting(p):
        return False
    if not p.get("meeting_hr_confirmed"):
        return False
    if str(p.get("interview_attendance_status") or "").strip():
        return False
    dt = parse_interview_datetime(p.get("office_interview_date"), p.get("office_interview_time"))
    if not dt or dt.date() != now.date():
        return False
    # after morning hour
    if now.hour * 60 + now.minute < MORNING_ATTENDANCE_HOUR * 60 + MORNING_ATTENDANCE_MINUTE:
        return False
    morning_date = str(p.get("interview_attendance_morning_date") or "")
    if morning_date == now.date().isoformat():
        last = p.get("interview_attendance_morning_last_sent_at")
        if last:
            try:
                last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=now.tzinfo)
                if (now - last_dt.astimezone(now.tzinfo)) < timedelta(minutes=MORNING_ATTENDANCE_REPEAT_MIN):  # type: ignore[arg-type]
                    return False
            except (ValueError, TypeError):
                return False
        else:
            return False
    return True


def set_attendance_status(candidate: models.Candidate, status: str) -> None:
    p = _payload(candidate)
    p["interview_attendance_status"] = status
    candidate.payload = p
    flag_modified(candidate, "payload")


def set_meeting_hr_confirmed(candidate: models.Candidate, value: bool = True) -> None:
    p = _payload(candidate)
    p["meeting_hr_confirmed"] = bool(value)
    candidate.payload = p
    flag_modified(candidate, "payload")
