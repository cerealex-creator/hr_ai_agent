"""Candidate interview questionnaire: load/save/generate (v2 PG)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings, get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.candidate_resume_eval import load_candidate_resume_text
from app.services.questionnaire_normalize import (
    ensure_question_ids,
    normalize_hr_rating,
    normalize_questionnaire_list,
    vacancy_questions_as_list,
)

RESUME_HINTS_SYSTEM = """Ты — HR-ассистент. По тексту резюме заполни для каждого вопроса опросника колонку «Что уже есть в резюме».

Правила:
- 1–3 коротких предложения: что резюме уже говорит по теме вопроса, с конкретными фактами из резюме.
- Если в резюме нет ничего по теме — напиши «Нет данных в резюме».
- Не выдумывай факты, которых нет в резюме.

Верни ТОЛЬКО JSON:
{"подсказки": ["текст для вопроса 1", "текст для вопроса 2", ...]}

Число элементов в подсказках ДОЛЖНО совпадать с числом вопросов."""

PERSONAL_FOLLOWUPS_SYSTEM = """Ты — HR-директор. Для каждого ОСНОВНОГО вопроса опросника добавь персональные уточнения по резюме кандидата.

Правила:
- Не меняй и не переписывай основные вопросы.
- 0–3 коротких уточняющих вопроса на каждый основной (можно пустой список).
- Уточнения только по фактам/пробелам резюме и комментарию ИИ; не дублируй шаблонные уточняющие.
- Стиль: разговорный, «Расскажите… / Был ли…».

Верни ТОЛЬКО JSON:
{"уточнения_по_резюме": [["уточнение1", "уточнение2"], [], ...]}
Число внешних списков = числу основных вопросов."""

QUESTIONNAIRE_FILL_SYSTEM = """Ты — HR-ассистент. Заполни опросник по расшифровке собеседования.

Для каждого вопроса:
- найди ответ кандидата по смыслу, даже если вопрос в беседе звучал иначе;
- если ответа по сути нет, так и напиши;
- дай предварительную оценку ответа;
- коротко поясни, почему поставлена именно такая оценка.

Верни ТОЛЬКО JSON:
{
  "items": [
    {
      "candidate_answer": "краткий ответ кандидата",
      "ai_rating": "good",
      "ai_note": "1-2 предложения с пояснением"
    }
  ]
}

