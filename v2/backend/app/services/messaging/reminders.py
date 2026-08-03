"""Telegram reminder / digest tick (parity with Streamlit telegram_reminders)."""

from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.db import models
from app.services.messaging.telegram_provider import send_html_message

logger = logging.getLogger(__name__)

REMINDER_60_WINDOW = (55, 65)
REMINDER_30_WINDOW = (25, 35)
REMINDER_10_WINDOW = (5, 15)
FEEDBACK_OVERDUE_MIN = timedelta(hours=24)
FEEDBACK_REPEAT_MIN = timedelta(hours=24)
THINK_LONG_MIN = timedelta(days=5)

DIGEST_SCHEDULE = (
    ("tuesday", 1, 18, 0),
    ("friday", 4, 15, 0),
)
DIGEST_TIME_TOLERANCE_MIN = 12
MONDAY_CATCHUP_HOUR = 10
MONDAY_CATCHUP_MINUTE = 0
INTERVIEW_REMINDER_EARLIEST_HOUR = 8
CLIENT_ZONE_STAGES = frozenset(
    {"client_review", "client_meeting", "client_pause", "offer", "started_work"}
)


def _tz() -> ZoneInfo:
    name = (get_settings().telegram_reminder_tz or "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return ZoneInfo("Europe/Moscow")


def _now(now: datetime | None = None) -> datetime:
    tz = _tz()
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def is_reminder_day_off(now: datetime | None = None) -> bool:
    now = _now(now)
    if now.weekday() >= 5:
        return True
    if now.weekday() == 0:
        return now.hour * 60 + now.minute < MONDAY_CATCHUP_HOUR * 60 + MONDAY_CATCHUP_MINUTE
    return False


def is_interview_reminder_allowed(now: datetime | None = None) -> bool:
    now = _now(now)
    if now.weekday() >= 5:
        return False
    return now.hour * 60 + now.minute >= INTERVIEW_REMINDER_EARLIEST_HOUR * 60


def _esc(text: Any) -> str:
    return html.escape(str(text or "").strip())


def _parse_iso(iso_str: Any) -> datetime | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz())
        return dt
    except (ValueError, TypeError):
        return None


def parse_interview_datetime(date_str: Any, time_str: Any, tz: ZoneInfo | None = None) -> datetime | None:
    if not date_str or not time_str:
        return None
    tz = tz or _tz()
    try:
        d = datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d").date()
        t = datetime.strptime(str(time_str).strip()[:5], "%H:%M").time()
        return datetime.combine(d, t, tzinfo=tz)
    except ValueError:
        return None


def format_interview_display(date_str: Any, time_str: Any) -> str:
    dt = parse_interview_datetime(date_str, time_str)
    return dt.strftime("%d.%m.%Y %H:%M") if dt else "—"


def _payload(c: models.Candidate) -> dict:
    return dict(c.payload or {})


def _has_meeting(payload: dict) -> bool:
    return bool(str(payload.get("office_interview_date") or "").strip()) and bool(
        str(payload.get("office_interview_time") or "").strip()
    )


def _meeting_format(payload: dict) -> str:
    parts = []
    if payload.get("remote_interview"):
        parts.append("удалённо")
    if payload.get("office_interview"):
        parts.append("офис")
    return ", ".join(parts)


def _primary_post(
    db: Session, candidate_id, chat_id: str | None
) -> models.MessagingPost | None:
    posts = list(
        db.scalars(
            select(models.MessagingPost)
            .where(
                models.MessagingPost.candidate_id == candidate_id,
                models.MessagingPost.kind.in_(("primary", "task")),
            )
            .order_by(models.MessagingPost.created_at.desc())
        ).all()
    )
    if not posts:
        return None
    if chat_id is None:
        return posts[0]
    for p in posts:
        if str((p.payload or {}).get("chat_id") or "") == str(chat_id):
            return p
        ch = db.get(models.MessagingChannel, p.channel_id)
        if ch and str(ch.external_id) == str(chat_id):
            return p
    return posts[0]


