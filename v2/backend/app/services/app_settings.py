"""Small app settings file. Shares Streamlit data/app_settings.json when present."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings

WARRANTY_MONTH_CHOICES = list(range(1, 7))

DEFAULT_PROVIDER_LINKS = {
    "yandex_cloud": {
        "id": "yandex_cloud",
        "label": "Яндекс Облако",
        "url": "https://console.yandex.cloud/folders/b1glrlal8l5f9uu25jjr/dashboard",
        "enabled": True,
    },
    "routerai": {
        "id": "routerai",
        "label": "RouterAI",
        "url": "https://routerai.ru/settings/billing",
        "enabled": True,
    },
}

DEFAULT_AI_PROVIDER = {
    "id": "routerai",
    "label": "RouterAI",
    "console_url": DEFAULT_PROVIDER_LINKS["routerai"]["url"],
    # Platform key/URL stay in env; only model name is overridden here when set.
    "model": "",
}

DEFAULT_CANDIDATE_COMMS = {
    "zoom": {"enabled": False, "account_note": "", "default_meeting_link": ""},
    "telemost": {"enabled": False, "default_meeting_link": ""},
    "other_video": {"enabled": False, "name": "", "default_meeting_link": ""},
    "messengers": {
        "telegram": {"enabled": False, "note": ""},
        "whatsapp": {"enabled": False, "note": ""},
        "max": {"enabled": False, "note": ""},
    },
    "message_templates": [
        {
            "id": "invite_call",
            "title": "Приглашение на созвон",
            "body": "Здравствуйте! Предлагаю созвониться: {meeting_link}",
        }
    ],
}


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


def get_ai_model_override() -> str:
    """User-chosen model name; empty = use env AI_MODEL_NAME."""
    return str(_load().get("ai_model") or "").strip()


def set_ai_model_override(model: str | None) -> str:
    data = _load()
    value = str(model or "").strip()
    if value:
        data["ai_model"] = value
    else:
        data.pop("ai_model", None)
    _save(data)
    return value


def resolve_ai_model_name(fallback: str | None = None) -> str:
    """Effective model: app_settings override → env → hardcoded default."""
    override = get_ai_model_override()
    if override:
        return override
    env_name = (fallback if fallback is not None else get_settings().ai_model_name) or ""
    env_name = str(env_name).strip()
    return env_name or "qwen/qwen3.5-plus-20260420"


def get_ai_provider() -> dict[str, Any]:
    raw = _load().get("ai_provider")
    base = dict(DEFAULT_AI_PROVIDER)
    if isinstance(raw, dict):
        for key in ("id", "label", "console_url"):
            if raw.get(key) is not None:
                base[key] = str(raw.get(key) or "").strip() or base[key]
    # Effective model for UI
    base["model"] = resolve_ai_model_name()
    base["model_override"] = get_ai_model_override()
    base["model_env_default"] = (get_settings().ai_model_name or "").strip() or base["model"]
    base["base_url_env"] = (get_settings().ai_base_url or "").strip()
    return base


def set_ai_provider(patch: dict[str, Any]) -> dict[str, Any]:
    data = _load()
    cur = data.get("ai_provider") if isinstance(data.get("ai_provider"), dict) else {}
    next_p = dict(cur)
    if "id" in patch:
        next_p["id"] = str(patch.get("id") or "").strip() or DEFAULT_AI_PROVIDER["id"]
    if "label" in patch:
        next_p["label"] = str(patch.get("label") or "").strip() or DEFAULT_AI_PROVIDER["label"]
    if "console_url" in patch:
        next_p["console_url"] = str(patch.get("console_url") or "").strip()
    data["ai_provider"] = next_p
    if "model" in patch:
        value = str(patch.get("model") or "").strip()
        if value:
            data["ai_model"] = value
        else:
            data.pop("ai_model", None)
    _save(data)
    return get_ai_provider()


def get_provider_links() -> list[dict[str, Any]]:
    raw = _load().get("provider_links")
    links: dict[str, dict[str, Any]] = {k: dict(v) for k, v in DEFAULT_PROVIDER_LINKS.items()}
    # Sync RouterAI console URL from ai_provider if set
    prov = get_ai_provider()
    if prov.get("console_url"):
        links["routerai"]["url"] = prov["console_url"]
        links["routerai"]["label"] = prov.get("label") or links["routerai"]["label"]
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            lid = str(item.get("id") or "").strip()
            if not lid:
                continue
            base = links.get(lid, {"id": lid, "label": lid, "url": "", "enabled": True})
            if item.get("label") is not None:
                base["label"] = str(item.get("label") or base["label"])
            if item.get("url") is not None:
                base["url"] = str(item.get("url") or "")
            if item.get("enabled") is not None:
                base["enabled"] = bool(item.get("enabled"))
            links[lid] = base
    elif isinstance(raw, dict):
        for lid, item in raw.items():
            if not isinstance(item, dict):
                continue
            base = links.get(str(lid), {"id": str(lid), "label": str(lid), "url": "", "enabled": True})
            base.update({k: item[k] for k in ("label", "url", "enabled") if k in item})
            base["id"] = str(lid)
            links[str(lid)] = base
    return [links[k] for k in sorted(links.keys(), key=lambda x: 0 if x == "yandex_cloud" else 1 if x == "routerai" else 2)]


def set_provider_links(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data = _load()
    cleaned: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        lid = str(item.get("id") or "").strip()
        if not lid:
            continue
        cleaned.append(
            {
                "id": lid,
                "label": str(item.get("label") or lid).strip(),
                "url": str(item.get("url") or "").strip(),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    data["provider_links"] = cleaned
    # Keep ai_provider console_url in sync with routerai link if present
    for item in cleaned:
        if item["id"] in ("routerai", "ai_provider"):
            prov = data.get("ai_provider") if isinstance(data.get("ai_provider"), dict) else {}
            prov = dict(prov)
            if item.get("url"):
                prov["console_url"] = item["url"]
            if item.get("label"):
                prov["label"] = item["label"]
            data["ai_provider"] = prov
            break
    _save(data)
    return get_provider_links()


def get_candidate_comms() -> dict[str, Any]:
    raw = _load().get("candidate_comms")
    out = json.loads(json.dumps(DEFAULT_CANDIDATE_COMMS))
    if not isinstance(raw, dict):
        return out
    for key in ("zoom", "telemost", "other_video"):
        if isinstance(raw.get(key), dict):
            out[key] = {**out[key], **{k: raw[key].get(k, out[key].get(k)) for k in out[key]}}
    if isinstance(raw.get("messengers"), dict):
        for mk, mv in raw["messengers"].items():
            if isinstance(mv, dict):
                base = out["messengers"].get(mk, {"enabled": False, "note": ""})
                out["messengers"][mk] = {**base, **mv}
    if isinstance(raw.get("message_templates"), list):
        out["message_templates"] = raw["message_templates"]
    return out


def set_candidate_comms(patch: dict[str, Any]) -> dict[str, Any]:
    data = _load()
    cur = get_candidate_comms()
    if isinstance(patch.get("zoom"), dict):
        cur["zoom"] = {**cur["zoom"], **patch["zoom"]}
    if isinstance(patch.get("telemost"), dict):
        cur["telemost"] = {**cur["telemost"], **patch["telemost"]}
    if isinstance(patch.get("other_video"), dict):
        cur["other_video"] = {**cur["other_video"], **patch["other_video"]}
    if isinstance(patch.get("messengers"), dict):
        for mk, mv in patch["messengers"].items():
            if isinstance(mv, dict):
                base = cur["messengers"].get(mk, {"enabled": False, "note": ""})
                cur["messengers"][mk] = {**base, **mv}
    if isinstance(patch.get("message_templates"), list):
        cur["message_templates"] = patch["message_templates"]
    data["candidate_comms"] = cur
    _save(data)
    return get_candidate_comms()


def get_app_settings() -> dict:
    from app.services.yandex_disk_oauth import get_disk_paths

    disk_paths = get_disk_paths()
    return {
        "default_warranty_months": get_default_warranty_months(),
        "ai_model": get_ai_model_override(),
        "ai_provider": get_ai_provider(),
        "provider_links": get_provider_links(),
        "candidate_comms": get_candidate_comms(),
        "yandex_disk_root": disk_paths["root"],
        "yandex_disk_inbox": disk_paths["inbox_name"],
        "path": str(_settings_path()),
    }
