"""AI interview evaluation using resume, initial resume eval and questionnaire."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings, get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.candidate_questionnaire import get_candidate_questionnaire
from app.services.candidate_resume_eval import (
    CandidateEvalError,
    _format_sections,
    load_candidate_resume_text,
)
from app.services.vacancy_docs import extract_profile_text

INTERVIEW_EVAL_SYSTEM = """Ты — опытный HR-директор. Оцени кандидата по итогам первичного собеседования.
Используй ВСЕ источники вместе:
- профиль вакансии,
- резюме кандидата,
- предварительную AI-оценку по резюме,
- опросник с заметками и оценками HR,
- расшифровку интервью и дополнительные заметки HR.

Шкала rating: 0–4 (целое число).
Верни ТОЛЬКО JSON:
{
  "rating": 3,
  "comment_sections": {
    "итог_по_интервью": "1–3 предложения с итогом после интервью",
    "подтверждено": ["что интервью подтвердило"],
    "не_подтвердилось_или_осталось_сомнительным": ["что осталось под риском"],
    "мотивация_и_поведение": "1–3 предложения про мотивацию, адекватность, причины смены работы, управляемость",
    "сверка_с_резюме": "как интервью подтвердило или скорректировало выводы по резюме",
    "итог": "1–2 предложения с финальным вердиктом"
  },
  "strengths": ["..."],
  "weaknesses": ["..."],
  "profile_requirements_met": {
    "hard_skills": 75,
    "soft_skills": 70,
    "experience": 80
  }
}

