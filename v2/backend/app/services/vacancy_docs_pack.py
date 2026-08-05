"""Generate vacancy document pack from profile + meeting materials (Streamlit parity)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.document_generate import QUESTIONNAIRE_RULES, _store_value
from app.services.vacancy_documents_write import merge_vacancy_documents
from app.services.vacancy_docs import extract_profile_text

MULTI_SOURCE_SYSTEM = f"""Ты — HR-директор. Создай согласованный пакет документов по вакансии из нескольких источников.

Приоритет источников:
1. Явные указания HR — высший приоритет.
2. Письменный профиль заказчика — основной источник истины.
3. Записи обсуждений, дополнительные документы и заметки — дополняют и уточняют профиль, но не заменяют его молча.

Правила:
- Не выдумывай факты, которых нет в источниках.
- Если дополнительный материал противоречит письменному профилю и указания HR не разрешают конфликт, сохрани данные письменного профиля.
- Все найденные противоречия перечисли отдельно.
- Опросник должен проверять требования итогового профиля.
- Текст вакансии и ключевые слова должны соответствовать итоговому профилю.
- Верни ТОЛЬКО валидный JSON без markdown.

Формат:
{{
  "должность": "...",
  "профиль": {{}},
  "текст_вакансии": "...",
  "опросник": [{{"вопрос": "...", "уточняющие_вопросы": [], "проверяет_требование": "...", "категория": "...", "пример_ответа": "..."}}],
  "ключевые_слова": ["..."],
  "противоречия_источников": ["..."]
}}

{QUESTIONNAIRE_RULES}
"""

MEETING_BRIEF_SYSTEM = """Ты — помощник рекрутера. Преврати расшифровку встречи по вакансии в краткий структурированный конспект.

Правила:
- убери мусор речи: повторы, междометия, обрывки;
- ничего не выдумывай;
- сохрани смысл без потери важных фактов;
- оформи как пары вопрос→ответ / тема→суть (кратко и ёмко).

