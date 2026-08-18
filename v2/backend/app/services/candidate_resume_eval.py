"""Funnel resume extract + AI evaluate (parity with Streamlit «Оценить по резюме»)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings, get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.candidate_fields import normalize_gender
from app.services.pdf_extract import fetch_resume_text_from_url
from app.services.vacancy_docs import extract_profile_text

RESUME_EXTRACT_SYSTEM = """Ты — HR-ассистент. Извлеки из текста резюме поля карточки кандидата.
Верни ТОЛЬКО JSON:
{
  "full_name": "ФИО",
  "phone": "телефон или пусто",
  "email": "email или пусто",
  "age": "возраст числом или пусто",
  "city": "город или пусто",
  "metro": "метро или пусто",
  "gender": "male или female, если явно указано в резюме, иначе null",
  "salary": "ожидания по ЗП текстом или пусто"
}
Не выдумывай данные, которых нет в резюме. Если ФИО нет — full_name: \"Нет информации\"."""

RESUME_EXTRACT_CONTROL_WORD_EXTRA = """
Дополнительно (если передано КОНТРОЛЬНОЕ СЛОВО):
Найди сопроводительное письмо в тексте (блок «О себе» / cover letter — НЕ опыт работы).
Ищи контрольное слово/фразу ТОЛЬКО в сопроводительном письме.
Допустима семантика «почти точное»: опечатки, раскладка, транслит.
Добавь в JSON поля:
  "control_word_status": "exact" | "fuzzy" | "missing" | "no_cover_letter",
  "control_word_match": "как написал кандидат или пустая строка",
  "control_word_note": "кратко: точное совпадение / найдено с опечаткой / не найдено / нет письма"
"""

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

Поля strengths и weaknesses обязательны: по 2–4 коротких пункта.
Минусы — конкретные пробелы или риски по профилю, не общие фразы.

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


def extract_fields_from_resume(
    resume_text: str,
    settings: Settings,
    *,
    control_word: str | None = None,
) -> dict[str, Any]:
    system = RESUME_EXTRACT_SYSTEM
    user = f"Текст резюме:\n{(resume_text or '')[:8000]}"
    word = (control_word or "").strip()
    if word:
        system = RESUME_EXTRACT_SYSTEM + "\n" + RESUME_EXTRACT_CONTROL_WORD_EXTRA
        user += f"\n\nКОНТРОЛЬНОЕ СЛОВО (искать только в сопроводительном письме): {word}"
    data = chat_json(
        settings,
        system=system,
        user=user,
        temperature=0.1,
        max_tokens=1200,
    )
    if not isinstance(data, dict):
        data = {}
    email_raw = str(data.get("email") or "").strip()
    email = email_raw if "@" in email_raw else ""
    out: dict[str, Any] = {
        "name": (data.get("full_name") or "Нет информации").strip() or "Нет информации",
        "phone": _format_phone(data.get("phone")),
        "email": email,
        "age": str(data.get("age") or "").strip(),
        "city": str(data.get("city") or "").strip(),
        "metro": str(data.get("metro") or "").strip(),
        "salary_expected": str(data.get("salary") or "").strip(),
        "gender": normalize_gender(data.get("gender")),
    }
    if word:
        status = str(data.get("control_word_status") or "").strip().lower()
        if status not in ("exact", "fuzzy", "missing", "no_cover_letter"):
            status = "missing"
        out["control_word_status"] = status
        out["control_word_match"] = str(data.get("control_word_match") or "").strip()
        out["control_word_note"] = str(data.get("control_word_note") or "").strip()
    return out


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
    for key in ("phone", "email", "age", "city", "metro", "salary_expected", "gender"):
        val = fields.get(key)
        if val is None:
            continue
        if key == "gender":
            g = normalize_gender(val)
            if g:
                payload[key] = g
            continue
        if key in ("control_word_status", "control_word_match", "control_word_note"):
            text = str(val or "").strip()
            if text:
                payload[key] = text
            continue
        text = str(val).strip()
        if text:
            # Don't overwrite an existing email with empty; only fill if present
            if key == "email" and payload.get("email") and not text:
                continue
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
    skip_questionnaire: bool = False,
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
            vac_payload = dict(vacancy.payload or {})
            cw: str | None = None
            if vac_payload.get("control_word_enabled"):
                cw = str(vac_payload.get("control_word") or "").strip() or None
            fields = extract_fields_from_resume(
                resume_text, settings, control_word=cw
            )
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
    if not skip_questionnaire and not get_candidate_questionnaire(candidate):
        items = generate_candidate_questionnaire(
            db, candidate, keep_manual=True, settings=settings
        )
        questionnaire_generated = True
        questionnaire_count = len(items)
    else:
        questionnaire_count = len(get_candidate_questionnaire(candidate))
    db.commit()
    db.refresh(candidate)
    if not str((candidate.payload or {}).get("photo_url") or "").strip():
        link = str((candidate.payload or {}).get("resume_link") or "").strip()
        if link:
            from app.services.candidate_photo import try_attach_candidate_photo_from_link

            try_attach_candidate_photo_from_link(db, candidate, link)
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


