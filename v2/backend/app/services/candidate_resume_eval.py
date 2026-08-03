"""Funnel resume extract + AI evaluate (parity with Streamlit «Оценить по резюме»)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings, get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.pdf_extract import fetch_resume_text_from_url
from app.services.vacancy_docs import extract_profile_text

RESUME_EXTRACT_SYSTEM = """Ты — HR-ассистент. Извлеки из текста резюме поля карточки кандидата.
Верни ТОЛЬКО JSON:
{
  "full_name": "ФИО",
  "phone": "телефон или пусто",
  "age": "возраст числом или пусто",
  "city": "город или пусто",
  "metro": "метро или пусто",
  "salary": "ожидания по ЗП текстом или пусто"
}
Не выдумывай данные, которых нет в резюме. Если ФИО нет — full_name: \"Нет информации\"."""

FUNNEL_EVAL_SYSTEM = """Ты — опытный HR-директор. Оцени соответствие резюме профилю должности на этапе холодного отбора.
Шкала rating: 0–4 (целое число).
Верни ТОЛЬКО JSON:
{
  "rating": 3,
  "comment_sections": {
    "соответствие": "1–3 предложения: насколько подходит под профиль",
    "опыт_и_навыки": "1–3 предложения по опыту и hard/soft skills",
    "риски": ["риск 1", "риск 2"],
    "проверить_на_интервью": ["что уточнить на интервью"],
    "итог": "1–2 предложения — краткий вердикт"
  },
  "strengths": ["..."],
  "weaknesses": ["..."]
}

Структура comment_sections обязательна. Поле "comment" не используй — только comment_sections.

Если передан КОММЕНТАРИЙ HR — обязательно учти его: это живые замечания рекрутера после контакта с кандидатом; согласуй оценку с ними и отрази в comment_sections."""

SECTION_ORDER = (
    ("соответствие", "Соответствие"),
    ("опыт_и_навыки", "Опыт и навыки"),
    ("риски", "Риски"),
    ("проверить_на_интервью", "Проверить на интервью"),
    ("итог", "Итог"),
)


