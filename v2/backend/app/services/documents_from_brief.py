"""Build vacancy documents from short HR answers via AI (always)."""

from __future__ import annotations

import re
from typing import Any

from app.core.config import Settings, get_settings
from app.services.vacancy_docs_pack import generate_package_from_sources


def _clean(text: str | None) -> str:
    return re.sub(r"[ \t]+", " ", (text or "").strip())


def _lines(text: str | None) -> list[str]:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    for line in raw.split("\n"):
        s = line.strip(" \t-•*—")
        if s:
            out.append(s)
    return out


def format_brief_as_profile_text(
    *,
    title: str,
    tasks: str,
    must_have: str,
    conditions: str = "",
) -> str:
    title_n = _clean(title) or "Вакансия"
    task_lines = _lines(tasks)
    must_lines = _lines(must_have)
    cond_lines = _lines(conditions)
    parts = [f"Должность: {title_n}", ""]
    if task_lines:
        parts.append("Задачи / чем занимается:")
        parts.extend(f"— {x}" for x in task_lines)
        parts.append("")
    if must_lines:
        parts.append("Обязательные требования (опыт, навыки):")
        parts.extend(f"— {x}" for x in must_lines)
        parts.append("")
    if cond_lines:
        parts.append("Условия (город, график, деньги и т.п.):")
        parts.extend(f"— {x}" for x in cond_lines)
        parts.append("")
    return "\n".join(parts).strip()


def build_documents_from_brief(
    *,
    title: str,
    tasks: str,
    must_have: str,
    conditions: str = "",
    interview_questions: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """AI pack from brief answers → profile / vacancy_text / questions / keywords / notes."""
    title_n = _clean(title) or "Вакансия"
    if not _lines(tasks) and not _lines(must_have):
        raise ValueError("Заполните хотя бы «задачи» или «обязательные требования»")

    profile_text = format_brief_as_profile_text(
        title=title_n,
        tasks=tasks,
        must_have=must_have,
        conditions=conditions,
    )
    q_lines = _lines(interview_questions)
    hr_bits = [
        "Источник: короткая анкета HR (не расшифровка встречи).",
        "Разверни ответы в полноценный профиль, текст вакансии, опросник и ключевые слова.",
        "Не выдумывай факты сверх анкеты; формулировки можно сделать профессиональнее и структурированнее.",
    ]
    if q_lines:
        hr_bits.append(
            "Обязательно включи в опросник (или близкие по смыслу) эти темы/вопросы от HR:\n"
            + "\n".join(f"— {q}" for q in q_lines)
        )

    pack = generate_package_from_sources(
        vacancy_title=title_n,
        profile_text=profile_text,
        supplemental_blocks=[],
        hr_instructions="\n".join(hr_bits),
        doc_flags={
            "profile": True,
            "questions": True,
            "vacancy_text": True,
            "keywords": True,
        },
        settings=settings or get_settings(),
    )

    out: dict[str, Any] = {
        "profile": pack.get("profile") or "",
        "vacancy_text": pack.get("vacancy_text") or "",
        "questions": pack.get("questions") or "[]",
        "keywords": pack.get("keywords") or "",
        "notes": "Собрано ИИ по ответам из формы «по вопросам».",
    }
    return out