def _name_from_filename(filename: str) -> str | None:
    """Best-effort ФИО from resume filename (before AI extract)."""
    raw = (filename or "").strip()
    if not raw:
        return None
    stem = raw.rsplit(".", 1)[0].strip() if "." in raw else raw
    stem = stem.replace("_", " ").replace("-", " ").strip()
    stem = re.sub(r"\s+", " ", stem)
    if not stem:
        return None
    low = stem.casefold()
    if low in {"resume", "cv", "резюме", "анкета", "файл", "document", "doc"}:
        return None
    if not re.search(r"[A-Za-zА-Яа-яЁё]", stem):
        return None
    if len(stem) > 120:
        stem = stem[:120].strip()
    return stem


def _incomplete_candidates(db: Session, vacancy_id: int) -> list[models.Candidate]:
    rows = list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)
        ).all()
    )
    return [c for c in rows if (c.payload or {}).get("ai_score") is None]


def _reuse_incomplete_from_resume_text(
    db: Session, vacancy: models.Vacancy, resume_text: str
) -> models.Candidate | None:
    from app.services.yandex_disk_sync import person_name_in_text

    text = (resume_text or "").strip()
    if not text:
        return None
    for cand in _incomplete_candidates(db, vacancy.id):
        name = (cand.name or "").strip()
        if not name or name.casefold() in {"новый кандидат", "new candidate"}:
            continue
        if person_name_in_text(name, text):
            return cand
    return None


