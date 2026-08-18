"""Telegram Bot API provider (outbound)."""

from __future__ import annotations

import socket
from typing import Any

import requests

from app.core.config import get_settings


def _force_ipv4_for_requests() -> None:
    """Docker bridge often has no IPv6 default route; urllib3 may try AAAA and fail."""
    try:
        import urllib3.util.connection as urllib3_connection

        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
    except Exception:  # noqa: BLE001
        pass


_force_ipv4_for_requests()


class TelegramProviderError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def get_bot_token() -> str:
    settings = get_settings()
    return (settings.telegram_bot_token or "").strip()


def normalize_chat_id(chat_id: str | int | None) -> int | str | None:
    if chat_id is None:
        return None
    s = str(chat_id).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return s


def send_html_message(
    chat_id: str | int,
    text: str,
    *,
    reply_markup: dict | None = None,
    reply_to_message_id: str | int | None = None,
    bot_token: str | None = None,
) -> tuple[bool, str, str | None]:
    """Returns (ok, message, external_message_id)."""
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN", None

    normalized = normalize_chat_id(chat_id)
    if normalized is None:
        return False, "Не указан chat_id", None

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": normalized,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id is not None:
        mid = str(reply_to_message_id).strip()
        if mid.isdigit():
            payload["reply_to_message_id"] = int(mid)
        elif mid:
            payload["reply_to_message_id"] = mid

    try:
        response = requests.post(url, json=payload, timeout=30)
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        return False, f"Сетевая ошибка: {exc}", None

    if data.get("ok"):
        mid = data.get("result", {}).get("message_id")
        return True, "Сообщение отправлено в Telegram", str(mid) if mid is not None else None

    desc = data.get("description", "неизвестно")
    if "chat not found" in str(desc).lower():
        desc += ". Проверьте Chat ID и что бот добавлен в чат."
    return False, f"Ошибка Telegram: {desc}", None


def edit_html_message(
    chat_id: str | int,
    message_id: str | int,
    text: str,
    *,
    reply_markup: dict | None = None,
    bot_token: str | None = None,
) -> tuple[bool, str]:
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN"
    normalized = normalize_chat_id(chat_id)
    if normalized is None:
        return False, "Не указан chat_id"
    payload: dict[str, Any] = {
        "chat_id": normalized,
        "message_id": int(message_id) if str(message_id).isdigit() else message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/editMessageText",
            json=payload,
            timeout=30,
        )
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if data.get("ok"):
        return True, "ok"
    desc = str(data.get("description") or "ошибка")
    # Telegram returns this when content is unchanged — treat as success.
    if "message is not modified" in desc.lower():
        return True, "ok"
    return False, desc


def edit_message_keyboard(
    chat_id: str | int,
    message_id: str | int,
    reply_markup: dict,
    *,
    bot_token: str | None = None,
) -> tuple[bool, str]:
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN"
    normalized = normalize_chat_id(chat_id)
    if normalized is None:
        return False, "Не указан chat_id"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/editMessageReplyMarkup",
            json={
                "chat_id": normalized,
                "message_id": int(message_id) if str(message_id).isdigit() else message_id,
                "reply_markup": reply_markup,
            },
            timeout=30,
        )
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if data.get("ok"):
        return True, "ok"
    desc = str(data.get("description") or "ошибка")
    if "message is not modified" in desc.lower():
        return True, "ok"
    return False, desc


def answer_callback_query(
    callback_query_id: str,
    *,
    text: str | None = None,
    show_alert: bool = False,
    bot_token: str | None = None,
) -> tuple[bool, str]:
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN"
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    if show_alert:
        payload["show_alert"] = True
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json=payload,
            timeout=15,
        )
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if data.get("ok"):
        return True, "ok"
    return False, str(data.get("description") or "ошибка")


def delete_message(
    chat_id: str | int,
    message_id: str | int,
    *,
    bot_token: str | None = None,
) -> tuple[bool, str]:
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN"
    normalized = normalize_chat_id(chat_id)
    if normalized is None:
        return False, "Не указан chat_id"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/deleteMessage",
            json={
                "chat_id": normalized,
                "message_id": int(message_id) if str(message_id).isdigit() else message_id,
            },
            timeout=15,
        )
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if data.get("ok"):
        return True, "ok"
    return False, str(data.get("description") or "ошибка")


def get_me(bot_token: str | None = None) -> tuple[bool, str, dict]:
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN", {}
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        data = r.json()
        if data.get("ok"):
            return True, "ok", data.get("result") or {}
        return False, str(data.get("description") or "error"), {}
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), {}
