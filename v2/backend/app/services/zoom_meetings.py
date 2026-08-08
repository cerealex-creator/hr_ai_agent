"""Create Zoom meetings and attach join_url to candidate payload."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.tenancy import candidate_org_id
from app.services.zoom_oauth import get_access_token, get_zoom_status


class ZoomMeetingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo("Europe/Moscow")
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def create_zoom_meeting(
    db: Session,
    org_id: uuid.UUID,
    *,
    topic: str,
    start_date: str,
    start_time: str,
    duration_minutes: int = 60,
) -> dict[str, Any]:
    """
    Create a scheduled Zoom meeting for the org's connected Zoom user.
    start_date: YYYY-MM-DD, start_time: HH:MM (Europe/Moscow).
    """
    status, msg = get_zoom_status(db, org_id)
    if status != "ready":
        raise ZoomMeetingError(msg or "Zoom не готов", 400)

    access, err = get_access_token(db, org_id)
    if err or not access:
        raise ZoomMeetingError(err or "Нет access_token Zoom", 400)

    date_s = (start_date or "").strip()[:10]
    time_s = (start_time or "").strip()[:5]
    if len(date_s) != 10 or len(time_s) != 5:
        raise ZoomMeetingError("Укажите дату и время встречи", 400)
    try:
        local = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M").replace(tzinfo=_tz())
    except ValueError as exc:
        raise ZoomMeetingError("Некорректные дата/время", 400) from exc

    start_iso = local.strftime("%Y-%m-%dT%H:%M:%S")
    duration = max(15, min(180, int(duration_minutes or 60)))
    body = {
        "topic": (topic or "Встреча").strip()[:200] or "Встреча",
        "type": 2,
        "start_time": start_iso,
        "duration": duration,
        "timezone": "Europe/Moscow",
        "settings": {
            "join_before_host": True,
            "waiting_room": False,
            "mute_upon_entry": True,
        },
    }
    try:
        resp = requests.post(
            "https://api.zoom.us/v2/users/me/meetings",
            headers={
                "Authorization": f"Bearer {access}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=45,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            detail = data.get("message") or data.get("reason") or resp.text[:240]
            raise ZoomMeetingError(f"Zoom API: {detail}", 400)
        join_url = str(data.get("join_url") or "").strip()
        if not join_url:
            raise ZoomMeetingError("Zoom не вернул join_url", 502)
        return {
            "join_url": join_url,
            "start_url": str(data.get("start_url") or "").strip(),
            "meeting_id": data.get("id"),
            "topic": data.get("topic") or topic,
            "start_time": start_iso,
            "duration": duration,
        }
    except ZoomMeetingError:
        raise
    except requests.RequestException as exc:
        raise ZoomMeetingError(f"Сеть Zoom: {exc}", 502) from exc


def schedule_zoom_for_candidate(
    db: Session,
    candidate: models.Candidate,
    *,
    start_date: str,
    start_time: str,
    duration_minutes: int = 60,
    org_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    resolved = org_id or candidate_org_id(db, candidate)
    if not resolved:
        raise ZoomMeetingError("Не удалось определить организацию кандидата", 400)
    topic = f"Встреча: {candidate.name or 'кандидат'}"
    meeting = create_zoom_meeting(
        db,
        resolved,
        topic=topic,
        start_date=start_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
    )
    payload = dict(candidate.payload or {})
    payload["office_interview_date"] = (start_date or "").strip()[:10]
    payload["office_interview_time"] = (start_time or "").strip()[:5]
    payload["remote_interview"] = True
    payload["office_interview"] = False
    payload["meeting_link"] = meeting["join_url"]
    payload["meeting_provider"] = "zoom"
    payload["meeting_provider_label"] = "Zoom"
    payload["zoom_meeting_id"] = meeting.get("meeting_id")
    payload["zoom_start_url"] = meeting.get("start_url") or ""
    candidate.payload = payload
    flag_modified(candidate, "payload")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return meeting
