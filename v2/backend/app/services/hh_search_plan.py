"""HH search plan: Strategist dialogue → approved machine criteria for hh_cold_search."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings, get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.hh_criteria_prefill import build_vacancy_context
from app.services.hh_search_criteria import (
    DOC_KEY,
    ensure_portrait,
    normalize_criteria,
    save_criteria_to_documents,
)

PLAN_DOC_KEY = "hh_search_plan"

STRATEGIST_SYSTEM = """Ты — стратег холодного поиска резюме на HH.ru для рекрутера.
По материалам вакансии составь ПЛАН поиска и отбора.

Верни ТОЛЬКО JSON:
{
  "human_text": "Markdown для рекрутера: 5–12 пунктов. Обязательно кратко объясни логику HH: что через ИЛИ, что через И. Без JSON API.",
  "machine": {
    "keywords": "синонимы/альтернативы через перевод строки (режим HH «любое из слов» / ИЛИ)",
    "keywords_and": "обязательные слова через перевод строки (режим «все слова» / И), напр. 1С — или пусто",
    "keywords_logic": "any",
    "area_id": null или число (1=Москва, 2=СПб, 3=Екатеринбург, 4=Новосибирск, 88=Казань, 66=НН),
    "area_name": "город или пусто",
    "schedule": "",
    "period_days": 7,
    "experience_from": null или число лет,
    "salary_to": null или верхняя вилка работодателя,
    "office_required": "first_3_months" | "always" | "no",
    "office_address": "",
    "max_commute_min": 60,
    "title_priority": ["..."],
    "must_have": ["..."],
    "reject": ["жёсткий отсев на уровне поиска/оценки"],
    "portrait": {"hard": ["..."], "important": ["..."], "nice": ["..."]},
    "max_search": 20,
    "max_evaluate": 10,
    "smart_prefilter": true,
    "soft_rules": {
      "ignore": ["что НЕ снижать в оценке"],
      "focus": ["на что смотреть при чтении"],
      "extra_stop": ["стоп только для скринера"]
    }
  }
}

Правила поиска HH (обязательно соблюдай — как в интерфейсе HH):
1) «Любое из слов» (ИЛИ): пиши альтернативы РОЛЕЙ/участков КАЖДУЮ С НОВОЙ СТРОКИ в keywords.
   Пример казначея: keywords = "Казначей\\nбанк-клиент\\nбанк" — НЕ склеивай их в одну фразу «Казначей банк-клиент».
   Термин с дефисом (банк-клиент) — одна строка-вариант целиком.
2) «Все слова» / обязательный навык (И): выноси в keywords_and (напр. только "1С"). Максимум 1–2 обязательных термина — иначе выдача схлопнется. НЕ пихай туда весь стек (ВЭД, календарь, выписки — это soft/must_have для ИИ).
3) keywords_logic оставляй "any" (режим «любое из» для одной строки с несколькими токенами, если keywords_and пуст и одна строка).
4) schedule всегда \"\" — не фильтруй график на API.
5) period_days по умолчанию 7 (Неделя на HH).
6) area_id обязателен при офисе в городе.

Не путай ИЛИ и связку: связка «бухгалтер + банк-клиент как обязательные оба» — это keywords_and или must_have для ИИ, а не одна строка keywords с AND по умолчанию без нужды.