Верни ТОЛЬКО JSON:
{
  "summary": "2–4 предложения о сути встречи",
  "qa": [{"q": "тема или вопрос", "a": "краткий ответ / договорённость"}],
  "open_points": ["неясности или что уточнить"]
}"""


def _trim(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def generate_package_from_sources(
    *,
    vacancy_title: str,
    profile_text: str,
    supplemental_blocks: list[tuple[str, str]],
    hr_instructions: str,
    doc_flags: dict[str, bool],
    settings: Settings,
) -> dict[str, Any]:
    requested: list[str] = []
    if doc_flags.get("profile", True):
        requested.append("профиль")
    if doc_flags.get("questions", True):
        requested.append("опросник")
    if doc_flags.get("vacancy_text", True):
        requested.append("текст вакансии")
    if doc_flags.get("keywords", True):
        requested.append("ключевые слова")
    if not requested:
        raise ValueError("Не выбран ни один документ для генерации")

    profile_block = _trim(profile_text, 14000) or "(письменный профиль не передан — опирайся на материалы встречи)"
    supplements: list[str] = []
    remaining = 18000
    for label, text in supplemental_blocks:
        clean = (text or "").strip()
        if not clean or remaining <= 0:
            continue
        chunk = _trim(clean, min(remaining, 8000))
        supplements.append(f"### {label}\n{chunk}")
        remaining -= len(chunk)

    user_parts = [
        f"Должность: {vacancy_title}",
        f"Создай документы: {', '.join(requested)}.",
        "ОСНОВНОЙ ПИСЬМЕННЫЙ ПРОФИЛЬ ЗАКАЗЧИКА:\n" + profile_block,
    ]
    if supplements:
        user_parts.append(
            "ДОПОЛНИТЕЛЬНЫЕ МАТЕРИАЛЫ (только дополняют/уточняют основной профиль):\n\n"
            + "\n\n".join(supplements)
        )
    if (hr_instructions or "").strip():
        user_parts.append("УКАЗАНИЯ HR (высший приоритет):\n" + _trim(hr_instructions, 4000))

    result = chat_json(
        settings,
        system=MULTI_SOURCE_SYSTEM,
        user="\n\n".join(user_parts),
        max_tokens=8000,
        temperature=0.2,
    )
    if not isinstance(result, dict):
        raise RuntimeError("ИИ вернул некорректный пакет документов")

    out: dict[str, Any] = {"должность": vacancy_title}
    if doc_flags.get("profile", True):
        prof = result.get("профиль") or result.get("profile") or {}
        if not isinstance(prof, dict) or not prof:
            raise RuntimeError("ИИ вернул пустой профиль")
        out["profile"] = _store_value("profile", prof)
    if doc_flags.get("vacancy_text", True):
        text = result.get("текст_вакансии") or result.get("vacancy_text") or ""
        out["vacancy_text"] = _store_value("vacancy_text", text)
    if doc_flags.get("questions", True):
        qs = result.get("опросник") or result.get("questions") or []
        out["questions"] = _store_value("questions", qs if isinstance(qs, list) else [])
    if doc_flags.get("keywords", True):
        kws = result.get("ключевые_слова") or result.get("keywords") or []
        out["keywords"] = _store_value("keywords", kws)
    conflicts = result.get("противоречия_источников") or result.get("conflicts") or []
    if isinstance(conflicts, str):
        conflicts = [conflicts] if conflicts.strip() else []
    out["conflicts"] = [str(x).strip() for x in conflicts if str(x).strip()]
    return out


def structure_meeting_brief(transcript: str, *, settings: Settings, title: str = "") -> dict[str, Any]:
    source = (transcript or "").strip()
    if not source:
        return {"summary": "", "qa": [], "open_points": []}
    user = f"Вакансия: {title or '—'}\n\nРАСШИФРОВКА:\n{_trim(source, 14000)}"
    result = chat_json(
        settings,
        system=MEETING_BRIEF_SYSTEM,
        user=user,
        max_tokens=3500,
        temperature=0.2,
    )
    if not isinstance(result, dict):
        return {"summary": "", "qa": [], "open_points": [], "raw_error": "bad_json"}
    qa_raw = result.get("qa") or []
    qa: list[dict[str, str]] = []
    if isinstance(qa_raw, list):
        for item in qa_raw:
            if not isinstance(item, dict):
                continue
            q = str(item.get("q") or item.get("вопрос") or "").strip()
            a = str(item.get("a") or item.get("ответ") or "").strip()
            if q or a:
                qa.append({"q": q, "a": a})
    open_pts = result.get("open_points") or result.get("открытые_вопросы") or []
    if isinstance(open_pts, str):
        open_pts = [open_pts] if open_pts.strip() else []
    return {
        "summary": str(result.get("summary") or result.get("summary_text") or "").strip(),
        "qa": qa,
        "open_points": [str(x).strip() for x in open_pts if str(x).strip()],
    }


def apply_pack_to_vacancy(
    db: Session,
    vacancy: models.Vacancy,
    pack: dict[str, Any],
    *,
    meeting_brief: dict[str, Any] | None = None,
    transcript_clean: str = "",
    source_label: str = "",
) -> models.Vacancy:
    updates = {k: pack[k] for k in ("profile", "vacancy_text", "questions", "keywords") if k in pack}
    if updates:
        merge_vacancy_documents(vacancy, updates)

    docs = dict(vacancy.documents or {})
    if meeting_brief is not None:
        docs["meeting_brief"] = meeting_brief
    if transcript_clean.strip():
        docs["meeting_transcript"] = transcript_clean.strip()
    if pack.get("conflicts"):
        docs["meeting_conflicts"] = list(pack.get("conflicts") or [])
    vacancy.documents = docs
    flag_modified(vacancy, "documents")
    db.add(vacancy)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fname = f"v2_{vacancy.id}_{stamp}_{uuid.uuid4().hex[:8]}.json"
    snapshot = {
        "profile": docs.get("profile") or "",
        "vacancy_text": docs.get("vacancy_text") or "",
        "questions": docs.get("questions") or "",
        "keywords": docs.get("keywords") or "",
        "meeting_brief": docs.get("meeting_brief") or {},
        "meeting_transcript": docs.get("meeting_transcript") or "",
        "conflicts": docs.get("meeting_conflicts") or [],
        "source_label": source_label,
    }
    gen = models.DocumentGeneration(
        id=uuid.uuid4(),
        vacancy_id=vacancy.id,
        client_id=vacancy.client_id,
        source_filename=fname,
        title=vacancy.title or "Вакансия",
        mode="from_materials",
        documents_snapshot=snapshot,
        created_at_legacy=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    db.add(gen)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def apply_history_pack_to_vacancy(
    db: Session,
    vacancy: models.Vacancy,
    generation: models.DocumentGeneration,
    *,
    keys: list[str] | None = None,
) -> models.Vacancy:
    snap = generation.documents_snapshot or {}
    allowed = ("profile", "vacancy_text", "questions", "keywords", "notes")
    use_keys = [k for k in (keys or list(allowed)) if k in allowed and k in snap]
    if not use_keys:
        raise ValueError("В снимке нет документов для применения")
    updates = {k: snap[k] for k in use_keys}
    merge_vacancy_documents(vacancy, updates)
    docs = dict(vacancy.documents or {})
    if "meeting_brief" in snap:
        docs["meeting_brief"] = snap["meeting_brief"]
    if "meeting_transcript" in snap:
        docs["meeting_transcript"] = snap["meeting_transcript"]
    vacancy.documents = docs
    flag_modified(vacancy, "documents")
    if generation.vacancy_id is None:
        generation.vacancy_id = vacancy.id
        db.add(generation)
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def profile_text_from_vacancy(vacancy: models.Vacancy) -> str:
    return extract_profile_text(vacancy.documents or {})
