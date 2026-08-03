"""Generate / regenerate vacancy document sections via RouterAI (v2 only)."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.services.ai_json import chat_json
from app.services.vacancy_docs import extract_profile_text

GENERATABLE_KEYS = ("profile", "vacancy_text", "questions", "keywords")

QUESTIONNAIRE_RULES = """
Опросник для первичного собеседования:
- 6–8 основных вопросов (макс. 10).
- Обязательно: причина поиска/ухода; что вдохновляет; что расстраивает; рекомендации/обратная связь прошлых работодателей.
- Остальное — hard skills / опыт / soft skills из профиля.
- У каждого: вопрос, уточняющие_вопросы (1–3), проверяет_требование, категория, пример_ответа.
"""

PROFILE_SYSTEM = """Ты — HR-директор. Сформируй или обнови профиль должности.
Верни ТОЛЬКО JSON:
{"профиль": {
  "подразделение": "",
  "непосредственный_руководитель": "",
  "задачи": ["..."],
  "анкетные_требования": {},
  "обязательные_требования": [],
  "желательные_требования": [],
  "психологические_черты": [],
  "стоп_факторы": [],
  "условия_работы": {}
}}
Если текущий профиль передан — сохрани удачную структуру и учти коррективы."""

VACANCY_TEXT_SYSTEM = """Ты — HR-директор. Сформируй или обнови текст вакансии (markdown/plain).
Верни ТОЛЬКО JSON: {"текст_вакансии": "..."}."""

KEYWORDS_SYSTEM = """Ты — HR-рекрутер. Сформируй ключевые слова для поиска кандидатов.
Верни ТОЛЬКО JSON: {"ключевые_слова": ["слово1", "слово2", ...]}."""

QUESTIONS_SYSTEM = f"""Ты — HR-директор с опытом первичных собеседований.
{QUESTIONNAIRE_RULES}
Верни ТОЛЬКО JSON:
{{"опросник": [{{"вопрос": "...", "уточняющие_вопросы": ["..."], "проверяет_требование": "...", "категория": "hard_skills|soft_skills|experience|motivation|reliability", "пример_ответа": "..."}}]}}
"""


def _as_profile_obj(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {"raw": text}
        except json.JSONDecodeError:
            return {"raw": text}
    return {"raw": text}


def _as_questions_list(raw: Any) -> list:
    if isinstance(raw, list):
        return raw
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return [{"вопрос": text, "пример_ответа": ""}]


def _profile_text(documents: dict) -> str:
    return extract_profile_text(documents)


def _store_value(key: str, value: Any) -> str | Any:
    if key == "profile":
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value or "")
    if key == "questions":
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value or "")
    if key == "keywords":
        if isinstance(value, list):
            return ", ".join(str(x).strip() for x in value if str(x).strip())
        return str(value or "").strip()
    return str(value or "").strip()


def generate_document_section(
    *,
    key: str,
    job_title: str,
    documents: dict,
    corrections: str = "",
    settings: Settings,
) -> dict[str, Any]:
    """
    Returns { key, value, mode: generate|regenerate }.
    value is ready to store in vacancy.documents[key].
    """
    if key not in GENERATABLE_KEYS:
        raise ValueError(f"Генерация для «{key}» не поддерживается")

    docs = documents or {}
    corr = (corrections or "").strip()
    title = (job_title or "").strip() or "—"

    current_raw = docs.get(key)
    has_current = False
    if isinstance(current_raw, str):
        has_current = bool(current_raw.strip())
    elif isinstance(current_raw, (dict, list)):
        has_current = bool(current_raw)
    mode = "regenerate" if has_current else "generate"

    if key == "profile":
        current = _as_profile_obj(current_raw)
        parts = [f"Должность: {title}"]
        if current:
            parts.append(f"ТЕКУЩИЙ ПРОФИЛЬ:\n{json.dumps(current, ensure_ascii=False, indent=2)}")
        else:
            notes = str(docs.get("notes") or "").strip()
            vac = str(docs.get("vacancy_text") or "").strip()
            if vac:
                parts.append(f"ТЕКСТ ВАКАНСИИ (если есть):\n{vac[:6000]}")
            if notes:
                parts.append(f"ЗАМЕТКИ:\n{notes[:2000]}")
            parts.append("Сформируй профиль должности с нуля по названию и доступному контексту.")
        if corr:
            parts.append(f"КОРРЕКТИВЫ ОТ HR (обязательно учти):\n{corr}")
        if mode == "regenerate" and not corr and not current:
            raise ValueError("Профиль пуст — нечего перегенерировать. Сначала сгенерируйте.")
        result = chat_json(settings, system=PROFILE_SYSTEM, user="\n\n".join(parts), max_tokens=4000)
        if not isinstance(result, dict):
            raise RuntimeError("ИИ вернул некорректный профиль")
        prof = result.get("профиль") or result.get("profile") or result
        if not isinstance(prof, dict) or not prof:
            raise RuntimeError("ИИ вернул пустой профиль")
        return {"key": key, "value": _store_value(key, prof), "mode": mode}

    profile_text = _profile_text(docs)
    if key in ("vacancy_text", "questions", "keywords") and not profile_text:
        raise ValueError("Сначала заполните или сгенерируйте профиль должности.")

    if key == "vacancy_text":
        parts = [
            f"Должность: {title}",
            f"ПРОФИЛЬ:\n{profile_text}",
            f"ТЕКУЩИЙ ТЕКСТ ВАКАНСИИ:\n{str(current_raw or '').strip() or '—'}",
        ]
        if corr:
            parts.append(f"КОРРЕКТИВЫ ОТ HR:\n{corr}")
        if mode == "generate":
            parts.append("Сформируй текст вакансии с нуля по профилю.")
        result = chat_json(settings, system=VACANCY_TEXT_SYSTEM, user="\n\n".join(parts), max_tokens=3500)
        if not isinstance(result, dict):
            raise RuntimeError("ИИ вернул некорректный текст")
        text = result.get("текст_вакансии") or result.get("vacancy_text") or ""
        if not str(text).strip():
            raise RuntimeError("ИИ вернул пустой текст вакансии")
        return {"key": key, "value": _store_value(key, text), "mode": mode}

    if key == "keywords":
        kw = current_raw
        if isinstance(kw, list):
            kw_text = ", ".join(str(x) for x in kw)
        else:
            kw_text = str(kw or "").strip()
        parts = [
            f"Должность: {title}",
            f"ПРОФИЛЬ:\n{profile_text}",
            f"ТЕКУЩИЕ КЛЮЧЕВЫЕ СЛОВА:\n{kw_text or '—'}",
        ]
        if corr:
            parts.append(f"КОРРЕКТИВЫ ОТ HR:\n{corr}")
        if mode == "generate":
            parts.append("Сформируй список ключевых слов для поиска.")
        result = chat_json(settings, system=KEYWORDS_SYSTEM, user="\n\n".join(parts), max_tokens=800)
        if not isinstance(result, dict):
            raise RuntimeError("ИИ вернул некорректные ключевые слова")
        kws = result.get("ключевые_слова") or result.get("keywords") or []
        return {"key": key, "value": _store_value(key, kws), "mode": mode}

    # questions
    current_list = _as_questions_list(current_raw)
    parts = [f"Должность: {title}", f"ПРОФИЛЬ ДОЛЖНОСТИ:\n{profile_text}"]
    if current_list:
        parts.append(f"ТЕКУЩИЙ ОПРОСНИК:\n{json.dumps(current_list, ensure_ascii=False, indent=2)}")
    if corr:
        parts.append(f"КОРРЕКТИВЫ ОТ HR (обязательно учти):\n{corr}")
    parts.append("Сформируй опросник для первичного собеседования.")
    result = chat_json(settings, system=QUESTIONS_SYSTEM, user="\n\n".join(parts), max_tokens=4500)
    if isinstance(result, list):
        raw = result
    elif isinstance(result, dict):
        raw = result.get("опросник") or result.get("questions") or []
    else:
        raw = []
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("ИИ вернул пустой или некорректный опросник")
    return {"key": key, "value": _store_value(key, raw), "mode": mode}