Правила hard vs soft:
- API: keywords / keywords_and / area / period / salary.
- Формат работы, джобхоппинг, культура — soft_rules / portrait.
"""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_plan() -> dict[str, Any]:
    return {
        "version": 0,
        "status": "empty",  # empty | draft | approved | stale
        "human_text": "",
        "machine": {},
        "notes": [],
        "sources": [],
        "created_at": None,
        "updated_at": None,
        "approved_at": None,
        "profile_fingerprint": "",
    }


def normalize_plan(raw: Any) -> dict[str, Any]:
    base = empty_plan()
    if not isinstance(raw, dict):
        return base
    data = deepcopy(base)
    data["version"] = int(raw.get("version") or 0)
    status = str(raw.get("status") or "empty").strip()
    if status not in ("empty", "draft", "approved", "stale"):
        status = "empty"
    data["status"] = status
    data["human_text"] = str(raw.get("human_text") or "").strip()
    data["machine"] = raw.get("machine") if isinstance(raw.get("machine"), dict) else {}
    notes = raw.get("notes")
    data["notes"] = [str(n).strip() for n in notes if str(n).strip()] if isinstance(notes, list) else []
    sources = raw.get("sources")
    data["sources"] = [str(s).strip() for s in sources if str(s).strip()] if isinstance(sources, list) else []
    for key in ("created_at", "updated_at", "approved_at", "profile_fingerprint"):
        data[key] = raw.get(key) or ("" if key == "profile_fingerprint" else None)
    return data


def get_plan_from_vacancy(vacancy: models.Vacancy) -> dict[str, Any]:
    docs = vacancy.documents or {}
    return normalize_plan(docs.get(PLAN_DOC_KEY))


def profile_fingerprint(vacancy: models.Vacancy) -> str:
    docs = vacancy.documents or {}
    profile = str(docs.get("profile") or docs.get("профиль") or "")[:2000]
    title = vacancy.title or ""
    return f"{len(title)}:{hash((title, profile)) & 0xFFFFFFFF:08x}"


def mark_plan_stale_if_needed(vacancy: models.Vacancy) -> bool:
    plan = get_plan_from_vacancy(vacancy)
    if plan["status"] != "approved":
        return False
    fp = profile_fingerprint(vacancy)
    if plan.get("profile_fingerprint") and plan["profile_fingerprint"] != fp:
        plan["status"] = "stale"
        plan["updated_at"] = _now()
        _save_plan(vacancy, plan)
        return True
    return False


def _save_plan(vacancy: models.Vacancy, plan: dict[str, Any]) -> None:
    docs = dict(vacancy.documents or {})
    docs[PLAN_DOC_KEY] = normalize_plan(plan)
    vacancy.documents = docs
    flag_modified(vacancy, "documents")


def soft_rules_text(machine: dict[str, Any] | None) -> str:
    soft = (machine or {}).get("soft_rules") if isinstance(machine, dict) else None
    if not isinstance(soft, dict):
        return ""
    parts: list[str] = ["ПРАВИЛА СКРИНЕРА (soft_rules из утверждённого плана):"]
    ignore = soft.get("ignore") if isinstance(soft.get("ignore"), list) else []
    focus = soft.get("focus") if isinstance(soft.get("focus"), list) else []
    stop = soft.get("extra_stop") if isinstance(soft.get("extra_stop"), list) else []
    if ignore:
        parts.append("ИГНОРИРОВАТЬ при оценке (не снижать балл, пометить «по правке рекрутера»):")
        parts.extend(f"- {x}" for x in ignore if str(x).strip())
    if focus:
        parts.append("ОБРАТИТЬ ВНИМАНИЕ:")
        parts.extend(f"- {x}" for x in focus if str(x).strip())
    if stop:
        parts.append("ДОП. СТОП-ФАКТОРЫ (только оценка, не API):")
        parts.extend(f"- {x}" for x in stop if str(x).strip())
    return "\n".join(parts) if len(parts) > 1 else ""


def compile_machine_to_criteria(machine: dict[str, Any] | None) -> dict[str, Any]:
    """Map strategist machine block → hh_search_criteria for the worker."""
    m = machine if isinstance(machine, dict) else {}
    soft = m.get("soft_rules") if isinstance(m.get("soft_rules"), dict) else {}
    ignore = [str(x).strip() for x in (soft.get("ignore") or []) if str(x).strip()]
    focus = [str(x).strip() for x in (soft.get("focus") or []) if str(x).strip()]
    stop = [str(x).strip() for x in (soft.get("extra_stop") or []) if str(x).strip()]

    comment_bits = []
    if ignore:
        comment_bits.append("Игнорировать: " + "; ".join(ignore))
    if focus:
        comment_bits.append("Фокус: " + "; ".join(focus))

    raw = {
        "keywords": m.get("keywords") or "",
        "keywords_and": m.get("keywords_and") or "",
        "keywords_logic": m.get("keywords_logic") or "any",
        "area_id": m.get("area_id"),
        "area_name": m.get("area_name") or "",
        "schedule": "",  # do not lock HH API schedule; keep soft in portrait
        "period_days": m.get("period_days") if m.get("period_days") is not None else 7,
        "experience_from": m.get("experience_from"),
        "salary_to": m.get("salary_to"),
        "office_required": m.get("office_required") or "first_3_months",
        "office_address": m.get("office_address") or "",
        "max_commute_min": m.get("max_commute_min") or 60,
        "title_priority": m.get("title_priority") or [],
        "must_have": m.get("must_have") or [],
        "reject": list(m.get("reject") or []) + stop,
        "portrait": m.get("portrait") if isinstance(m.get("portrait"), dict) else {},
        "recruiter_comment": "\n".join(comment_bits),
        "max_search": m.get("max_search") or 20,
        "max_evaluate": m.get("max_evaluate") or 10,
        "smart_prefilter": m.get("smart_prefilter", True),
        "soft_rules": soft,
        "prefill_meta": {
            "prefilled_at": _now(),
            "sources": ["hh_search_plan"],
            "recruiter_edited": True,
        },
    }
    return ensure_portrait(normalize_criteria(raw))


def _call_strategist(
    *,
    context: str,
    notes: list[str],
    previous: dict[str, Any] | None,
    settings: Settings,
) -> dict[str, Any]:
    user_parts = [context]
    if previous and previous.get("human_text"):
        user_parts.append("\n=== ПРЕДЫДУЩИЙ ПЛАН ===\n" + str(previous.get("human_text")))
        user_parts.append("\n=== MACHINE (предыдущий) ===\n" + str(previous.get("machine") or {}))
    if notes:
        user_parts.append("\n=== КОРРЕКТИРОВКИ РЕКРУТЕРА (учти все) ===\n" + "\n".join(f"- {n}" for n in notes))
    data = chat_json(
        settings,
        system=STRATEGIST_SYSTEM,
        user="\n".join(user_parts),
        temperature=0.25,
        max_tokens=3500,
    )
    if not isinstance(data, dict):
        raise RuntimeError("Стратег вернул не JSON-объект")
    human = str(data.get("human_text") or "").strip()
    machine = data.get("machine") if isinstance(data.get("machine"), dict) else {}
    if not human:
        raise RuntimeError("Стратег не вернул human_text")
    if not str(machine.get("keywords") or "").strip():
        raise RuntimeError("Стратег не вернул keywords в machine")
    return {"human_text": human, "machine": machine}


def generate_plan(
    db: Session,
    vacancy: models.Vacancy,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    context, sources = build_vacancy_context(vacancy, db)
    if len(context.strip()) < 40:
        raise ValueError("Мало данных: заполните профиль или добавьте расшифровку разговора")
    result = _call_strategist(context=context, notes=[], previous=None, settings=settings)
    prev = get_plan_from_vacancy(vacancy)
    plan = normalize_plan(
        {
            "version": int(prev.get("version") or 0) + 1,
            "status": "draft",
            "human_text": result["human_text"],
            "machine": result["machine"],
            "notes": [],
            "sources": sources,
            "created_at": prev.get("created_at") or _now(),
            "updated_at": _now(),
            "approved_at": None,
            "profile_fingerprint": profile_fingerprint(vacancy),
        }
    )
    _save_plan(vacancy, plan)
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return plan


def revise_plan(
    db: Session,
    vacancy: models.Vacancy,
    note: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    note = (note or "").strip()
    if not note:
        raise ValueError("Укажите корректировку")
    prev = get_plan_from_vacancy(vacancy)
    if not prev.get("human_text") and not prev.get("machine"):
        raise ValueError("Сначала подготовьте план")
    notes = list(prev.get("notes") or []) + [note]
    context, sources = build_vacancy_context(vacancy, db)
    result = _call_strategist(context=context, notes=notes, previous=prev, settings=settings)
    plan = normalize_plan(
        {
            "version": int(prev.get("version") or 0) + 1,
            "status": "draft",
            "human_text": result["human_text"],
            "machine": result["machine"],
            "notes": notes,
            "sources": sources or prev.get("sources") or [],
            "created_at": prev.get("created_at") or _now(),
            "updated_at": _now(),
            "approved_at": None,
            "profile_fingerprint": profile_fingerprint(vacancy),
        }
    )
    _save_plan(vacancy, plan)
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return plan


def approve_plan(db: Session, vacancy: models.Vacancy) -> dict[str, Any]:
    plan = get_plan_from_vacancy(vacancy)
    if not plan.get("human_text") or not plan.get("machine"):
        raise ValueError("Нет плана для утверждения")
    criteria = compile_machine_to_criteria(plan.get("machine"))
    docs = save_criteria_to_documents(vacancy.documents, criteria)
    plan["status"] = "approved"
    plan["approved_at"] = _now()
    plan["updated_at"] = _now()
    plan["profile_fingerprint"] = profile_fingerprint(vacancy)
    docs[PLAN_DOC_KEY] = normalize_plan(plan)
    # keep soft_rules on criteria for portrait_text
    crit = dict(docs[DOC_KEY])
    crit["soft_rules"] = (plan.get("machine") or {}).get("soft_rules") or {}
    docs[DOC_KEY] = crit
    vacancy.documents = docs
    flag_modified(vacancy, "documents")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return {"plan": get_plan_from_vacancy(vacancy), "criteria": normalize_criteria(crit)}
