"""Manual HH resume evaluation + AI suggestions to soften search criteria."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.hh_client import HhApiError, HhClient
from app.services.hh_resume_text import resume_card_summary, resume_to_text
from app.services.hh_search_criteria import (
    criteria_from_vacancy_documents,
    ensure_portrait,
    normalize_criteria,
    portrait_text_for_ai,
)
from app.services.resume_eval import evaluate_resume_text
from app.services.vacancy_docs import extract_profile_text

_RESUME_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w.-]*\.)?hh\.(?:ru|kz|uz)/resume/([a-zA-Z0-9]+)",
    re.I,
)
_BARE_ID_RE = re.compile(r"^[a-zA-Z0-9]{10,64}$")


def parse_hh_resume_refs(text: str) -> list[str]:
    """Extract unique HH resume ids from URLs or bare ids (one per line or mixed)."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in (text or "").replace(",", "\n").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _RESUME_URL_RE.search(line)
        if m:
            rid = m.group(1)
        elif _BARE_ID_RE.match(line):
            rid = line
        else:
            # try id after last slash
            tail = line.rstrip("/").split("/")[-1].split("?")[0]
            rid = tail if _BARE_ID_RE.match(tail) else ""
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append(rid)
    return out


def evaluate_manual_hh_resumes(
    db: Session,
    vacancy: models.Vacancy,
    refs_text: str,
    *,
    settings: Settings | None = None,
    criteria: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch HH resumes by id/URL and score them vs vacancy profile. Sequential."""
    settings = settings or get_settings()
    ids = parse_hh_resume_refs(refs_text)
    if not ids:
        raise ValueError("Не найдено ссылок или id резюме HH")

    crit = normalize_criteria(criteria or {})
    if not crit.get("keywords") and not (crit.get("portrait") or {}).get("hard"):
        crit = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    crit = ensure_portrait(crit)
    selection_rules = portrait_text_for_ai(crit)
    profile = extract_profile_text(vacancy.documents)

    client = HhClient(settings)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for rid in ids:
        entry: dict[str, Any] = {
            "hh_resume_id": rid,
            "url": f"https://hh.ru/resume/{rid}",
            "title": "",
            "area": None,
            "ai_score": None,
            "ai_preview": "",
            "ai_strengths": [],
            "ai_weaknesses": [],
            "ai_comment_sections": {},
            "title_fit": None,
            "office_fit": None,
            "commute_ok": None,
            "error": None,
        }
        try:
            raw = client.get_resume(rid)
            card = resume_card_summary(raw)
            entry.update(card)
            text = resume_to_text(raw)
            scored = evaluate_resume_text(
                text,
                profile,
                vacancy.title or "",
                settings,
                selection_rules=selection_rules,
            )
            entry.update(
                {
                    "ai_score": scored.get("ai_score"),
                    "ai_preview": scored.get("ai_preview") or "",
                    "ai_strengths": scored.get("ai_strengths") or [],
                    "ai_weaknesses": scored.get("ai_weaknesses") or [],
                    "ai_comment_sections": scored.get("ai_comment_sections") or {},
                    "title_fit": scored.get("title_fit"),
                    "office_fit": scored.get("office_fit"),
                    "commute_ok": scored.get("commute_ok"),
                }
            )
        except HhApiError as exc:
            entry["error"] = str(exc)
            errors.append(f"{rid}: {exc}")
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)
            errors.append(f"{rid}: {exc}")
        rows.append(entry)

    rows.sort(key=lambda r: (-(r.get("ai_score") if isinstance(r.get("ai_score"), int) else -1), r.get("title") or ""))
    return {
        "items": rows,
        "compared": len(rows),
        "errors": errors,
        "criteria_snapshot": {
            "keywords": crit.get("keywords"),
            "portrait": crit.get("portrait"),
            "must_have": crit.get("must_have"),
            "reject": crit.get("reject"),
            "period_days": crit.get("period_days"),
            "area_id": crit.get("area_id"),
            "schedule": crit.get("schedule"),
            "experience_from": crit.get("experience_from"),
            "salary_to": crit.get("salary_to"),
        },
    }


SOFTEN_SYSTEM = """Ты помощник рекрутера по поиску на HH.
По текущим критериям и результатам (или эталонным резюме) предложи, что можно смягчить,
чтобы найти больше подходящих кандидатов — без разрушения смысла вакансии.

Верни JSON:
{
  "summary": "2-4 предложения: почему выдача узкая / что видно по хорошим резюме",
  "suggestions": [
    {
      "id": "snake_case_id",
      "title": "Краткий заголовок",
      "rationale": "Почему это поможет",
      "field": "period_days|area_id|schedule|experience_from|salary_to|must_have|reject|portrait_hard|portrait_important|keywords|priorities",
      "action": "clear|set|remove_item|downgrade_priority|widen",
      "value": null,
      "item": null,
      "priority_key": null,
      "new_priority": null
    }
  ]
}

Правила:
- 3–8 suggestions, только практичные.
- action=set → value новое значение; clear → обнулить поле; remove_item → item текст из списка;
  downgrade_priority → priority_key + new_priority (hard|important|nice);
  widen → для period_days увеличить (value=число дней), для area очистить.
- Не выдумывай поля вне списка.
- id уникальны.
"""


def suggest_criteria_softening(
    *,
    vacancy_title: str,
    criteria: dict[str, Any],
    search_results: list[dict[str, Any]] | None = None,
    good_resumes: list[dict[str, Any]] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    crit = normalize_criteria(criteria or {})
    parts = [
        f"Вакансия: {vacancy_title}",
        f"Критерии JSON:\n{crit}",
    ]
    if search_results:
        brief = []
        for r in search_results[:25]:
            brief.append(
                {
                    "title": r.get("title"),
                    "score": r.get("ai_score"),
                    "preview": (r.get("ai_preview") or "")[:180],
                    "skipped_prefilter": r.get("skipped_prefilter"),
                    "prefilter_reason": r.get("prefilter_reason"),
                    "error": r.get("error"),
                }
            )
        parts.append(f"Результаты автопоиска (сжато):\n{brief}")
    if good_resumes:
        brief = []
        for r in good_resumes[:12]:
            brief.append(
                {
                    "title": r.get("title"),
                    "score": r.get("ai_score"),
                    "strengths": r.get("ai_strengths") or [],
                    "weaknesses": r.get("ai_weaknesses") or [],
                    "preview": (r.get("ai_preview") or "")[:200],
                }
            )
        parts.append(f"Хорошие / эталонные резюме:\n{brief}")

    data = chat_json(
        settings,
        system=SOFTEN_SYSTEM,
        user="\n\n".join(parts),
        temperature=0.3,
        max_tokens=2500,
    )
    if not isinstance(data, dict):
        return {"summary": "", "suggestions": []}
    suggestions = data.get("suggestions") if isinstance(data.get("suggestions"), list) else []
    cleaned = []
    for s in suggestions:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        if not sid:
            continue
        cleaned.append(
            {
                "id": sid,
                "title": str(s.get("title") or sid).strip(),
                "rationale": str(s.get("rationale") or "").strip(),
                "field": str(s.get("field") or "").strip(),
                "action": str(s.get("action") or "").strip(),
                "value": s.get("value"),
                "item": s.get("item"),
                "priority_key": s.get("priority_key"),
                "new_priority": s.get("new_priority"),
            }
        )
    return {
        "summary": str(data.get("summary") or "").strip(),
        "suggestions": cleaned,
    }


def apply_soften_suggestions(
    criteria: dict[str, Any],
    suggestions: list[dict[str, Any]],
    selected_ids: list[str],
) -> dict[str, Any]:
    """Apply checked soften suggestions to criteria (pure function)."""
    crit = normalize_criteria(criteria or {})
    wanted = {str(x).strip() for x in selected_ids if str(x).strip()}
    by_id = {str(s.get("id") or ""): s for s in suggestions if isinstance(s, dict)}

    def _remove_line(lines: list[str], item: str) -> list[str]:
        needle = (item or "").strip().lower()
        if not needle:
            return lines
        return [x for x in lines if x.strip().lower() != needle]

    for sid in wanted:
        s = by_id.get(sid)
        if not s:
            continue
        field = str(s.get("field") or "")
        action = str(s.get("action") or "")
        if field == "period_days":
            if action == "clear":
                crit["period_days"] = None
            elif action in ("set", "widen"):
                try:
                    crit["period_days"] = int(s.get("value") or 365)
                except (TypeError, ValueError):
                    crit["period_days"] = 365
        elif field == "area_id":
            if action in ("clear", "widen"):
                crit["area_id"] = None
                crit["area_name"] = ""
            elif action == "set":
                try:
                    crit["area_id"] = int(s.get("value"))
                except (TypeError, ValueError):
                    pass
        elif field == "schedule":
            if action == "clear":
                crit["schedule"] = ""
            elif action == "set":
                crit["schedule"] = str(s.get("value") or "")
        elif field == "experience_from":
            if action == "clear":
                crit["experience_from"] = None
            elif action == "set":
                try:
                    crit["experience_from"] = int(s.get("value"))
                except (TypeError, ValueError):
                    crit["experience_from"] = None
        elif field == "salary_to":
            if action == "clear":
                crit["salary_to"] = None
            elif action == "set":
                try:
                    crit["salary_to"] = int(s.get("value"))
                except (TypeError, ValueError):
                    pass
        elif field == "must_have":
            if action == "remove_item":
                crit["must_have"] = _remove_line(list(crit.get("must_have") or []), str(s.get("item") or ""))
            elif action == "clear":
                crit["must_have"] = []
        elif field == "reject":
            if action == "remove_item":
                crit["reject"] = _remove_line(list(crit.get("reject") or []), str(s.get("item") or ""))
            elif action == "clear":
                crit["reject"] = []
        elif field == "portrait_hard":
            portrait = dict(crit.get("portrait") or {})
            hard = list(portrait.get("hard") or [])
            if action == "remove_item":
                hard = _remove_line(hard, str(s.get("item") or ""))
            elif action == "clear":
                hard = []
            portrait["hard"] = hard
            crit["portrait"] = portrait
        elif field == "portrait_important":
            portrait = dict(crit.get("portrait") or {})
            important = list(portrait.get("important") or [])
            if action == "remove_item":
                important = _remove_line(important, str(s.get("item") or ""))
            portrait["important"] = important
            crit["portrait"] = portrait
        elif field == "keywords" and action == "set":
            crit["keywords"] = str(s.get("value") or crit.get("keywords") or "")
        elif field == "priorities" and action == "downgrade_priority":
            key = str(s.get("priority_key") or "").strip()
            new_p = str(s.get("new_priority") or "nice").strip()
            if key and new_p in ("hard", "important", "nice"):
                pri = dict(crit.get("priorities") or {})
                pri[key] = new_p
                crit["priorities"] = pri

    return ensure_portrait(normalize_criteria(crit))
