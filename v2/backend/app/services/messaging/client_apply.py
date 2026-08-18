"""Apply client-zone updates to a Candidate row (PostgreSQL only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.candidate_write import apply_hr_stage
from app.services.messaging.keyboards import CLIENT_STATUS_META, STATUSES_THAT_CANCEL_MEETING

CLIENT_STATUS_TO_HR_STAGE = {
    "ready": "client_meeting",
    "think": "client_pause",
    "reject": "rejected_client",
    "offer": "offer",
    "started": "started_work",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_tg_callback_id(candidate: models.Candidate) -> str:
    payload = dict(candidate.payload or {})
    existing = str(payload.get("tg_callback_id") or "").strip()
    if existing:
        return existing
    cid = str(candidate.id).replace("-", "")[:8]
    payload["tg_callback_id"] = cid
    candidate.payload = payload
    flag_modified(candidate, "payload")
    return cid


def format_telegram_comment_entry(
    text: str,
    *,
    author: str = "",
    status_key: str | None = None,
) -> str:
    clean = (text or "").strip()
    if not clean:
        return ""
    moment = datetime.now(ZoneInfo("Europe/Moscow"))
    stamp = moment.strftime("%d.%m.%Y, %H:%M")
    author_label = (author or "").strip()
    if author_label.isdigit():
        author_label = f"id:{author_label}"

    body = clean
    if status_key:
        meta = CLIENT_STATUS_META.get(status_key) or {}
        label = meta.get("label") or status_key
        body = f"к статусу «{label}»: {clean}"

    if author_label:
        return f"[{stamp}, {author_label}] {body}"
    return f"[{stamp}] {body}"


def clear_client_meeting(candidate: models.Candidate) -> bool:
    payload = dict(candidate.payload or {})
    had = bool(
        str(payload.get("office_interview_date") or "").strip()
        and str(payload.get("office_interview_time") or "").strip()
    )
    payload["office_interview_date"] = ""
    payload["office_interview_time"] = ""
    payload["remote_interview"] = False
    payload["office_interview"] = False
    payload["meeting_hr_confirmed"] = False
    payload["interview_attendance_status"] = ""
    payload["interview_attendance_morning_date"] = ""
    payload["interview_attendance_morning_last_sent_at"] = ""
    candidate.payload = payload
    flag_modified(candidate, "payload")
    return had


def apply_client_update(
    candidate: models.Candidate,
    *,
    status_key: str | None = None,
    comment: str | None = None,
    append_comment: bool = False,
    office_interview_date: str | None = None,
    office_interview_time: str | None = None,
    remote_interview: bool | None = None,
    office_interview: bool | None = None,
    actor: str = "telegram",
    actor_note: str = "",
) -> None:
    """Mirror Streamlit apply_client_update for PG candidates."""
    note = f"{actor}: {actor_note}" if actor_note else actor
    payload = dict(candidate.payload or {})

    if status_key is not None:
        old_status = candidate.client_status
        if status_key != old_status:
            history = list(payload.get("client_status_history") or [])
            history.append({"status": status_key, "at": _now_iso(), "note": note})
            payload["client_status_history"] = history
            if status_key == "think" and old_status != "think":
                payload["think_long_reminder_sent"] = False
            if old_status == "wait" and status_key != "wait":
                payload["feedback_reminder_last_sent_at"] = ""
        candidate.client_status = status_key
        candidate.status_updated_at = _now_iso()

        if status_key == "reject":
            candidate.payload = payload
            flag_modified(candidate, "payload")
            apply_hr_stage(candidate, "rejected_client", f"отказ в клиентской зоне ({note})")
            payload = dict(candidate.payload or {})
        elif status_key == "offer":
            candidate.payload = payload
            flag_modified(candidate, "payload")
            apply_hr_stage(candidate, "offer", f"оффер в клиентской зоне ({note})")
            payload = dict(candidate.payload or {})
        elif status_key == "started":
            candidate.payload = payload
            flag_modified(candidate, "payload")
            apply_hr_stage(candidate, "started_work", f"вышел на работу ({note})")
            payload = dict(candidate.payload or {})
        elif status_key in ("ready", "think"):
            mapped = CLIENT_STATUS_TO_HR_STAGE.get(status_key)
            if mapped and candidate.hr_stage != mapped:
                candidate.payload = payload
                flag_modified(candidate, "payload")
                label = "Встреча" if status_key == "ready" else "Подумать"
                apply_hr_stage(candidate, mapped, f"статус «{label}» ({note})")
                payload = dict(candidate.payload or {})

        if status_key in STATUSES_THAT_CANCEL_MEETING:
            candidate.payload = payload
            flag_modified(candidate, "payload")
            clear_client_meeting(candidate)
            payload = dict(candidate.payload or {})

        if status_key != old_status and old_status == "think" and status_key != "think":
            from app.services.bitrix.think_followup import clear_think_state as clear_bitrix_think

            candidate.payload = payload
            flag_modified(candidate, "payload")
            clear_bitrix_think(candidate)
            payload = dict(candidate.payload or {})

    if comment is not None:
        text = comment.strip()
        if actor in ("telegram", "client_zone") and text:
            text = format_telegram_comment_entry(
                text,
                author=actor_note,
                status_key=status_key,
            )
        if append_comment and text:
            prev = str(payload.get("client_comment") or "").strip()
            payload["client_comment"] = f"{prev}\n{text}".strip() if prev else text
        elif comment is not None:
            payload["client_comment"] = text

    if office_interview_date is not None:
        payload["office_interview_date"] = office_interview_date.strip()
    if office_interview_time is not None:
        payload["office_interview_time"] = office_interview_time.strip()
    if remote_interview is not None:
        payload["remote_interview"] = bool(remote_interview)
    if office_interview is not None:
        payload["office_interview"] = bool(office_interview)

    if office_interview_date is not None or office_interview_time is not None:
        key = f"{payload.get('office_interview_date') or ''}_{payload.get('office_interview_time') or ''}"
        if payload.get("interview_schedule_key") != key:
            payload["interview_schedule_key"] = key
            payload["interview_reminder_30_sent"] = False
            payload["interview_reminder_10_sent"] = False
            payload["interview_reminder_60_sent"] = False
            payload["meeting_hr_confirmed"] = False
            payload["interview_attendance_status"] = ""
            payload["interview_attendance_morning_date"] = ""
            payload["interview_attendance_morning_last_sent_at"] = ""

    candidate.payload = payload
    flag_modified(candidate, "payload")


def candidate_view_dict(candidate: models.Candidate) -> dict[str, Any]:
    """Flat dict for keyboard/card helpers (payload + top-level fields)."""
    p = dict(candidate.payload or {})
    return {
        "id": str(candidate.id),
        "name": candidate.name,
        "client_status": candidate.client_status,
        "hr_stage": candidate.hr_stage,
        "tg_callback_id": p.get("tg_callback_id") or ensure_tg_callback_id(candidate),
        "office_interview_date": p.get("office_interview_date") or "",
        "office_interview_time": p.get("office_interview_time") or "",
        "remote_interview": bool(p.get("remote_interview")),
        "office_interview": bool(p.get("office_interview")),
        "client_comment": p.get("client_comment") or "",
        "hr_comment": p.get("hr_comment") or "",
        "resume_link": p.get("resume_link") or "",
        "hh_resume_link": p.get("hh_resume_link") or "",
        "video_link": p.get("video_link") or "",
        "portfolio_link": p.get("portfolio_link") or "",
        "task_link": p.get("task_link") or "",
    }
