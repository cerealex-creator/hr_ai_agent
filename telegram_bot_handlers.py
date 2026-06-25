"""Обработчики Telegram-клиентской зоны (статусы и комментарии)."""

import asyncio
import importlib
import logging
from datetime import datetime

from aiogram import F, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiogram.filters import Command

from client_actions import (
    HR_MEETING_CONFIRM_USERNAME,
    apply_and_save_cancel_meeting,
    apply_and_save_client_action,
    apply_and_save_confirm_hr_meeting,
    build_meeting_confirmation_html,
    can_confirm_hr_meeting,
    ensure_client_zone_for_telegram,
    find_candidate_by_telegram_message,
    find_candidate_by_tg_callback_id,
    find_vacancies_by_chat_id,
    find_vacancy_by_id,
    vacancy_chat_matches,
)
from interview_attendance import (
    ATTENDANCE_CANCELLED_CANDIDATE,
    ATTENDANCE_CANCELLED_CLIENT,
    ATTENDANCE_CONFIRMED,
    apply_and_save_interview_attendance,
    build_morning_attendance_message,
)
from telegram_notify import _esc
from telegram_workflow import (
    apply_status_change,
    get_pending_action,
    status_requires_comment,
    store_pending_comment,
    store_pending_status,
    telegram_actor_label,
    try_handle_pending_action,
)
from vacancy_store import get_status_meta

logger = logging.getLogger(__name__)


def _reload_telegram_client():
    import telegram_client
    importlib.reload(telegram_client)
    return telegram_client


