"""Фоновые напоминания бота в Telegram-чатах вакансий."""

import html
import logging
from datetime import datetime, timedelta

from models import is_visible_in_client_zone
from vacancy_store import migrate_candidate
from interview_schedule import (
    format_interview_display,
    get_timezone,
    parse_interview_datetime,
    validate_interview_schedule,
)
from client_actions import get_primary_telegram_post, find_vacancies_by_chat_id
from telegram_notify import _esc

logger = logging.getLogger(__name__)

REMINDER_60_WINDOW = (55, 65)
FEEDBACK_OVERDUE_MIN = timedelta(hours=24)
FEEDBACK_REPEAT_MIN = timedelta(hours=24)
THINK_LONG_MIN = timedelta(days=5)

# Вторник 18:00 и пятница 15:00 (часовой пояс TELEGRAM_REMINDER_TZ)
DIGEST_SCHEDULE = (
    ("tuesday", 1, 18, 0),
    ("friday", 4, 15, 0),
)
DIGEST_TIME_TOLERANCE_MIN = 12

# Накопленное за сб–вс отправляем в понедельник с этого времени (TELEGRAM_REMINDER_TZ)
MONDAY_CATCHUP_HOUR = 10
MONDAY_CATCHUP_MINUTE = 0

# Встречи с 09:00 → напоминание «за час» не раньше 08:00
INTERVIEW_REMINDER_EARLIEST_HOUR = 8
INTERVIEW_REMINDER_EARLIEST_MINUTE = 0


def _normalize_now(now=None):
    tz = get_timezone()
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)
    return now


def is_reminder_day_off(now=None):
    """Сб–вс без напоминаний; в понедельник — до 10:00 (накопленное за выходные)."""
    now = _normalize_now(now)
    if now.weekday() >= 5:
        return True
    if now.weekday() == 0:
        return now.hour * 60 + now.minute < MONDAY_CATCHUP_HOUR * 60 + MONDAY_CATCHUP_MINUTE
    return False


def is_interview_reminder_allowed(now=None):
    """Напоминание за ~1 ч до встречи: не в сб–вс и не раньше 08:00."""
    now = _normalize_now(now)
    if now.weekday() >= 5:
        return False
    return (
        now.hour * 60 + now.minute
        >= INTERVIEW_REMINDER_EARLIEST_HOUR * 60 + INTERVIEW_REMINDER_EARLIEST_MINUTE
    )


def _esc_local(text):
    return html.escape(str(text or "").strip())


def _parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(str(iso_str).replace("Z", ""))
    except (ValueError, TypeError):
        return None


def _overdue_days_label(days):
    if days <= 1:
        return "более суток"
    return f"более {days} суток"


def build_interview_reminder_60_message(candidate, vacancy_title):
    name = _esc_local(candidate.get("name", "кандидатом"))
    vac = _esc_local(vacancy_title)
    when = format_interview_display(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    )
    return (
        f"<b>⏰ Через час встреча</b>\n"
        f"👤 <b>{name}</b> · 🏢 {vac}\n"
        f"🕐 {when}"
    )


def build_feedback_overdue_message(candidate, vacancy_title, days):
    name = _esc_local(candidate.get("name", "кандидатом"))
    vac = _esc_local(vacancy_title)
    overdue = _overdue_days_label(days)
    return (
        f"⏳ <b>{name}</b> · 🏢 {vac}\n"
        f"Обратная связь не получена <b>{overdue}</b>.\n"
        f"Изучите карточку выше и выберите статус 👆"
    )


def build_think_long_message(candidate, vacancy_title):
    name = _esc_local(candidate.get("name", "кандидатом"))
    vac = _esc_local(vacancy_title)
    return (
        f"🟡 <b>{name}</b> · 🏢 {vac}\n"
        f"Статус «Подумать» без изменений <b>более 5 дней</b>.\n"
        f"Пожалуйста, обновите решение по карточке выше 👆"
    )


def _candidate_has_meeting(cand):
    return not validate_interview_schedule(
        cand.get("office_interview_date"),
        cand.get("office_interview_time"),
    )


