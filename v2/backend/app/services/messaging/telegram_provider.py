"""Telegram Bot API provider (outbound)."""

from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Any, Iterator

import requests

from app.core.config import get_settings

TELEGRAM_API_HOST = "api.telegram.org"
# Timeweb and some RU hosts resolve api.telegram.org to IPs that are unreachable;
# 149.154.167.220 is a stable Bot API endpoint for forced IPv4 connect + SNI.
TELEGRAM_API_IPV4_FALLBACKS = (
    "149.154.167.220",
    "149.154.167.40",
    "149.154.175.50",
    "149.154.175.100",
)

_session: requests.Session | None = None


def _force_ipv4_for_requests() -> None:
    """Docker bridge often has no IPv6 default route; urllib3 may try AAAA and fail."""
    family = lambda: socket.AF_INET
    try:
        import urllib3.util.connection as urllib3_connection

        urllib3_connection.allowed_gai_family = family
    except Exception:  # noqa: BLE001
        pass
    try:
        from urllib3.util import connection as urllib3_connection2

        urllib3_connection2.allowed_gai_family = family
    except Exception:  # noqa: BLE001
        pass


_force_ipv4_for_requests()


class TelegramProviderError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _telegram_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        proxy = (get_settings().telegram_proxy or "").strip()
        if proxy:
            _session.proxies.update({"http": proxy, "https": proxy})
    return _session


def _telegram_ipv4_candidates() -> list[str]:
    settings = get_settings()
    forced = (settings.telegram_api_ipv4 or "").strip()
    out: list[str] = []
    if forced:
        out.append(forced)
    for ip in TELEGRAM_API_IPV4_FALLBACKS:
        if ip not in out:
            out.append(ip)
    try:
        for _, _, _, _, addr in socket.getaddrinfo(
            TELEGRAM_API_HOST, 443, socket.AF_INET, socket.SOCK_STREAM
        ):
            ip = addr[0]
            if ip not in out:
                out.append(ip)
    except OSError:
        pass
    return out


@contextmanager
def _connect_via_ipv4(ip: str) -> Iterator[None]:
    import urllib3.util.connection as urllib3_connection

    orig = urllib3_connection.create_connection

    def patched(address, *args, **kwargs):
        host, port = address
        if host == TELEGRAM_API_HOST:
            address = (ip, port)
        return orig(address, *args, **kwargs)

    urllib3_connection.create_connection = patched
    try:
        yield
    finally:
        urllib3_connection.create_connection = orig


def _telegram_api_request(
    method: str,
    api_method: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> tuple[bool, dict[str, Any] | None, str]:
    """Call Bot API; returns (transport_ok, json_body, error_message)."""
    url = f"https://{TELEGRAM_API_HOST}/bot{token}/{api_method}"
    connect_timeout = min(10.0, max(4.0, timeout / 3))
    read_timeout = timeout
    last_err = "не удалось подключиться к Telegram"

    for ip in _telegram_ipv4_candidates():
        try:
            with _connect_via_ipv4(ip):
                response = _telegram_session().request(
                    method,
                    url,
                    json=payload,
                    timeout=(connect_timeout, read_timeout),
                )
            try:
                data = response.json()
            except ValueError:
                return False, None, f"Telegram вернул не JSON: HTTP {response.status_code}"
            return True, data, ""
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            continue

    return False, None, f"Сетевая ошибка: {last_err}"


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

    ok, data, err = _telegram_api_request("POST", "sendMessage", token=token, payload=payload, timeout=30)
    if not ok or data is None:
        return False, err, None

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

    ok, data, err = _telegram_api_request(
        "POST", "editMessageText", token=token, payload=payload, timeout=30
    )
    if not ok or data is None:
        return False, err
    if data.get("ok"):
        return True, "ok"
    desc = str(data.get("description") or "ошибка")
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

    ok, data, err = _telegram_api_request(
        "POST",
        "editMessageReplyMarkup",
        token=token,
        payload={
            "chat_id": normalized,
            "message_id": int(message_id) if str(message_id).isdigit() else message_id,
            "reply_markup": reply_markup,
        },
        timeout=30,
    )
    if not ok or data is None:
        return False, err
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

    ok, data, err = _telegram_api_request(
        "POST", "answerCallbackQuery", token=token, payload=payload, timeout=15
    )
    if not ok or data is None:
        return False, err
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

    ok, data, err = _telegram_api_request(
        "POST",
        "deleteMessage",
        token=token,
        payload={
            "chat_id": normalized,
            "message_id": int(message_id) if str(message_id).isdigit() else message_id,
        },
        timeout=15,
    )
    if not ok or data is None:
        return False, err
    if data.get("ok"):
        return True, "ok"
    return False, str(data.get("description") or "ошибка")


def get_me(bot_token: str | None = None) -> tuple[bool, str, dict]:
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN", {}

    ok, data, err = _telegram_api_request("GET", "getMe", token=token, timeout=15)
    if not ok or data is None:
        return False, err, {}
    if data.get("ok"):
        return True, "ok", data.get("result") or {}
    return False, str(data.get("description") or "error"), {}
