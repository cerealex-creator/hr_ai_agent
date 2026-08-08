"""Zoom User OAuth (authorization code) — tokens per Organization.integrations.zoom."""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.db import models

ZOOM_AUTH_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
# Classic scopes work with many Marketplace apps; granular apps may need meeting:write:meeting
DEFAULT_SCOPES = "meeting:write user:read offline_access"


def _root_data():
    return get_settings().resolved_legacy_data_dir()


def get_client_id() -> str:
    s = get_settings()
    return (s.zoom_client_id or os.getenv("ZOOM_CLIENT_ID") or "").strip()


def get_client_secret() -> str:
    s = get_settings()
    return (s.zoom_client_secret or os.getenv("ZOOM_CLIENT_SECRET") or "").strip()


def get_redirect_uri() -> str:
    s = get_settings()
    return (s.zoom_redirect_uri or os.getenv("ZOOM_REDIRECT_URI") or "http://localhost:8765/").strip()


def legacy_token_path() -> str:
    """Former global file path (migration / diagnostics only)."""
    s = get_settings()
    env = (s.zoom_token_path or os.getenv("ZOOM_TOKEN_PATH") or "").strip()
    if env:
        return env
    return str(_root_data() / "zoom_oauth_token.json")


def credentials_configured() -> bool:
    return bool(get_client_id() and get_client_secret())


def _basic_auth_header() -> str:
    raw = f"{get_client_id()}:{get_client_secret()}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def get_zoom_token(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    org = db.get(models.Organization, org_id)
    if not org:
        return {}
    integrations = org.integrations if isinstance(org.integrations, dict) else {}
    zoom = integrations.get("zoom")
    return dict(zoom) if isinstance(zoom, dict) else {}


def save_zoom_token(db: Session, org_id: uuid.UUID, token_data: dict[str, Any]) -> None:
    org = db.get(models.Organization, org_id)
    if not org:
        raise ValueError(f"Organization not found: {org_id}")
    integrations = dict(org.integrations or {}) if isinstance(org.integrations, dict) else {}
    clean = {
        "access_token": str(token_data.get("access_token") or "").strip(),
        "refresh_token": str(token_data.get("refresh_token") or "").strip(),
        "expires_at": int(token_data.get("expires_at") or token_data.get("expiry") or 0),
        "scope": str(token_data.get("scope") or ""),
        "token_type": str(token_data.get("token_type") or "bearer"),
    }
    integrations["zoom"] = clean
    org.integrations = integrations
    flag_modified(org, "integrations")
    db.add(org)
    db.commit()
    db.refresh(org)


def extract_oauth_code(pasted: str) -> str | None:
    text = (pasted or "").strip().strip('"').strip("'")
    if not text:
        return None
    if "://" in text or text.startswith("http"):
        code = parse_qs(urlparse(text).query).get("code", [None])[0]
        if code:
            return code
    if "code=" in text:
        q = text if text.startswith("?") else f"?{text.lstrip('?')}"
        code = parse_qs(urlparse(f"http://local{q}").query).get("code", [None])[0]
        if code:
            return code
        if text.startswith("code="):
            return text[5:].split("&", 1)[0].strip() or None
    if " " not in text and len(text) >= 8:
        return text
    return None


def oauth_auth_url() -> tuple[bool, str, str | None]:
    if not credentials_configured():
        return False, "Нет ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET", None
    params = {
        "response_type": "code",
        "client_id": get_client_id(),
        "redirect_uri": get_redirect_uri(),
    }
    scopes = (get_settings().zoom_oauth_scopes or os.getenv("ZOOM_OAUTH_SCOPES") or DEFAULT_SCOPES).strip()
    if scopes:
        params["scope"] = scopes
    url = f"{ZOOM_AUTH_URL}?{urlencode(params)}"
    return (
        True,
        "Откройте ссылку Zoom. После входа скопируйте адрес из строки браузера "
        f"(редирект на {get_redirect_uri()}?code=...) или только code — и вставьте ниже.",
        url,
    )


