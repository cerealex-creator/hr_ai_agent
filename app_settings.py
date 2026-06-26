"""Глобальные настройки приложения (data/app_settings.json)."""

from __future__ import annotations

import json
import os

APP_SETTINGS_FILE = os.path.join("data", "app_settings.json")
WARRANTY_MONTH_CHOICES = list(range(1, 7))
DEFAULT_APP_SETTINGS = {
    "default_warranty_months": 3,
}


def _ensure_dir():
    os.makedirs(os.path.dirname(APP_SETTINGS_FILE) or ".", exist_ok=True)


def load_app_settings():
    _ensure_dir()
    if not os.path.exists(APP_SETTINGS_FILE):
        return dict(DEFAULT_APP_SETTINGS)
    try:
        with open(APP_SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_APP_SETTINGS)
    if not isinstance(data, dict):
        return dict(DEFAULT_APP_SETTINGS)
    merged = dict(DEFAULT_APP_SETTINGS)
    merged.update(data)
    return merged


def save_app_settings(settings):
    _ensure_dir()
    payload = dict(DEFAULT_APP_SETTINGS)
    payload.update(settings or {})
    with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def get_default_warranty_months():
    months = load_app_settings().get("default_warranty_months", 3)
    if months not in WARRANTY_MONTH_CHOICES:
        return 3
    return months


def set_default_warranty_months(months):
    if months not in WARRANTY_MONTH_CHOICES:
        months = 3
    settings = load_app_settings()
    settings["default_warranty_months"] = months
    return save_app_settings(settings)
