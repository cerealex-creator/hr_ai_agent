"""Small app settings file (warranty defaults). Shares Streamlit data/app_settings.json when present."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings

WARRANTY_MONTH_CHOICES = list(range(1, 7))


def _settings_path() -> Path:
    return get_settings().resolved_legacy_data_dir() / "app_settings.json"


def _load() -> dict:
    path = _settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_default_warranty_months() -> int:
    raw = _load().get("default_warranty_months", 3)
    try:
        months = int(raw)
    except (TypeError, ValueError):
        months = 3
    if months not in WARRANTY_MONTH_CHOICES:
        return 3
    return months


def set_default_warranty_months(months: int) -> int:
    months = int(months)
    if months not in WARRANTY_MONTH_CHOICES:
        raise ValueError(f"months: {WARRANTY_MONTH_CHOICES}")
    data = _load()
    data["default_warranty_months"] = months
    _save(data)
    return months


def get_app_settings() -> dict:
    return {
        "default_warranty_months": get_default_warranty_months(),
        "path": str(_settings_path()),
    }
