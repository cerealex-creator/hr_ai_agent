"""Provider registry: UI catalog + dispatch for send-to-client (D3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.app_settings import get_bitrix
from app.services.messaging.providers.base import MessagingProvider


@dataclass(frozen=True)
class ProviderCatalogItem:
    id: str
    label: str
    kind: str  # active | upcoming
    selectable: bool
    unavailable_reason: str | None = None
    description: str = ""


# Channels that can appear in client_notify.channels and perform send.
ACTIVE_CHANNEL_IDS = frozenset({"bitrix", "web", "telegram"})
# Showcase-only (upsell) — never selectable.
UPCOMING_CHANNEL_IDS = frozenset({"whatsapp", "max"})

PROVIDER_BLOCKED_HINT = "Недоступно в текущей конфигурации / Блокировка провайдера"


class BitrixProvider:
    id = "bitrix"
    label = "Bitrix24"

    def is_available(self) -> bool:
        cfg = get_bitrix()
        return bool(cfg.get("enabled") and str(cfg.get("incoming_webhook_url") or "").strip())

    def unavailable_reason(self) -> str | None:
        cfg = get_bitrix()
        if not cfg.get("enabled"):
            return "Bitrix выключен в настройках"
        if not str(cfg.get("incoming_webhook_url") or "").strip():
            return "Не задан incoming webhook URL"
        return None

    def send_candidate(
        self,
        db: Session,
        candidate: models.Candidate,
        *,
        move_to_client_review: bool = False,
    ) -> dict[str, Any]:
        from app.services.bitrix.outbound import send_candidate_bitrix_task

        return send_candidate_bitrix_task(
            db, candidate, move_to_client_review=move_to_client_review
        )


class TelegramProvider:
    id = "telegram"
    label = "Telegram"

    def is_available(self) -> bool:
        settings = get_settings()
        return bool(
            settings.messaging_outbound_enabled and (settings.telegram_bot_token or "").strip()
        )

    def unavailable_reason(self) -> str | None:
        settings = get_settings()
        if not settings.messaging_outbound_enabled:
            return PROVIDER_BLOCKED_HINT
        if not (settings.telegram_bot_token or "").strip():
            return PROVIDER_BLOCKED_HINT
        return None

    def send_candidate(
        self,
        db: Session,
        candidate: models.Candidate,
        *,
        move_to_client_review: bool = False,
    ) -> dict[str, Any]:
        from app.services.messaging.gateway import send_candidate_card

        return send_candidate_card(db, candidate, move_to_client_review=move_to_client_review)


class WebClientZoneProvider:
    """Ensures client-zone token exists; returns shareable /c/{token} link (no external API)."""

    id = "web"
    label = "Веб-зона заказчика"

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def send_candidate(
        self,
        db: Session,
        candidate: models.Candidate,
        *,
        move_to_client_review: bool = False,
    ) -> dict[str, Any]:
        from app.services.tenancy import generate_client_zone_token

        vacancy = db.get(models.Vacancy, candidate.vacancy_id)
        if not vacancy or vacancy.client_id is None:
            raise RuntimeError("У вакансии нет клиента — веб-зона недоступна")
        client = db.get(models.Client, vacancy.client_id)
        if not client:
            raise RuntimeError("Клиент не найден")
        if not (client.client_zone_token or "").strip():
            client.client_zone_token = generate_client_zone_token(db)
            db.commit()
            db.refresh(client)
        path = f"/c/{client.client_zone_token}"
        label = client.name
        if client.parent_id:
            parent = db.get(models.Client, client.parent_id)
            if parent and parent.name:
                label = f"{parent.name} · {client.name}"
        return {
            "ok": True,
            "provider": "web",
            "message": (
                f"Кандидат в веб-зоне заказчика ({label}). "
                f"Отправьте заказчику ссылку из раздела «Клиентская зона» или настроек компании: {path}"
            ),
            "client_zone_path": path,
            "company_id": client.id,
            "company_name": label,
            "scope_client_ids": [int(client.id)],
        }


class StubProvider:
    """Upcoming channel for upsell showcase (never sends)."""

    def __init__(self, provider_id: str, label: str):
        self.id = provider_id
        self.label = label

    def is_available(self) -> bool:
        return False

    def unavailable_reason(self) -> str | None:
        return "Скоро · расширенная версия"

    def send_candidate(
        self,
        db: Session,
        candidate: models.Candidate,
        *,
        move_to_client_review: bool = False,
    ) -> dict[str, Any]:
        raise RuntimeError(f"Канал {self.id} ещё не подключён")


_PROVIDERS: dict[str, MessagingProvider] = {
    "bitrix": BitrixProvider(),
    "web": WebClientZoneProvider(),
    "telegram": TelegramProvider(),
    "whatsapp": StubProvider("whatsapp", "WhatsApp"),
    "max": StubProvider("max", "Max"),
}


def get_provider(provider_id: str) -> MessagingProvider | None:
    return _PROVIDERS.get(str(provider_id or "").strip())


def list_providers() -> list[MessagingProvider]:
    order = ("bitrix", "web", "telegram", "whatsapp", "max")
    return [_PROVIDERS[i] for i in order if i in _PROVIDERS]


def catalog_for_ui() -> list[dict[str, Any]]:
    """Registry snapshot for settings UI (no secrets)."""
    items: list[dict[str, Any]] = []
    for p in list_providers():
        upcoming = p.id in UPCOMING_CHANNEL_IDS
        available = False if upcoming else p.is_available()
        reason = p.unavailable_reason() if not available else None
        # Telegram: selectable only when available (pilot: usually blocked).
        # Bitrix/web: selectable even if Bitrix not fully configured (user can enable channel ahead).
        if upcoming:
            selectable = False
        elif p.id == "telegram":
            selectable = available
        else:
            selectable = True
        items.append(
            {
                "id": p.id,
                "label": p.label,
                "kind": "upcoming" if upcoming else "active",
                "selectable": selectable,
                "unavailable_reason": reason,
                "description": {
                    "bitrix": "Задача ответственному + ссылки решения",
                    "web": "Секретная ссылка /c/… без логина",
                    "telegram": "Чат заказчика (кнопки статуса)",
                    "whatsapp": "Планируется в расширенной версии",
                    "max": "Планируется в расширенной версии",
                }.get(p.id, ""),
            }
        )
    return items


def telegram_hr_notify_allowed() -> bool:
    """HR internal Telegram DM: outbound on + TELEGRAM_HR_USER_ID set."""
    settings = get_settings()
    return bool(
        settings.messaging_outbound_enabled and (settings.telegram_hr_user_id or "").strip()
    )
