"""Candidate funnel writes for v2 (PostgreSQL only — does not touch Streamlit data/)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models

HR_STAGES: dict[str, str] = {
    "resume_screening": "Отсев резюме",
    "primary_contact": "Первичный контакт",
    "no_response_3d": "Кандидат не отвечает более 3 дней",
    "interview_scheduled": "Собеседование назначено",
    "interview_done": "Собеседование проведено",
    "test_task": "Тестовое задание",
    "client_review": "На оценке у заказчика",
    "client_pause": "Пауза",
    "client_meeting": "Встреча с заказчиком",
    "offer": "Оффер",
    "internship": "Выход на стажировку",
    "started_work": "Вышел на работу",
    "rejected": "Отказ",
    "archived": "Архив",
    "rejected_candidate": "Отказ кандидата",
    "rejected_client": "Отказ заказчика",
    "rejected_hr": "Отказ мой",
    "rejected_vacancy_closed": "Отказ: вакансия закрыта",
}

CLIENT_ZONE_ENTRY_STAGE = "client_review"
INTERVIEW_STAGE = "interview_scheduled"

HR_STAGE_TO_CLIENT_STATUS = {
    "client_meeting": "ready",
    "client_pause": "think",
    "offer": "offer",
    "started_work": "started",
    "rejected_client": "reject",
}

CLIENT_STATUS_TO_HR_STAGE = {
    "ready": "client_meeting",
    "think": "client_pause",
    "reject": "rejected_client",
    "offer": "offer",
    "started": "started_work",
}

# Payload keys editable via PATCH (plus top-level name/hr columns separately)
PATCHABLE_PAYLOAD_FIELDS = (
    "phone",
    "email",
    "age",
    "city",
    "metro",
    "salary_expected",
    "resume_link",  # Yandex PDF (opened resume)
    "hh_resume_link",  # HH link (often without contacts until opened manually)
    "portfolio_link",
    "video_link",
    "task_link",
    "hr_comment",
    "transcript",
    "interview_eval_notes",
    "questionnaire_recruiter_notes",
    "office_interview_date",
    "office_interview_time",
    "remote_interview",
    "office_interview",
    "meeting_link",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _reached_hr_stage(payload: dict, current_stage: str, target: str) -> bool:
    if current_stage == target:
        return True
    return any(
        isinstance(e, dict) and e.get("stage") == target
        for e in (payload.get("hr_stage_history") or [])
    )


def apply_hr_stage(
    candidate: models.Candidate,
    new_stage: str,
    note: str = "",
) -> str | None:
    """Mirror Streamlit set_hr_stage. Returns previous stage (or None if unchanged)."""
    if new_stage not in HR_STAGES:
        raise ValueError(f"Неизвестный этап: {new_stage}")
    old = candidate.hr_stage
    payload = dict(candidate.payload or {})
    note_text = (note or "").strip()
    if old == new_stage:
        if note_text:
            history = list(payload.get("hr_stage_history") or [])
            history.append({"stage": new_stage, "at": _now_iso(), "note": note_text})
            payload["hr_stage_history"] = history
            candidate.payload = payload
            flag_modified(candidate, "payload")
        return None
    candidate.hr_stage = new_stage
    history = list(payload.get("hr_stage_history") or [])
    history.append({"stage": new_stage, "at": _now_iso(), "note": note_text})
    payload["hr_stage_history"] = history

    if new_stage == CLIENT_ZONE_ENTRY_STAGE and old != CLIENT_ZONE_ENTRY_STAGE:
        candidate.client_status = "wait"
        candidate.status_updated_at = _now_iso()
        candidate.payload = payload
        flag_modified(candidate, "payload")
        from app.services.messaging.client_apply import clear_client_meeting

        clear_client_meeting(candidate)
        payload = dict(candidate.payload or {})
    elif _reached_hr_stage(payload, new_stage, CLIENT_ZONE_ENTRY_STAGE):
        mapped = HR_STAGE_TO_CLIENT_STATUS.get(new_stage)
        if mapped and candidate.client_status != mapped:
            candidate.client_status = mapped
            candidate.status_updated_at = _now_iso()

    candidate.payload = payload
    flag_modified(candidate, "payload")
    return old


def suggested_hr_stage_from_client_status(candidate: models.Candidate) -> str | None:
    mapped = CLIENT_STATUS_TO_HR_STAGE.get((candidate.client_status or "").strip())
    if not mapped or mapped == candidate.hr_stage:
        return None
    return mapped


def validate_interview_fields(payload: dict, stage: str) -> list[str]:
    if stage != INTERVIEW_STAGE:
        return []
    missing: list[str] = []
    if not str(payload.get("office_interview_date") or "").strip():
        missing.append("дата собеседования")
    if not str(payload.get("office_interview_time") or "").strip():
        missing.append("время собеседования")
    return missing


def patch_candidate(
    candidate: models.Candidate,
    *,
    name: str | None = None,
    fields: dict[str, Any] | None = None,
) -> models.Candidate:
    payload = dict(candidate.payload or {})
    fields = fields or {}
    if name is not None:
        candidate.name = name.strip()
    for key in PATCHABLE_PAYLOAD_FIELDS:
        if key not in fields:
            continue
        val = fields[key]
        if val is None:
            payload[key] = ""
        elif isinstance(val, str):
            payload[key] = val.strip()
        else:
            payload[key] = val
    from app.services.meeting_links import maybe_attach_meeting_link

    payload = maybe_attach_meeting_link(payload)
    candidate.payload = payload
    flag_modified(candidate, "payload")
    return candidate


def create_candidate(
    db: Session,
    *,
    vacancy_id: int,
    name: str = "",
    fields: dict[str, Any] | None = None,
) -> models.Candidate:
    now = _now_iso()
    fields = fields or {}
    payload: dict[str, Any] = {
        "phone": "",
        "age": "",
        "city": "",
        "metro": "",
        "salary_expected": "",
        "resume_link": "",
        "hh_resume_link": "",
        "portfolio_link": "",
        "video_link": "",
        "task_link": "",
        "hr_comment": "",
        "transcript": "",
        "interview_eval_notes": "",
        "questionnaire_recruiter_notes": "",
        "office_interview_date": "",
        "office_interview_time": "",
        "client_comment": "",
        "photo_url": "",
        "ai_score": None,
        "ai_comment": "",
        "ai_comment_sections": {},
        "hr_stage_history": [],
        "cold_screening": False,
        "source": "manual",
        "viewed": False,
    }
    for key in PATCHABLE_PAYLOAD_FIELDS:
        if key in fields and fields[key] is not None:
            payload[key] = str(fields[key]).strip() if isinstance(fields[key], str) else fields[key]
    display = (name or "").strip() or "Новый кандидат"
    cand = models.Candidate(
        id=uuid.uuid4(),
        vacancy_id=vacancy_id,
        name=display,
        hr_stage="resume_screening",
        client_status="wait",
        created_at=now,
        status_updated_at=now,
        payload=payload,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


def delete_candidate(db: Session, candidate: models.Candidate) -> None:
    cand_id = candidate.id
    post_ids = list(
        db.scalars(
            select(models.MessagingPost.id).where(models.MessagingPost.candidate_id == cand_id)
        ).all()
    )
    if post_ids:
        db.execute(
            delete(models.MessagingAction).where(models.MessagingAction.post_id.in_(post_ids))
        )
        db.execute(
            delete(models.MessagingPost).where(models.MessagingPost.id.in_(post_ids))
        )
    db.delete(candidate)
    db.commit()


def set_stage(
    db: Session,
    candidate: models.Candidate,
    *,
    hr_stage: str,
    note: str = "",
    office_interview_date: str | None = None,
    office_interview_time: str | None = None,
    keep_calendar_event: bool = False,
    warranty_start_date: str | None = None,
    warranty_months: int | None = None,
) -> models.Candidate:
    payload = dict(candidate.payload or {})
    if office_interview_date is not None:
        payload["office_interview_date"] = office_interview_date.strip()
    if office_interview_time is not None:
        payload["office_interview_time"] = office_interview_time.strip()
    from app.services.meeting_links import maybe_attach_meeting_link

    payload = maybe_attach_meeting_link(payload)
    candidate.payload = payload
    flag_modified(candidate, "payload")

    missing = validate_interview_fields(payload, hr_stage)
    if missing:
        raise ValueError("Для этапа «Собеседование назначено» укажите: " + ", ".join(missing))

    previous = apply_hr_stage(candidate, hr_stage, note=note)

    from app.services.interview_calendar import sync_interview_calendar
    from app.services.warranty import maybe_apply_warranty_on_stage

    cal_ok, cal_msg = sync_interview_calendar(
        db,
        candidate,
        previous_stage=previous,
        keep_calendar_event=keep_calendar_event,
    )
    if not cal_ok and cal_msg:
        raise ValueError(cal_msg)

    maybe_apply_warranty_on_stage(
        db,
        candidate,
        start_date=warranty_start_date,
        months=warranty_months,
    )

    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate
