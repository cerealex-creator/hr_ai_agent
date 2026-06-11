"""Обработчики Telegram-клиентской зоны (статусы и комментарии)."""

import asyncio
import importlib
import logging

from aiogram import F, types
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from client_actions import (
    apply_and_save_client_action,
    find_candidate_by_telegram_message,
    find_candidate_by_tg_callback_id,
)
from telegram_notify import _esc

logger = logging.getLogger(__name__)

pending_comment = {}


def _reload_telegram_client():
    import telegram_client
    importlib.reload(telegram_client)
    return telegram_client


def _keyboard_from_dict(markup_dict):
    builder = InlineKeyboardBuilder()
    for row in markup_dict.get("inline_keyboard", []):
        buttons = [
            InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
            for btn in row
        ]
        builder.row(*buttons)
    return builder.as_markup()


async def _update_card_message(chat_id, message_id, text, keyboard_dict):
    """Обновляет текст и кнопки через Telegram Bot API (requests)."""
    tc = _reload_telegram_client()

    ok, err = await asyncio.to_thread(
        tc.edit_telegram_message,
        chat_id,
        message_id,
        text,
        keyboard_dict,
    )
    if ok:
        return True, None

    logger.warning("editMessageText failed: %s", err)

    ok_markup, err_markup = await asyncio.to_thread(
        tc.edit_message_keyboard,
        chat_id,
        message_id,
        keyboard_dict,
    )
    if ok_markup:
        ok_text, err_text = await asyncio.to_thread(
            tc.edit_telegram_message,
            chat_id,
            message_id,
            text,
            keyboard_dict,
        )
        if ok_text or (err_text and "not modified" in err_text.lower()):
            return True, None
        if ok_markup:
            return True, None

    return False, err or err_markup


async def _edit_card_locked(callback, candidate, vacancy):
    tc = _reload_telegram_client()
    kind = tc.get_post_kind(
        candidate, callback.message.chat.id, callback.message.message_id
    )
    text = tc.build_candidate_card_html(
        candidate,
        vacancy["title"],
        status_key=candidate.get("client_status", "wait"),
        locked=True,
        kind=kind,
    )
    keyboard = tc.build_locked_keyboard(candidate)
    ok, err = await _update_card_message(
        callback.message.chat.id,
        callback.message.message_id,
        text,
        keyboard,
    )
    if not ok:
        raise RuntimeError(err or "не удалось обновить сообщение")


async def _edit_card_change_mode(callback, candidate, vacancy):
    tc = _reload_telegram_client()
    kind = tc.get_post_kind(
        candidate, callback.message.chat.id, callback.message.message_id
    )
    text = tc.build_candidate_card_html(
        candidate,
        vacancy["title"],
        status_key=candidate.get("client_status", "wait"),
        locked=True,
        kind=kind,
    )
    text += "\n\n👇 <i>Выберите новый статус</i>"
    keyboard = tc.build_change_status_keyboard(candidate)
    ok, err = await _update_card_message(
        callback.message.chat.id,
        callback.message.message_id,
        text,
        keyboard,
    )
    if not ok:
        raise RuntimeError(err or "не удалось обновить сообщение")


async def _finalize_comment(
    bot,
    *,
    chat_id,
    candidate_id,
    comment_text,
    user_message=None,
    prompt_message_id=None,
    card_message_id=None,
):
    comment_at = user_message.date if user_message else None
    ok, _feedback, candidate, vacancy = apply_and_save_client_action(
        candidate_id,
        chat_id=chat_id,
        comment=comment_text,
        append_comment=True,
        actor="telegram",
        actor_note=(
            (user_message.from_user.username or str(user_message.from_user.id))
            if user_message else "telegram"
        ),
        comment_at=comment_at,
    )
    if not ok or not candidate:
        if user_message:
            await user_message.reply("⚠️ Не удалось сохранить комментарий")
        return False

    name = candidate.get("name", "Кандидат")
    safe_comment = _esc(comment_text)

    if prompt_message_id:
        try:
            await bot.delete_message(chat_id, prompt_message_id)
        except Exception as exc:
            logger.warning("Не удалось удалить подсказку комментария: %s", exc)

    if user_message:
        try:
            await user_message.delete()
        except Exception as exc:
            logger.warning(
                "Не удалось удалить сообщение пользователя (нужны права админа у бота): %s",
                exc,
            )

    await bot.send_message(
        chat_id,
        f"💬 <b>Комментарий к {_esc(name)} сохранён:</b>\n<i>{safe_comment}</i>",
        parse_mode="HTML",
    )

    if card_message_id and vacancy:
        try:
            tc = _reload_telegram_client()
            kind = tc.get_post_kind(candidate, chat_id, card_message_id)
            text = tc.build_candidate_card_html(
                candidate,
                vacancy["title"],
                status_key=candidate.get("client_status", "wait"),
                locked=True,
                kind=kind,
            )
            keyboard = tc.build_locked_keyboard(candidate)
            await _update_card_message(chat_id, card_message_id, text, keyboard)
        except Exception as exc:
            logger.warning("Не удалось обновить карточку после комментария: %s", exc)

    return True


def register_client_zone_handlers(dp):
    @dp.callback_query(F.data.startswith("cs:"))
    async def on_client_status(callback: types.CallbackQuery):
        tc = _reload_telegram_client()
        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await callback.answer("Некорректные данные", show_alert=True)
            return

        _, callback_id, status_key = parts
        if status_key not in tc.TELEGRAM_CHAT_STATUS_KEYS:
            await callback.answer("Этот статус недоступен в чате", show_alert=True)
            return

        user = callback.from_user
        actor_note = user.username or str(user.id)
        ok, msg, candidate, vacancy = apply_and_save_client_action(
            callback_id,
            chat_id=callback.message.chat.id,
            status_key=status_key,
            actor="telegram",
            actor_note=actor_note,
        )
        if not ok:
            await callback.answer(msg, show_alert=True)
            return

        from vacancy_store import get_status_meta
        meta = get_status_meta(candidate.get("client_status", "wait"))

        try:
            await _edit_card_locked(callback, candidate, vacancy)
            await callback.answer(meta["label"], show_alert=False)
        except Exception as exc:
            logger.exception("Ошибка обновления карточки после статуса: %s", exc)
            await callback.answer(
                f"Статус сохранён ({meta['label']}), но карточка не обновилась",
                show_alert=True,
            )

    @dp.callback_query(F.data.startswith("cchg:"))
    async def on_change_status_request(callback: types.CallbackQuery):
        callback_id = callback.data.split(":", 1)[1]
        vacancy, candidate, _ = find_candidate_by_tg_callback_id(callback_id)
        if not candidate or not vacancy:
            await callback.answer("Кандидат не найден", show_alert=True)
            return
        try:
            await _edit_card_change_mode(callback, candidate, vacancy)
            await callback.answer()
        except Exception as exc:
            logger.exception("Ошибка режима смены статуса: %s", exc)
            await callback.answer("Не удалось обновить сообщение", show_alert=True)

    @dp.callback_query(F.data.startswith("ccl:"))
    async def on_cancel_change_status(callback: types.CallbackQuery):
        callback_id = callback.data.split(":", 1)[1]
        vacancy, candidate, _ = find_candidate_by_tg_callback_id(callback_id)
        if not candidate or not vacancy:
            await callback.answer("Кандидат не найден", show_alert=True)
            return
        try:
            await _edit_card_locked(callback, candidate, vacancy)
            await callback.answer("Отменено")
        except Exception as exc:
            logger.exception("Ошибка отмены смены статуса: %s", exc)
            await callback.answer("Ошибка обновления", show_alert=True)

    @dp.callback_query(F.data.startswith("cc:"))
    async def on_client_comment_request(callback: types.CallbackQuery):
        callback_id = callback.data.split(":", 1)[1]
        prompt = await callback.message.reply(
            "💬 Напишите комментарий к кандидату следующим сообщением в чат."
        )
        pending_comment[callback.from_user.id] = {
            "candidate_id": callback_id,
            "chat_id": callback.message.chat.id,
            "card_message_id": callback.message.message_id,
            "prompt_message_id": prompt.message_id,
        }
        await callback.answer()

    @dp.message(F.reply_to_message)
    async def on_reply_comment(message: types.Message):
        if message.text and message.text.startswith("/"):
            return

        user_id = message.from_user.id
        reply = message.reply_to_message

        state = pending_comment.get(user_id)
        if state and state.get("prompt_message_id") == reply.message_id:
            pending_comment.pop(user_id, None)
            await _finalize_comment(
                message.bot,
                chat_id=message.chat.id,
                candidate_id=state["candidate_id"],
                comment_text=message.text or "",
                user_message=message,
                prompt_message_id=state.get("prompt_message_id"),
                card_message_id=state.get("card_message_id"),
            )
            return

        vacancy, candidate, _data = find_candidate_by_telegram_message(
            message.chat.id,
            reply.message_id,
        )
        if not candidate:
            return

        callback_id = candidate.get("tg_callback_id") or candidate.get("id")
        await _finalize_comment(
            message.bot,
            chat_id=message.chat.id,
            candidate_id=callback_id,
            comment_text=message.text or "",
            user_message=message,
            card_message_id=reply.message_id,
        )


async def try_handle_pending_comment(message: types.Message) -> bool:
    user_id = message.from_user.id
    state = pending_comment.pop(user_id, None)
    if not state:
        return False

    await _finalize_comment(
        message.bot,
        chat_id=state.get("chat_id", message.chat.id),
        candidate_id=state["candidate_id"],
        comment_text=message.text or "",
        user_message=message,
        prompt_message_id=state.get("prompt_message_id"),
        card_message_id=state.get("card_message_id"),
    )
    return True
