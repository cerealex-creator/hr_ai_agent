"""Interview digest: Q&A essence + HR-only communication note."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.services.ai_json import chat_json

INTERVIEW_DIGEST_SYSTEM = """Ты — помощник рекрутера. По расшифровке собеседования сделай выжимку.

Правила:
- убери мусор речи: повторы, междометия, звуки, слова-паразиты, «воду»;
- ничего не выдумывай и не добавляй фактов;
- сохрани смысл вопросов и ответов;
- оформи пары вопрос → краткий ответ по сути (ёмко, без лишних слов);
- в communication опиши только стиль изложения кандидата (1–2 предложения для HR):
  много паразитов/пауз/лишних слов → сложнее коммуницировать;
  или мысли точные и краткие → удобно коммуницировать.
  Не оценивай профессионализм и не дублируй содержание ответов.

Верни ТОЛЬКО JSON:
{
  "summary": "2–4 предложения: о чём говорили и главный итог",
  "qa": [{"q": "вопрос или тема", "a": "суть ответа"}],
  "communication": "характеристика стиля речи для HR"
}"""


def _trim(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def empty_digest(*, error: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {
        "summary": "",
        "qa": [],
        "communication": "",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    if error:
        out["error"] = error
    return out


def structure_interview_digest(
    transcript: str,
    *,
    settings: Settings | None = None,
    candidate_name: str = "",
    vacancy_title: str = "",
) -> dict[str, Any]:
    source = (transcript or "").strip()
    if not source:
        return empty_digest(error="empty_transcript")
    settings = settings or get_settings()
    header = []
    if vacancy_title:
        header.append(f"Вакансия: {vacancy_title}")
    if candidate_name:
        header.append(f"Кандидат: {candidate_name}")
    prefix = ("\n".join(header) + "\n\n") if header else ""
    try:
        result = chat_json(
            settings,
            system=INTERVIEW_DIGEST_SYSTEM,
            user=f"{prefix}РАСШИФРОВКА:\n{_trim(source, 14000)}",
            max_tokens=3500,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        return empty_digest(error=str(exc)[:300])
    if not isinstance(result, dict):
        return empty_digest(error="bad_json")
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
    return {
        "summary": str(result.get("summary") or result.get("summary_text") or "").strip(),
        "qa": qa,
        "communication": str(
            result.get("communication") or result.get("стиль_речи") or ""
        ).strip(),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def ensure_interview_digest_token(payload: dict[str, Any]) -> str:
    tok = str(payload.get("interview_digest_token") or "").strip()
    if not tok:
        tok = secrets.token_urlsafe(24)
        payload["interview_digest_token"] = tok
    return tok


def public_app_base(settings: Settings | None = None) -> str:
    """HTTPS UI origin for customer links. Empty locally unless configured."""
    settings = settings or get_settings()
    raw = (getattr(settings, "public_app_url", None) or "").strip().rstrip("/")
    if raw:
        return raw
    for origin in getattr(settings, "cors_origin_list", None) or []:
        o = str(origin or "").strip().rstrip("/")
        if o.startswith("https://"):
            return o
    try:
        from app.services.bitrix.tokens import public_api_base

        return (public_api_base() or "").strip().rstrip("/")
    except Exception:  # noqa: BLE001
        return ""


def interview_digest_public_url(payload: dict[str, Any] | None, *, settings: Settings | None = None) -> str | None:
    p = payload or {}
    digest = p.get("interview_digest")
    if not isinstance(digest, dict):
        return None
    has_body = bool(str(digest.get("summary") or "").strip() or digest.get("qa"))
    if not has_body:
        return None
    tok = str(p.get("interview_digest_token") or "").strip()
    if not tok:
        return None
    base = public_app_base(settings)
    if not base:
        return None
    return f"{base}/i/{tok}"


def digest_for_api(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    raw = (payload or {}).get("interview_digest")
    if not isinstance(raw, dict):
        return None
    qa_raw = raw.get("qa") or []
    qa: list[dict[str, str]] = []
    if isinstance(qa_raw, list):
        for item in qa_raw:
            if not isinstance(item, dict):
                continue
            q = str(item.get("q") or "").strip()
            a = str(item.get("a") or "").strip()
            if q or a:
                qa.append({"q": q, "a": a})
    return {
        "summary": str(raw.get("summary") or "").strip(),
        "qa": qa,
        "communication": str(raw.get("communication") or "").strip(),
        "created_at": str(raw.get("created_at") or "").strip() or None,
        "public_url": interview_digest_public_url(payload),
    }


def digest_for_client(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Public page payload: no HR communication note."""
    full = digest_for_api(payload)
    if not full:
        return None
    return {
        "summary": full["summary"],
        "qa": full["qa"],
        "created_at": full.get("created_at"),
    }
