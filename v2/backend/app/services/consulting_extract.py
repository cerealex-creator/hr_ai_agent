"""Разбор публичной ссылки Яндекса для доказательств проекта."""

from __future__ import annotations

from app.services.source_extract import extract_text_from_bytes
from app.services.transcription import get_yandex_download_url, get_yandex_public_meta, parse_yandex_link
from app.services.yandex_public import is_yandex_pdf, is_yandex_video_or_audio, list_yandex_public_folder


def looks_public_yandex(url: str) -> bool:
    low = (url or "").lower()
    return "disk.yandex" in low or "yadi.sk" in low


def extract_public_source(url: str) -> tuple[str, str]:
    """Текст и статус: ok | folder | media | fail."""
    link = (url or "").strip()
    if not link or not looks_public_yandex(link):
        return "", "fail"
    root, path = parse_yandex_link(link)
    meta = get_yandex_public_meta(root or link, path=path)
    if not meta:
        return "", "fail"
    if is_yandex_video_or_audio(meta):
        return "", "media"
    kind = (meta.get("type") or "").lower()
    if kind == "dir":
        items = list_yandex_public_folder(root or link, path or "")
        names = [str(it.get("name") or "").strip() for it in items if it.get("name")]
        listing = "Папка «%s»\n%s" % (meta.get("name") or "без названия", "\n".join(f"- {n}" for n in names[:80]))
        return listing.strip(), "folder"
    if is_yandex_pdf(meta) or (meta.get("name") or ""):
        direct = meta.get("file") or get_yandex_download_url(link)
        if not direct:
            return "", "fail"
        try:
            from app.services.pdf_extract import download_url_bytes

            raw = download_url_bytes(str(direct), timeout=45)
        except Exception:  # noqa: BLE001
            return "", "fail"
        text = extract_text_from_bytes(str(meta.get("name") or "file"), raw)
        if text.strip():
            return text.strip()[:20000], "ok"
        return "", "fail"
    return "", "fail"
