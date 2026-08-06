"""RouterAI chat → JSON helper with legacy-compatible repair (audit M2)."""

from __future__ import annotations

import json
import re
from ast import literal_eval
from typing import Any

import requests

from app.core.config import Settings
from app.services.log_sanitize import sanitize_for_log

# Combined user / large-field cap before LLM (audit Q12)
MAX_AI_INPUT_CHARS = 12_000


def truncate_ai_input(text: str | None, limit: int = MAX_AI_INPUT_CHARS) -> str:
    s = (text or "").strip()
    if limit and len(s) > limit:
        return s[:limit]
    return s


def _extract_json_payload(content: str) -> str:
    text = str(content or "").strip()
    text = re.sub(
        r"<(?:think|thinking|redacted_thinking)>.*?</(?:think|thinking|redacted_thinking)>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    text = text.strip()
    if not text.startswith("{") and not text.startswith("["):
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            text = match.group(1)
    return text.strip()


def _escape_newlines_in_json_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string:
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                out.append("\\r")
                continue
            if ch == "\t":
                out.append("\\t")
                continue
        out.append(ch)
    return "".join(out)


def _insert_missing_commas(text: str) -> str:
    text = re.sub(
        r'([}\]"0-9]|true|false|null)\s*\n(\s*")',
        r"\1,\n\2",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\}\s*\n\s*\{", "},\n{", text)
    text = re.sub(r"\]\s*\n\s*\[", "],\n[", text)
    return text


def _close_truncated_json(text: str) -> str:
    text = text.rstrip()
    if not text:
        return text
    text = re.sub(r",\s*$", "", text)
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        text += '"'
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    closers = {"{": "}", "[": "]"}
    while stack:
        text += closers[stack.pop()]
    return text


def parse_ai_json(content: str) -> dict[str, Any] | list[Any]:
    """Parse model JSON; repair trailing commas, missing commas, fences, truncation.

    Returns ``{}`` if nothing usable (callers that need hard fail should check).
    """
    text = _extract_json_payload(content)
    if not text:
        return {}

    def _ok(data: Any) -> dict[str, Any] | list[Any] | None:
        if isinstance(data, (dict, list)):
            return data
        return None

    try:
        parsed = _ok(json.loads(text))
        if parsed is not None:
            return parsed
    except json.JSONDecodeError:
        pass

    candidates = [text]
    repaired = re.sub(r",\s*([}\]])", r"\1", text)
    candidates.append(repaired)
    candidates.append(_escape_newlines_in_json_strings(repaired))
    candidates.append(_insert_missing_commas(repaired))
    candidates.append(_insert_missing_commas(_escape_newlines_in_json_strings(repaired)))
    candidates.append(_close_truncated_json(candidates[-1]))

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = _ok(json.loads(candidate))
            if parsed is not None:
                return parsed
        except json.JSONDecodeError:
            pass
        try:
            lit = literal_eval(candidate)
            parsed = _ok(lit)
            if parsed is not None:
                return parsed
        except (SyntaxError, ValueError):
            pass

    unquoted = re.sub(
        r"([{,]\s*)([A-Za-zА-Яа-яЁё_][\wА-Яа-яЁё-]*)(\s*:)",
        r'\1"\2"\3',
        _insert_missing_commas(_escape_newlines_in_json_strings(repaired)),
    )
    for candidate in (unquoted, _close_truncated_json(unquoted)):
        try:
            parsed = _ok(json.loads(candidate))
            if parsed is not None:
                return parsed
        except json.JSONDecodeError:
            pass

    return {}


def chat_json(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    max_tokens: int = 4000,
    db=None,
    task: str = "chat_json",
) -> dict[str, Any] | list[Any]:
    api_key = (settings.routerai_api_key or settings.ai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Нет ключа ИИ (ROUTERAI_API_KEY / AI_API_KEY).")
    from app.services.app_settings import resolve_ai_model_name
    from app.services.ai_errors import log_ai_error

    base = (settings.ai_base_url or "https://routerai.ru/api/v1").rstrip("/")
    model = resolve_ai_model_name(settings.ai_model_name)
    user_trim = truncate_ai_input(user)
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": system.rstrip() + "\n\n/no_think\nОтвечай сразу валидным JSON.",
            },
            {"role": "user", "content": user_trim},
        ],
    }
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"ИИ API {resp.status_code}: {sanitize_for_log(resp.text, max_len=400)}"
        )
    data = resp.json()
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    parsed = parse_ai_json(content)
    if parsed == {} or parsed == []:
        log_ai_error(
            db,
            task=task,
            error_kind="json_parse",
            error_message="empty or invalid JSON from model",
            raw_response=content,
            meta={"model": model},
        )
    return parsed