def oauth_complete_with_code(db: Session, org_id: uuid.UUID, pasted: str) -> tuple[bool, str]:
    if not credentials_configured():
        return False, "Нет ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET"
    code = extract_oauth_code(pasted)
    if not code:
        return False, "Не удалось извлечь code из вставленного текста"
    try:
        resp = requests.post(
            ZOOM_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": get_redirect_uri(),
            },
            timeout=30,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            detail = data.get("reason") or data.get("error") or resp.text[:200]
            return False, f"Zoom token error: {detail}"
        access = str(data.get("access_token") or "").strip()
        if not access:
            return False, "Zoom не вернул access_token"
        expires_in = int(data.get("expires_in") or 3600)
        payload = {
            "access_token": access,
            "refresh_token": str(data.get("refresh_token") or "").strip(),
            "expires_at": int(time.time()) + max(60, expires_in - 60),
            "scope": data.get("scope") or "",
            "token_type": data.get("token_type") or "bearer",
        }
        save_zoom_token(db, org_id, payload)
        return True, "Zoom подключён для вашей компании"
    except requests.RequestException as exc:
        return False, f"Сеть Zoom: {exc}"


def get_access_token(db: Session, org_id: uuid.UUID) -> tuple[str | None, str | None]:
    """Return valid access_token for org, refreshing and saving if needed."""
    if not credentials_configured():
        return None, "Zoom не настроен (ZOOM_CLIENT_ID / SECRET)"
    token = get_zoom_token(db, org_id)
    access = str(token.get("access_token") or "").strip()
    expires_at = int(token.get("expires_at") or token.get("expiry") or 0)
    if access and expires_at > int(time.time()) + 30:
        return access, None
    refresh = str(token.get("refresh_token") or "").strip()
    if not refresh:
        return None, "Нет Zoom для компании — админ должен пройти OAuth в настройках"
    try:
        resp = requests.post(
            ZOOM_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": refresh},
            timeout=30,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            detail = data.get("reason") or data.get("error") or resp.text[:200]
            return None, f"Zoom refresh error: {detail}"
        access = str(data.get("access_token") or "").strip()
        if not access:
            return None, "Zoom refresh не вернул access_token"
        expires_in = int(data.get("expires_in") or 3600)
        token.update(
            {
                "access_token": access,
                "refresh_token": str(data.get("refresh_token") or refresh).strip(),
                "expires_at": int(time.time()) + max(60, expires_in - 60),
                "scope": data.get("scope") or token.get("scope") or "",
            }
        )
        save_zoom_token(db, org_id, token)
        return access, None
    except requests.RequestException as exc:
        return None, f"Сеть Zoom: {exc}"


def get_zoom_status(db: Session, org_id: uuid.UUID) -> tuple[str, str]:
    if not credentials_configured():
        return (
            "not_configured",
            "Задайте ZOOM_CLIENT_ID и ZOOM_CLIENT_SECRET в .env (Zoom Marketplace → User OAuth app)",
        )
    token = get_zoom_token(db, org_id)
    if not token.get("access_token") and not token.get("refresh_token"):
        return "needs_auth", "Для вашей компании Zoom ещё не подключён — нужна авторизация админом"
    access, err = get_access_token(db, org_id)
    if err or not access:
        return "needs_auth", err or "Токен Zoom устарел — переподключите"
    return "ready", "Подключено для вашей компании"


def load_legacy_file_token() -> dict[str, Any]:
    path = legacy_token_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def migrate_legacy_token_to_org(db: Session, org_id: uuid.UUID) -> bool:
    """
    One-shot: if org has no zoom tokens and legacy file exists, copy into integrations.
    Returns True if migrated.
    """
    existing = get_zoom_token(db, org_id)
    if existing.get("access_token") or existing.get("refresh_token"):
        return False
    legacy = load_legacy_file_token()
    if not legacy.get("access_token") and not legacy.get("refresh_token"):
        return False
    save_zoom_token(db, org_id, legacy)
    return True