class CandidateEvalError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _format_phone(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D+", "", text)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return text


def _format_sections(sections: dict[str, Any]) -> str:
    parts: list[str] = []
    used: set[str] = set()
    for key, title in SECTION_ORDER:
        used.add(key)
        val = sections.get(key)
        if val is None or val == "":
            continue
        if isinstance(val, list):
            body = "\n".join(f"- {item}" for item in val if str(item).strip())
        else:
            body = str(val).strip()
        if body:
            parts.append(f"{title}\n{body}")
    for key, val in sections.items():
        if key in used or val is None or val == "":
            continue
        if isinstance(val, list):
            body = "\n".join(f"- {item}" for item in val if str(item).strip())
        else:
            body = str(val).strip()
        if body:
            parts.append(f"{key}\n{body}")
    return "\n\n".join(parts).strip()


def load_candidate_resume_text(candidate: models.Candidate) -> tuple[str, str]:
    payload = candidate.payload or {}
    text = str(payload.get("resume_text") or "").strip()
    if text:
        return text, ""
    link = str(payload.get("resume_link") or "").strip()
    if not link:
        return "", "Нет текста резюме и ссылки resume_link"
    text, err = fetch_resume_text_from_url(link)
    return text, err


def extract_fields_from_resume(resume_text: str, settings: Settings) -> dict[str, Any]:
    data = chat_json(
        settings,
        system=RESUME_EXTRACT_SYSTEM,
        user=f"Текст резюме:\n{(resume_text or '')[:8000]}",
        temperature=0.1,
        max_tokens=1200,
    )
    if not isinstance(data, dict):
        data = {}
    return {
        "name": (data.get("full_name") or "Нет информации").strip() or "Нет информации",
        "phone": _format_phone(data.get("phone")),
        "age": str(data.get("age") or "").strip(),
        "city": str(data.get("city") or "").strip(),
        "metro": str(data.get("metro") or "").strip(),
        "salary_expected": str(data.get("salary") or "").strip(),
    }


def evaluate_resume_for_funnel(
    resume_text: str,
    *,
    profile_text: str,
    job_title: str,
    hr_comment: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    profile = (profile_text or "").strip()[:5000]
    resume = (resume_text or "").strip()[:8000]
    if not resume:
        raise CandidateEvalError("Пустой текст резюме")
    user = (
        f"Должность: {job_title}\n\nПРОФИЛЬ:\n{profile or '—'}\n\nРЕЗЮМЕ:\n{resume}"
    )
    hr = (hr_comment or "").strip()
    if hr:
        user += (
            "\n\nКОММЕНТАРИЙ HR (обязательно учти — замечания рекрутера после контакта):\n"
            f"{hr[:2000]}"
        )
    data = chat_json(
        settings,
        system=FUNNEL_EVAL_SYSTEM,
        user=user,
        temperature=0.3,
        max_tokens=2500,
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
    plain = _format_sections(sections)
    return {
        "ai_score": rating,
        "ai_score_source": "resume",
        "ai_comment": plain,
        "ai_comment_sections": sections,
        "ai_strengths": data.get("strengths") or [],
        "ai_weaknesses": data.get("weaknesses") or [],
        "profile_checked": True,
    }


def apply_extract_to_candidate(candidate: models.Candidate, fields: dict[str, Any]) -> None:
    payload = dict(candidate.payload or {})
    name = (fields.get("name") or "").strip()
    if name and name != "Нет информации":
        candidate.name = name
    elif not (candidate.name or "").strip() or candidate.name.startswith("HH ·"):
        if name:
            candidate.name = name
    for key in ("phone", "age", "city", "metro", "salary_expected"):
        val = fields.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text:
            payload[key] = text
    candidate.payload = payload
    flag_modified(candidate, "payload")


def apply_eval_to_candidate(candidate: models.Candidate, ev: dict[str, Any], *, resume_text: str = "") -> None:
    payload = dict(candidate.payload or {})
    if resume_text:
        payload["resume_text"] = resume_text
    payload["resume_ai_score"] = ev.get("ai_score")
    payload["resume_ai_comment"] = ev.get("ai_comment") or ""
    payload["resume_ai_comment_sections"] = ev.get("ai_comment_sections") or {}
    payload["resume_ai_strengths"] = ev.get("ai_strengths") or []
    payload["resume_ai_weaknesses"] = ev.get("ai_weaknesses") or []
    payload["ai_score"] = ev.get("ai_score")
    payload["ai_score_source"] = ev.get("ai_score_source") or "resume"
    payload["ai_comment"] = ev.get("ai_comment") or ""
    payload["ai_comment_sections"] = ev.get("ai_comment_sections") or {}
    payload["ai_strengths"] = ev.get("ai_strengths") or []
    payload["ai_weaknesses"] = ev.get("ai_weaknesses") or []
    payload["profile_checked"] = bool(ev.get("profile_checked", True))
    candidate.payload = payload
    flag_modified(candidate, "payload")


def evaluate_candidate_resume(
    db: Session,
    candidate: models.Candidate,
    *,
    populate_fields: bool = True,
    settings: Settings | None = None,
) -> dict[str, Any]:
    from app.services.candidate_questionnaire import (
        generate_candidate_questionnaire,
        get_candidate_questionnaire,
    )

    settings = settings or get_settings()
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy:
        raise CandidateEvalError("Вакансия не найдена", 404)

    resume_text, err = load_candidate_resume_text(candidate)
    if err and not resume_text:
        raise CandidateEvalError(err, 400)
    if not resume_text:
        raise CandidateEvalError("Не удалось получить текст резюме", 400)

    if populate_fields:
        try:
            fields = extract_fields_from_resume(resume_text, settings)
            apply_extract_to_candidate(candidate, fields)
        except Exception as exc:  # noqa: BLE001
            # evaluation can still proceed
            extract_error = str(exc)
        else:
            extract_error = None
    else:
        extract_error = None

    profile = extract_profile_text(vacancy.documents)
    hr_comment = str((candidate.payload or {}).get("hr_comment") or "")
    ev = evaluate_resume_for_funnel(
        resume_text,
        profile_text=profile,
        job_title=vacancy.title,
        hr_comment=hr_comment,
        settings=settings,
    )
    apply_eval_to_candidate(candidate, ev, resume_text=resume_text)
    questionnaire_generated = False
    questionnaire_count = 0
    if not get_candidate_questionnaire(candidate):
        items = generate_candidate_questionnaire(db, candidate, settings=settings)
        questionnaire_generated = True
        questionnaire_count = len(items)
    else:
        questionnaire_count = len(get_candidate_questionnaire(candidate))
    db.commit()
    db.refresh(candidate)
    return {
        "ok": True,
        "ai_score": ev.get("ai_score"),
        "extract_error": extract_error,
        "profile_present": bool((profile or "").strip()),
        "questionnaire_generated": questionnaire_generated,
        "questionnaire_count": questionnaire_count,
    }


def parse_bulk_link_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def bulk_add_from_resume_links(
    db: Session,
    vacancy: models.Vacancy,
    links: list[str],
    *,
    evaluate: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Create candidates from PDF links; optionally run AI evaluate."""
    from app.services.candidate_write import create_candidate

    settings = settings or get_settings()
    created_ids: list[str] = []
    messages: list[str] = []
    errors: list[str] = []

    for raw in links:
        link = raw.strip()
        if not link:
            continue
        text, err = fetch_resume_text_from_url(link)
        name = "Новый кандидат"
        fields: dict[str, Any] = {"resume_link": link, "cold_screening": True}
        if text:
            try:
                extracted = extract_fields_from_resume(text, settings)
                name = extracted.get("name") or name
                for k in ("phone", "age", "city", "metro", "salary_expected"):
                    if extracted.get(k):
                        fields[k] = extracted[k]
                fields["resume_text"] = text
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{link}: extract {exc}")
                fields["resume_text"] = text
        elif err:
            errors.append(f"{link}: {err}")
            # still create stub with link
        cand = create_candidate(db, vacancy_id=vacancy.id, name=name, fields=fields)
        payload = dict(cand.payload or {})
        payload["source"] = "bulk_links"
        payload["cold_screening"] = True
        if fields.get("resume_text"):
            payload["resume_text"] = fields["resume_text"]
        cand.payload = payload
        flag_modified(cand, "payload")
        db.commit()
        db.refresh(cand)

        if evaluate and text:
            try:
                profile = extract_profile_text(vacancy.documents)
                ev = evaluate_resume_for_funnel(
                    text,
                    profile_text=profile,
                    job_title=vacancy.title,
                    settings=settings,
                )
                apply_eval_to_candidate(cand, ev, resume_text=text)
                db.commit()
                messages.append(f"{cand.name}: оценка {ev.get('ai_score')}/4")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{cand.name}: evaluate {exc}")
        else:
            messages.append(f"Добавлен: {cand.name}")
        created_ids.append(str(cand.id))

    return {
        "created": len(created_ids),
        "candidate_ids": created_ids,
        "messages": messages[:40],
        "errors": errors[:20],
    }