def build_feedback_overdue_message(name: str, vacancy_title: str, days: int) -> str:
    overdue = "более суток" if days <= 1 else f"более {days} суток"
    return (
        f"⏳ <b>{_esc(name)}</b> · 🏢 {_esc(vacancy_title)}\n"
        f"Обратная связь не получена <b>{overdue}</b>.\n"
        f"Изучите карточку выше и выберите статус 👆"
    )


def build_think_long_message(name: str, vacancy_title: str, *, days: int | None = None) -> str:
    if days is not None and days >= 5:
        wait_line = f"Статус «Подумать» без изменений <b>более {days} дн.</b>.\n"
    elif days is not None and days >= 1:
        wait_line = f"Статус «Подумать» без изменений уже <b>{days} дн.</b>.\n"
    elif days is not None:
        wait_line = "Статус «Подумать» — просим принять решение.\n"
    else:
        wait_line = "Напоминаем: статус «Подумать» — просим принять решение.\n"
    return (
        f"⏳ <b>{_esc(name)}</b> · {_esc(vacancy_title)}\n"
        f"{wait_line}"
        f"Нужна оценка или финальный статус."
    )


def build_manual_decide_reminder(name: str, vacancy_title: str, *, days_waiting: int | None) -> str:
    """HR-triggered remind — never claim «5 days» if less time passed."""
    return build_think_long_message(name, vacancy_title, days=days_waiting)


def build_manual_evaluate_reminder(name: str, vacancy_title: str, *, days_waiting: int | None) -> str:
    if days_waiting is not None and days_waiting >= 1:
        return build_feedback_overdue_message(name, vacancy_title, days_waiting)
    return (
        f"📬 <b>{_esc(name)}</b> · {_esc(vacancy_title)}\n"
        f"Напоминаем: кандидат ждёт вашей оценки."
    )


def build_interview_reminder_60_message(c: models.Candidate, vacancy_title: str) -> str:
    p = _payload(c)
    when = format_interview_display(p.get("office_interview_date"), p.get("office_interview_time"))
    fmt = _meeting_format(p)
    fmt_part = f" ({_esc(fmt)})" if fmt else ""
    status = str(p.get("interview_attendance_status") or "").strip()
    if status == "confirmed":
        note = "✅ Кандидат подтвердил встречу"
    elif status == "cancelled_candidate":
        note = "❌ Кандидат отменил встречу"
    elif status == "cancelled_client":
        note = "⛔ Встреча отменена заказчиком"
    else:
        note = "⚠️ Без подтверждения"
    return (
        f"⏰ <b>Через ~1 час встреча с заказчиком</b>\n"
        f"👤 <b>{_esc(c.name)}</b> · 🏢 {_esc(vacancy_title)}\n"
        f"🕐 {when}{fmt_part}\n{note}"
    )


def build_reminder_30_message(c: models.Candidate, vacancy_title: str) -> str:
    p = _payload(c)
    when = format_interview_display(p.get("office_interview_date"), p.get("office_interview_time"))
    lines = [
        "<b>⏰ Через 30 минут собеседование</b>",
        "",
        f"<b>👤 {_esc(c.name)}</b>",
        f"<b>🏢 Вакансия:</b> {_esc(vacancy_title)}",
        f"<b>🕐 {when}</b>",
    ]
    phone = str(p.get("phone") or "").strip()
    if phone:
        lines.append(f"📞 {_esc(phone)}")
    return "\n".join(lines)


def build_reminder_10_message(c: models.Candidate) -> str:
    p = _payload(c)
    when = format_interview_display(p.get("office_interview_date"), p.get("office_interview_time"))
    return (
        f"<b>🔔 Напоминание</b>\n\n"
        f"Через 10 минут собеседование с <b>{_esc(c.name)}</b>\n"
        f"🕐 {when}"
    )


