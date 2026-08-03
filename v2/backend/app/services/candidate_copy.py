"""Copy candidate into another vacancy (funnel reset, contacts kept)."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db import models


KEEP_FIELDS = (
    "phone",
    "age",
    "city",
    "metro",
    "salary_expected",
    "age_location",
    "resume_link",
    "hh_resume_link",
    "portfolio_link",
    "resume_text",
    "cold_screening",
    "ignore_flags",
    "control_word_status",
    "control_word_match",
    "control_word_note",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def prepare_candidate_copy(
    source: models.Candidate,
    *,
    target_vacancy_id: int,
) -> models.Candidate:
    src = dict(source.payload or {})
    now = _now_iso()
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
        "ai_score": None,
        "ai_comment": "",
        "ai_comment_sections": {},
        "ai_strengths": [],
        "ai_weaknesses": [],
        "ai_profile_requirements_met": {},
        "ai_flags_applied": [],
        "ai_score_source": None,
        "interview_focus_questions": [],
        "interview_questionnaire": [],
        "hr_stage_history": [],
        "client_status_history": [],
        "client_final_verdict": "",
        "cold_screening": False,
        "source": "copy",
        "viewed": False,
        "remote_interview": False,
        "office_interview": False,
        "interview_schedule_key": "",
        "interview_reminder_30_sent": False,
        "interview_reminder_10_sent": False,
        "interview_reminder_60_sent": False,
        "feedback_reminder_last_sent_at": "",
        "think_long_reminder_sent": False,
        "calendar_event_id": "",
        "meeting_hr_confirmed": False,
        "meeting_hr_confirmation_post": None,
        "interview_attendance_status": "",
        "interview_attendance_morning_date": "",
        "interview_attendance_morning_last_sent_at": "",
        "profile_checked": False,
        "extra_materials": [],
        "copied_from": {
            "candidate_id": str(source.id),
            "vacancy_id": source.vacancy_id,
            "copied_at": now,
        },
    }
    for field in KEEP_FIELDS:
        if field in src:
            payload[field] = copy.deepcopy(src.get(field))

    return models.Candidate(
        id=uuid.uuid4(),
        vacancy_id=target_vacancy_id,
        name=source.name or "Кандидат",
        hr_stage="resume_screening",
        client_status="wait",
        created_at=now,
        status_updated_at=now,
        payload=payload,
    )


def copy_candidate_to_vacancy(
    db: Session,
    source: models.Candidate,
    target_vacancy_id: int,
) -> models.Candidate:
    target = db.get(models.Vacancy, target_vacancy_id)
    if not target:
        raise ValueError("Целевая вакансия не найдена")
    if not target.active:
        raise ValueError("Целевая вакансия не активна")
    if target.id == source.vacancy_id:
        raise ValueError("Выберите другую вакансию")
    cand = prepare_candidate_copy(source, target_vacancy_id=target_vacancy_id)
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand
