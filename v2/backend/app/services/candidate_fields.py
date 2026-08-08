"""Pull common candidate fields from JSONB payload for API responses."""

from __future__ import annotations

from typing import Any


def payload_get(payload: dict | None, *keys: str) -> Any:
    if not payload:
        return None
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def candidate_public_fields(payload: dict | None) -> dict[str, Any]:
    p = payload or {}
    score = payload_get(p, "ai_score")
    if isinstance(score, str):
        try:
            score = float(score) if "." in score else int(score)
        except ValueError:
            pass
    return {
        "phone": payload_get(p, "phone"),
        "email": payload_get(p, "email"),
        "city": payload_get(p, "city"),
        "metro": payload_get(p, "metro"),
        "age": payload_get(p, "age", "age_location"),
        "salary_expected": payload_get(p, "salary_expected"),
        "resume_link": payload_get(p, "resume_link"),
        "hh_resume_link": payload_get(p, "hh_resume_link"),
        "portfolio_link": payload_get(p, "portfolio_link"),
        "video_link": payload_get(p, "video_link"),
        "task_link": payload_get(p, "task_link"),
        "hr_comment": payload_get(p, "hr_comment"),
        "transcript": payload_get(p, "transcript"),
        "interview_eval_notes": payload_get(p, "interview_eval_notes"),
        "questionnaire_recruiter_notes": payload_get(p, "questionnaire_recruiter_notes"),
        "client_comment": payload_get(p, "client_comment"),
        "ai_score": score,
        "ai_score_source": payload_get(p, "ai_score_source"),
        "ai_comment": payload_get(p, "ai_comment"),
        "ai_comment_sections": p.get("ai_comment_sections")
        if isinstance(p.get("ai_comment_sections"), dict)
        else None,
        "interview_questionnaire": (
            p.get("interview_questionnaire")
            if isinstance(p.get("interview_questionnaire"), list)
            else None
        ),
        "control_word_status": payload_get(p, "control_word_status"),
        "control_word_match": payload_get(p, "control_word_match"),
        "control_word_note": payload_get(p, "control_word_note"),
        "office_interview_date": payload_get(p, "office_interview_date"),
        "office_interview_time": payload_get(p, "office_interview_time"),
        "hh_resume_id": payload_get(p, "hh_resume_id"),
    }
