"""Post-search summary + recommendations for the recruiter."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.core.config import Settings, get_settings
from app.services.ai_json import chat_json

DEBRIEF_SYSTEM = """Ты помощник рекрутера после холодного поиска на HH.
По статистике прогона предложи конкретные правки запроса/фильтров.
Верни JSON:
{
  "headline": "1 короткое предложение итога",
  "suggestions": ["2–5 конкретных действий: изменить keywords, period, убрать/добавить слово, расширить/сузить город…"],
  "warnings": ["0–3 риска, если есть"]
}
Пиши по-русски, без воды. Не предлагай открывать контакты.
"""


def summarize_results(results: list[dict[str, Any]], *, found: int, evaluated: int) -> dict[str, Any]:
    evaluated_rows = [
        r
        for r in results
        if r.get("ai_score") is not None
        and not r.get("skipped_prefilter")
        and not r.get("skipped_seen")
        and not r.get("skipped_eval")
    ]
    skipped = [
        r
        for r in results
        if r.get("skipped_prefilter") or r.get("skipped_seen") or r.get("skipped_eval")
    ]
    reasons: Counter[str] = Counter()
    for r in skipped:
        reason = (
            str(r.get("prefilter_reason") or r.get("seen_label") or "").strip()
            or ("уже смотрели" if r.get("skipped_seen") else "отсеян")
        )
        # normalize long reasons to short keys
        key = reason.split(":")[0].strip()[:80]
        reasons[key] += 1

    scores = [int(r["ai_score"]) for r in evaluated_rows if r.get("ai_score") is not None]
    return {
        "found": found,
        "evaluated": evaluated,
        "shown": len(evaluated_rows),
        "skipped": len(skipped),
        "score_avg": round(sum(scores) / len(scores), 2) if scores else None,
        "score_ge_3": sum(1 for s in scores if s >= 3),
        "reject_reasons": [{"reason": k, "count": v} for k, v in reasons.most_common(8)],
    }


def build_debrief(
    *,
    results: list[dict[str, Any]],
    found: int,
    evaluated: int,
    criteria: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    stats = summarize_results(results, found=found, evaluated=evaluated)
    settings = settings or get_settings()
    keywords = str(criteria.get("keywords") or "")[:500]
    area = criteria.get("area_name") or criteria.get("area_id") or "—"
    period = criteria.get("period_days")
    try:
        data = chat_json(
            settings,
            system=DEBRIEF_SYSTEM,
            user=(
                f"Статистика: {stats}\n"
                f"Город: {area}; period_days={period}\n"
                f"Keywords:\n{keywords}\n"
                f"Примеры оценённых: "
                + str(
                    [
                        {
                            "title": r.get("title"),
                            "area": r.get("area"),
                            "score": r.get("ai_score"),
                            "preview": (r.get("ai_preview") or "")[:120],
                        }
                        for r in results
                        if r.get("ai_score") is not None
                    ][:6]
                )
            ),
            temperature=0.2,
            max_tokens=900,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            **stats,
            "headline": f"Изучено {found}, оценено {evaluated}, в списке {stats['shown']}.",
            "suggestions": [
                "Перегенерировать план с более точными запросами (2–4 слова в строке).",
                "Проверить город и period (неделя vs месяц).",
            ],
            "warnings": [f"ИИ-итог недоступен: {exc}"[:200]],
        }

    if not isinstance(data, dict):
        data = {}
    suggestions = data.get("suggestions") if isinstance(data.get("suggestions"), list) else []
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    return {
        **stats,
        "headline": str(data.get("headline") or "").strip()
        or f"Изучено {found}, оценено {evaluated}, показано {stats['shown']}.",
        "suggestions": [str(s).strip() for s in suggestions if str(s).strip()][:6],
        "warnings": [str(w).strip() for w in warnings if str(w).strip()][:4],
    }
