"""AI structured briefing for Analytics (stats dashboard context)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.services.ai_json import chat_json
from app.services.stats_service import build_dashboard_stats

SYSTEM = """Ты — аналитик HR-рекрутинга. По запросу пользователя и ФАКТАМ из JSON
собери красивый структурированный расклад для экрана «Аналитика».

Правила:
- Используй ТОЛЬКО числа и имена из данных. Не выдумывай KPI, кандидатов, вакансии.
- Если данных мало — честно напиши об этом в summary и actions.
- Пиши по-русски, коротко и по делу.
- Ответ — один JSON-объект без markdown.

Формат ответа:
{
  "title": "заголовок расклада",
  "summary": "2–4 предложения: суть ситуации",
  "kpis": [
    {"label": "подпись", "value": "число или текст", "tone": "blue|attention|orange|teal|neutral"}
  ],
  "sections": [
    {
      "title": "заголовок блока",
      "body": "опциональный абзац",
      "items": [
        {"text": "строка списка", "tone": "neutral|attention|ok"}
      ]
    }
  ],
  "actions": ["конкретный следующий шаг", "..."]
}

kpis: 3–6 штук. sections: 1–4. actions: 2–5.
tone у kpi: blue|attention|orange|teal|neutral.
"""


def _compact_dashboard(data: dict[str, Any]) -> dict[str, Any]:
    kpis = [
        {"key": k.get("key"), "label": k.get("label"), "value": k.get("value"), "unit": k.get("unit")}
        for k in (data.get("kpis") or [])[:12]
    ]
    attention = [
        {
            "name": a.get("name"),
            "vacancy": a.get("vacancy_title"),
            "reason": a.get("reason"),
        }
        for a in (data.get("attention") or [])[:15]
    ]
    funnel = [
        {"stage": f.get("stage"), "count": f.get("count")}
        for f in (data.get("funnel_flow") or [])[:20]
    ]
    vacancies = [
        {
            "title": v.get("title"),
            "active": v.get("active"),
            "days_open": v.get("days_open"),
            "candidates": v.get("candidates"),
            "hires": v.get("hires"),
        }
        for v in (data.get("vacancies_table") or [])[:20]
    ]
    risks = data.get("warranty_risks") or {}
    claims = [
        {
            "name": c.get("candidate_name"),
            "vacancy": c.get("vacancy_title"),
            "days": c.get("days_worked"),
            "reason": c.get("reason"),
        }
        for c in (risks.get("claims") or [])[:10]
    ]
    hh = data.get("hh")
    return {
        "period": data.get("period"),
        "period_from": data.get("period_from"),
        "period_to": data.get("period_to"),
        "kpis": kpis,
        "attention": attention,
        "funnel_flow": funnel,
        "vacancies": vacancies,
        "warranty": {
            "claims_count": risks.get("claims_count", 0),
            "warranty_searches": risks.get("warranty_searches", 0),
            "multi_hire_vacancies": risks.get("multi_hire_vacancies", 0),
            "claims": claims,
        },
        "hh": hh,
    }


def _normalize_brief(raw: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(raw, list):
        raw = raw[0] if raw and isinstance(raw[0], dict) else {}
    if not isinstance(raw, dict):
        raw = {}

    def _tone(v: Any, allowed: set[str], default: str) -> str:
        s = str(v or "").strip().lower()
        return s if s in allowed else default

    kpis_out = []
    for row in raw.get("kpis") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        value = row.get("value")
        if value is None:
            continue
        if not label:
            continue
        kpis_out.append(
            {
                "label": label[:80],
                "value": str(value)[:40],
                "tone": _tone(row.get("tone"), {"blue", "attention", "orange", "teal", "neutral"}, "neutral"),
            }
        )

    sections_out = []
    for sec in raw.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "").strip()
        if not title:
            continue
        items = []
        for it in sec.get("items") or []:
            if not isinstance(it, dict):
                continue
            text = str(it.get("text") or "").strip()
            if not text:
                continue
            items.append(
                {
                    "text": text[:240],
                    "tone": _tone(it.get("tone"), {"neutral", "attention", "ok"}, "neutral"),
                }
            )
        body = str(sec.get("body") or "").strip()[:800] or None
        sections_out.append({"title": title[:100], "body": body, "items": items[:12]})

    actions = []
    for a in raw.get("actions") or []:
        t = str(a or "").strip()
        if t:
            actions.append(t[:200])

    title = str(raw.get("title") or "Расклад ИИ").strip()[:120] or "Расклад ИИ"
    summary = str(raw.get("summary") or "").strip()[:800]
    return {
        "title": title,
        "summary": summary,
        "kpis": kpis_out[:6],
        "sections": sections_out[:4],
        "actions": actions[:5],
    }


def generate_stats_ai_brief(
    db: Session,
    *,
    prompt: str,
    client_id: int | None = None,
    vacancy_id: int | None = None,
    period: str = "day",
    date_from: str | None = None,
    date_to: str | None = None,
    active_vacancies_only: bool = True,
    organization_id: Any = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    text = (prompt or "").strip()
    if len(text) < 3:
        raise ValueError("Опишите запрос подробнее (хотя бы несколько слов)")
    if len(text) > 2000:
        raise ValueError("Слишком длинный запрос (макс. 2000 символов)")

    settings = settings or get_settings()

    # Executive: funnel + vacancies + risks; operational: attention
    exec_dash = build_dashboard_stats(
        db,
        mode="executive",
        period=period,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
    )
    op_dash = build_dashboard_stats(
        db,
        mode="operational",
        period=period,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
    )
    merged = dict(exec_dash)
    merged["attention"] = op_dash.get("attention") or []
    merged["kpis"] = op_dash.get("kpis") or exec_dash.get("kpis") or []
    if op_dash.get("hh"):
        merged["hh"] = op_dash["hh"]

    context = _compact_dashboard(merged)
    user = (
        f"Запрос пользователя:\n{text}\n\n"
        f"Данные статистики (JSON, только факты):\n{json.dumps(context, ensure_ascii=False)}"
    )
    raw = chat_json(
        settings,
        system=SYSTEM,
        user=user,
        temperature=0.35,
        max_tokens=3500,
        db=db,
        task="stats_ai_brief",
    )
    brief = _normalize_brief(raw)
    if not brief.get("summary") and not brief.get("kpis") and not brief.get("sections"):
        raise RuntimeError("ИИ не вернул расклад — попробуйте переформулировать запрос")
    return brief
