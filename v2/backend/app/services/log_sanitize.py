"""Mask PII (phones, emails) before writing to logs or ai_error_logs."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
# RU / intl phones: +7..., 8..., groups of digits
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\-\s()]{8,}\d)",
)


def sanitize_text(text: str | None, *, max_len: int | None = None) -> str:
    s = str(text or "")
    s = _EMAIL_RE.sub("[email]", s)
    s = _PHONE_RE.sub("[phone]", s)
    if max_len is not None and len(s) > max_len:
        s = s[:max_len] + "…"
    return s


def sanitize_for_log(obj: object, *, max_len: int = 800) -> str:
    return sanitize_text(str(obj), max_len=max_len)
