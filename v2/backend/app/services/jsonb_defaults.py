"""Canonical JSONB defaults for Candidate.payload / Vacancy.documents / Vacancy.payload.

Used by normalize_jsonb script (audit M11). Deep-fill only adds *missing* keys;
never overwrites existing values.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def deep_fill_missing(target: Any, defaults: Any) -> tuple[Any, bool]:
    """Return (filled, changed). Only adds *missing* keys; explicit null scalars stay."""
    if not isinstance(defaults, dict):
        return target, False
    if not isinstance(target, dict):
        return deepcopy(defaults), True
    changed = False
    out = dict(target)
    for key, default_val in defaults.items():
        if key not in out:
            out[key] = deepcopy(default_val)
            changed = True
            continue
        cur = out[key]
        if isinstance(default_val, dict):
            if cur is None or not isinstance(cur, dict):
                out[key] = deepcopy(default_val)
                changed = True
            else:
                nested, nested_changed = deep_fill_missing(cur, default_val)
                if nested_changed:
                    out[key] = nested
                    changed = True
        elif isinstance(default_val, list) and not isinstance(cur, list):
            out[key] = deepcopy(default_val)
            changed = True
    return out, changed


def default_candidate_payload() -> dict[str, Any]:
    return {
        "phone": "",
        "email": "",
        "age": "",
        "age_location": "",
        "city": "",
        "metro": "",
        "salary_expected": "",
        "resume_link": "",
        "hh_resume_link": "",
        "anonymized_resume_link": "",
        "resume_preview_included": False,
        "resume_preview_visible": True,
        "resume_preview_status": "",
        "resume_preview_hr_comment": "",
        "hh_resume_id": "",
        "portfolio_link": "",
        "video_link": "",
        "task_link": "",
        "meeting_link": "",
        "extra_materials": [],
        "resume_text": "",
        "hr_comment": "",
        "client_comment": "",
        "transcript": "",
        "interview_eval_notes": "",
        "questionnaire_recruiter_notes": "",
        "client_final_verdict": "",
        "ai_score": None,
        "ai_score_source": None,
        "ai_comment": "",
        "ai_comment_sections": {},
        "ai_strengths": [],
        "ai_weaknesses": [],
        "ai_profile_requirements_met": {},
        "ai_flags_applied": [],
        "profile_checked": False,
        "resume_ai_score": None,
        "resume_ai_comment": "",
        "resume_ai_comment_sections": {},
        "resume_ai_strengths": [],
        "resume_ai_weaknesses": [],
        "interview_ai_score": None,
        "interview_ai_comment": "",
        "interview_ai_comment_sections": {},
        "interview_ai_strengths": [],
        "interview_ai_weaknesses": [],
        "interview_profile_requirements_met": {},
        "hr_stage_history": [],
        "client_status_history": [],
        "cold_screening": False,
        "source": "manual",
        "viewed": False,
        "contacts_opened": False,
        "ignore_flags": None,
        "control_word_status": "",
        "control_word_match": "",
        "control_word_note": "",
        "interview_focus_questions": [],
        "interview_questionnaire": [],
        "office_interview_date": "",
        "office_interview_time": "",
        "remote_interview": False,
        "office_interview": False,
        "interview_schedule_key": "",
        "interview_reminder_30_sent": False,
        "interview_reminder_10_sent": False,
        "interview_reminder_60_sent": False,
        "feedback_reminder_last_sent_at": "",
        "think_long_reminder_sent": False,
        "meeting_hr_confirmed": False,
        "meeting_hr_confirmation_post": None,
        "interview_attendance_status": "",
        "interview_attendance_morning_date": "",
        "interview_attendance_morning_last_sent_at": "",
        "calendar_event_id": "",
        "tg_callback_id": "",
        "hh_title_fit": None,
        "hh_office_fit": None,
        "hh_commute_ok": None,
        "liked": False,
        "liked_at": "",
        "talent_reserve": False,
        "talent_reserve_at": "",
        "talent_reserve_note": "",
        "talent_reserve_by": "",
    }


def default_vacancy_documents() -> dict[str, Any]:
    from app.services.hh_preset import empty_preset
    from app.services.hh_search_criteria import empty_criteria
    from app.services.hh_search_plan import empty_plan

    return {
        "profile": "",
        "vacancy_text": "",
        "questions": "",
        "keywords": "",
        "notes": "",
        "meeting_brief": {"summary": "", "qa": [], "open_points": []},
        "meeting_transcript": "",
        "meeting_conflicts": [],
        "hh_preset": empty_preset(),
        "hh_search_criteria": empty_criteria(),
        "hh_search_plan": empty_plan(),
    }


def default_vacancy_payload() -> dict[str, Any]:
    from app.services.app_settings import get_default_warranty_months
    from app.services.stage_schema import default_stage_schema

    return {
        "close_reason": None,
        "is_test": False,
        "vacancy_summary": "",
        "show_portfolio_field": False,
        "control_word_enabled": False,
        "control_word": "",
        "search_mode": "normal",
        "warranty_source_vacancy_id": None,
        "warranty": {
            "active": False,
            "start_date": "",
            "months": get_default_warranty_months(),
            "candidate_id": "",
            "start_kind": "",
        },
        "yandex_disk": {
            "root_url": "",
            "subfolders": {
                "resume": "Резюме",
                "video": "Записи",
                "task": "Задания",
            },
            "seen_paths": [],
            "last_sync_at": "",
            "ingest_new_resumes": True,
        },
        "resume_preview_token": "",
        "resume_preview_sent_at": "",
        "stage_schema": default_stage_schema(),
    }
