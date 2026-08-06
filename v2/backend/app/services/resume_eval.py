"""Cold resume evaluation for HH shortlist (no Streamlit coupling)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.ai_errors import log_ai_error
from app.services.ai_json import MAX_AI_INPUT_CHARS, chat_json, truncate_ai_input

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


def evaluate_resume_text(
    resume_text: str,
    profile_text: str,
    job_title: str,
    settings: Settings,
    *,
    selection_rules: str = "",
    db: Session | None = None,
) -> dict[str, Any]:
    # Budget: title/rules short; rest shared under MAX_AI_INPUT_CHARS
    rules = (selection_rules or "").strip()[:2000]
    title = (job_title or "").strip()[:500]
    header = f"Должность: {title}"
    if rules:
        header += f"\n\n{rules}"
    budget = max(2000, MAX_AI_INPUT_CHARS - len(header) - 64)
    profile_budget = min(5000, budget // 3)
    resume_budget = budget - profile_budget
    profile = truncate_ai_input((profile_text or "").strip(), profile_budget)
    resume = truncate_ai_input((resume_text or "").strip(), resume_budget)
    if not resume:
        raise RuntimeError("Пустой текст резюме для оценки")

    user_content = f"{header}\n\nПРОФИЛЬ:\n{profile or '—'}\n\nРЕЗЮМЕ:\n{resume}"
    user_content = truncate_ai_input(user_content, MAX_AI_INPUT_CHARS)

    result = chat_json(
        settings,
        system=EVAL_SYSTEM,
        user=user_content,
        temperature=0.3,
        max_tokens=1500,
        db=db,
        task="resume_eval",
    )
    if not isinstance(result, dict) or "rating" not in result:
        if isinstance(result, dict) and result:
            log_ai_error(
                db,
                task="resume_eval",
                error_kind="schema",
                error_message="missing rating in parsed JSON",
                raw_response=str(result)[:2000],
                meta={"job_title": title[:120]},
            )
        raise RuntimeError("ИИ вернул невалидный JSON (оценка резюме)")

    try:
        rating = int(result.get("rating"))
    except (TypeError, ValueError) as exc:
        log_ai_error(
            db,
            task="resume_eval",
            error_kind="schema",
            error_message=f"rating not int: {exc}",
            raw_response=str(result)[:2000],
            meta={"job_title": title[:120]},
        )
        raise RuntimeError("ИИ вернул rating в неверном формате") from exc
    rating = max(0, min(4, rating))
    sections = (
        result.get("comment_sections")
        if isinstance(result.get("comment_sections"), dict)
        else {}
    )
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