def _apply_job_mark(data, job):
    for vacancy in data.get("vacancies", []):
        if vacancy.get("id") != job.get("vacancy_id"):
            continue
        for cand in vacancy.get("candidates", []):
            if cand.get("id") != job.get("candidate_id"):
                continue
            migrate_candidate(cand)
            mark = job.get("mark_type")
            if mark == "interview_60":
                cand["interview_reminder_60_sent"] = True
            elif mark == "feedback":
                cand["feedback_reminder_last_sent_at"] = job.get("marked_at", datetime.now().isoformat())
            elif mark == "think_long":
                cand["think_long_reminder_sent"] = True
            return True
    return False


def collect_reminder_jobs(now=None):
    from vacancy_store import load_vacancies

    now = _normalize_now(now)
    tz = now.tzinfo
    data = load_vacancies()
    quiet = is_reminder_day_off(now)

    jobs = []

    for vacancy in data.get("vacancies", []):
        if not vacancy.get("active", True):
            continue
        from telegram_chat_id import resolve_vacancy_chat_id

        chat_id = resolve_vacancy_chat_id(vacancy)
        if not chat_id:
            continue
        vac_title = vacancy.get("title", "")
        vacancy_id = vacancy.get("id")

        for cand in vacancy.get("candidates", []):
            migrate_candidate(cand)
            cand_id = cand.get("id")

            if _candidate_has_meeting(cand) and is_interview_reminder_allowed(now):
                dt = parse_interview_datetime(
                    cand.get("office_interview_date"),
                    cand.get("office_interview_time"),
                    tz=tz,
                )
                if dt and dt > now:
                    minutes = (dt - now).total_seconds() / 60
                    if (
                        REMINDER_60_WINDOW[0] <= minutes <= REMINDER_60_WINDOW[1]
                        and not cand.get("interview_reminder_60_sent")
                    ):
                        post = get_primary_telegram_post(
                            cand, chat_id, vacancy_id=vacancy_id
                        )
                        if post:
                            jobs.append({
                                "chat_id": chat_id,
                                "text": build_interview_reminder_60_message(cand, vac_title),
                                "reply_to_message_id": post.get("message_id"),
                                "label": f"interview_60:{cand_id}",
                                "vacancy_id": vacancy_id,
                                "candidate_id": cand_id,
                                "mark_type": "interview_60",
                            })

            if quiet:
                continue

            if not is_visible_in_client_zone(cand):
                continue

            post = get_primary_telegram_post(cand, chat_id, vacancy_id=vacancy_id)

            if cand.get("client_status") == "wait" and post:
                sent_at = _parse_iso(post.get("sent_at"))
                if sent_at:
                    if sent_at.tzinfo is None:
                        sent_at = sent_at.replace(tzinfo=tz)
                    elapsed = now - sent_at.astimezone(tz)
                    if elapsed >= FEEDBACK_OVERDUE_MIN:
                        last = _parse_iso(cand.get("feedback_reminder_last_sent_at"))
                        if last and last.tzinfo is None:
                            last = last.replace(tzinfo=tz)
                        if last is None or (now - last.astimezone(tz)) >= FEEDBACK_REPEAT_MIN:
                            days = max(1, elapsed.days)
                            jobs.append({
                                "chat_id": chat_id,
                                "text": build_feedback_overdue_message(cand, vac_title, days),
                                "reply_to_message_id": post.get("message_id"),
                                "label": f"feedback:{cand_id}",
                                "vacancy_id": vacancy_id,
                                "candidate_id": cand_id,
                                "mark_type": "feedback",
                                "marked_at": now.isoformat(),
                            })

            if (
                cand.get("client_status") == "think"
                and not cand.get("think_long_reminder_sent")
                and post
            ):
                updated = _parse_iso(cand.get("status_updated_at"))
                if updated:
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=tz)
                    if (now - updated.astimezone(tz)) >= THINK_LONG_MIN:
                        jobs.append({
                            "chat_id": chat_id,
                            "text": build_think_long_message(cand, vac_title),
                            "reply_to_message_id": post.get("message_id"),
                            "label": f"think_long:{cand_id}",
                            "vacancy_id": vacancy_id,
                            "candidate_id": cand_id,
                            "mark_type": "think_long",
                        })

    return jobs, data


def _in_digest_time_window(now, hour, minute):
    target = hour * 60 + minute
    current = now.hour * 60 + now.minute
    return abs(current - target) <= DIGEST_TIME_TOLERANCE_MIN


