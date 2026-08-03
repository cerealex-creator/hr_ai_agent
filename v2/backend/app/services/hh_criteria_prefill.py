"""AI prefill of HH search criteria from vacancy profile + transcript."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import models
from app.services.hh_search_criteria import (
    AREA_PRESETS,
    ensure_portrait,
    normalize_criteria,
)
from app.services.vacancy_docs import extract_keywords, extract_profile_text

PREFILL_SYSTEM = """Ты — старший рекрутер. По материалам вакансии заполни критерии холодного поиска резюме на HH.ru.
Цель: узкая воронка и жёсткий отсев «не тех» (чужая сфера, overqualified, завышенные запросы).

Верни ТОЛЬКО JSON:
{
  "keywords": "строка: 2–5 запросов через перевод строки (близкие названия должности)",
  "area_id": null или число (1=Москва, 2=СПб, 3=Екатеринбург, 4=Новосибирск, 88=Казань, 66=НН),
  "area_name": "город или пусто",
  "schedule": "" | "fullDay" | "flexible" | "remote" | "shift",
  "office_required": "first_3_months" | "always" | "no",
  "office_address": "если есть в тексте, иначе пусто",
  "max_commute_min": 60,
  "salary_to": null или число (верхняя вилка работодателя, если известна),
  "period_days": 30,
  "experience_from": null или число лет,
  "title_priority": ["близкие названия", "..."],
  "must_have": ["обязательные/желательные навыки и сферы, напр. опыт в fashion"],
  "reject": ["жёсткий отсев: руководитель направления / head of / директор если вакансия исполнительская", "только другая сфера без релевантного опыта", "..."],
  "portrait": {
    "hard": ["краткие правила отсева"],
    "important": ["важные предпочтения: сфера, стек"],
    "nice": ["желательное"]
  },
  "recruiter_comment_suggestion": "1–3 предложения подсказок рекрутеру (не обязательный комментарий)"
}