def bulk_add_from_resume_links(
    db: Session,
    vacancy: models.Vacancy,
    links: list[str],
    *,
    evaluate: bool = False,
    for_resume_preview: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Create candidates from PDF links. AI extract/eval is deferred (see enqueue)."""
    from app.services.candidate_write import create_candidate
    from app.services.candidate_photo import try_attach_candidate_photo_from_link

    settings = settings or get_settings()
    created_ids: list[str] = []
    messages: list[str] = []
    errors: list[str] = []
    evaluate_ids: list[str] = []

    for raw in links:
        link = raw.strip()
        if not link:
            continue
        text, err = fetch_resume_text_from_url(link)
        name = "Новый кандидат"
        fields: dict[str, Any] = {"resume_link": link, "cold_screening": True}
        if text:
            fields["resume_text"] = text
        elif err:
            errors.append(f"{link}: {err}")

        cand = _reuse_incomplete_from_resume_text(db, vacancy, text or "")
        reused = cand is not None
        if cand is None:
            cand = create_candidate(db, vacancy_id=vacancy.id, name=name, fields=fields)
        payload = dict(cand.payload or {})
        payload["source"] = payload.get("source") or "bulk_links"
        payload["cold_screening"] = True
        if not str(payload.get("resume_link") or "").strip():
            payload["resume_link"] = link
        if for_resume_preview:
            from app.services.resume_preview import mark_resume_preview

            cand.payload = payload
            flag_modified(cand, "payload")
            mark_resume_preview(cand, pdf_url=link, included=True)
            payload = dict(cand.payload or {})
        if fields.get("resume_text"):
            payload["resume_text"] = fields["resume_text"]
        cand.payload = payload
        flag_modified(cand, "payload")
        db.commit()
        db.refresh(cand)

        try_attach_candidate_photo_from_link(db, cand, link)

        created_ids.append(str(cand.id))
        label = "Дополнена карточка" if reused else "Добавлен"
        if evaluate and (text or "").strip():
            evaluate_ids.append(str(cand.id))
            eval_hint = "лёгкая оценка в очереди" if for_resume_preview else "оценка ИИ в очереди"
            messages.append(f"{label}: {cand.name} — {eval_hint}")
        else:
            messages.append(f"{label}: {cand.name}")

    return {
        "created": len(created_ids),
        "candidate_ids": created_ids,
        "candidate_id": created_ids[0] if created_ids else None,
        "messages": messages[:40],
        "errors": errors[:20],
        "evaluate_candidate_ids": evaluate_ids,
    }


def add_candidate_from_resume_file(
    db: Session,
    vacancy: models.Vacancy,
    *,
    filename: str,
    content: bytes,
    evaluate: bool = False,
    for_resume_preview: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Create one candidate from an uploaded resume file (pdf/docx/txt/…)."""
    from app.services.candidate_write import create_candidate
    from app.services.source_extract import DOC_EXT, extract_text_from_bytes

    settings = settings or get_settings()
    name_hint = (filename or "resume").strip() or "resume"
    ext = ("." + name_hint.rsplit(".", 1)[-1].lower()) if "." in name_hint else ""
    if ext and ext not in DOC_EXT:
        raise ValueError(f"Формат не поддерживается ({ext}). Используйте PDF, Word, TXT, Excel.")
    if not content:
        raise ValueError("Пустой файл")
    if len(content) > 15 * 1024 * 1024:
        raise ValueError("Файл больше 15 МБ")

    text = extract_text_from_bytes(name_hint, content)
    cand_name = _name_from_filename(name_hint) or "Новый кандидат"
    fields: dict[str, Any] = {
        "cold_screening": True,
        "resume_filename": name_hint,
    }
    errors: list[str] = []
    if text.strip():
        fields["resume_text"] = text
    else:
        errors.append("Не удалось извлечь текст из файла")

    from app.services.yandex_disk_sync import match_candidate_by_filename

    reused = False
    cand = match_candidate_by_filename(name_hint, _incomplete_candidates(db, vacancy.id))
    if cand is None:
        cand = _reuse_incomplete_from_resume_text(db, vacancy, text)
    if cand is None:
        cand = create_candidate(db, vacancy_id=vacancy.id, name=cand_name, fields=fields)
    else:
        reused = True
        if cand_name and cand_name != "Новый кандидат" and (
            not (cand.name or "").strip() or cand.name.startswith("Новый")
        ):
            cand.name = cand_name
    payload = dict(cand.payload or {})
    payload["source"] = payload.get("source") or "resume_upload"
    payload["cold_screening"] = True
    payload["resume_filename"] = name_hint
    if fields.get("resume_text"):
        payload["resume_text"] = fields["resume_text"]
    cand.payload = payload
    flag_modified(cand, "payload")
    db.commit()
    db.refresh(cand)

    if ext.lower() == ".pdf":
        from app.services.candidate_photo import try_attach_candidate_photo

        try_attach_candidate_photo(db, cand, pdf_bytes=content)

    if for_resume_preview:
        from app.services.resume_preview import mark_resume_preview

        mark_resume_preview(cand, included=True)
        db.add(cand)
        db.commit()
        db.refresh(cand)

    messages: list[str] = []
    evaluate_ids: list[str] = []
    label = "Дополнена карточка" if reused else "Добавлен"
    if evaluate and text.strip():
        evaluate_ids.append(str(cand.id))
        eval_hint = "лёгкая оценка в очереди" if for_resume_preview else "оценка ИИ в очереди"
        messages.append(f"{label}: {cand.name} — {eval_hint}")
    else:
        messages.append(f"{label}: {cand.name}")
    if for_resume_preview and not str((cand.payload or {}).get("anonymized_resume_link") or "").strip():
        messages.append(
            f"{cand.name}: для кнопки «Посмотреть резюме» вставьте публичную ссылку Я.Диска в поле макета"
        )

    return {
        "created": 1,
        "candidate_ids": [str(cand.id)],
        "candidate_id": str(cand.id),
        "messages": messages,
        "errors": errors[:10],
        "evaluate_candidate_ids": evaluate_ids,
    }


def attach_resume_to_candidate(
    db: Session,
    candidate: models.Candidate,
    *,
    filename: str | None = None,
    content: bytes | None = None,
    resume_link: str | None = None,
) -> models.Candidate:
    """Attach PDF/file or URL to an existing card (does not create a new candidate)."""
    from app.services.source_extract import DOC_EXT, extract_text_from_bytes

    link = (resume_link or "").strip()
    raw = content or b""
    name_hint = (filename or "").strip()

    if not raw and not link:
        raise ValueError("Добавьте файл резюме или ссылку на PDF")

    payload = dict(candidate.payload or {})
    if raw:
        ext = ("." + name_hint.rsplit(".", 1)[-1].lower()) if "." in name_hint else ""
        if ext and ext not in DOC_EXT:
            raise ValueError(f"Формат не поддерживается ({ext}). Используйте PDF, Word, TXT.")
        if len(raw) > 15 * 1024 * 1024:
            raise ValueError("Файл больше 15 МБ")
        text = extract_text_from_bytes(name_hint or "resume.pdf", raw)
        if not text.strip():
            raise ValueError("Не удалось извлечь текст из файла")
        payload["resume_text"] = text
        payload["resume_filename"] = name_hint or "resume.pdf"
        if ext.lower() == ".pdf":
            from app.services.candidate_photo import try_attach_candidate_photo

            try_attach_candidate_photo(db, candidate, pdf_bytes=raw)
            payload = dict(candidate.payload or {})
            payload["resume_text"] = text
            payload["resume_filename"] = name_hint or "resume.pdf"
    else:
        text, err = fetch_resume_text_from_url(link)
        payload["resume_link"] = link
        if text.strip():
            payload["resume_text"] = text
        elif err:
            raise ValueError(err or "Не удалось скачать резюме по ссылке")
        if not str(payload.get("photo_url") or "").strip() and link:
            from app.services.candidate_photo import try_attach_candidate_photo_from_link

            try_attach_candidate_photo_from_link(db, candidate, link)
            payload = dict(candidate.payload or {})
            payload["resume_link"] = link
            if text.strip():
                payload["resume_text"] = text

    candidate.payload = payload
    flag_modified(candidate, "payload")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate
