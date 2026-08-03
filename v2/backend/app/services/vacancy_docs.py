"""Helpers: keywords + profile text from vacancy documents."""

from __future__ import annotations

import json
from typing import Any


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(value)
    return str(value).strip()


def extract_keywords(documents: dict | None) -> str:
    docs = documents or {}
    for key in ("keywords", "ключевые_слова", "ключевые слова"):
        raw = docs.get(key)
        if isinstance(raw, list):
            return " ".join(str(x).strip() for x in raw if str(x).strip())
        text = _as_text(raw)
        if text:
            # pipe / comma / newline separated
            if "\n" in text or "|" in text:
                parts = [p.strip(" |-") for p in text.replace("|", "\n").splitlines()]
                return " ".join(p for p in parts if p)
            return text
    return ""


def extract_profile_text(documents: dict | None) -> str:
    docs = documents or {}
    for key in ("profile", "профиль"):
        raw = docs.get(key)
        if isinstance(raw, dict):
            if isinstance(raw.get("raw"), str) and raw["raw"].strip():
                return raw["raw"].strip()
            return _as_text(raw)
        text = _as_text(raw)
        if text:
            return text
    # fallback vacancy text
    for key in ("vacancy_text", "текст_вакансии"):
        text = _as_text(docs.get(key))
        if text:
            return text
    return ""
