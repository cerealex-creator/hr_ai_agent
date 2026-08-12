"""Authenticated Yandex Disk API: app root folders, vacancy trees, inbox listing.

Public-folder sync (yandex_disk_sync) stays as read-only fallback.
OAuth token is stored under legacy data dir (same pattern as Google Calendar).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.db import models
from app.services.app_settings import _load as load_app_settings
from app.services.app_settings import _save as save_app_settings
from app.services.yandex_disk_sync import DEFAULT_SUBFOLDERS, ensure_yandex_config

DISK_API = "https://cloud-api.yandex.net/v1/disk"
OAUTH_AUTHORIZE = "https://oauth.yandex.ru/authorize"
# Implicit-flow landing page — must match Redirect URI in the Yandex OAuth app.
OAUTH_REDIRECT_URI = "https://oauth.yandex.ru/verification_code"
DEFAULT_ROOT = "/HR_AI_Agent"
DEFAULT_INBOX = "_inbox"
TOKEN_FILENAME = "yandex_disk_oauth.json"


def _token_path() -> Path:
    env = (get_settings().yandex_disk_oauth_token_path or "").strip()
    if env:
        return Path(env)
    return get_settings().resolved_legacy_data_dir() / TOKEN_FILENAME


def get_disk_token() -> str:
    settings = get_settings()
    env_token = (settings.yandex_disk_oauth_token or "").strip()
    if env_token:
        return env_token
    path = _token_path()
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("access_token") or data.get("token") or "").strip()
    except Exception:
        return ""


def save_disk_token(token: str) -> str:
    value = (token or "").strip()
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "access_token": value,
                "saved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return value


def clear_disk_token() -> None:
    path = _token_path()
    if path.is_file():
        path.unlink()


def reset_disk_connection() -> dict[str, Any]:
    """
    Full local disconnect: remove OAuth token file, clear Client ID in app_settings,
    reset folder paths to defaults. Does NOT delete folders/files on Yandex Disk.
    """
    clear_disk_token()
    set_disk_client_id("")
    paths = set_disk_paths(root=DEFAULT_ROOT, inbox_name=DEFAULT_INBOX)
    status = disk_status()
    env_token = bool((get_settings().yandex_disk_oauth_token or "").strip())
    env_client = bool((get_settings().yandex_disk_client_id or "").strip())
    note = (
        "Локальные настройки Диска сброшены (токен, Client ID, пути). "
        "Папки на Яндекс Диске не удалялись."
    )
    if env_token or env_client:
        note += (
            " Внимание: в .env всё ещё заданы YANDEX_DISK_OAUTH_TOKEN и/или "
            "YANDEX_DISK_CLIENT_ID — уберите их, если нужна полная отвязка."
        )
    return {
        **status,
        "reset": True,
        "message": note,
        "root": paths["root"],
        "inbox_path": paths["inbox_path"],
    }


def get_disk_paths() -> dict[str, str]:
    data = load_app_settings()
    root = str(data.get("yandex_disk_root") or DEFAULT_ROOT).strip() or DEFAULT_ROOT
    if not root.startswith("/"):
        root = "/" + root
    inbox_name = str(data.get("yandex_disk_inbox") or DEFAULT_INBOX).strip() or DEFAULT_INBOX
    inbox_name = inbox_name.strip("/")
    return {
        "root": root.rstrip("/") or DEFAULT_ROOT,
        "inbox_name": inbox_name,
        "inbox_path": f"{root.rstrip('/')}/{inbox_name}",
    }


def set_disk_paths(*, root: str | None = None, inbox_name: str | None = None) -> dict[str, str]:
    data = load_app_settings()
    if root is not None:
        r = root.strip() or DEFAULT_ROOT
        if not r.startswith("/"):
            r = "/" + r
        data["yandex_disk_root"] = r.rstrip("/") or DEFAULT_ROOT
    if inbox_name is not None:
        data["yandex_disk_inbox"] = (inbox_name or DEFAULT_INBOX).strip().strip("/") or DEFAULT_INBOX
    save_app_settings(data)
    return get_disk_paths()


def get_disk_client_id() -> str:
    data = load_app_settings()
    from_settings = str(data.get("yandex_disk_client_id") or "").strip()
    if from_settings:
        return from_settings
    return (get_settings().yandex_disk_client_id or "").strip()


def set_disk_client_id(client_id: str | None) -> str:
    data = load_app_settings()
    value = (client_id or "").strip()
    data["yandex_disk_client_id"] = value
    save_app_settings(data)
    return value


def oauth_authorize_url(client_id: str | None = None) -> str | None:
    cid = (client_id or "").strip() or get_disk_client_id()
    if not cid:
        return None
    return (
        f"{OAUTH_AUTHORIZE}?response_type=token&client_id={quote(cid)}"
        f"&redirect_uri={quote(OAUTH_REDIRECT_URI)}"
        f"&scope={quote('cloud_api:disk.app_folder cloud_api:disk.read cloud_api:disk.write')}"
    )


def disk_status() -> dict[str, Any]:
    try:
        token = get_disk_token()
    except Exception:  # noqa: BLE001
        token = ""
    try:
        paths = get_disk_paths()
    except Exception:  # noqa: BLE001
        paths = {"root": DEFAULT_ROOT, "inbox_path": f"{DEFAULT_ROOT}/{DEFAULT_INBOX}"}
    try:
        client_id = get_disk_client_id()
    except Exception:  # noqa: BLE001
        client_id = ""
    try:
        token_path = str(_token_path())
    except Exception:  # noqa: BLE001
        token_path = ""
    out: dict[str, Any] = {
        "connected": bool(token),
        "token_path": token_path,
        "token_from_env": bool((get_settings().yandex_disk_oauth_token or "").strip()),
        "client_id": client_id,
        "client_id_configured": bool(client_id),
        "authorize_url": oauth_authorize_url(client_id) if client_id else None,
        "create_app_url": "https://oauth.yandex.ru/client/new",
        "root": paths.get("root") or DEFAULT_ROOT,
        "inbox_path": paths.get("inbox_path") or f"{DEFAULT_ROOT}/{DEFAULT_INBOX}",
        "login": None,
        "message": "",
    }
    if not token:
        out["message"] = "Нет OAuth-токена Диска. Вставьте токен или пройдите авторизацию."
        return out
    try:
        info = _api_get("/v1/disk", token)
        user = info.get("user") if isinstance(info.get("user"), dict) else {}
        out["login"] = user.get("login")
        out["message"] = "Диск подключён"
    except Exception as exc:  # noqa: BLE001
        out["connected"] = False
        out["message"] = str(exc)
    return out


class DiskApiError(RuntimeError):
    pass


def parse_yadisk_app_path(url: str) -> str | None:
    """yadisk-app:/HR_…/file.pdf → абсолютный путь на Диске."""
    text = (url or "").strip()
    if not text.lower().startswith("yadisk-app:"):
        return None
    path = text.split(":", 1)[1].strip()
    if not path:
        return None
    return path if path.startswith("/") else f"/{path}"


def download_disk_path_bytes(path: str, *, token: str | None = None) -> bytes:
    """Скачать файл по пути на подключённом Яндекс.Диске (OAuth)."""
    tok = (token or get_disk_token()).strip()
    if not tok:
        raise DiskApiError(
            "Яндекс.Диск не подключён — подключите в Настройках или задайте YANDEX_DISK_OAUTH_TOKEN"
        )
    meta = _api_get(f"{DISK_API}/resources/download", tok, {"path": path})
    href = str(meta.get("href") or "").strip()
    if not href:
        raise DiskApiError("Нет ссылки на скачивание с Диска")
    resp = requests.get(href, timeout=120)
    if resp.status_code >= 400:
        raise DiskApiError(f"Скачивание с Диска: HTTP {resp.status_code}")
    return resp.content


def public_url_for_app_link(url_or_path: str, *, token: str | None = None) -> str:
    """
    yadisk-app:/… или путь на Диске → публичный https URL для заказчика.
    Если файл ещё не опубликован — публикуем через OAuth.
    """
    path = parse_yadisk_app_path(url_or_path)
    if not path:
        text = (url_or_path or "").strip()
        if text.startswith("/"):
            path = text
        else:
            return ""
    tok = (token or get_disk_token()).strip()
    if not tok:
        return ""
    try:
        meta = _api_get(f"{DISK_API}/resources", tok, {"path": path})
        public = str(meta.get("public_url") or "").strip()
        if public.startswith("http"):
            return public
        _api_put_publish(path, tok)
        meta = _api_get(f"{DISK_API}/resources", tok, {"path": path})
        public = str(meta.get("public_url") or "").strip()
        return public if public.startswith("http") else ""
    except DiskApiError:
        return ""


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"OAuth {token}", "Accept": "application/json"}


def _api_get(path: str, token: str, params: dict | None = None) -> dict[str, Any]:
    url = path if path.startswith("http") else f"https://cloud-api.yandex.net{path}"
    resp = requests.get(url, headers=_headers(token), params=params or {}, timeout=60)
    if resp.status_code >= 400:
        raise DiskApiError(f"Disk API {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


def _api_put(path: str, token: str, params: dict | None = None) -> dict[str, Any]:
    url = path if path.startswith("http") else f"https://cloud-api.yandex.net{path}"
    resp = requests.put(url, headers=_headers(token), params=params or {}, timeout=60)
    if resp.status_code in (201, 409):
        return resp.json() if resp.content else {"ok": True}
    if resp.status_code >= 400:
        raise DiskApiError(f"Disk API {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


def _api_put_publish(path: str, token: str) -> dict[str, Any]:
    resp = requests.put(
        f"{DISK_API}/resources/publish",
        headers=_headers(token),
        params={"path": path},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise DiskApiError(f"Publish {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


def ensure_folder(token: str, path: str) -> None:
    path = path.rstrip("/") or "/"
    try:
        _api_put(f"{DISK_API}/resources", token, {"path": path})
    except DiskApiError as exc:
        try:
            _api_get(f"{DISK_API}/resources", token, {"path": path})
        except DiskApiError:
            raise exc from exc


def _safe_name(title: str, vacancy_id: int) -> str:
    raw = (title or "vacancy").strip() or "vacancy"
    raw = re.sub(r'[\\/:*?"<>|]+', "_", raw)
    raw = re.sub(r"\s+", " ", raw).strip()[:80]
    return f"{vacancy_id}_{raw}"


def ensure_app_root(token: str | None = None) -> dict[str, Any]:
    token = token or get_disk_token()
    if not token:
        raise DiskApiError("Нет OAuth-токена Яндекс.Диска")
    paths = get_disk_paths()
    ensure_folder(token, paths["root"])
    ensure_folder(token, paths["inbox_path"])
    return {"root": paths["root"], "inbox_path": paths["inbox_path"]}


def ensure_vacancy_folders(
    db: Session,
    vacancy: models.Vacancy,
    *,
    publish: bool = True,
) -> dict[str, Any]:
    """Create root/vacancy/{Резюме,Записи,Задания}; optionally publish and save public URL."""
    token = get_disk_token()
    if not token:
        raise DiskApiError("Нет OAuth-токена Яндекс.Диска")
    paths = ensure_app_root(token)
    folder_name = _safe_name(vacancy.title or "", vacancy.id)
    vac_path = f"{paths['root']}/{folder_name}"
    ensure_folder(token, vac_path)
    sub_paths = {}
    for key, label in DEFAULT_SUBFOLDERS.items():
        p = f"{vac_path}/{label}"
        ensure_folder(token, p)
        sub_paths[key] = p

    public_url = ""
    if publish:
        try:
            _api_put_publish(vac_path, token)
            meta = _api_get(f"{DISK_API}/resources", token, {"path": vac_path})
            public_url = str(meta.get("public_url") or "").strip()
        except DiskApiError:
            public_url = ""

    cfg = ensure_yandex_config(vacancy)
    if public_url:
        cfg["root_url"] = public_url
    cfg["app_disk_path"] = vac_path
    cfg["managed_by_app"] = True
    payload = dict(vacancy.payload or {})
    payload["yandex_disk"] = cfg
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    return {
        "path": vac_path,
        "subfolders": sub_paths,
        "public_url": public_url,
        "config": {
            "root_url": cfg.get("root_url") or "",
            "app_disk_path": vac_path,
            "managed_by_app": True,
        },
    }


def list_inbox_files(limit: int = 50) -> dict[str, Any]:
    token = get_disk_token()
    if not token:
        raise DiskApiError("Нет OAuth-токена Яндекс.Диска")
    paths = get_disk_paths()
    ensure_folder(token, paths["inbox_path"])
    data = _api_get(
        f"{DISK_API}/resources",
        token,
        {"path": paths["inbox_path"], "limit": max(1, min(200, limit))},
    )
    embedded = data.get("_embedded") or {}
    items = embedded.get("items") or []
    files = []
    for it in items:
        if not isinstance(it, dict) or it.get("type") != "file":
            continue
        name = str(it.get("name") or "")
        files.append(
            {
                "name": name,
                "path": it.get("path") or "",
                "mime_type": it.get("mime_type"),
                "size": it.get("size"),
                "modified": it.get("modified"),
                "suggested_vacancy_hint": _hint_from_filename(name),
            }
        )
    return {"inbox_path": paths["inbox_path"], "items": files, "count": len(files)}


def _hint_from_filename(name: str) -> str:
    stem = name.rsplit(".", 1)[0]
    if "__" in stem:
        return stem.split("__", 1)[0].strip()
    parts = stem.split("_")
    if len(parts) > 1 and parts[0].isdigit():
        return parts[0]
    return stem.split()[0] if stem.split() else ""


def suggest_inbox_routes(db: Session, limit: int = 50) -> dict[str, Any]:
    """L2 stub: list inbox + match hint against active vacancy titles (no auto-move yet)."""
    listed = list_inbox_files(limit=limit)
    vacancies = (
        db.execute(select(models.Vacancy).where(models.Vacancy.active.is_(True)).limit(200))
        .scalars()
        .all()
    )
    title_map = [(v.id, (v.title or "").strip()) for v in vacancies]

    def match(hint: str) -> dict[str, Any] | None:
        h = (hint or "").lower().strip()
        if not h:
            return None
        best = None
        best_score = 0.0
        for vid, title in title_map:
            t = title.lower()
            if not t:
                continue
            if h == t or h in t or t in h:
                score = min(len(h), len(t)) / max(len(h), len(t), 1)
                if score > best_score:
                    best_score = score
                    best = {"vacancy_id": vid, "title": title, "confidence": round(score, 2)}
        return best

    routed = []
    for item in listed["items"]:
        hint = str(item.get("suggested_vacancy_hint") or "")
        suggestion = match(hint)
        conf = (suggestion or {}).get("confidence", 0) if suggestion else 0
        routed.append(
            {
                **item,
                "suggestion": suggestion,
                "needs_review": suggestion is None or conf < 0.45,
            }
        )

    return {
        "inbox_path": listed["inbox_path"],
        "items": routed,
        "message": (
            "Авто-перенос пока выключен. Кладёте файлы в inbox как «Вакансия__ФИО.pdf» — "
            "система подскажет вакансию. Move+ИИ-маршрутизация — следующий шаг."
        ),
    }