Допустимые оценки: good, satisfactory, doubtful, no.
Число элементов в items должно совпадать с числом вопросов."""


class QuestionnaireError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_candidate_questionnaire(candidate: models.Candidate) -> list[dict[str, Any]]:
    items = normalize_questionnaire_list(
        (candidate.payload or {}).get("interview_questionnaire") or []
    )
    return ensure_question_ids(items)


def save_candidate_questionnaire(
    db: Session,
    candidate: models.Candidate,
    items: list[Any],
) -> list[dict[str, Any]]:
    normalized = ensure_question_ids(normalize_questionnaire_list(items))
    payload = dict(candidate.payload or {})
    payload["interview_questionnaire"] = normalized
    candidate.payload = payload
    flag_modified(candidate, "payload")
    db.commit()
    db.refresh(candidate)
    return normalized


def copy_vacancy_questionnaire_template(base: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = normalize_questionnaire_list(base)
    for item in items:
        item["уточнения_по_резюме"] = []
        # Keep template followups; clear answers/ratings for fresh candidate copy
        item["ответ"] = ""
        item["оценка_hr"] = ""
        item["оценка"] = ""
        item["ответ_кандидата"] = ""
        item["оценка_ии"] = ""
        item["пояснение_ии"] = ""
        item["в_резюме"] = item.get("в_резюме") or ""
        item["_qid"] = ""
    return ensure_question_ids(items)


def _merge_keep_manual(
    old_items: list[dict[str, Any]],
    new_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    old_map = {
        str(item.get("вопрос") or "").strip().lower(): item for item in old_items if str(item.get("вопрос") or "").strip()
    }
    merged: list[dict[str, Any]] = []
    for item in new_items:
        key = str(item.get("вопрос") or "").strip().lower()
        prev = old_map.get(key)
        if prev:
            for field in (
                "ответ",
                "оценка_hr",
                "оценка",
                "ответ_кандидата",
                "оценка_ии",
                "пояснение_ии",
            ):
                if str(prev.get(field) or "").strip():
                    item[field] = prev.get(field)
        merged.append(item)
    return ensure_question_ids(merged)


def _enrich_resume_hints(
    resume_text: str,
    items: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    if not items or not (resume_text or "").strip():
        return items
    q_block = "\n".join(f"{i + 1}. {q.get('вопрос', '')}" for i, q in enumerate(items))
    data = chat_json(
        settings,
        system=RESUME_HINTS_SYSTEM,
        user=f"Текст резюме:\n{resume_text[:8000]}\n\nВопросы:\n{q_block}",
        temperature=0.2,
        max_tokens=3000,
    )
    hints = data.get("подсказки") if isinstance(data, dict) else None
    if not isinstance(hints, list):
        return items
    for i, item in enumerate(items):
        if i < len(hints) and hints[i] is not None:
            item["в_резюме"] = str(hints[i]).strip()
    return items


def _enrich_personal_followups(
    resume_text: str,
    items: list[dict[str, Any]],
    settings: Settings,
    *,
    hr_comment: str = "",
    eval_comment: str = "",
    strengths: list | None = None,
    weaknesses: list | None = None,
) -> list[dict[str, Any]]:
    if not items or not (resume_text or "").strip():
        return items
    q_block = "\n".join(f"{i + 1}. {q.get('вопрос', '')}" for i, q in enumerate(items))
    user_parts = [
        f"РЕЗЮМЕ:\n{resume_text[:8000]}",
        f"ОСНОВНЫЕ ВОПРОСЫ ОПРОСНИКА (не менять, только уточнения по резюме):\n{q_block}",
    ]
    if (eval_comment or "").strip():
        user_parts.append(f"КОММЕНТАРИЙ ИИ ПО РЕЗЮМЕ:\n{eval_comment[:1500]}")
    if strengths:
        user_parts.append(
            "СИЛЬНЫЕ СТОРОНЫ:\n" + "\n".join(f"- {s}" for s in list(strengths)[:10])
        )
    if weaknesses:
        user_parts.append(
            "СЛАБЫЕ СТОРОНЫ / ПРОБЕЛЫ:\n" + "\n".join(f"- {w}" for w in list(weaknesses)[:10])
        )
    if (hr_comment or "").strip():
        user_parts.append(
            "КОММЕНТАРИЙ HR:\n" + hr_comment.strip()[:2000]
        )
    user_parts.append(
        "Сформируй персональные уточняющие вопросы по резюме для каждого основного вопроса."
    )
    data = chat_json(
        settings,
        system=PERSONAL_FOLLOWUPS_SYSTEM,
        user="\n\n".join(user_parts),
        temperature=0.3,
        max_tokens=3500,
    )
    followups = []
    if isinstance(data, dict):
        followups = data.get("уточнения_по_резюме") or data.get("уточняющие") or []
    if not isinstance(followups, list):
        followups = []
    for i, item in enumerate(items):
        raw = followups[i] if i < len(followups) else []
        if not isinstance(raw, list):
            raw = [raw] if raw else []
        personal = []
        for f in raw:
            text = str(f).strip()
            if text and text not in personal:
                personal.append(text)
        item["уточнения_по_резюме"] = personal[:5]
    return items


def generate_candidate_questionnaire(
    db: Session,
    candidate: models.Candidate,
    *,
    recruiter_notes: str = "",
    keep_manual: bool = False,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Template from vacancy + resume hints + personal followups."""
    settings = settings or get_settings()
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy:
        raise QuestionnaireError("Вакансия не найдена", 404)

    base = vacancy_questions_as_list(vacancy.documents)
    if not base:
        raise QuestionnaireError(
            "Сначала заполните опросник в документах вакансии — он будет шаблоном для всех кандидатов.",
            400,
        )

    resume_text, err = load_candidate_resume_text(candidate)
    if err and not resume_text:
        raise QuestionnaireError(err, 400)
    if not resume_text:
        raise QuestionnaireError("Нет текста резюме — опросник нельзя сформировать", 400)

    existing = get_candidate_questionnaire(candidate)
    items = copy_vacancy_questionnaire_template(base)
    payload = candidate.payload or {}
    items = _enrich_resume_hints(resume_text, items, settings)
    items = _enrich_personal_followups(
        resume_text,
        items,
        settings,
        hr_comment="\n\n".join(
            part for part in [str(payload.get("hr_comment") or "").strip(), recruiter_notes.strip()] if part
        ),
        eval_comment=str(payload.get("ai_comment") or ""),
        strengths=payload.get("ai_strengths") or [],
        weaknesses=payload.get("ai_weaknesses") or [],
    )
    if keep_manual and existing:
        items = _merge_keep_manual(existing, items)
    return save_candidate_questionnaire(db, candidate, items)


