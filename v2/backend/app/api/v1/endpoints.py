"""Backward-compatible entry: re-exports aggregated router (audit M6)."""
from app.api.v1.router import router
from app.api.v1.common import _parse_webhook_payload  # noqa: F401 — main.py

__all__ = ["router", "_parse_webhook_payload"]
