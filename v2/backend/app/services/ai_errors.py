"""Persist sanitized AI parse/schema failures for prompt tuning."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db import models
from app.services.log_sanitize import sanitize_text

logger = logging.getLogger(__name__)

_RAW_MAX = 8000


def log_ai_error(
    db: Session | None,
    *,
    task: str,
    error_kind: str,
    error_message: str,
    raw_response: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    """Best-effort insert; never raises to callers. Opens own session if db is None."""
    safe_raw = sanitize_text(raw_response, max_len=_RAW_MAX)
    safe_msg = sanitize_text(error_message, max_len=500)
    safe_meta = meta or {}
    own_session = False
    session = db
    try:
        if session is None:
            from app.db.session import SessionLocal

            session = SessionLocal()
            own_session = True
        row = models.AiErrorLog(
            task=task,
            error_kind=error_kind,
            error_message=safe_msg,
            raw_response=safe_raw,
            meta=safe_meta,
        )
        session.add(row)
        session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("failed to persist ai_error_log")
        try:
            if session is not None:
                session.rollback()
        except Exception:  # noqa: BLE001
            pass
    finally:
        if own_session and session is not None:
            session.close()