def _mark(candidate: models.Candidate, mark_type: str, *, marked_at: str | None = None, marked_date: str | None = None) -> None:
    p = _payload(candidate)
    if mark_type == "interview_60":
        p["interview_reminder_60_sent"] = True
    elif mark_type == "interview_30":
        p["interview_reminder_30_sent"] = True
    elif mark_type == "interview_10":
        p["interview_reminder_10_sent"] = True
    elif mark_type == "feedback":
        p["feedback_reminder_last_sent_at"] = marked_at or datetime.now().isoformat()
    elif mark_type == "think_long":
        p["think_long_reminder_sent"] = True
    elif mark_type == "attendance_morning":
        p["interview_attendance_morning_date"] = marked_date or ""
        p["interview_attendance_morning_last_sent_at"] = marked_at or datetime.now().isoformat()
    candidate.payload = p
    flag_modified(candidate, "payload")


def collect_reminder_jobs(db: Session, now: datetime | None = None) -> list[dict[str, Any]]:
    now = _now(now)
    quiet = is_reminder_day_off(now)
    jobs: list[dict[str, Any]] = []
    hr_chat = (get_settings().telegram_hr_user_id or "").strip() or None

    vacancies = {
        v.id: v
        for v in db.scalars(select(models.Vacancy).where(models.Vacancy.active.is_(True))).all()
    }
    candidates = list(db.scalars(select(models.Candidate)).all())

    for cand in candidates:
        vacancy = vacancies.get(cand.vacancy_id)
        if not vacancy:
            continue
        chat_id = (vacancy.chat_id or "").strip()
        if not chat_id:
            continue
        p = _payload(cand)
        vac_title = vacancy.title or ""

        if _has_meeting(p) and is_interview_reminder_allowed(now):
            dt = parse_interview_datetime(p.get("office_interview_date"), p.get("office_interview_time"), now.tzinfo)  # type: ignore[arg-type]
            if dt and dt > now:
                minutes = (dt - now).total_seconds() / 60
                post = _primary_post(db, cand.id, chat_id)

                # −60 group (client meeting): only if HR confirmed
                if REMINDER_60_WINDOW[0] <= minutes <= REMINDER_60_WINDOW[1] and not p.get(
                    "interview_reminder_60_sent"
                ):
                    if not p.get("meeting_hr_confirmed"):
                        jobs.append(
                            {
                                "label": f"interview_60_skip:{cand.id}",
                                "candidate_id": cand.id,
                                "mark_type": "interview_60",
                                "skip_send": True,
                            }
                        )
                    elif str(p.get("interview_attendance_status") or "") in (
                        "cancelled_candidate",
                        "cancelled_client",
                    ):
                        jobs.append(
                            {
                                "label": f"interview_60_skip_att:{cand.id}",
                                "candidate_id": cand.id,
                                "mark_type": "interview_60",
                                "skip_send": True,
                            }
                        )
                    elif post:
                        jobs.append(
                            {
                                "chat_id": chat_id,
                                "text": build_interview_reminder_60_message(cand, vac_title),
                                "reply_to_message_id": post.external_message_id,
                                "label": f"interview_60:{cand.id}",
                                "candidate_id": cand.id,
                                "mark_type": "interview_60",
                            }
                        )

                # −30 / −10 to HR DM
                if hr_chat and REMINDER_30_WINDOW[0] <= minutes <= REMINDER_30_WINDOW[1] and not p.get(
                    "interview_reminder_30_sent"
                ):
                    jobs.append(
                        {
                            "chat_id": hr_chat,
                            "text": build_reminder_30_message(cand, vac_title),
                            "label": f"interview_30:{cand.id}",
                            "candidate_id": cand.id,
                            "mark_type": "interview_30",
                        }
                    )
                if hr_chat and REMINDER_10_WINDOW[0] <= minutes <= REMINDER_10_WINDOW[1] and not p.get(
                    "interview_reminder_10_sent"
                ):
                    jobs.append(
                        {
                            "chat_id": hr_chat,
                            "text": build_reminder_10_message(cand),
                            "label": f"interview_10:{cand.id}",
                            "candidate_id": cand.id,
                            "mark_type": "interview_10",
                        }
                    )

        if quiet:
            continue
        if cand.hr_stage not in CLIENT_ZONE_STAGES and cand.client_status == "wait":
            # still allow wait reminders if already in client zone entry
            if cand.hr_stage not in ("client_review", "client_pause", "client_meeting"):
                pass

        post = _primary_post(db, cand.id, chat_id)
        if cand.client_status == "wait" and post and cand.hr_stage in (
            "client_review",
            "client_pause",
            "client_meeting",
        ):
            sent_at = _parse_iso((post.payload or {}).get("sent_at") or post.created_at.isoformat())
            if sent_at:
                elapsed = now - sent_at.astimezone(now.tzinfo)  # type: ignore[arg-type]
                if elapsed >= FEEDBACK_OVERDUE_MIN:
                    last = _parse_iso(p.get("feedback_reminder_last_sent_at"))
                    if last is None or (now - last.astimezone(now.tzinfo)) >= FEEDBACK_REPEAT_MIN:  # type: ignore[arg-type]
                        days = max(1, elapsed.days)
                        jobs.append(
                            {
                                "chat_id": chat_id,
                                "text": build_feedback_overdue_message(cand.name, vac_title, days),
                                "reply_to_message_id": post.external_message_id,
                                "label": f"feedback:{cand.id}",
                                "candidate_id": cand.id,
                                "mark_type": "feedback",
                                "marked_at": now.isoformat(),
                            }
                        )

        if cand.client_status == "think" and not p.get("think_long_reminder_sent") and post:
            updated = _parse_iso(cand.status_updated_at)
            if updated and (now - updated.astimezone(now.tzinfo)) >= THINK_LONG_MIN:  # type: ignore[arg-type]
                jobs.append(
                    {
                        "chat_id": chat_id,
                        "text": build_think_long_message(
                            cand.name,
                            vac_title,
                            days=max(5, (now - updated.astimezone(now.tzinfo)).days),  # type: ignore[arg-type]
                        ),
                        "reply_to_message_id": post.external_message_id,
                        "label": f"think_long:{cand.id}",
                        "candidate_id": cand.id,
                        "mark_type": "think_long",
                    }
                )

    return jobs


