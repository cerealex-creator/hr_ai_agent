"""Attach candidate photo from PDF or HH (best effort)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings, get_settings
from app.db import models
from app.services.photo_extract import extract_photo_from_pdf_bytes

logger = logging.getLogger(__name__)


def hh_photo_url_from_data(data: dict[str, Any] | None) -> str | None:
    """Extract portrait URL from HH resume JSON or search snapshot."""
    if not isinstance(data, dict):
        return None
    photo = data.get("photo")
    if isinstance(photo, dict):
        for key in ("medium", "small", "url", "100", "500", "40"):
            val = photo.get(key)
            if isinstance(val, str) and val.strip().startswith("http"):
                return val.strip()
    if isinstance(photo, str) and photo.strip().startswith("http"):
        return photo.strip()
    for key in ("photo_url", "photo_urls"):
        val = data.get(key)
        if isinstance(val, str) and val.strip().startswith("http"):
            return val.strip()
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip().startswith("http"):
                    return item.strip()
    return None


def upload_candidate_photo_jpeg(jpeg: bytes, candidate_id: str, *, settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    bucket = (settings.yandex_bucket_name or "").strip()
    access_key = (settings.yandex_access_key_id or "").strip()
    secret_key = (settings.yandex_secret_access_key or "").strip()
    if not bucket or not access_key or not secret_key:
        logger.info("Yandex S3 not configured — skip candidate photo upload")
        return None
    if not jpeg:
        return None

    object_name = f"photos/{candidate_id}.jpg"
    try:
        from boto3 import client  # noqa: PLC0415

        s3 = client(
            "s3",
            endpoint_url="https://storage.yandexcloud.net",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        s3.put_object(
            Bucket=bucket,
            Key=object_name,
            Body=jpeg,
            ContentType="image/jpeg",
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to upload candidate photo to S3")
        return None
    return f"https://storage.yandexcloud.net/{bucket}/{object_name}"


def try_attach_candidate_photo(
    db: Session,
    candidate: models.Candidate,
    *,
    pdf_bytes: bytes | None = None,
    hh_photo_url: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """
    Best effort: set payload.photo_url. Never raises.
    HH URL is stored as-is; PDF portrait is uploaded to S3.
    """
    try:
        payload = dict(candidate.payload or {})
        existing = str(payload.get("photo_url") or "").strip()
        if existing:
            return False

        settings = settings or get_settings()
        hh_url = (hh_photo_url or "").strip()
        if hh_url.startswith("http"):
            payload["photo_url"] = hh_url
            candidate.payload = payload
            flag_modified(candidate, "payload")
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            return True

        if pdf_bytes and pdf_bytes.lstrip().startswith(b"%PDF"):
            jpeg = extract_photo_from_pdf_bytes(pdf_bytes)
            if not jpeg:
                return False
            url = upload_candidate_photo_jpeg(jpeg, str(candidate.id), settings=settings)
            if not url:
                return False
            payload["photo_url"] = url
            candidate.payload = payload
            flag_modified(candidate, "payload")
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            return True
        return False
    except Exception:  # noqa: BLE001
        logger.exception("candidate photo attach failed for %s", getattr(candidate, "id", "?"))
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False
