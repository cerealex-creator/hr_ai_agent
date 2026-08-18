"""Vacancy thematic avatar keys (icons in UI)."""

from __future__ import annotations

import re
from typing import Any

# Stable ids — must match frontend VacancyAvatar
AVATAR_KEYS: tuple[str, ...] = (
    "design",
    "marketing",
    "sales",
    "it",
    "hr",
    "logistics",
    "finance",
    "support",
    "admin",
    "legal",
    "education",
    "general",
    "pencil",
    "monitor",
    "cargo",
    "alert",
    "people",
    "question",
)

AVATAR_LABELS: dict[str, str] = {
    "design": "Дизайн",
    "marketing": "Маркетинг",
    "sales": "Продажи",
    "it": "IT / разработка",
    "hr": "HR / подбор",
    "logistics": "Логистика",
    "finance": "Финансы",
    "support": "Поддержка",
    "admin": "Админ / офис",
    "legal": "Юриспруденция",
    "education": "Обучение",
    "general": "Общая",
    "pencil": "Карандаш",
    "monitor": "Монитор",
    "cargo": "Ящик / груз",
    "alert": "Восклицательный знак",
    "people": "Люди",
    "question": "Вопросительный знак",
}

# (avatar_key, keywords) — first match wins
_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "design",
        (
            "дизайн",
            "designer",
            "графич",
            "illustr",
            "иллюстр",
            "ui/ux",
            "ui ",
            "ux ",
            "креативн",
            "art director",
            "арт-директор",
            "арт директор",
        ),
    ),
    (
        "marketing",
        (
            "маркетинг",
            "smm",
            "контент",
            "реклам",
            "pr ",
            "пиар",
            "бренд",
            "seo",
            "таргет",
            "performance",
        ),
    ),
    (
        "sales",
        (
            "продаж",
            "sales",
            "account manager",
            "аккаунт",
            "менеджер по работ",
            "коммерческ",
            "бизнес-развит",
            "bizdev",
        ),
    ),
    (
        "it",
        (
            "разработ",
            "программист",
            "developer",
            "engineer",
            "python",
            "frontend",
            "backend",
            "fullstack",
            "devops",
            "qa",
            "тестир",
            "системн",
            "data ",
            "аналитик данн",
            "1с",
            "1c",
        ),
    ),
    ("hr", ("hr", "рекрут", "кадр", "talent", "people partner", "подбор персон")),
    (
        "logistics",
        ("логист", "склад", "водител", "курьер", "supply", "закупк", "транспорт"),
    ),
    (
        "finance",
        ("бухгалтер", "финанс", "экономист", "казнач", "аудит", "контролёр", "контролер"),
    ),
    ("support", ("поддержк", "support", "оператор", "helpdesk", "клиентский сервис")),
    (
        "admin",
        ("администратор", "ассистент", "секретар", "офис-менеджер", "офис менеджер", "делопроизв"),
    ),
    ("legal", ("юрист", "legal", "правов", "compliance")),
    (
        "education",
        ("препод", "учител", "тренер", "методист", "обучен", "edtech", "тьютор"),
    ),
]


def normalize_avatar_key(raw: Any) -> str | None:
    key = str(raw or "").strip().lower()
    return key if key in AVATAR_KEYS else None


def infer_avatar_key(title: str | None) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip().lower())
    if not text:
        return "general"
    padded = f" {text} "
    for key, words in _RULES:
        for w in words:
            needle = w.lower()
            if needle.endswith(" "):
                if needle in padded:
                    return key
            elif needle in text:
                return key
    return "general"


def resolve_avatar_key(payload: dict | None, title: str | None = None) -> str:
    key = normalize_avatar_key((payload or {}).get("avatar_key"))
    if key:
        return key
    return infer_avatar_key(title)


def avatar_catalog() -> list[dict[str, str]]:
    return [{"id": k, "label": AVATAR_LABELS[k]} for k in AVATAR_KEYS]