def regenerate_candidate_questionnaire(
    db: Session,
    candidate: models.Candidate,
    *,
    recruiter_notes: str,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    payload = dict(candidate.payload or {})
    has_eval = bool(
        str(payload.get("resume_ai_comment") or "").strip()
        or str(payload.get("ai_comment") or "").strip()
        or payload.get("ai_score") is not None
    )
    if not has_eval:
        raise QuestionnaireError("Сначала запустите оценку кандидата", 400)
    if str(payload.get("video_link") or "").strip():
        raise QuestionnaireError(
            "После добавления записи собеседования опросник нельзя перегенерировать",
            400,
        )
    notes = recruiter_notes.strip()
    if not notes:
        raise QuestionnaireError("Напишите замечания рекрутера", 400)
    payload["questionnaire_recruiter_notes"] = notes
    candidate.payload = payload
    flag_modified(candidate, "payload")
    return generate_candidate_questionnaire(
        db,
        candidate,
        recruiter_notes=notes,
        keep_manual=True,
        settings=settings,
    )


def fill_candidate_questionnaire_from_transcript(
    db: Session,
    candidate: models.Candidate,
    *,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    payload = candidate.payload or {}
    transcript = str(payload.get("transcript") or "").strip()
    if not transcript:
        raise QuestionnaireError("Сначала получите расшифровку собеседования", 400)
    items = get_candidate_questionnaire(candidate)
    if not items:
        # After interview-first flow the questionnaire may still be empty — build it now.
        items = generate_candidate_questionnaire(db, candidate, settings=settings)
        if not items:
            raise QuestionnaireError("Не удалось сформировать опросник для заполнения", 400)

    q_block = "\n".join(
        f"{i + 1}. {q.get('вопрос', '')}\n"
        f"Желательный ответ: {q.get('пример_ответа', '')}\n"
        f"Уже есть в резюме: {q.get('в_резюме', '')}"
        for i, q in enumerate(items)
    )
    data = chat_json(
        settings,
        system=QUESTIONNAIRE_FILL_SYSTEM,
        user=f"РАСШИФРОВКА СОБЕСЕДОВАНИЯ:\n{transcript[:12000]}\n\nОПРОСНИК:\n{q_block[:6000]}",
        temperature=0.2,
        max_tokens=3500,
    )
    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        raise QuestionnaireError("Не удалось заполнить опросник по расшифровке", 502)

    updated: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        out = dict(item)
        raw = raw_items[i] if i < len(raw_items) and isinstance(raw_items[i], dict) else {}
        out["ответ_кандидата"] = str(raw.get("candidate_answer") or "").strip()
        out["оценка_ии"] = normalize_hr_rating(raw.get("ai_rating"))
        out["пояснение_ии"] = str(raw.get("ai_note") or "").strip()
        updated.append(out)
    return save_candidate_questionnaire(db, candidate, updated)
