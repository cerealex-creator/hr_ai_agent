"""Sync interview stage changes with Google Calendar."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.db import models
from app.services.candidate_write import INTERVIEW_STAGE
from app.services.google_calendar import (
    create_or_update_interview_event,
    delete_interview_event,
    is_calendar_ready,
)


def parse_interview_datetime(date_str: str | None, time_str: str | None) -> datetime | None:
    d = (date_str or "").strip()[:10]
    t = (time_str or "").strip()
    if not d or not t:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(f"{d} {t}", fmt)
        except ValueError:
            continue
    try:
        hhmm = t[:5]
        return datetime.strptime(f"{d} {hhmm}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def sync_interview_calendar(
    db: Session,
    candidate: models.Candidate,
    *,
    previous_stage: str | None = None,
    keep_calendar_event: bool = False,
) -> tuple[bool, str]:
    if not is_calendar_ready():
        return True, ""

    vac = db.get(models.Vacancy, candidate.vacancy_id)
    vacancy_title = vac.title if vac else ""
    payload = dict(candidate.payload or {})
    cand_view = {
        "name": candidate.name,
        "phone": payload.get("phone") or "",
        "resume_link": payload.get("resume_link") or "",
        "video_link": payload.get("video_link") or "",
        "hr_comment": payload.get("hr_comment") or "",
        "calendar_event_id": payload.get("calendar_event_id") or "",
    }
    current = candidate.hr_stage
    tz_name = get_settings().telegram_reminder_tz or "Europe/Moscow"

    if current == INTERVIEW_STAGE:
        dt = parse_interview_datetime(
            str(payload.get("office_interview_date") or ""),
            str(payload.get("office_interview_time") or ""),
        )
        if not dt:
            return False, "Не указаны дата и время для календаря"
        try:
            tz = ZoneInfo(tz_name)
            dt = dt.replace(tzinfo=tz)
        except Exception:
            pass
        ok, msg, event_id = create_or_update_interview_event(
            cand_view, vacancy_title, dt, tz_name
        )
        if ok and event_id:
            payload["calendar_event_id"] = event_id
            candidate.payload = payload
            flag_modified(candidate, "payload")
        return ok, msg

    if previous_stage == INTERVIEW_STAGE or cand_view.get("calendar_event_id"):
        if keep_calendar_event:
            return True, "Событие в Google Calendar оставлено"
        ok, msg = delete_interview_event(cand_view)
        if cand_view.get("calendar_event_id") != payload.get("calendar_event_id"):
            payload["calendar_event_id"] = cand_view.get("calendar_event_id") or ""
            candidate.payload = payload
            flag_modified(candidate, "payload")
        elif not cand_view.get("calendar_event_id"):
            payload["calendar_event_id"] = ""
            candidate.payload = payload
            flag_modified(candidate, "payload")
        return ok, msg

    return True, ""
