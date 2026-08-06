"""Inbound messaging idempotency (Telegram callback_query.id, etc.)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models


def already_processed(
    db: Session,
    *,
    provider: str,
    external_id: str,
) -> bool:
    eid = (external_id or "").strip()
    if not eid:
        return False
    row = db.execute(
        select(models.ProcessedMessagingUpdate.id).where(
            models.ProcessedMessagingUpdate.provider == provider,
            models.ProcessedMessagingUpdate.external_id == eid,
        )
    ).scalar_one_or_none()
    return row is not None


def mark_processed(
    db: Session,
    *,
    provider: str,
    external_id: str,
    kind: str = "callback_query",
) -> bool:
    """Return True if newly marked, False if already existed."""
    eid = (external_id or "").strip()
    if not eid:
        return False
    if already_processed(db, provider=provider, external_id=eid):
        return False
    db.add(
        models.ProcessedMessagingUpdate(
            provider=provider,
            external_id=eid,
            kind=kind,
        )
    )
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