Правила:
- Если должность исполнительская/специалист — в reject и hard обязательно отсев head/руководитель направления/директор/C-level и завышенных ЗП-ожиданий.
- Желательная сфера из профиля (fashion и т.п.) → must_have + important; чужая сфера без пересечения → hard/reject.
- Не выдумывай адрес офиса и вилку, если их нет в тексте.
- keywords — конкретные названия ролей, не общие слова вроде «менеджер».
- period_days: обычно 7–30 (свежие резюме); null только если явно нужна вся база.
"""


def _parse_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


def transcript_from_documents(documents: dict | None) -> str:
    docs = documents or {}
    for key in (
        "transcript",
        "расшифровка",
        "transcription",
        "client_call",
        "запись_разговора",
        "notes",
        "заметки",
    ):
        raw = docs.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, dict):
            for sub in ("text", "transcript", "raw"):
                if isinstance(raw.get(sub), str) and raw[sub].strip():
                    return raw[sub].strip()
    return ""


def latest_vacancy_transcript(db: Session, vacancy_id: int) -> tuple[str, str | None]:
    """Return (transcript_text, job_id_str_or_None) from latest completed transcribe job."""
    row = db.execute(
        select(models.Job)
        .where(
            models.Job.vacancy_id == vacancy_id,
            models.Job.job_type == "transcribe_media",
            models.Job.status == "completed",
        )
        .order_by(models.Job.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not row:
        return "", None
    payload = row.payload or {}
    text = str(payload.get("transcript") or "").strip()
    return text, str(row.id) if text else None


def build_vacancy_context(
    vacancy: models.Vacancy,
    db: Session,
) -> tuple[str, list[str]]:
    """Assemble text context + list of source labels."""
    sources: list[str] = []
    parts: list[str] = [f"Название вакансии: {vacancy.title}"]
    docs = vacancy.documents or {}

    profile = extract_profile_text(docs)
    if profile:
        parts.append(f"\n=== ПРОФИЛЬ ДОЛЖНОСТИ ===\n{profile[:8000]}")
        sources.append("профиль")

    for key, label in (
        ("vacancy_text", "текст_вакансии"),
        ("текст_вакансии", "текст_вакансии"),
        ("questions", "вопросы"),
        ("вопросы", "вопросы"),
    ):
        raw = docs.get(key)
        if isinstance(raw, str) and raw.strip() and raw.strip() not in (profile or ""):
            parts.append(f"\n=== {label.upper()} ===\n{raw.strip()[:4000]}")
            sources.append(label)

    kw = extract_keywords(docs)
    if kw:
        parts.append(f"\n=== КЛЮЧЕВЫЕ СЛОВА (документы) ===\n{kw}")
        sources.append("keywords")

    doc_tr = transcript_from_documents(docs)
    if doc_tr:
        parts.append(f"\n=== РАСШИФРОВКА (в документах) ===\n{doc_tr[:6000]}")
        sources.append("расшифровка_в_документах")

    job_tr, job_id = latest_vacancy_transcript(db, vacancy.id)
    if job_tr and job_tr != doc_tr:
        parts.append(f"\n=== РАСШИФРОВКА РАЗГОВОРА (job {job_id}) ===\n{job_tr[:6000]}")
        sources.append("расшифровка_job")

    area_hint = "Известные area_id: " + ", ".join(f"{a['name']}={a['id']}" for a in AREA_PRESETS)
    parts.append(f"\n{area_hint}")
    return "\n".join(parts), sources


def needs_ai_prefill(documents: dict | None) -> bool:
    docs = documents or {}
    stored = docs.get("hh_search_criteria")
    if not isinstance(stored, dict):
        return True
    meta = stored.get("prefill_meta") if isinstance(stored.get("prefill_meta"), dict) else {}
    if meta.get("prefilled_at") or meta.get("skip_prefill"):
        return False
    c = normalize_criteria(stored)
    if (
        c["keywords"]
        or c["must_have"]
        or c["reject"]
        or c.get("recruiter_comment")
        or any(c["portrait"].get(k) for k in ("hard", "important", "nice"))
    ):
        return False
    return True


def _merge_ai_into_criteria(base: dict[str, Any], ai: dict[str, Any]) -> dict[str, Any]:
    c = normalize_criteria(base)
    if ai.get("keywords"):
        c["keywords"] = str(ai["keywords"]).strip()
    if ai.get("area_id") is not None:
        try:
            c["area_id"] = int(ai["area_id"])
        except (TypeError, ValueError):
            pass
    if ai.get("area_name"):
        c["area_name"] = str(ai["area_name"]).strip()
    if c["area_id"] and not c["area_name"]:
        for a in AREA_PRESETS:
            if a["id"] == c["area_id"]:
                c["area_name"] = a["name"]
                break
    if ai.get("schedule") is not None:
        c["schedule"] = str(ai.get("schedule") or "").strip()
    if ai.get("office_required") in {"first_3_months", "always", "no"}:
        c["office_required"] = ai["office_required"]
    if ai.get("office_address"):
        c["office_address"] = str(ai["office_address"]).strip()
    if ai.get("max_commute_min") is not None:
        try:
            c["max_commute_min"] = int(ai["max_commute_min"])
        except (TypeError, ValueError):
            pass
    if ai.get("salary_to") is not None:
        try:
            c["salary_to"] = int(ai["salary_to"])
        except (TypeError, ValueError):
            pass
    if "period_days" in ai:
        try:
            p = ai.get("period_days")
            c["period_days"] = int(p) if p not in (None, "") else None
        except (TypeError, ValueError):
            pass
    if ai.get("experience_from") is not None:
        try:
            c["experience_from"] = int(ai["experience_from"])
        except (TypeError, ValueError):
            pass
    for key in ("title_priority", "must_have", "reject"):
        if isinstance(ai.get(key), list) and ai[key]:
            c[key] = [str(x).strip() for x in ai[key] if str(x).strip()]
    if isinstance(ai.get("portrait"), dict):
        portrait = {"hard": [], "important": [], "nice": []}
        for tier in portrait:
            raw = ai["portrait"].get(tier)
            if isinstance(raw, list):
                portrait[tier] = [str(x).strip() for x in raw if str(x).strip()]
        if any(portrait.values()):
            c["portrait"] = portrait
    return ensure_portrait(c)


def prefill_criteria_with_ai(
    vacancy: models.Vacancy,
    db: Session,
    settings: Settings,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Returns {criteria, sources, suggestion}."""
    api_key = (settings.routerai_api_key or settings.ai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Нет ключа ИИ (ROUTERAI_API_KEY) для prefill критериев")

    context, sources = build_vacancy_context(vacancy, db)
    if len(context.strip()) < 40:
        raise RuntimeError(
            "Мало данных для prefill: заполните профиль вакансии или прикрепите расшифровку"
        )

    from app.services.app_settings import resolve_ai_model_name

    base_url = (settings.ai_base_url or "https://routerai.ru/api/v1").rstrip("/")
    model = resolve_ai_model_name(settings.ai_model_name)
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.2,
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "system",
                    "content": PREFILL_SYSTEM + "\n\n/no_think\nОтвечай сразу валидным JSON.",
                },
                {"role": "user", "content": context},
            ],
        },
        timeout=120,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ИИ prefill {resp.status_code}: {resp.text[:300]}")
    content = (((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    ai = _parse_json(content)
    if not ai:
        raise RuntimeError("ИИ не вернул валидный JSON для критериев")

    base = normalize_criteria(existing or {})
    criteria = _merge_ai_into_criteria(base, ai)
    criteria["prefill_meta"] = {
        "prefilled_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "recruiter_edited": False,
        "model": model,
    }
    suggestion = str(ai.get("recruiter_comment_suggestion") or "").strip()
    return {"criteria": criteria, "sources": sources, "suggestion": suggestion}
