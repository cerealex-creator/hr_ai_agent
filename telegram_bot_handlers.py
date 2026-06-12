"""Обработчики Telegram-клиентской зоны (статусы и комментарии)."""

import importlib
import logging
from datetime import datetime

from aiogram import F, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from client_actions import (
    HR_MEETING_CONFIRM_USERNAME,
    apply_and_save_cancel_meeting,
    apply_and_save_client_action,
    apply_and_save_confirm_hr_meeting,
    build_meeting_confirmation_html,
    can_confirm_hr_meeting,
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


async def _update_card_message(
    text,
    keyboard_dict,
    *,
    callback=None,
    bot=None,
    chat_id=None,
    message_id=None,
):
    """Обновляет текст и кнопки карточки через aiogram."""
    markup = _keyboard_from_dict(keyboard_dict)

    async def _edit_message(msg, *, edit_bot=None, edit_chat_id=None, edit_message_id=None):
        try:
            if msg is not None:
                await msg.edit_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup,
                    disable_web_page_preview=True,
                )
            else:
                await edit_bot.edit_message_text(
                    chat_id=edit_chat_id,
                    message_id=edit_message_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup,
                    disable_web_page_preview=True,
                )
            return True, None
        except TelegramBadRequest as exc:
            err = str(exc)
            if "message is not modified" in err.lower():
                return True, None
            logger.warning("edit_text failed: %s", err)
            try:
                if msg is not None:
                    await msg.edit_reply_markup(reply_markup=markup)
                    await msg.edit_text(
                        text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                else:
                    await edit_bot.edit_message_reply_markup(
                        chat_id=edit_chat_id,
                        message_id=edit_message_id,
                        reply_markup=markup,
                    )
                    await edit_bot.edit_message_text(
                        chat_id=edit_chat_id,
                        message_id=edit_message_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                return True, None
            except TelegramBadRequest as exc2:
                if "message is not modified" in str(exc2).lower():
                    return True, None
                logger.warning("edit_reply_markup failed: %s", exc2)
                return False, str(exc2)

    if callback and callback.message:
        return await _edit_message(callback.message)
    if bot is not None and chat_id is not None and message_id is not None:
        return await _edit_message(
            None,
            edit_bot=bot,
            edit_chat_id=chat_id,
            edit_message_id=message_id,
        )
    return False, "сообщение для редактирования не найдено"


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
    ok, err = await _update_card_message(text, keyboard, callback=callback)
    if not ok:
        raise RuntimeError(err or "не удалось обновить сообщение")


async def _edit_card_interview_dates(callback, candidate, vacancy):
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
        interview_prompt="📅 <i>Выберите дату встречи</i>",
    )
    keyboard = tc.build_interview_date_keyboard(candidate)
    ok, err = await _update_card_message(text, keyboard, callback=callback)
    if not ok:
        raise RuntimeError(err or "не удалось обновить сообщение")


async def _edit_card_interview_times(callback, candidate, vacancy, date_token):
    tc = _reload_telegram_client()
    kind = tc.get_post_kind(
        candidate, callback.message.chat.id, callback.message.message_id
    )
    date_label = tc.parse_interview_date_token(date_token)
    try:
        display_date = datetime.strptime(date_label, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        display_date = date_label
    text = tc.build_candidate_card_html(
        candidate,
        vacancy["title"],
        status_key=candidate.get("client_status", "wait"),
        locked=True,
        kind=kind,
        interview_prompt=f"🕐 <i>Выберите время на {display_date}</i>",
    )
    keyboard = tc.build_interview_time_keyboard(candidate, date_token)
    ok, err = await _update_card_message(text, keyboard, callback=callback)
    if not ok:
        raise RuntimeError(err or "не удалось обновить сообщение")


async def _edit_card_interview_format(callback, candidate, vacancy, date_token, time_token):
    tc = _reload_telegram_client()
    kind = tc.get_post_kind(
        candidate, callback.message.chat.id, callback.message.message_id
    )
    date_str = tc.parse_interview_date_token(date_token)
    time_str = tc.parse_interview_time_token(time_token)
    when = tc.format_interview_display(date_str, time_str)
    text = tc.build_candidate_card_html(
        candidate,
        vacancy["title"],
        status_key=candidate.get("client_status", "wait"),
        locked=True,
        kind=kind,
        interview_prompt=f"📍 <i>Формат встречи {when}</i>",
    )
    keyboard = tc.build_interview_format_keyboard(candidate, date_token, time_token)
    ok, err = await _update_card_message(text, keyboard, callback=callback)
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
    ok, err = await _update_card_message(text, keyboard, callback=callback)
    if not ok:
        raise RuntimeError(err or "не удалось обновить сообщение")


async def _refresh_candidate_telegram_cards(bot, candidate, vacancy):
    tc = _reload_telegram_client()
    keyboard = tc.build_locked_keyboard(candidate)
    for post in candidate.get("telegram_posts", []):
        kind = post.get("kind", "primary")
        card_text = tc.build_candidate_card_html(
            candidate,
            vacancy["title"],
            status_key=candidate.get("client_status", "wait"),
            locked=True,
            kind=kind,
        )
        try:
            await bot.edit_message_text(
                chat_id=post.get("chat_id"),
                message_id=post.get("message_id"),
                text=card_text,
                parse_mode=ParseMode.HTML,
                reply_markup=_keyboard_from_dict(keyboard),
                disable_web_page_preview=True,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.warning("Не удалось обновить карточку %s: %s", post.get("message_id"), exc)


async def _send_interview_date_fallback(callback, candidate, vacancy, status_label):
    tc = _reload_telegram_client()
    name = _esc(candidate.get("name", "кандидата"))
    keyboard = _keyboard_from_dict(tc.build_interview_date_keyboard(candidate))
    await callback.message.reply(
        f"✅ Статус «{status_label}» сохранён для <b>{name}</b>.\n"
        f"📅 <i>Выберите дату встречи:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


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
            await _update_card_message(
                text,
                keyboard,
                bot=bot,
                chat_id=chat_id,
                message_id=card_message_id,
            )
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
        await callback.answer(meta["label"], show_alert=False)

        try:
            tc = _reload_telegram_client()
            if status_key == "ready" and tc.needs_interview_schedule(candidate):
                await _edit_card_interview_dates(callback, candidate, vacancy)
            else:
                await _edit_card_locked(callback, candidate, vacancy)
        except Exception as exc:
            logger.exception("Ошибка обновления карточки после статуса: %s", exc)
            try:
                if status_key == "ready":
                    await _send_interview_date_fallback(
                        callback, candidate, vacancy, meta["label"]
                    )
                else:
                    await callback.message.reply(
                        f"✅ Статус «{meta['label']}» сохранён, но карточка не обновилась.",
                        parse_mode=ParseMode.HTML,
                    )
            except Exception as fallback_exc:
                logger.exception("Ошибка резервного сообщения: %s", fallback_exc)

    @dp.callback_query(F.data.startswith("ivi:"))
    async def on_interview_start(callback: types.CallbackQuery):
        callback_id = callback.data.split(":", 1)[1]
        vacancy, candidate, _ = find_candidate_by_tg_callback_id(callback_id)
        if not candidate or not vacancy:
            await callback.answer("Кандидат не найден", show_alert=True)
            return
        await callback.answer()
        try:
            await _edit_card_interview_dates(callback, candidate, vacancy)
        except Exception as exc:
            logger.exception("Ошибка выбора даты собеседования: %s", exc)
            await callback.message.reply(
                "⚠️ Не удалось обновить карточку. Выберите дату в сообщении ниже.",
                reply_markup=_keyboard_from_dict(
                    _reload_telegram_client().build_interview_date_keyboard(candidate)
                ),
            )

    @dp.callback_query(F.data.startswith("ivd:"))
    async def on_interview_date(callback: types.CallbackQuery):
        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer("Некорректные данные", show_alert=True)
            return
        _, callback_id, date_token = parts
        vacancy, candidate, _ = find_candidate_by_tg_callback_id(callback_id)
        if not candidate or not vacancy:
            await callback.answer("Кандидат не найден", show_alert=True)
            return
        await callback.answer()
        try:
            await _edit_card_interview_times(callback, candidate, vacancy, date_token)
        except Exception as exc:
            logger.exception("Ошибка выбора времени собеседования: %s", exc)
            await callback.message.reply("⚠️ Не удалось показать время. Попробуйте ещё раз.")

    @dp.callback_query(F.data.startswith("ivt:"))
    async def on_interview_time(callback: types.CallbackQuery):
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer("Некорректные данные", show_alert=True)
            return
        _, callback_id, date_token, time_token = parts
        vacancy, candidate, _ = find_candidate_by_tg_callback_id(callback_id)
        if not candidate or not vacancy:
            await callback.answer("Кандидат не найден", show_alert=True)
            return
        await callback.answer()
        try:
            await _edit_card_interview_format(
                callback, candidate, vacancy, date_token, time_token
            )
        except Exception as exc:
            logger.exception("Ошибка выбора формата собеседования: %s", exc)
            await callback.message.reply("⚠️ Не удалось показать формат встречи. Попробуйте ещё раз.")

    @dp.callback_query(F.data.startswith("ivf:"))
    async def on_interview_save(callback: types.CallbackQuery):
        parts = callback.data.split(":")
        if len(parts) != 5:
            await callback.answer("Некорректные данные", show_alert=True)
            return
        _, callback_id, date_token, time_token, fmt_flag = parts
        tc = _reload_telegram_client()
        try:
            date_str = tc.parse_interview_date_token(date_token)
            time_str = tc.parse_interview_time_token(time_token)
        except ValueError:
            await callback.answer("Некорректная дата или время", show_alert=True)
            return

        remote, office = tc.interview_format_flags(fmt_flag)
        user = callback.from_user
        ok, msg, candidate, vacancy = apply_and_save_client_action(
            callback_id,
            chat_id=callback.message.chat.id,
            office_interview_date=date_str,
            office_interview_time=time_str,
            remote_interview=remote,
            office_interview=office,
            actor="telegram",
            actor_note=user.username or str(user.id),
        )
        if not ok:
            await callback.answer(msg, show_alert=True)
            return

        await callback.answer("Встреча сохранена", show_alert=False)
        try:
            await _edit_card_locked(callback, candidate, vacancy)
        except Exception as exc:
            logger.exception("Ошибка сохранения собеседования: %s", exc)
            await callback.message.reply(
                "✅ Встреча сохранена, но карточка не обновилась.",
                parse_mode=ParseMode.HTML,
            )

    @dp.callback_query(F.data.startswith("mcf:"))
    async def on_meeting_hr_confirm(callback: types.CallbackQuery):
        if not can_confirm_hr_meeting(callback.from_user):
            await callback.answer(
                f"Подтверждение доступно только @{HR_MEETING_CONFIRM_USERNAME}",
                show_alert=True,
            )
            return

        callback_id = callback.data.split(":", 1)[1]
        username = callback.from_user.username or HR_MEETING_CONFIRM_USERNAME
        ok, msg, candidate, vacancy = apply_and_save_confirm_hr_meeting(
            callback_id,
            confirmer_username=username,
        )
        if not ok:
            await callback.answer(msg, show_alert=True)
            return

        await callback.answer("Встреча подтверждена", show_alert=False)
        try:
            await callback.message.edit_text(
                build_meeting_confirmation_html(
                    candidate,
                    confirmed=True,
                    confirmer_username=username,
                ),
                parse_mode=ParseMode.HTML,
            )
        except TelegramBadRequest as exc:
            logger.warning("Не удалось обновить сообщение подтверждения: %s", exc)

        if vacancy and candidate:
            try:
                await _refresh_candidate_telegram_cards(callback.bot, candidate, vacancy)
            except Exception as exc:
                logger.warning("Не удалось обновить карточки после подтверждения: %s", exc)

    @dp.callback_query(F.data.startswith("ivx:"))
    async def on_interview_cancel_meeting(callback: types.CallbackQuery):
        callback_id = callback.data.split(":", 1)[1]
        user = callback.from_user
        ok, msg, candidate, vacancy = apply_and_save_cancel_meeting(
            callback_id,
            chat_id=callback.message.chat.id,
            actor="telegram",
            actor_note=user.username or str(user.id),
        )
        if not ok:
            await callback.answer(msg, show_alert=True)
            return
        await callback.answer("Встреча отменена", show_alert=False)
        try:
            await _edit_card_locked(callback, candidate, vacancy)
        except Exception as exc:
            logger.exception("Ошибка обновления карточки после отмены встречи: %s", exc)
            await callback.message.reply(
                "✅ Встреча отменена, но карточка не обновилась.",
                parse_mode=ParseMode.HTML,
            )

    @dp.callback_query(F.data.startswith("ivc:"))
    async def on_interview_cancel(callback: types.CallbackQuery):
        callback_id = callback.data.split(":", 1)[1]
        vacancy, candidate, _ = find_candidate_by_tg_callback_id(callback_id)
        if not candidate or not vacancy:
            await callback.answer("Кандидат не найден", show_alert=True)
            return
        await callback.answer("Отменено")
        try:
            await _edit_card_locked(callback, candidate, vacancy)
        except Exception as exc:
            logger.exception("Ошибка отмены назначения собеседования: %s", exc)

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