def format_vacancy_digest_html(vacancies: list[models.Vacancy], db: Session) -> str:
    lines = ["<b>📊 Сводка по вакансиям</b>", ""]
    for vac in vacancies:
        cands = list(
            db.scalars(select(models.Candidate).where(models.Candidate.vacancy_id == vac.id)).all()
        )
        wait = sum(1 for c in cands if c.client_status == "wait")
        think = sum(1 for c in cands if c.client_status == "think")
        ready = sum(1 for c in cands if c.client_status == "ready")
        lines.append(
            f"<b>{_esc(vac.title)}</b> — ждёт: {wait}, подумать: {think}, встреча: {ready}, всего: {len(cands)}"
        )
    return "\n".join(lines)


def collect_digest_jobs(db: Session, now: datetime | None = None) -> list[dict[str, Any]]:
    now = _now(now)
    today = now.date().isoformat()
    jobs: list[dict[str, Any]] = []
    settings = get_settings()
    # state in org payload
    org = db.scalar(select(models.Organization).limit(1))
    org_payload = dict((org.payload if hasattr(org, "payload") else {}) or {}) if org else {}
    # Organization has no payload — use ImportRun-less store via MessagingChannel metadata or settings file.
    # Use a singleton row approach: store on first MessagingChannel metadata_json["_digest_state"] is messy.
    # Simpler: store digest state in Organization — but no payload column.
    # Use env-less in-memory is bad. Add to a channel metadata under key digest_state globally via settings table.
    # For MVP: store on Organization by extending — skip, use candidate-less JSON in redis? 
    # Simplest for v2: store digest flags in first organization's... we don't have it.
    # Use MessagingChannel with external_id="__digest_state__" synthetic.

    state_ch = db.scalar(
        select(models.MessagingChannel).where(
            models.MessagingChannel.provider == "telegram",
            models.MessagingChannel.external_id == "__digest_state__",
        )
    )
    if not state_ch:
        state_ch = models.MessagingChannel(
            provider="telegram",
            external_id="__digest_state__",
            name="digest state",
            metadata_json={},
        )
        db.add(state_ch)
        db.flush()
    state = dict(state_ch.metadata_json or {})

    vacancies = list(db.scalars(select(models.Vacancy).where(models.Vacancy.active.is_(True))).all())
    by_chat: dict[str, list[models.Vacancy]] = {}
    for v in vacancies:
        cid = (v.chat_id or "").strip()
        if cid:
            by_chat.setdefault(cid, []).append(v)

    for slot_key, weekday, hour, minute in DIGEST_SCHEDULE:
        if now.weekday() != weekday:
            continue
        target = hour * 60 + minute
        if abs(now.hour * 60 + now.minute - target) > DIGEST_TIME_TOLERANCE_MIN:
            continue
        for chat_id, vacs in by_chat.items():
            flag = f"{slot_key}:{chat_id}:{today}"
            if state.get(flag):
                continue
            jobs.append(
                {
                    "chat_id": chat_id,
                    "text": format_vacancy_digest_html(vacs, db),
                    "label": f"digest:{slot_key}:{chat_id}",
                    "digest_flag": flag,
                }
            )
    # stash state channel id for apply
    for j in jobs:
        j["_state_channel_id"] = str(state_ch.id)
    return jobs


