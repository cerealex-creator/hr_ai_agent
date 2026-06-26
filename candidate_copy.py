"""Копирование кандидата из архива (или другой вакансии) в активную."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime

import streamlit as st

from candidate_funnel import new_candidate_template


def prepare_candidate_copy(source: dict, *, source_vacancy_id, target_vacancy_id) -> dict:
    """
    Копия карточки для новой вакансии: контакты и резюме сохраняются,
    воронка, интервью, задание и оценка ИИ — сбрасываются.
    """
    fresh = new_candidate_template(target_vacancy_id)
    cand = copy.deepcopy(fresh)

    keep_fields = (
        "name",
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
    )
    for field in keep_fields:
        if field in source:
            cand[field] = copy.deepcopy(source.get(field))

    if source.get("ignore_flags"):
        cand["ignore_flags"] = copy.deepcopy(source["ignore_flags"])

    now = datetime.now().isoformat()
    cand.update({
        "id": str(uuid.uuid4()),
        "created_at": now,
        "status_updated_at": now,
        "viewed": False,
        "hr_stage": "resume_screening",
        "hr_stage_history": [],
        "client_status": "wait",
        "client_status_history": [],
        "client_comment": "",
        "client_final_verdict": "",
        "transcript": "",
        "video_link": "",
        "task_link": "",
        "hr_comment": "",
        "interview_eval_notes": "",
        "office_interview_date": "",
        "office_interview_time": "",
        "remote_interview": False,
        "office_interview": False,
        "ai_score": None,
        "ai_comment": "",
        "ai_strengths": [],
        "ai_weaknesses": [],
        "ai_profile_requirements_met": {},
        "ai_flags_applied": [],
        "ai_score_source": None,
        "interview_focus_questions": [],
        "interview_questionnaire": [],
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
        "copied_from": {
            "candidate_id": source.get("id"),
            "vacancy_id": source_vacancy_id,
            "copied_at": now,
        },
    })
    return cand


def append_candidate_to_vacancy(target_vacancy, candidate, deps) -> bool:
    target_vacancy.setdefault("candidates", []).append(candidate)
    vacancies = deps["load_vacancies"]()
    for v in vacancies:
        if v["id"] == target_vacancy["id"]:
            v["candidates"] = target_vacancy["candidates"]
    deps["save_vacancies"](vacancies)
    return True


def render_copy_candidate_ui(source_cand, source_vacancy, deps, *, key_prefix: str):
    from vacancy_display import build_vacancy_picker_options

    active = [v for v in deps["load_vacancies"]() if v.get("active", True)]
    if not active:
        st.caption("Нет активных вакансий — создайте или откройте вакансию в работе.")
        return

    labels, by_label = build_vacancy_picker_options(active)
    default_label = labels[0]
    picked = st.selectbox(
        "Целевая вакансия",
        labels,
        key=f"{key_prefix}_target_vac",
    )
    target = by_label[picked or default_label]
    draft = prepare_candidate_copy(
        source_cand,
        source_vacancy_id=source_vacancy["id"],
        target_vacancy_id=target["id"],
    )

    st.caption(
        "При копировании сбрасываются этапы, интервью, задание и оценка ИИ. "
        "Контакты и резюме можно поправить перед добавлением."
    )
    draft["name"] = st.text_input("ФИО", value=draft.get("name", ""), key=f"{key_prefix}_name")
    draft["phone"] = st.text_input("Телефон", value=draft.get("phone", ""), key=f"{key_prefix}_phone")
    draft["resume_link"] = st.text_input(
        "Ссылка на резюме",
        value=draft.get("resume_link", ""),
        key=f"{key_prefix}_resume",
    )
    draft["hh_resume_link"] = st.text_input(
        "Ссылка HH",
        value=draft.get("hh_resume_link", ""),
        key=f"{key_prefix}_hh",
    )

    if st.button("Добавить в выбранную вакансию", key=f"{key_prefix}_confirm", type="primary"):
        fresh_target = next(
            (v for v in deps["load_vacancies"]() if v["id"] == target["id"]),
            target,
        )
        append_candidate_to_vacancy(fresh_target, draft, deps)
        st.session_state.opened_vacancy_id = fresh_target["id"]
        st.session_state.pop("opened_archive_vacancy_id", None)
        st.success(
            f"Кандидат «{draft.get('name') or 'Без имени'}» добавлен в «{fresh_target.get('title')}». "
            "Откройте вкладку «Вакансии в работе»."
        )
        st.rerun()