Правила:
- comment_sections обязателен.
- Если есть оценки HR по вопросам опросника, учитывай их как сигнал рекрутера.
- Если интервью противоречит оценке по резюме — явно укажи, что именно изменилось.
- Не выдумывай факты, которых нет в источниках.
- profile_requirements_met: только целые проценты 0–100."""


def _questionnaire_to_interview_prompt(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    lines: list[str] = []
    for i, item in enumerate(items, 1):
        parts = [f"{i}. {str(item.get('вопрос') or '').strip()}"]
        if item.get("пример_ответа"):
            parts.append(f"   Желательный ответ: {str(item.get('пример_ответа')).strip()}")
        if item.get("в_резюме"):
            parts.append(f"   Уже в резюме: {str(item.get('в_резюме')).strip()}")
        followups = item.get("уточнения_по_резюме") or []
        if isinstance(followups, list):
            cleaned = [str(x).strip() for x in followups if str(x).strip()]
            if cleaned:
                parts.append("   Уточнения по резюме: " + "; ".join(cleaned))
        rating = str(item.get("оценка_hr") or item.get("оценка") or "").strip()
        if rating:
            parts.append(f"   Оценка HR: {rating}")
        answer = str(item.get("ответ") or "").strip()
        if answer:
            parts.append(f"   Заметка HR: {answer}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def apply_interview_eval_to_candidate(candidate: models.Candidate, ev: dict[str, Any]) -> None:
    payload = dict(candidate.payload or {})
    payload["interview_ai_score"] = ev.get("ai_score")
    payload["interview_ai_comment"] = ev.get("ai_comment") or ""
    payload["interview_ai_comment_sections"] = ev.get("ai_comment_sections") or {}
    payload["interview_ai_strengths"] = ev.get("ai_strengths") or []
    payload["interview_ai_weaknesses"] = ev.get("ai_weaknesses") or []
    payload["interview_profile_requirements_met"] = ev.get("profile_requirements_met") or {}

    # Current card summary should reflect the latest, richer post-interview assessment.
    payload["ai_score"] = ev.get("ai_score")
    payload["ai_score_source"] = "interview"
    payload["ai_comment"] = ev.get("ai_comment") or ""
    payload["ai_comment_sections"] = ev.get("ai_comment_sections") or {}
    payload["ai_strengths"] = ev.get("ai_strengths") or []
    payload["ai_weaknesses"] = ev.get("ai_weaknesses") or []

    candidate.payload = payload
    flag_modified(candidate, "payload")


def evaluate_candidate_interview(
    db: Session,
    candidate: models.Candidate,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy:
        raise CandidateEvalError("Вакансия не найдена", 404)

    payload = candidate.payload or {}
    profile = extract_profile_text(vacancy.documents)
    resume_text, err = load_candidate_resume_text(candidate)
    if err and not resume_text:
        raise CandidateEvalError(err, 400)
    if not resume_text:
        raise CandidateEvalError("Нет текста резюме для оценки по интервью", 400)

    questionnaire = get_candidate_questionnaire(candidate)
    transcript = str(payload.get("transcript") or "").strip()
    interview_notes = str(payload.get("interview_eval_notes") or "").strip()
    if not questionnaire and not transcript and not interview_notes:
        raise CandidateEvalError(
            "Нет данных интервью: заполните опросник, расшифровку или заметки HR",
            400,
        )

    resume_score = payload.get("resume_ai_score", payload.get("ai_score"))
    resume_comment = str(payload.get("resume_ai_comment") or payload.get("ai_comment") or "").strip()
    resume_sections = payload.get("resume_ai_comment_sections")
    if not resume_comment and isinstance(resume_sections, dict):
        resume_comment = _format_sections(resume_sections)

    questionnaire_block = _questionnaire_to_interview_prompt(questionnaire)
    user_parts = [
        f"Должность: {vacancy.title}",
        f"ПРОФИЛЬ ВАКАНСИИ:\n{(profile or '—').strip()[:5000]}",
        f"РЕЗЮМЕ КАНДИДАТА:\n{resume_text[:8000]}",
    ]
    if resume_score is not None or resume_comment:
        user_parts.append(
            "ПРЕДВАРИТЕЛЬНАЯ ОЦЕНКА ПО РЕЗЮМЕ:\n"
            f"score: {resume_score if resume_score is not None else '—'}/4\n"
            f"{resume_comment[:2500]}"
        )
    if questionnaire_block:
        user_parts.append(
            "ОПРОСНИК И РЕЗУЛЬТАТЫ ПЕРВИЧНОГО СОБЕСЕДОВАНИЯ:\n" + questionnaire_block[:5000]
        )
    user_parts.append(
        "РАСШИФРОВКА ИНТЕРВЬЮ:\n"
        + (transcript[:9000] if transcript else "Нет расшифровки — опирайся на опросник и заметки HR")
    )
    if interview_notes:
        user_parts.append("ДОПОЛНИТЕЛЬНЫЕ ЗАМЕТКИ HR:\n" + interview_notes[:2500])
    if str(payload.get("hr_comment") or "").strip():
        user_parts.append("ПРЕДЫДУЩИЙ КОММЕНТАРИЙ HR:\n" + str(payload.get("hr_comment")).strip()[:2000])

    data = chat_json(
        settings,
        system=INTERVIEW_EVAL_SYSTEM,
        user="\n\n".join(user_parts),
        temperature=0.3,
        max_tokens=3500,
    )
    if not isinstance(data, dict):
        data = {}

    try:
        rating = int(data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    rating = max(0, min(4, rating))
    sections = data.get("comment_sections") if isinstance(data.get("comment_sections"), dict) else {}
    if not sections and data.get("comment"):
        sections = {"итог": str(data.get("comment")).strip()}

    profile_met = data.get("profile_requirements_met")
    if not isinstance(profile_met, dict):
        profile_met = {}

    ev = {
        "ai_score": rating,
        "ai_score_source": "interview",
        "ai_comment": _format_sections(sections),
        "ai_comment_sections": sections,
        "ai_strengths": data.get("strengths") or [],
        "ai_weaknesses": data.get("weaknesses") or [],
        "profile_requirements_met": profile_met,
    }
    apply_interview_eval_to_candidate(candidate, ev)
    db.commit()
    db.refresh(candidate)
    return {
        "ok": True,
        "ai_score": rating,
        "candidate": candidate,
        "profile_present": bool((profile or "").strip()),
    }
