"""Cold resume evaluation for HH shortlist (no Streamlit coupling)."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.core.config import Settings

EVAL_SYSTEM = """Ты — опытный HR-директор. Оцени соответствие резюме профилю на этапе холодного отбора.
Шкала rating: 0–4 (целое число).

Если есть блок «КОММЕНТАРИЙ РЕКРУТЕРА» — это приоритет №1: следуй ему раньше остальных правил.

Приоритеты в блоке «ПРАВИЛА ОТБОРА»:
- ЖЁСТКО: нет совпадения → rating 0 или 1, в «риски» явно укажи причину отсева.
- ВАЖНО: нет → сильно понизь rating (обычно не выше 2), но можно оставить.
- ЖЕЛАТЕЛЬНО: при конфликте с более важными критериями «закрывай глаза» на них в первую очередь.

Дополнительно жёстко учитывай:
- Сфера (industry): если в профиле/правилах нужна конкретная сфера (fashion и т.п.), а в резюме её нет и нет близкого пересечения → rating ≤ 1.
- Уровень должности: кандидат head of / руководитель направления / директор на исполнительскую роль → обычно rating 0–1 (overqualified + завышенные ожидания по ЗП), если рекрутер явно не просит иное.
- Зарплатные ожидания: если в резюме ЗП заметно выше вилки вакансии → понизь rating и укажи в рисках.

Дополнительно верни флаги:
- title_fit: "yes" | "partial" | "no"
- office_fit: "yes" | "partial" | "no" | "unknown"
- commute_ok: "yes" | "no" | "unknown"

Верни ТОЛЬКО JSON:
{
  "rating": 3,
  "title_fit": "yes",
  "office_fit": "partial",
  "commute_ok": "unknown",
  "comment_sections": {
    "соответствие": "1–2 предложения",
    "опыт_и_навыки": "1–2 предложения",
    "риски": ["..."],
    "проверить_на_интервью": ["..."],
    "итог": "1 предложение — брать ли в работу / открывать ли контакт"
  },
  "strengths": ["..."],
  "weaknesses": ["..."]
}
Контактов в резюме может не быть — оценивай по опыту и навыкам."""


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


def evaluate_resume_text(
    resume_text: str,
    profile_text: str,
    job_title: str,
    settings: Settings,
    *,
    selection_rules: str = "",
) -> dict[str, Any]:
    api_key = (settings.routerai_api_key or settings.ai_api_key or "").strip()
    if not api_key:
        raise RuntimeError(
            "Нет ключа ИИ (ROUTERAI_API_KEY / AI_API_KEY). Нужен для оценки резюме."
        )
    base = (settings.ai_base_url or "https://routerai.ru/api/v1").rstrip("/")
    model = (settings.ai_model_name or "").strip() or "qwen/qwen3.5-plus-20260420"

    profile = (profile_text or "").strip()[:5000]
    resume = (resume_text or "").strip()[:8000]
    rules = (selection_rules or "").strip()[:4000]
    if not resume:
        raise RuntimeError("Пустой текст резюме для оценки")

    user_parts = [f"Должность: {job_title}"]
    if rules:
        user_parts.append(f"\n{rules}")
    user_parts.append(f"\nПРОФИЛЬ:\n{profile or '—'}")
    user_parts.append(f"\nРЕЗЮМЕ:\n{resume}")

    payload = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": EVAL_SYSTEM + "\n\n/no_think\nОтвечай сразу валидным JSON."},
            {"role": "user", "content": "\n".join(user_parts)},
        ],
    }
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ИИ API {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    result = _parse_json(content)
    rating = result.get("rating", 0)
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    rating = max(0, min(4, rating))
    sections = result.get("comment_sections") if isinstance(result.get("comment_sections"), dict) else {}
    итог = ""
    if sections:
        итог = str(sections.get("итог") or "").strip()

    def _fit(key: str) -> str:
        v = str(result.get(key) or "unknown").strip().lower()
        if v in {"yes", "partial", "no", "unknown"}:
            return v
        return "unknown"

    return {
        "ai_score": rating,
        "ai_comment_sections": sections,
        "ai_preview": итог or str(result.get("comment") or "")[:280],
        "ai_strengths": result.get("strengths") or [],
        "ai_weaknesses": result.get("weaknesses") or [],
        "title_fit": _fit("title_fit"),
        "office_fit": _fit("office_fit"),
        "commute_ok": _fit("commute_ok"),
    }
