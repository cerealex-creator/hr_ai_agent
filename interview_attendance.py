"""Утреннее подтверждение явки кандидата (личка HR) и напоминание за час в общий чат (только встречи с заказчиком, подтверждённые HR)."""

from __future__ import annotations

from interview_schedule import format_interview_display, parse_interview_datetime
from telegram_notify import _esc

ATTENDANCE_CONFIRMED = "confirmed"
ATTENDANCE_CANCELLED_CANDIDATE = "cancelled_candidate"
ATTENDANCE_CANCELLED_CLIENT = "cancelled_client"

MORNING_ATTENDANCE_HOUR = 9
MORNING_ATTENDANCE_MINUTE = 0
MORNING_ATTENDANCE_REPEAT_MIN = 30


def reset_interview_attendance(candidate):
    candidate["interview_attendance_status"] = ""
    candidate["interview_attendance_morning_date"] = ""
    candidate["interview_attendance_morning_last_sent_at"] = ""


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
    repeat=False,
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
    if repeat:
        lines.insert(0, "🔁 <b>Напоминание:</b> ответ по явке ещё не получен.\n")
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
    """Сохраняет ответ HR по явке. В общий чат — отмена кандидатом только для встреч с заказчиком (подтверждённых HR)."""
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
        from client_actions import is_client_confirmed_group_meeting

        if is_client_confirmed_group_meeting(candidate):
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


def _parse_iso_datetime(raw, tz):
    if not raw:
        return None
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", ""))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def is_morning_attendance_due(cand, now, tz):
    """Нужно ли отправить (или повторить) утреннее напоминание в личку HR."""
    status = (cand.get("interview_attendance_status") or "").strip()
    if status:
        return False
    dt = parse_interview_datetime(
        cand.get("office_interview_date"),
        cand.get("office_interview_time"),
        tz=tz,
    )
    if not dt or dt.date() != now.date():
        return False
    if now >= dt:
        return False
    day_start = now.replace(
        hour=MORNING_ATTENDANCE_HOUR,
        minute=MORNING_ATTENDANCE_MINUTE,
        second=0,
        microsecond=0,
    )
    if now < day_start:
        return False
    last = _parse_iso_datetime(cand.get("interview_attendance_morning_last_sent_at"), tz)
    if last is None or last.date() != now.date():
        return True
    elapsed_min = (now - last).total_seconds() / 60
    return elapsed_min >= MORNING_ATTENDANCE_REPEAT_MIN


def collect_morning_attendance_jobs(now, tz, data):
    from client_actions import has_client_meeting_scheduled
    from telegram_notify import get_hr_user_id

    hr_chat_id = get_hr_user_id()
    if not hr_chat_id:
        return []

    today_iso = now.date().isoformat()
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
            if not is_morning_attendance_due(cand, now, tz):
                continue

            status = (cand.get("interview_attendance_status") or "").strip()
            last = _parse_iso_datetime(
                cand.get("interview_attendance_morning_last_sent_at"), tz
            )
            repeat = last is not None and last.date() == now.date()
            jobs.append({
                "chat_id": hr_chat_id,
                "text": build_morning_attendance_message(
                    cand,
                    vac_title,
                    repeat=repeat,
                ),
                "reply_markup": build_morning_attendance_keyboard(cand),
                "label": f"attendance_morning:{cand.get('id')}",
                "vacancy_id": vacancy_id,
                "candidate_id": cand.get("id"),
                "mark_type": "attendance_morning",
                "marked_at": now.isoformat(),
                "marked_date": today_iso,
            })
    return jobs
