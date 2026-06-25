"""Дата/время собеседования и Telegram-напоминания HR."""

import html
import json
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

VACANCIES_FILE = "data/vacancies_db.json"
INTERVIEW_STAGE = "interview_scheduled"

REMINDER_30_WINDOW = (25, 35)  # минут до собеседования
REMINDER_10_WINDOW = (5, 15)


def build_time_options():
    options = [""]
    current = time(9, 0)
    end = time(18, 0)
    while current <= end:
        options.append(current.strftime("%H:%M"))
        minutes = current.hour * 60 + current.minute + 30
        current = time(minutes // 60, minutes % 60)
    return options


def schedule_key(date_str, time_str):
    return f"{(date_str or '').strip()}_{(time_str or '').strip()}"


def reset_reminders_if_schedule_changed(cand, date_str, time_str):
    key = schedule_key(date_str, time_str)
    if cand.get("interview_schedule_key") != key:
        cand["interview_schedule_key"] = key
        cand["interview_reminder_30_sent"] = False
        cand["interview_reminder_10_sent"] = False
        cand["interview_reminder_60_sent"] = False
        from interview_attendance import reset_interview_attendance

        reset_interview_attendance(cand)


def sync_interview_calendar(
    cand, vacancy_title, previous_stage=None, keep_calendar_event=False
):
    """
    Синхронизирует событие в Google Calendar.
    keep_calendar_event: не удалять событие при смене этапа с «Назначено собеседование».
    Возвращает (ok, message) — message пустой если действие не требовалось.
    """
    try:
        from google_calendar import (
            create_or_update_interview_event,
            delete_interview_event,
            is_calendar_ready,
        )
    except ImportError:
        return True, ""

    if not is_calendar_ready():
        return True, ""

    current = cand.get("hr_stage")
    if current == INTERVIEW_STAGE:
        dt = parse_interview_datetime(
            cand.get("office_interview_date"),
            cand.get("office_interview_time"),
        )
        if not dt:
            return False, "Не указаны дата и время для календаря"
        tz_name = os.getenv("TELEGRAM_REMINDER_TZ", "Europe/Moscow")
        ok, msg, event_id = create_or_update_interview_event(
            cand, vacancy_title, dt, tz_name
        )
        if ok and event_id:
            cand["calendar_event_id"] = event_id
        return ok, msg

    if previous_stage == INTERVIEW_STAGE or cand.get("calendar_event_id"):
        if keep_calendar_event:
            return True, "Событие в Google Calendar оставлено"
        ok, msg = delete_interview_event(cand)
        return ok, msg

    return True, ""


def validate_interview_schedule(date_str, time_str):
    missing = []
    if not (date_str or "").strip():
        missing.append("Дата первичного собеседования")
    if not (time_str or "").strip():
        missing.append("Время первичного собеседования")
    return missing


def get_timezone():
    tz_name = os.getenv("TELEGRAM_REMINDER_TZ", "Europe/Moscow")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def parse_interview_datetime(date_str, time_str, tz=None):
    if not date_str or not time_str:
        return None
    tz = tz or get_timezone()
    try:
        d = datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d").date()
        t = datetime.strptime(str(time_str).strip()[:5], "%H:%M").time()
        return datetime.combine(d, t, tzinfo=tz)
    except ValueError:
        return None


def format_interview_display(date_str, time_str):
    dt = parse_interview_datetime(date_str, time_str)
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def _esc(text):
    return html.escape(str(text or "").strip())


def build_reminder_30_message(cand, vacancy_title):
    name = _esc(cand.get("name", "Без имени"))
    vac = _esc(vacancy_title)
    when = format_interview_display(
        cand.get("office_interview_date"), cand.get("office_interview_time")
    )
    lines = [
        "<b>⏰ Через 30 минут собеседование</b>",
        "",
        f"<b>👤 {name}</b>",
        f"<b>🏢 Вакансия:</b> {vac}",
        f"<b>🕐 {when}</b>",
    ]
    phone = cand.get("phone", "").strip()
    if phone:
        lines.append(f"📞 {_esc(phone)}")
    resume = cand.get("resume_link", "").strip()
    if resume:
        lines.append(f'📄 <a href="{_esc(resume)}"><b>Резюме</b></a>')
    video = cand.get("video_link", "").strip()
    if video:
        lines.append(f'🎥 <a href="{_esc(video)}"><b>Запись собеседования</b></a>')
    return "\n".join(lines)


def build_reminder_10_message(cand):
    name = _esc(cand.get("name", "кандидатом"))
    when = format_interview_display(
        cand.get("office_interview_date"), cand.get("office_interview_time")
    )
    return (
        f"<b>🔔 Напоминание</b>\n\n"
        f"Через 10 минут собеседование с <b>{name}</b>\n"
        f"🕐 {when}"
    )


def get_hr_telegram_chat_id():
    from telegram_notify import get_hr_user_id
    return get_hr_user_id()


def send_telegram_html(chat_id, text):
    from telegram_notify import send_telegram_html as _send
    ok, msg, _ = _send(chat_id, text)
    if ok:
        return True, "ok"
    return False, msg


def load_vacancies():
    from vacancy_store import load_vacancies_list
    return load_vacancies_list()


def save_vacancies(vacancies):
    from vacancy_store import save_vacancies_list
    save_vacancies_list(vacancies)


def process_interview_reminders(now=None, dry_run=False):
    """Напоминания о собеседованиях через Telegram отключены."""
    return []


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    results = process_interview_reminders(dry_run=dry)
    if results:
        print("\n".join(results))
    else:
        print("Нет напоминаний для отправки.")