def run_reminder_tick(db: Session, *, dry_run: bool = False) -> dict[str, int]:
    settings = get_settings()
    if not settings.messaging_inbound_enabled:
        return {"sent": 0, "skipped": 0, "note": "inbound off"}  # type: ignore[dict-item]

    jobs = collect_reminder_jobs(db) + collect_digest_jobs(db)
    sent = 0
    skipped = 0
    by_id = {c.id: c for c in db.scalars(select(models.Candidate)).all()}

    state_ch = None
    for job in jobs:
        if job.get("skip_send"):
            cand = by_id.get(job.get("candidate_id"))
            if cand and job.get("mark_type"):
                _mark(cand, job["mark_type"], marked_at=job.get("marked_at"))
            skipped += 1
            continue
        if dry_run:
            logger.info("[dry-run] %s", job.get("label"))
            continue
        ok, msg, _mid = send_html_message(
            job["chat_id"],
            job["text"],
            reply_to_message_id=job.get("reply_to_message_id"),
            reply_markup=job.get("reply_markup"),
        )
        if not ok:
            logger.warning("reminder failed %s: %s", job.get("label"), msg)
            continue
        sent += 1
        cand = by_id.get(job.get("candidate_id"))
        if cand and job.get("mark_type"):
            _mark(
                cand,
                job["mark_type"],
                marked_at=job.get("marked_at"),
                marked_date=job.get("marked_date"),
            )
        if job.get("digest_flag"):
            if state_ch is None and job.get("_state_channel_id"):
                import uuid as _uuid

                state_ch = db.get(models.MessagingChannel, _uuid.UUID(job["_state_channel_id"]))
            if state_ch:
                meta = dict(state_ch.metadata_json or {})
                meta[job["digest_flag"]] = True
                state_ch.metadata_json = meta
                flag_modified(state_ch, "metadata_json")

    db.commit()
    return {"sent": sent, "skipped": skipped}
