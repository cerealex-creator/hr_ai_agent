"""Утреннее подтверждение явки кандидата и напоминание за час в общий чат."""

from __future__ import annotations

from interview_schedule import format_interview_display, parse_interview_datetime
from telegram_notify import _esc

ATTENDANCE_CONFIRMED = "confirmed"
ATTENDANCE_CANCELLED_CANDIDATE = "cancelled_candidate"
ATTENDANCE_CANCELLED_CLIENT = "cancelled_client"

MORNING_ATTENDANCE_HOUR = 9
MORNING_ATTENDANCE_MINUTE = 0
MORNING_ATTENDANCE_TOLERANCE_MIN = 12


def reset_interview_attendance(candidate):
    candidate["interview_attendance_status"] = ""
    candidate["interview_attendance_morning_date"] = ""


def _meeting_format_label(candidate):
    parts = []
    if candidate.get("remote_interview"):
        parts.append("удалённо")
    if candidate.get("office_interview"):
        parts.append("офис")
    return ", ".join(parts)


def interview_place_line(candidate):
    fmt = _meeting_format_label(candidate)
    if not fmt:
        return ""
    return f"📍 {_esc(fmt)}"


def attendance_status_note(status):
    if status == ATTENDANCE_CONFIRMED:
        return "✅ Кандидат подтвердил встречу"
    if status == ATTENDANCE_CANCELLED_CANDIDATE:
        return "❌ Кандидат отменил встречу"
    if status == ATTENDANCE_CANCELLED_CLIENT:
        return "⛔ Встреча отменена заказчиком"
    return "⚠️ Без подтверждения"


def build_morning_attendance_message(
    candidate,
    vacancy_title,
    *,
    resolved=False,
    status="",
):
    name = _esc(candidate.get("name", "кандидатом"))
    vac = _esc(vacancy_title)
    when = format_interview_display(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    )
    fmt = _meeting_format_label(candidate)
    fmt_part = f" ({_esc(fmt)})" if fmt else ""
    lines = [
        f"<b>☀️ Сегодня собеседование</b>",
        f"👤 <b>{name}</b> · 🏢 {vac}",
        f"🕐 {when}{fmt_part}",
        "",
        "Уточните у кандидата явку на встречу и выберите действие:",
    ]
    if resolved:
        lines = [
            f"<b>☀️ Собеседование сегодня</b>",
            f"👤 <b>{name}</b> · 🏢 {vac}",
            f"🕐 {when}{fmt_part}",
            "",
            f"{attendance_status_note(status)}",
        ]
    return "\n".join(lines)


def build_morning_attendance_keyboard(candidate):
    from vacancy_store import migrate_candidate

    migrate_candidate(candidate)
    callback_id = candidate.get("tg_callback_id") or candidate.get("id")
    return {
        "inline_keyboard": [
            [{"text": "✅ Подтверждаю", "callback_data": f"iac:{callback_id}"}],
            [
                {
                    "text": "❌ Отмена собеседования кандидатом",
                    "callback_data": f"iak:{callback_id}",
                },
            ],
            [
                {
                    "text": "⛔ Отмена собеседования Заказчиком",
                    "callback_data": f"icl:{callback_id}",
                },
            ],
        ]
    }


def build_interview_reminder_60_message(candidate, vacancy_title):
    name = _esc(candidate.get("name", "кандидатом"))
    vac = _esc(vacancy_title)
    when = format_interview_display(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    )
    fmt = _meeting_format_label(candidate)
    fmt_part = f" ({_esc(fmt)})" if fmt else ""
    status = (candidate.get("interview_attendance_status") or "").strip()
    note = attendance_status_note(status)
    return (
        f"<b>⏰ Через час встреча</b>\n"
        f"👤 <b>{name}</b> · 🏢 {vac}\n"
        f"🕐 {when}{fmt_part}\n"
        f"{note}"
    )


def build_candidate_cancelled_group_message(candidate, vacancy_title):
    name = _esc(candidate.get("name", "кандидатом"))
    vac = _esc(vacancy_title)
    when = format_interview_display(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    )
    return (
        f"<b>❌ Кандидат отменил встречу</b>\n"
        f"👤 <b>{name}</b> · 🏢 {vac}\n"
        f"🕐 {when}"
    )


