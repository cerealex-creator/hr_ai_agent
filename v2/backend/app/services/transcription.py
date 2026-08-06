"""Yandex Disk / SpeechKit transcription (ported for v2 workers)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests

from app.core.config import Settings, get_settings
from app.services.ai_json import chat_json

ProgressCb = Callable[[int, str], None]

TRANSCRIPT_CLEANUP_SYSTEM = """Ты — помощник рекрутера. Приведи расшифровку собеседования к читаемому виду.

Правила:
- убери мусор речи: повторы, междометия, обрывки без смысла;
- ничего не выдумывай и не добавляй фактов;
- сохрани смысл ответов кандидата;
- оформи текст короткими абзацами или списками по темам, чтобы его было удобно читать рекрутеру.

Верни ТОЛЬКО JSON:
{"clean_text": "готовый очищенный текст"}"""


def _progress(cb: ProgressCb | None, pct: int, label: str) -> None:
    if cb:
        cb(pct, label)


def parse_yandex_link(url: str) -> tuple[str | None, str | None]:
    """Разбирает ссылку yadisk:ROOT::/path или обычный public URL."""
    url = (url or "").strip()
    if not url:
        return None, None
    if url.startswith("yadisk:"):
        payload = url[7:]
        if "::" in payload:
            root, path = payload.split("::", 1)
            return root.strip(), (path or "").strip() or None
        return payload.strip(), None
    return url, None


def get_yandex_public_meta(url: str, *, path: str | None = None) -> dict[str, Any] | None:
    public_key, parsed_path = parse_yandex_link(url)
    use_path = path if path is not None else parsed_path
    if not public_key:
        return None
    if not ("disk.yandex" in public_key or "yadi.sk" in public_key):
        return None
    params: dict[str, str] = {"public_key": public_key}
    if use_path:
        if not str(use_path).startswith("/"):
            use_path = "/" + str(use_path)
        params["path"] = str(use_path)
    try:
        response = requests.get(
            "https://cloud-api.yandex.net/v1/disk/public/resources",
            params=params,
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None


def get_yandex_download_url(url: str, *, path: str | None = None) -> str | None:
    public_key, parsed_path = parse_yandex_link(url)
    use_path = path if path is not None else parsed_path
    meta = get_yandex_public_meta(public_key or "", path=use_path) if public_key else None
    if meta and meta.get("file"):
        return meta["file"]
    if not public_key:
        return None
    params: dict[str, str] = {"public_key": public_key}
    if use_path:
        if not str(use_path).startswith("/"):
            use_path = "/" + str(use_path)
        params["path"] = str(use_path)
    try:
        response = requests.get(
            "https://cloud-api.yandex.net/v1/disk/public/resources/download",
            params=params,
            timeout=30,
        )
        if response.status_code == 200:
            return response.json().get("href")
    except requests.RequestException:
        pass
    if "/i/" in public_key and not use_path:
        return public_key
    # fallback: scrape downloader link from public page
    try:
        html = requests.get(
            public_key if "http" in public_key else url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        ).text
        match = re.search(r'"href":"(https://downloader\.disk\.yandex\.ru[^"]+)"', html)
        if match:
            return match.group(1).replace("\\/", "/")
    except requests.RequestException:
        pass
    return None


def resolve_direct_url(source_url: str) -> str:
    source_url = (source_url or "").strip()
    if not source_url:
        raise RuntimeError("Пустая ссылка на медиа")
    if (
        source_url.startswith("yadisk:")
        or "disk.yandex" in source_url
        or "yadi.sk" in source_url
    ):
        direct = get_yandex_download_url(source_url)
        if not direct:
            raise RuntimeError("Не удалось получить прямую ссылку Яндекс.Диска")
        return direct
    return source_url


def resolve_ffmpeg_binary(configured: str = "") -> str:
    candidates = (
        (configured or "").strip(),
        (os.getenv("FFMPEG_BINARY") or "").strip(),
        shutil.which("ffmpeg") or "",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    )
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def convert_to_pcm(input_path: str, ffmpeg_binary: str = "") -> str:
    output_path = os.path.splitext(input_path)[0] + "_speechkit.pcm"
    binary = resolve_ffmpeg_binary(ffmpeg_binary)
    if not binary:
        raise RuntimeError("Не найден ffmpeg. Установите ffmpeg и повторите.")
    try:
        subprocess.run(
            [
                binary,
                "-y",
                "-i",
                input_path,
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не удалось запустить ffmpeg: {binary}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="ignore").strip()
        raise RuntimeError(
            "Ошибка конвертации через ffmpeg. "
            + (f"stderr: {stderr}" if stderr else "Проверьте формат файла.")
        ) from exc
    return output_path


def validate_speechkit_config(
    *,
    bucket: str,
    access_key: str,
    secret_key: str,
    api_key: str,
) -> None:
    missing = []
    if not (bucket or "").strip():
        missing.append("YANDEX_BUCKET_NAME")
    if not (access_key or "").strip():
        missing.append("YANDEX_ACCESS_KEY_ID")
    if not (secret_key or "").strip():
        missing.append("YANDEX_SECRET_ACCESS_KEY")
    if not (api_key or "").strip():
        missing.append("YANDEX_API_KEY")
    if missing:
        raise RuntimeError(
            "Не настроен Яндекс SpeechKit / Object Storage. Не хватает: "
            + ", ".join(missing)
            + ". Добавьте ключи в `.env` (корень проекта или v2/.env)."
        )


def upload_to_s3_and_get_url(
    local_path: str,
    *,
    bucket: str,
    access_key: str,
    secret_key: str,
) -> str:
    from boto3 import client

    s3_client = client(
        "s3",
        endpoint_url="https://storage.yandexcloud.net",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    object_name = os.path.basename(local_path)
    if not os.path.exists(local_path):
        raise RuntimeError(f"Файл для загрузки не найден: {local_path}")
    try:
        s3_client.upload_file(local_path, bucket, object_name)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Ошибка загрузки в Yandex Object Storage. "
            "Проверьте бакет и права storage.editor. "
            f"Детали: {type(exc).__name__}: {exc}"
        ) from exc
    return f"https://storage.yandexcloud.net/{bucket}/{object_name}"


def delete_s3_object(
    object_name: str,
    *,
    bucket: str,
    access_key: str,
    secret_key: str,
) -> None:
    """Best-effort delete of SpeechKit PCM (audit M10). Never raises."""
    name = (object_name or "").strip()
    if not name or not bucket:
        return
    try:
        from boto3 import client

        s3_client = client(
            "s3",
            endpoint_url="https://storage.yandexcloud.net",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        s3_client.delete_object(Bucket=bucket, Key=name)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("S3 delete failed for %s/%s", bucket, name)


def recognize_long_audio(
    audio_url: str,
    api_key: str,
    *,
    on_progress: ProgressCb | None = None,
    should_cancel: Callable[[], bool] | None = None,
    poll_seconds: float = 5.0,
    max_wait_seconds: float = 900.0,
) -> str:
    response = requests.post(
        "https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize",
        headers={"Authorization": f"Api-Key {api_key}"},
        json={
            "config": {
                "specification": {
                    "languageCode": "ru-RU",
                    "profanityFilter": "false",
                    "audioEncoding": "LINEAR16_PCM",
                    "sampleRateHertz": 16000,
                    "audioChannelCount": 1,
                }
            },
            "audio": {"uri": audio_url},
        },
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"SpeechKit: ошибка запроса ({response.status_code}). {response.text}"
        )
    operation_id = response.json()["id"]
    ticks = 0
    deadline = time.monotonic() + max(60.0, float(max_wait_seconds))
    while True:
        if should_cancel and should_cancel():
            raise RuntimeError("Отменено")
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"SpeechKit: превышено время ожидания ({int(max_wait_seconds)} с)"
            )
        ticks += 1
        # progress 70→95 while waiting
        pct = min(95, 70 + ticks)
        _progress(on_progress, pct, f"SpeechKit: ожидание результата… ({ticks})")
        time.sleep(poll_seconds)
        status_response = requests.get(
            f"https://operation.api.cloud.yandex.net/operations/{operation_id}",
            headers={"Authorization": f"Api-Key {api_key}"},
            timeout=30,
        )
        if status_response.status_code != 200:
            raise RuntimeError(
                f"SpeechKit: ошибка статуса ({status_response.status_code}). "
                f"{status_response.text}"
            )
        status_data = status_response.json()
        if not status_data.get("done"):
            continue
        if "error" in status_data:
            raise RuntimeError(f"SpeechKit: ошибка распознавания: {status_data['error']}")
        full_text = ""
        for chunk in status_data.get("response", {}).get("chunks", []):
            alts = chunk.get("alternatives") or []
            if alts:
                full_text += (alts[0].get("text") or "") + " "
        return full_text.strip()


def guess_extension(source_url: str, content_type: str) -> str:
    ct = (content_type or "").lower()
    url = (source_url or "").lower()
    path = unquote(urlparse(url).path)
    for ext in (".webm", ".mp4", ".mp3", ".wav", ".ogg", ".m4a", ".mov", ".mkv"):
        if path.endswith(ext) or ext[1:] in ct:
            return ext
    if "webm" in ct:
        return ".webm"
    if "mpeg" in ct or "mp3" in ct:
        return ".mp3"
    if "wav" in ct:
        return ".wav"
    return ".mp4"


def download_media(direct_url: str, on_progress: ProgressCb | None = None) -> str:
    _progress(on_progress, 15, "Скачивание файла")
    response = requests.get(direct_url, timeout=600, stream=True)
    if response.status_code != 200:
        raise RuntimeError(f"Ошибка скачивания: HTTP {response.status_code}")
    ext = guess_extension(direct_url, response.headers.get("content-type", ""))
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                tmp.write(chunk)
        path = tmp.name
    size_mb = Path(path).stat().st_size / (1024 * 1024)
    _progress(on_progress, 30, f"Файл скачан ({size_mb:.1f} МБ)")
    return path


def transcribe_from_url(
    source_url: str,
    *,
    api_key: str,
    bucket: str,
    access_key: str,
    secret_key: str,
    ffmpeg_binary: str = "",
    on_progress: ProgressCb | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Full pipeline. Returns {transcript, source_url, chars}."""
    validate_speechkit_config(
        bucket=bucket, access_key=access_key, secret_key=secret_key, api_key=api_key
    )
    if should_cancel and should_cancel():
        raise RuntimeError("Отменено")

    _progress(on_progress, 5, "Получение прямой ссылки")
    direct = resolve_direct_url(source_url)

    if should_cancel and should_cancel():
        raise RuntimeError("Отменено")
    media_path = download_media(direct, on_progress=on_progress)
    pcm_path = None
    s3_object_name: str | None = None
    try:
        if should_cancel and should_cancel():
            raise RuntimeError("Отменено")
        _progress(on_progress, 45, "Конвертация ffmpeg → PCM")
        pcm_path = convert_to_pcm(media_path, ffmpeg_binary=ffmpeg_binary)

        if should_cancel and should_cancel():
            raise RuntimeError("Отменено")
        _progress(on_progress, 60, "Загрузка в Object Storage")
        audio_url = upload_to_s3_and_get_url(
            pcm_path, bucket=bucket, access_key=access_key, secret_key=secret_key
        )
        s3_object_name = os.path.basename(pcm_path)

        _progress(on_progress, 70, "Запрос в SpeechKit")
        text = recognize_long_audio(
            audio_url,
            api_key,
            on_progress=on_progress,
            should_cancel=should_cancel,
        )
        if not text:
            raise RuntimeError("SpeechKit вернул пустой текст")
        _progress(on_progress, 100, "Расшифровка готова")
        return {
            "transcript": text,
            "source_url": source_url,
            "chars": len(text),
            "preview": text[:280] + ("…" if len(text) > 280 else ""),
        }
    finally:
        if s3_object_name:
            delete_s3_object(
                s3_object_name,
                bucket=bucket,
                access_key=access_key,
                secret_key=secret_key,
            )
        for path in (media_path, pcm_path):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass


