"""Download PDF and extract text (v2)."""

from __future__ import annotations

from io import BytesIO

import requests

from app.services.transcription import get_yandex_download_url, get_yandex_public_meta, parse_yandex_link
from app.services.yandex_public import is_yandex_pdf, is_yandex_video_or_audio


def _pdf_text_from_bytes(content: bytes) -> str:
    if not content or not content.lstrip().startswith(b"%PDF"):
        return ""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Нужен пакет pypdf") from exc
    reader = PdfReader(BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            continue
    return "\n".join(parts).strip()


def download_url_bytes(url: str, *, timeout: int = 60) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.content


def extract_text_from_pdf_url(url: str) -> str:
    """Public Yandex Disk or direct PDF URL → text."""
    url = (url or "").strip()
    if not url:
        return ""
    download = url
    if url.startswith("yadisk:") or "disk.yandex" in url or "yadi.sk" in url:
        direct = get_yandex_download_url(url)
        if not direct:
            root, path = parse_yandex_link(url)
            meta = get_yandex_public_meta(root or url, path=path or None)
            if meta and meta.get("file"):
                direct = meta["file"]
        if not direct:
            return ""
        download = direct
    try:
        content = download_url_bytes(download)
    except Exception:  # noqa: BLE001
        return ""
    return _pdf_text_from_bytes(content)


def fetch_resume_text_from_url(url: str) -> tuple[str, str]:
    """
    Returns (text, error).
    Video links are not transcribed here — use job transcribe_media separately.
    """
    url = (url or "").strip()
    if not url:
        return "", "Пустая ссылка"

    if url.startswith("yadisk:") or "disk.yandex" in url or "yadi.sk" in url:
        root, path = parse_yandex_link(url)
        meta = get_yandex_public_meta(root or url, path=path or None)
        if meta and is_yandex_video_or_audio(meta):
            return "", "Ссылка на видео/аудио — сначала расшифруйте (Задачи → Расшифровать)"
        text = extract_text_from_pdf_url(url)
        if len(text) >= 50:
            return text, ""
        if meta and not is_yandex_pdf(meta):
            label = meta.get("name") or meta.get("mime_type") or "файл"
            return "", f"Файл на Яндекс.Диске не PDF ({label})"
        return "", "Не удалось извлечь текст из PDF на Яндекс.Диске"

    try:
        content = download_url_bytes(url)
    except Exception as exc:  # noqa: BLE001
        return "", f"Не удалось скачать: {exc}"
    text = _pdf_text_from_bytes(content)
    if len(text) >= 50:
        return text, ""
    if content.lstrip().startswith(b"%PDF"):
        return "", "PDF скачан, но текст не извлечён (возможно скан)"
    return "", "По ссылке не PDF или текст слишком короткий"
