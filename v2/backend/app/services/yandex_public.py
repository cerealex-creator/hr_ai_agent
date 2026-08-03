"""Yandex Disk public folder helpers for v2 (no Streamlit imports)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from app.services.transcription import get_yandex_public_meta, parse_yandex_link


def format_yandex_link(root_url: str, path: str = "") -> str:
    root = (root_url or "").strip()
    rel = (path or "").strip()
    if not root:
        return ""
    if not rel:
        return root
    if not rel.startswith("/"):
        rel = "/" + rel
    return f"yadisk:{root}::{rel}"


def yandex_public_view_url(root_url: str, path: str) -> str:
    root = (root_url or "").strip().rstrip("/")
    rel = (path or "").strip()
    if not root:
        return ""
    if not rel:
        return root
    if not rel.startswith("/"):
        rel = "/" + rel
    segments = [quote(part, safe="") for part in rel.strip("/").split("/") if part]
    if not segments:
        return root
    return f"{root}/{'/'.join(segments)}"


def yandex_link_for_display(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    root, path = parse_yandex_link(url)
    if not root:
        return url
    if not path:
        return root
    if "/i/" in root:
        return root
    meta = get_yandex_public_meta(root, path=path)
    if meta:
        public_url = (meta.get("public_url") or "").strip()
        if public_url:
            return public_url
    return yandex_public_view_url(root, path)


def yandex_path_is_valid(public_key: str, path: str) -> bool:
    if not public_key:
        return False
    if not (path or "").strip():
        return True
    return get_yandex_public_meta(public_key, path=path) is not None


def list_yandex_public_folder(public_key: str, path: str = "", *, limit: int = 200) -> list[dict[str, Any]]:
    meta = get_yandex_public_meta(public_key, path=path or "")
    if not meta:
        return []
    embedded = meta.get("_embedded") or {}
    items = embedded.get("items") or []
    return items[:limit] if limit else items


def is_yandex_pdf(meta: dict | None) -> bool:
    if not meta:
        return False
    name = (meta.get("name") or "").lower()
    mime = (meta.get("mime_type") or "").lower()
    return name.endswith(".pdf") or mime == "application/pdf"


def is_yandex_video_or_audio(meta: dict | None) -> bool:
    if not meta:
        return False
    media = (meta.get("media_type") or "").lower()
    if media in ("video", "audio"):
        return True
    mime = (meta.get("mime_type") or "").lower()
    name = (meta.get("name") or "").lower()
    if mime.startswith(("video/", "audio/")):
        return True
    return name.endswith((".mp4", ".webm", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".ogg", ".m4a"))