def transcribe_from_path(
    media_path: str,
    *,
    api_key: str,
    bucket: str,
    access_key: str,
    secret_key: str,
    ffmpeg_binary: str = "",
    on_progress: ProgressCb | None = None,
    should_cancel: Callable[[], bool] | None = None,
    source_label: str = "",
) -> dict[str, Any]:
    """SpeechKit pipeline for a local media file (upload). Does not delete media_path."""
    validate_speechkit_config(
        bucket=bucket, access_key=access_key, secret_key=secret_key, api_key=api_key
    )
    if not media_path or not os.path.exists(media_path):
        raise RuntimeError(f"Медиафайл не найден: {media_path}")
    pcm_path = None
    s3_object_name: str | None = None
    try:
        if should_cancel and should_cancel():
            raise RuntimeError("Отменено")
        _progress(on_progress, 45, "Конвертация ffmpeg → PCM")
        pcm_path = convert_to_pcm(media_path, ffmpeg_binary=ffmpeg_binary)
        if should_cancel and should_cancel():
            raise RuntimeError("Отменено")
        _progress(on_progress, 60, "Загрузка в Object Storage")
        audio_url = upload_to_s3_and_get_url(
            pcm_path, bucket=bucket, access_key=access_key, secret_key=secret_key
        )
        s3_object_name = os.path.basename(pcm_path)
        _progress(on_progress, 70, "Запрос в SpeechKit")
        text = recognize_long_audio(
            audio_url,
            api_key,
            on_progress=on_progress,
            should_cancel=should_cancel,
        )
        if not text:
            raise RuntimeError("SpeechKit вернул пустой текст")
        _progress(on_progress, 100, "Расшифровка готова")
        return {
            "transcript": text,
            "source_url": source_label or media_path,
            "chars": len(text),
            "preview": text[:280] + ("…" if len(text) > 280 else ""),
        }
    finally:
        if s3_object_name:
            delete_s3_object(
                s3_object_name,
                bucket=bucket,
                access_key=access_key,
                secret_key=secret_key,
            )
        if pcm_path and os.path.exists(pcm_path):
            try:
                os.unlink(pcm_path)
            except OSError:
                pass


def cleanup_transcript_text(text: str, settings: Settings | None = None) -> str:
    source = (text or "").strip()
    if not source:
        return ""
    settings = settings or get_settings()
    data = chat_json(
        settings,
        system=TRANSCRIPT_CLEANUP_SYSTEM,
        user=f"ТЕКСТ РАСШИФРОВКИ:\n{source[:14000]}",
        temperature=0.1,
        max_tokens=3500,
    )
    cleaned = ""
    if isinstance(data, dict):
        cleaned = str(data.get("clean_text") or "").strip()
    return cleaned or source