def _keyboard_from_dict(markup_dict):
    builder = InlineKeyboardBuilder()
    for row in markup_dict.get("inline_keyboard", []):
        buttons = []
        for btn in row:
            if btn.get("url"):
                buttons.append(
                    InlineKeyboardButton(text=btn["text"], url=btn["url"])
                )
            else:
                buttons.append(
                    InlineKeyboardButton(
                        text=btn["text"],
                        callback_data=btn["callback_data"],
                    )
                )
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
        vacancy=vacancy,
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
        vacancy=vacancy,
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
        vacancy=vacancy,
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
        vacancy=vacancy,
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
        vacancy=vacancy,
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
            vacancy=vacancy,
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
        actor_note=telegram_actor_label(user_message.from_user) if user_message else "telegram",
        comment_at=comment_at,
    )
    if not ok or not candidate:
        if user_message:
            await user_message.reply("⚠️ Не удалось сохранить комментарий")
        return False

    if vacancy and card_message_id:
        from telegram_client import anchor_candidate_card_message

        anchor_candidate_card_message(
            vacancy, candidate, chat_id, int(card_message_id)
        )

    name = candidate.get("name", "Кандидат")

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
        f"💬 <b>Комментарий к {_esc(name)} сохранён.</b>",
        parse_mode="HTML",
    )

    if card_message_id and vacancy:
        try:
            tc = _reload_telegram_client()
            kind = tc.get_post_kind(candidate, chat_id, card_message_id)
            text = tc.build_candidate_card_html(
                candidate,
                vacancy["title"],
                vacancy=vacancy,
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


async def _handle_interview_attendance_callback(callback, status):
    if callback.message.chat.type != "private":
        await callback.answer(
            "Подтверждение явки доступно только в личном чате с ботом",
            show_alert=True,
        )
        return
    if not can_confirm_hr_meeting(callback.from_user):
        await callback.answer(
            f"Доступно только @{HR_MEETING_CONFIRM_USERNAME}",
            show_alert=True,
        )
        return

    callback_id = callback.data.split(":", 1)[1]
    ok, msg, candidate, vacancy, group_job = apply_and_save_interview_attendance(
        callback_id,
        status,
    )
    if not ok:
        await callback.answer(msg, show_alert=True)
        return

    await callback.answer(msg, show_alert=False)
    if candidate and vacancy:
        try:
            await callback.message.edit_text(
                build_morning_attendance_message(
                    candidate,
                    vacancy.get("title", ""),
                    resolved=True,
                    status=status,
                ),
                parse_mode=ParseMode.HTML,
            )
        except TelegramBadRequest as exc:
            logger.warning("Не удалось обновить утреннее напоминание: %s", exc)

    if group_job:
        # Подтверждение и отмена заказчиком в общий чат не уходят.
        try:
            await callback.bot.send_message(
                group_job["chat_id"],
                group_job["text"],
                parse_mode=ParseMode.HTML,
                reply_to_message_id=group_job.get("reply_to_message_id"),
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.warning("Не удалось отправить отмену встречи в чат: %s", exc)


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

        vacancy, candidate, _ = find_candidate_by_tg_callback_id(callback_id)
        if not candidate or not vacancy:
            await callback.answer("Кандидат не найден", show_alert=True)
            return
        if not vacancy_chat_matches(vacancy, callback.message.chat.id):
            await callback.answer("Этот чат не привязан к вакансии кандидата", show_alert=True)
            return
        if not ensure_client_zone_for_telegram(candidate, callback.message.chat.id):
            await callback.answer("Кандидат ещё не на этапе оценки заказчика", show_alert=True)
            return
        if candidate.get("client_status") == status_key:
            await callback.answer("Статус уже выбран", show_alert=True)
            return

        from telegram_client import anchor_candidate_card_message

        anchor_candidate_card_message(
            vacancy,
            candidate,
            callback.message.chat.id,
            callback.message.message_id,
        )

        user = callback.from_user
        actor_note = telegram_actor_label(user)

        if status_requires_comment(status_key):
            meta = get_status_meta(status_key)
            prompt = await callback.message.reply(
                f"💬 Напишите комментарий к статусу «{meta['label']}» "
                f"ответом на это сообщение."
            )
            store_pending_status(
                user.id,
                candidate_id=callback_id,
                status_key=status_key,
                chat_id=callback.message.chat.id,
                card_message_id=callback.message.message_id,
                prompt_message_id=prompt.message_id,
                actor_note=actor_note,
            )
            await callback.answer()
            return

        await apply_status_change(
            callback.bot,
            candidate_id=callback_id,
            chat_id=callback.message.chat.id,
            status_key=status_key,
            actor_note=actor_note,
            card_message_id=callback.message.message_id,
            callback=callback,
        )

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
            actor_note=telegram_actor_label(user),
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
        confirmer_label = telegram_actor_label(callback.from_user)
        ok, msg, candidate, vacancy = apply_and_save_confirm_hr_meeting(
            callback_id,
            confirmer_label=confirmer_label,
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
                    confirmer_label=confirmer_label,
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

    @dp.callback_query(F.data.startswith("iac:"))
    async def on_attendance_confirmed(callback: types.CallbackQuery):
        await _handle_interview_attendance_callback(callback, ATTENDANCE_CONFIRMED)

    @dp.callback_query(F.data.startswith("iak:"))
    async def on_attendance_cancelled_candidate(callback: types.CallbackQuery):
        await _handle_interview_attendance_callback(
            callback, ATTENDANCE_CANCELLED_CANDIDATE
        )

    @dp.callback_query(F.data.startswith("icl:"))
    async def on_attendance_cancelled_client(callback: types.CallbackQuery):
        await _handle_interview_attendance_callback(
            callback, ATTENDANCE_CANCELLED_CLIENT
        )

    @dp.callback_query(F.data.startswith("ivx:"))
    async def on_interview_cancel_meeting(callback: types.CallbackQuery):
        callback_id = callback.data.split(":", 1)[1]
        user = callback.from_user
        ok, msg, candidate, vacancy = apply_and_save_cancel_meeting(
            callback_id,
            chat_id=callback.message.chat.id,
            actor="telegram",
            actor_note=telegram_actor_label(user),
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
        store_pending_comment(
            callback.from_user.id,
            candidate_id=callback_id,
            chat_id=callback.message.chat.id,
            card_message_id=callback.message.message_id,
            prompt_message_id=prompt.message_id,
        )
        await callback.answer()

    @dp.message(F.reply_to_message)
    async def on_reply_comment(message: types.Message):
        if message.text and message.text.startswith("/"):
            return

        user_id = message.from_user.id
        reply = message.reply_to_message

        state = get_pending_action(user_id)
        if state and state.get("prompt_message_id") == reply.message_id:
            from telegram_workflow import pop_pending_action

            pop_pending_action(user_id)
            if state.get("action") == "status":
                text = (message.text or "").strip()
                if not text:
                    await message.reply("⚠️ Комментарий обязателен для этого статуса.")
                    store_pending_status(
                        user_id,
                        candidate_id=state["candidate_id"],
                        status_key=state["status_key"],
                        chat_id=state["chat_id"],
                        card_message_id=state.get("card_message_id"),
                        prompt_message_id=state.get("prompt_message_id"),
                        actor_note=state.get("actor_note", telegram_actor_label(message.from_user)),
                    )
                    return
                await apply_status_change(
                    message.bot,
                    candidate_id=state["candidate_id"],
                    chat_id=state.get("chat_id", message.chat.id),
                    status_key=state["status_key"],
                    actor_note=state.get("actor_note", telegram_actor_label(message.from_user)),
                    comment_text=text,
                    card_message_id=state.get("card_message_id"),
                    user_message=message,
                    prompt_message_id=state.get("prompt_message_id"),
                )
            else:
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
    return await try_handle_pending_action(message)


def _nav_actor(target):
    if isinstance(target, types.CallbackQuery):
        return target.bot, target.message.chat.id, target.from_user.id
    return target.bot, target.chat.id, target.from_user.id


async def _send_vacancy_picker(target, vacancies, *, title="📋 Выберите вакансию"):
    from telegram_candidate_nav import format_vacancy_nav_label, vacancy_picker_keyboard
    from telegram_nav_session import track_nav_message

    bot, chat_id, user_id = _nav_actor(target)
    lines = [f"<b>{title}</b>", ""]
    for vac in vacancies:
        lines.append(f"• {format_vacancy_nav_label(vac)}")
    text = "\n".join(lines)
    markup = _keyboard_from_dict(vacancy_picker_keyboard(vacancies))

    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            track_nav_message(chat_id, user_id, target.message.message_id)
        except TelegramBadRequest:
            sent = await target.message.answer(
                text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
            track_nav_message(chat_id, user_id, sent.message_id)
        await target.answer()
    else:
        sent = await bot.send_message(
            chat_id, text, parse_mode=ParseMode.HTML, reply_markup=markup
        )
        track_nav_message(chat_id, user_id, sent.message_id)


async def _send_candidate_navigator(target, vacancy, index=0):
    from telegram_candidate_nav import (
        collect_vacancy_navigator_items,
        format_navigator_html,
        format_vacancy_nav_label,
        build_navigator_keyboard,
    )
    from telegram_nav_session import track_nav_message

    bot, chat_id, user_id = _nav_actor(target)
    items = collect_vacancy_navigator_items(vacancy, runtime_chat_id=chat_id)
    if not items:
        text = (
            f"Нет карточек кандидатов в чате для "
            f"«{_esc(format_vacancy_nav_label(vacancy))}».\n"
            f"Отправьте кандидатов из приложения HR."
        )
        if isinstance(target, types.CallbackQuery):
            await target.answer("Нет карточек в чате", show_alert=True)
            await target.message.answer(text, parse_mode=ParseMode.HTML)
        else:
            await target.answer(text, parse_mode=ParseMode.HTML)
        return

    total = len(items)
    index = index % total
    item = items[index]
    text = format_navigator_html(vacancy, item, index, total)
    markup = _keyboard_from_dict(build_navigator_keyboard(vacancy, index, total))

    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(
                text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
            track_nav_message(chat_id, user_id, target.message.message_id)
        except TelegramBadRequest:
            sent = await target.message.answer(
                text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
            track_nav_message(chat_id, user_id, sent.message_id)
        await target.answer()
    else:
        sent = await bot.send_message(
            chat_id, text, parse_mode=ParseMode.HTML, reply_markup=markup
        )
        track_nav_message(chat_id, user_id, sent.message_id)


def register_group_chat_handlers(dp):
    """Команды для групповых чатов: /pending, /help."""

    @dp.message(Command("candidates"), F.chat.type.in_({"group", "supergroup"}))
    async def cmd_candidates(message: types.Message):
        from telegram_candidate_nav import find_vacancies_for_nav
        from telegram_notify import normalize_chat_id
        from vacancy_store import load_vacancies_list

        args = (message.text or "").split(maxsplit=1)
        query = args[1].strip() if len(args) > 1 else None
        vacancies = find_vacancies_for_nav(message.chat.id, query)
        logger.info(
            "/candidates chat_id=%s norm=%s db_vacancies=%s found=%s query=%r",
            message.chat.id,
            normalize_chat_id(message.chat.id),
            len(load_vacancies_list()),
            len(vacancies),
            query,
        )

        if not vacancies:
            if query:
                await message.answer(
                    f"Вакансия «{_esc(query)}» не найдена в этом чате.\n"
                    f"Пример: <code>/candidates Кладовщик</code>",
                    parse_mode=ParseMode.HTML,
                )
            else:
                from vacancy_store import load_chats

                known_lines = []
                for chat in load_chats():
                    cid = chat.get("id")
                    cnt = len(find_vacancies_by_chat_id(cid, only_active=True))
                    if cnt:
                        known_lines.append(
                            f"• {_esc(chat.get('name', 'Чат'))}: {cnt} вак. "
                            f"(<code>{normalize_chat_id(cid)}</code>)"
                        )
                known_block = (
                    "\n".join(known_lines)
                    if known_lines
                    else "• нет привязанных чатов с активными вакансиями"
                )
                await message.answer(
                    "В этом чате нет активных вакансий.\n\n"
                    f"ID этого чата: <code>{message.chat.id}</code>\n\n"
                    f"В базе HR активные вакансии привязаны к:\n{known_block}\n\n"
                    "Если вы в нужной группе — обновите Chat ID в "
                    "HR → Настройки → Telegram (или создайте вакансию заново с этим чатом).",
                    parse_mode=ParseMode.HTML,
                )
            return

        from telegram_nav_session import cleanup_session, set_nav_command

        await cleanup_session(message.bot, message.chat.id, message.from_user.id)
        set_nav_command(message.chat.id, message.from_user.id, message.message_id)

        if len(vacancies) == 1:
            await _send_candidate_navigator(message, vacancies[0], index=0)
            return

        await _send_vacancy_picker(
            message,
            vacancies,
            title="📋 Кандидаты — выберите вакансию",
        )

    @dp.callback_query(F.data == "cf:0")
    async def on_nav_finish(callback: types.CallbackQuery):
        from telegram_nav_session import cleanup_session

        await cleanup_session(
            callback.bot,
            callback.message.chat.id,
            callback.from_user.id,
            include_current=callback.message.message_id,
        )
        await callback.answer("Навигация завершена")

    @dp.callback_query(F.data.startswith("cg:"))
    async def on_goto_candidate_card(callback: types.CallbackQuery):
        from telegram_candidate_nav import (
            collect_vacancy_navigator_items,
            send_candidate_card_pointer,
        )

        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer("Некорректные данные", show_alert=True)
            return
        try:
            vacancy_id = int(parts[1])
            index = int(parts[2])
        except ValueError:
            await callback.answer("Некорректные данные", show_alert=True)
            return

        vacancy = find_vacancy_by_id(vacancy_id)
        if not vacancy or not vacancy_chat_matches(vacancy, callback.message.chat.id):
            await callback.answer("Вакансия не найдена", show_alert=True)
            return

        runtime_chat_id = callback.message.chat.id
        items = collect_vacancy_navigator_items(
            vacancy, runtime_chat_id=runtime_chat_id
        )
        if not items:
            await callback.answer("Нет карточек в чате", show_alert=True)
            return

        item = items[index % len(items)]
        ok, feedback = await send_candidate_card_pointer(
            callback.bot,
            runtime_chat_id,
            callback.from_user.id,
            item,
            vacancy=vacancy,
        )
        if ok:
            await callback.answer(feedback)
        else:
            logger.warning(
                "Переход к карточке не удался vacancy=%s index=%s: %s",
                vacancy_id,
                index,
                feedback,
            )
            await callback.answer(feedback, show_alert=True)

    @dp.callback_query(F.data.startswith("cv:"))
    async def on_nav_vacancy_pick(callback: types.CallbackQuery):
        try:
            vacancy_id = int(callback.data.split(":", 1)[1])
        except ValueError:
            await callback.answer("Некорректные данные", show_alert=True)
            return
        vacancy = find_vacancy_by_id(vacancy_id)
        if not vacancy or not vacancy_chat_matches(vacancy, callback.message.chat.id):
            await callback.answer("Вакансия не найдена", show_alert=True)
            return
        await _send_candidate_navigator(callback, vacancy, index=0)

    @dp.callback_query(F.data.startswith("cn:"))
    async def on_candidate_nav(callback: types.CallbackQuery):
        parts = callback.data.split(":")
        if len(parts) < 3:
            await callback.answer("Некорректные данные", show_alert=True)
            return

        token = parts[1]
        if token == "pick":
            from telegram_candidate_nav import find_vacancies_for_nav

            vacancies = find_vacancies_for_nav(callback.message.chat.id)
            if not vacancies:
                await callback.answer("Нет активных вакансий", show_alert=True)
                return
            if len(vacancies) == 1:
                await _send_candidate_navigator(callback, vacancies[0], index=0)
                return
            await _send_vacancy_picker(
                callback,
                vacancies,
                title="📋 Кандидаты — выберите вакансию",
            )
            return

        if len(parts) >= 3 and parts[2] == "noop":
            await callback.answer()
            return

        try:
            vacancy_id = int(token)
            index = int(parts[2])
        except ValueError:
            await callback.answer("Некорректные данные", show_alert=True)
            return

        vacancy = find_vacancy_by_id(vacancy_id)
        if not vacancy or not vacancy_chat_matches(vacancy, callback.message.chat.id):
            await callback.answer("Вакансия не найдена", show_alert=True)
            return
        await _send_candidate_navigator(callback, vacancy, index=index)

    async def _send_pending_ephemeral(chat_id, bot, text, *, extra_keyboard=None):
        from telegram_nav_session import pending_keyboard_with_close

        markup = _keyboard_from_dict(pending_keyboard_with_close(extra_keyboard))
        return await bot.send_message(
            chat_id,
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=markup,
        )

    async def _show_pending_on_message(message, text, *, extra_keyboard=None):
        from telegram_nav_session import (
            arm_pending_ephemeral_delete,
            begin_pending_ephemeral,
            cleanup_pending_ephemeral,
            set_pending_response,
        )

        chat_id = message.chat.id
        user_id = message.from_user.id
        await cleanup_pending_ephemeral(message.bot, chat_id, user_id)
        begin_pending_ephemeral(chat_id, user_id, command_id=message.message_id)
        sent = await _send_pending_ephemeral(
            chat_id, message.bot, text, extra_keyboard=extra_keyboard
        )
        set_pending_response(chat_id, user_id, sent.message_id)
        await arm_pending_ephemeral_delete(message.bot, chat_id, user_id)

    @dp.callback_query(F.data == "pd:close")
    async def on_pending_close(callback: types.CallbackQuery):
        from telegram_nav_session import cleanup_pending_ephemeral

        await cleanup_pending_ephemeral(
            callback.bot,
            callback.message.chat.id,
            callback.from_user.id,
        )
        await callback.answer()

    @dp.message(Command("pending"))
    async def cmd_pending(message: types.Message):
        if message.chat.type not in ("group", "supergroup"):
            return

        from telegram_reminders import collect_pending_candidates, format_pending_list_html

        vacancies = find_vacancies_by_chat_id(message.chat.id)
        if not vacancies:
            await message.answer("В этом чате нет привязанных активных вакансий.")
            return

        args = (message.text or "").split(maxsplit=1)
        if len(args) > 1 and args[1].strip().lower() == "all":
            items = collect_pending_candidates(message.chat.id)
            text = format_pending_list_html(items, show_vacancy=len(vacancies) > 1)
            await _show_pending_on_message(message, text)
            return

        if len(vacancies) == 1:
            items = collect_pending_candidates(message.chat.id, vacancies[0]["id"])
            text = format_pending_list_html(items, show_vacancy=False)
            await _show_pending_on_message(message, text)
            return

        picker_rows = []
        for vac in vacancies:
            pending_count = len(collect_pending_candidates(message.chat.id, vac["id"]))
            label = f"{vac['title']} ({pending_count})"
            picker_rows.append([{"text": label, "callback_data": f"vp:{vac['id']}"}])
        picker_rows.append([{"text": "📋 Все вакансии", "callback_data": "vp:all"}])
        await _show_pending_on_message(
            message,
            "<b>⏳ Ждут оценки</b>\n\nВыберите вакансию:",
            extra_keyboard={"inline_keyboard": picker_rows},
        )

    @dp.message(Command("menu"), F.chat.type.in_({"group", "supergroup"}))
    async def cmd_menu_group(message: types.Message):
        await message.answer(
            "В группе: /candidates — карточки вакансии, /pending — ждут оценки.\n"
            "Сводка по кандидатам — автоматически вт 18:00 и пт 15:00."
        )

    @dp.callback_query(F.data.startswith("vp:"))
    async def on_pending_vacancy_pick(callback: types.CallbackQuery):
        from telegram_nav_session import (
            arm_pending_ephemeral_delete,
            pending_keyboard_with_close,
            set_pending_response,
        )
        from telegram_reminders import collect_pending_candidates, format_pending_list_html

        token = callback.data.split(":", 1)[1]
        chat_id = callback.message.chat.id
        user_id = callback.from_user.id
        vacancies = find_vacancies_by_chat_id(chat_id)
        show_vacancy = len(vacancies) > 1

        if token == "all":
            items = collect_pending_candidates(chat_id)
        else:
            try:
                vacancy_id = int(token)
            except ValueError:
                await callback.answer("Некорректные данные", show_alert=True)
                return
            items = collect_pending_candidates(chat_id, vacancy_id)

        text = format_pending_list_html(items, show_vacancy=show_vacancy and token == "all")
        markup = _keyboard_from_dict(pending_keyboard_with_close())
        try:
            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=markup,
            )
            set_pending_response(chat_id, user_id, callback.message.message_id)
        except TelegramBadRequest:
            sent = await callback.message.answer(
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=markup,
            )
            set_pending_response(chat_id, user_id, sent.message_id)
        await arm_pending_ephemeral_delete(callback.bot, chat_id, user_id)
        await callback.answer()
