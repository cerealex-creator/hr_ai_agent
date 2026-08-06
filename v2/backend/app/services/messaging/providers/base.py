"""Messaging provider contract (D3 multi-provider foundation)."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.db import models


@runtime_checkable
class MessagingProvider(Protocol):
    """Adapter for one client-facing channel (Bitrix, Telegram, future WhatsApp…)."""

    id: str
    label: str

    def is_available(self) -> bool:
        """Runtime readiness (tokens, flags, network policy)."""
        ...

    def unavailable_reason(self) -> str | None:
        """Human hint when not selectable / send will fail."""
        ...

    def send_candidate(
        self,
        db: Session,
        candidate: models.Candidate,
        *,
        move_to_client_review: bool = False,
    ) -> dict[str, Any]:
        """Deliver candidate card / task. Returns provider-specific result dict with ok=True."""
        ...