def should_skip_group_reminder_60(candidate):
    status = (candidate.get("interview_attendance_status") or "").strip()
    return status in (ATTENDANCE_CANCELLED_CLIENT, ATTENDANCE_CANCELLED_CANDIDATE)


def _resolve_candidate(candidate_id):
    from client_actions import find_candidate_by_id, find_candidate_by_tg_callback_id

    if len(str(candidate_id)) <= 8:
        return find_candidate_by_tg_callback_id(candidate_id)
    return find_candidate_by_id(candidate_id)


def apply_and_save_interview_attendance(
    candidate_id,
    status,
):
    """Сохраняет ответ HR по явке. В общий чат — только отмена кандидатом (сразу)."""
    from client_actions import has_client_meeting_scheduled
    from telegram_chat_id import resolve_vacancy_chat_id
    from client_actions import get_primary_telegram_post
    from vacancy_store import save_vacancies

    vacancy, candidate, data = _resolve_candidate(candidate_id)
    if not vacancy or not candidate:
        return False, "Кандидат не найден", None, None, None
    if not has_client_meeting_scheduled(candidate):
        return False, "Встреча не назначена", None, None, None

    current = (candidate.get("interview_attendance_status") or "").strip()
    if current:
        return False, "Ответ уже зафиксирован", candidate, vacancy, None

    candidate["interview_attendance_status"] = status
    group_job = None

    if status in (ATTENDANCE_CANCELLED_CLIENT, ATTENDANCE_CANCELLED_CANDIDATE):
        candidate["interview_reminder_60_sent"] = True

    if status == ATTENDANCE_CANCELLED_CANDIDATE:
        chat_id = resolve_vacancy_chat_id(vacancy)
        if chat_id:
            post = get_primary_telegram_post(
                candidate, chat_id, vacancy_id=vacancy.get("id")
            )
            group_job = {
                "chat_id": chat_id,
                "text": build_candidate_cancelled_group_message(
                    candidate, vacancy.get("title", "")
                ),
                "reply_to_message_id": (post or {}).get("message_id"),
                "label": f"attendance_cancel_candidate:{candidate.get('id')}",
            }

    save_vacancies(data)
    labels = {
        ATTENDANCE_CONFIRMED: "Подтверждено",
        ATTENDANCE_CANCELLED_CANDIDATE: "Отмена кандидатом",
        ATTENDANCE_CANCELLED_CLIENT: "Отмена заказчиком",
    }
    return True, labels.get(status, "Сохранено"), candidate, vacancy, group_job


def is_morning_attendance_window(now):
    target = MORNING_ATTENDANCE_HOUR * 60 + MORNING_ATTENDANCE_MINUTE
    current = now.hour * 60 + now.minute
    return abs(current - target) <= MORNING_ATTENDANCE_TOLERANCE_MIN


def collect_morning_attendance_jobs(now, tz, data):
    from client_actions import has_client_meeting_scheduled
    from telegram_notify import get_hr_user_id

    hr_chat_id = get_hr_user_id()
    if not hr_chat_id:
        return []

    today_iso = now.date().isoformat()
    if not is_morning_attendance_window(now):
        return []

    jobs = []
    for vacancy in data.get("vacancies", []):
        if not vacancy.get("active", True):
            continue
        vac_title = vacancy.get("title", "")
        vacancy_id = vacancy.get("id")

        for cand in vacancy.get("candidates", []):
            from vacancy_store import migrate_candidate

            migrate_candidate(cand)
            if not has_client_meeting_scheduled(cand):
                continue
            dt = parse_interview_datetime(
                cand.get("office_interview_date"),
                cand.get("office_interview_time"),
                tz=tz,
            )
            if not dt or dt.date().isoformat() != today_iso:
                continue
            if cand.get("interview_attendance_morning_date") == today_iso:
                continue

            status = (cand.get("interview_attendance_status") or "").strip()
            resolved = bool(status)
            jobs.append({
                "chat_id": hr_chat_id,
                "text": build_morning_attendance_message(
                    cand,
                    vac_title,
                    resolved=resolved,
                    status=status,
                ),
                "reply_markup": None if resolved else build_morning_attendance_keyboard(cand),
                "label": f"attendance_morning:{cand.get('id')}",
                "vacancy_id": vacancy_id,
                "candidate_id": cand.get("id"),
                "mark_type": "attendance_morning",
                "marked_at": today_iso,
            })
    return jobs
