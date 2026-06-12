"""Сессия навигации по кандидатам — учёт и удаление технических сообщений бота."""

import asyncio
import logging

logger = logging.getLogger(__name__)

POINTER_TTL_SEC = 12
PENDING_TTL_SEC = 60

_sessions = {}
_pending_ephemeral = {}


def _key(chat_id, user_id):
    return (int(chat_id), int(user_id))


def _get(chat_id, user_id):
    key = _key(chat_id, user_id)
    if key not in _sessions:
        _sessions[key] = {"messages": set(), "pointers": set(), "command_id": None}
    return _sessions[key]


def set_nav_command(chat_id, user_id, command_id):
    """Сообщение-команда /candidates — удаляется вместе с навигатором."""
    if command_id:
        _get(chat_id, user_id)["command_id"] = int(command_id)


def track_nav_message(chat_id, user_id, message_id):
    if message_id:
        _get(chat_id, user_id)["messages"].add(int(message_id))


def track_pointer(chat_id, user_id, message_id):
    if message_id:
        _get(chat_id, user_id)["pointers"].add(int(message_id))


async def _safe_delete(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id, int(message_id))
        return True
    except Exception as exc:
        logger.debug("Не удалось удалить сообщение %s: %s", message_id, exc)
        return False


async def schedule_pointer_cleanup(bot, chat_id, user_id, message_id, delay=None):
    """Автоудаление указателя «к карточке» через несколько секунд."""
    delay = POINTER_TTL_SEC if delay is None else delay
    await asyncio.sleep(delay)
    sess = _sessions.get(_key(chat_id, user_id))
    if not sess or int(message_id) not in sess["pointers"]:
        return
    if await _safe_delete(bot, chat_id, message_id):
        sess["pointers"].discard(int(message_id))


def pending_keyboard_with_close(markup_dict=None):
    rows = []
    if markup_dict:
        rows.extend(markup_dict.get("inline_keyboard", []))
    rows.append([{"text": "✖️ Закрыть", "callback_data": "pd:close"}])
    return {"inline_keyboard": rows}


def begin_pending_ephemeral(chat_id, user_id, *, command_id=None):
    """Новая сессия /pending: команда пользователя + ответ бота."""
    _pending_ephemeral[_key(chat_id, user_id)] = {
        "command_id": int(command_id) if command_id else None,
        "response_id": None,
        "version": 0,
    }


def set_pending_response(chat_id, user_id, response_id):
    sess = _pending_ephemeral.get(_key(chat_id, user_id))
    if sess is not None and response_id:
        sess["response_id"] = int(response_id)


async def cleanup_pending_ephemeral(bot, chat_id, user_id):
    """Удаляет ответ бота и исходную команду (/pending)."""
    sess = _pending_ephemeral.pop(_key(chat_id, user_id), None)
    if not sess:
        return 0
    deleted = 0
    for field in ("response_id", "command_id"):
        mid = sess.get(field)
        if mid and await _safe_delete(bot, chat_id, mid):
            deleted += 1
    return deleted


async def arm_pending_ephemeral_delete(bot, chat_id, user_id, delay=None):
    """Автоудаление через delay: команда + ответ одним пакетом."""
    delay = PENDING_TTL_SEC if delay is None else delay
    key = _key(chat_id, user_id)
    sess = _pending_ephemeral.get(key)
    if not sess:
        return
    sess["version"] = sess.get("version", 0) + 1
    version = sess["version"]

    async def _job():
        await asyncio.sleep(delay)
        current = _pending_ephemeral.get(key)
        if not current or current.get("version") != version:
            return
        await cleanup_pending_ephemeral(bot, chat_id, user_id)

    asyncio.create_task(_job())


async def cleanup_session(bot, chat_id, user_id, *, include_current=None):
    """Удаляет навигатор, выбор вакансии и все указатели сессии."""
    key = _key(chat_id, user_id)
    sess = _sessions.pop(key, None)
    ids = set()
    if sess:
        ids |= sess["messages"]
        ids |= sess["pointers"]
        if sess.get("command_id"):
            ids.add(sess["command_id"])
    if include_current:
        ids.add(int(include_current))

    deleted = 0
    for mid in ids:
        if await _safe_delete(bot, chat_id, mid):
            deleted += 1
    return deleted
