"""Minimal RouterAI chat → JSON helper (v2, no Streamlit imports)."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.core.config import Settings


def parse_ai_json(content: str) -> dict[str, Any] | list[Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, (dict, list)):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, (dict, list)):
                return data
        except json.JSONDecodeError:
            return {}
    return {}


def chat_json(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    max_tokens: int = 4000,
) -> dict[str, Any] | list[Any]:
    api_key = (settings.routerai_api_key or settings.ai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Нет ключа ИИ (ROUTERAI_API_KEY / AI_API_KEY).")
    base = (settings.ai_base_url or "https://routerai.ru/api/v1").rstrip("/")
    model = (settings.ai_model_name or "").strip() or "qwen/qwen3.5-plus-20260420"
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": system.rstrip() + "\n\n/no_think\nОтвечай сразу валидным JSON.",
            },
            {"role": "user", "content": user},
        ],
    }
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ИИ API {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    return parse_ai_json(content)