def collect_scheduled_digest_jobs(now=None):
    """Сводки по расписанию: вторник 18:00, пятница 15:00."""
    from vacancy_store import load_vacancies
    from telegram_chat_stats import format_chat_digest_html, group_active_vacancies_by_chat
    from telegram_scheduler_state import digest_already_sent_today, mark_digest_sent

    tz = get_timezone()
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)

    today_iso = now.date().isoformat()
    jobs = []
    data = load_vacancies()
    vacancies = data.get("vacancies", [])
    by_chat = group_active_vacancies_by_chat(vacancies)

    for slot_key, weekday, hour, minute in DIGEST_SCHEDULE:
        if now.weekday() != weekday:
            continue
        if not _in_digest_time_window(now, hour, minute):
            continue

        for chat_id, chat_vacancies in by_chat.items():
            if digest_already_sent_today(chat_id, slot_key, today_iso):
                continue
            if not chat_vacancies:
                continue
            jobs.append({
                "chat_id": chat_id,
                "text": format_chat_digest_html(chat_vacancies),
                "label": f"digest:{slot_key}:{chat_id}",
                "slot_key": slot_key,
                "today_iso": today_iso,
            })

    return jobs


async def run_reminder_tick(bot, *, dry_run=False):
    jobs, data = collect_reminder_jobs()
    digest_jobs = collect_scheduled_digest_jobs()
    jobs = list(jobs) + [
        {**j, "mark_type": None} for j in digest_jobs
    ]
    sent = 0
    for job in jobs:
        if dry_run:
            logger.info("[dry-run] %s", job["label"])
            continue
        try:
            await bot.send_message(
                job["chat_id"],
                job["text"],
                parse_mode="HTML",
                reply_to_message_id=job.get("reply_to_message_id"),
                disable_web_page_preview=True,
            )
            if job.get("mark_type"):
                _apply_job_mark(data, job)
            elif job.get("slot_key"):
                from telegram_scheduler_state import mark_digest_sent

                mark_digest_sent(job["chat_id"], job["slot_key"], job["today_iso"])
            sent += 1
            logger.info("Напоминание отправлено: %s", job["label"])
        except Exception as exc:
            logger.warning("Не удалось отправить %s: %s", job["label"], exc)

    if sent and not dry_run:
        from vacancy_store import save_vacancies
        save_vacancies(data)

    return sent


def collect_pending_candidates(chat_id, vacancy_id=None):
    vacancies = find_vacancies_by_chat_id(chat_id)
    if vacancy_id is not None:
        vacancies = [v for v in vacancies if v.get("id") == vacancy_id]

    result = []
    for vacancy in vacancies:
        for cand in vacancy.get("candidates", []):
            migrate_candidate(cand)
            if not is_visible_in_client_zone(cand):
                continue
            if cand.get("client_status") != "wait":
                continue
            from telegram_chat_id import resolve_vacancy_chat_id

            post = get_primary_telegram_post(
                cand,
                resolve_vacancy_chat_id(vacancy, chat_id),
                vacancy_id=vacancy.get("id"),
            )
            result.append({"vacancy": vacancy, "candidate": cand, "post": post})
    return result


def format_pending_list_html(items, *, show_vacancy=False):
    from telegram_workflow import telegram_message_link

    if not items:
        return "✅ Нет кандидатов, ожидающих оценки."

    lines = ["<b>⏳ Ждут оценки</b>", ""]
    for idx, item in enumerate(items, 1):
        cand = item["candidate"]
        vac = item["vacancy"]
        name = _esc(cand.get("name", "Без имени"))
        post = item.get("post")
        if show_vacancy and vac.get("title"):
            lines.append(f"{idx}. <b>{name}</b> — 🏢 {_esc(vac['title'])}")
        else:
            lines.append(f"{idx}. <b>{name}</b>")
        if post and post.get("message_id"):
            link = telegram_message_link(post.get("chat_id"), post["message_id"])
            lines.append(f'   <a href="{link}">Перейти к карточке</a>')
        lines.append("")
    return "\n".join(lines).strip()


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    jobs, _ = collect_reminder_jobs()
    if jobs:
        for j in jobs:
            print(f"[{j['label']}]\n{j['text']}\n")
    else:
        print("Нет напоминаний для отправки.")
