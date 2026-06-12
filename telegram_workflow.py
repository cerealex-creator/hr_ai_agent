"""Сценарии Telegram-клиентской зоны: статус, комментарий, уведомления."""

from aiogram.enums import ParseMode

from client_actions import apply_and_save_client_action, find_candidate_by_tg_callback_id
from telegram_notify import _esc
from vacancy_store import get_status_meta

# Статусы без обязательного комментария
STATUS_WITHOUT_COMMENT = frozenset({"ready", "offer"})

pending_actions = {}


def status_requires_comment(status_key):
    return status_key not in STATUS_WITHOUT_COMMENT


def telegram_actor_label(user):
    """Имя Фамилия из Telegram, иначе @username, иначе id."""
    if not user:
        return "telegram"
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    full = f"{first} {last}".strip()
    if full:
        return full
    username = (user.username or "").strip()
    if username:
        return f"@{username}"
    return str(user.id)


def telegram_message_link(chat_id, message_id):
    """Ссылка на сообщение в супергруппе."""
    cid = str(chat_id).strip()
    if cid.startswith("-100"):
        cid = cid[4:]
    elif cid.startswith("-"):
        cid = cid[1:]
    return f"https://t.me/c/{cid}/{message_id}"


def build_status_change_notification(
    candidate,
    vacancy,
    *,
    actor_label,
    status_key,
    comment_text=None,
):
    meta = get_status_meta(status_key)
    lines = [
        f"{meta['icon']} <b>{_esc(actor_label)}</b> — статус <b>«{meta['label']}»</b>",
        f"👤 {_esc(candidate.get('name', 'Кандидат'))}",
    ]
    if vacancy and vacancy.get("title"):
        lines.append(f"🏢 {_esc(vacancy['title'])}")
    clean_comment = (comment_text or "").strip()
    if clean_comment:
        lines.append(f"<i>{_esc(clean_comment)}</i>")
    return "\n".join(lines)


async def notify_status_change(
    bot,
    *,
    chat_id,
    candidate,
    vacancy,
    actor_label,
    status_key,
    comment_text=None,
    reply_to_message_id=None,
):
    text = build_status_change_notification(
        candidate,
        vacancy,
        actor_label=actor_label,
        status_key=status_key,
        comment_text=comment_text,
    )
    await bot.send_message(
        chat_id,
        text,
        parse_mode=ParseMode.HTML,
        reply_to_message_id=reply_to_message_id,
    )


async def apply_status_change(
    bot,
    *,
    candidate_id,
    chat_id,
    status_key,
    actor_note,
    comment_text=None,
    card_message_id=None,
    callback=None,
    user_message=None,
    prompt_message_id=None,
):
    """
    Сохраняет статус (и опционально комментарий), шлёт уведомление, обновляет карточку.
    callback — для обновления карточки и мастера встречи; user_message — для сценария с комментарием.
    """
    from telegram_bot_handlers import (
        _edit_card_interview_dates,
        _edit_card_locked,
        _reload_telegram_client,
        _send_interview_date_fallback,
        _update_card_message,
    )

    comment_at = user_message.date if user_message else None
    ok, msg, candidate, vacancy = apply_and_save_client_action(
        candidate_id,
        chat_id=chat_id,
        status_key=status_key,
        comment=comment_text,
        append_comment=bool((comment_text or "").strip()),
        actor="telegram",
        actor_note=actor_note,
        comment_at=comment_at,
    )
    if not ok or not candidate:
        if user_message:
            await user_message.reply(f"⚠️ {msg}")
        elif callback:
            await callback.answer(msg, show_alert=True)
        return False

    meta = get_status_meta(status_key)
    reply_to = card_message_id
    if not reply_to and callback and callback.message:
        reply_to = callback.message.message_id

    if vacancy and reply_to:
        from telegram_client import anchor_candidate_card_message

        anchor_candidate_card_message(
            vacancy, candidate, chat_id, int(reply_to)
        )

    try:
        await notify_status_change(
            bot,
            chat_id=chat_id,
            candidate=candidate,
            vacancy=vacancy,
            actor_label=actor_note,
            status_key=status_key,
            comment_text=comment_text,
            reply_to_message_id=reply_to,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Не удалось отправить уведомление о статусе: %s", exc)

    if prompt_message_id:
        try:
            await bot.delete_message(chat_id, prompt_message_id)
        except Exception:
            pass

    if user_message:
        try:
            await user_message.delete()
        except Exception:
            pass

    tc = _reload_telegram_client()
    if callback:
        await callback.answer(meta["label"], show_alert=False)
        try:
            if status_key == "ready" and tc.needs_interview_schedule(candidate):
                await _edit_card_interview_dates(callback, candidate, vacancy)
            else:
                await _edit_card_locked(callback, candidate, vacancy)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Ошибка обновления карточки: %s", exc)
            if status_key == "ready":
                await _send_interview_date_fallback(callback, candidate, vacancy, meta["label"])
    elif card_message_id and vacancy:
        kind = tc.get_post_kind(candidate, chat_id, card_message_id)
        text = tc.build_candidate_card_html(
            candidate,
            vacancy["title"],
            status_key=candidate.get("client_status", "wait"),
            locked=True,
            kind=kind,
        )
        keyboard = (
            tc.build_interview_date_keyboard(candidate)
            if status_key == "ready" and tc.needs_interview_schedule(candidate)
            else tc.build_locked_keyboard(candidate)
        )
        await _update_card_message(
            text,
            keyboard,
            bot=bot,
            chat_id=chat_id,
            message_id=card_message_id,
        )

    return True


def store_pending_status(user_id, *, candidate_id, status_key, chat_id, card_message_id, prompt_message_id, actor_note):
    pending_actions[user_id] = {
        "action": "status",
        "candidate_id": candidate_id,
        "status_key": status_key,
        "chat_id": chat_id,
        "card_message_id": card_message_id,
        "prompt_message_id": prompt_message_id,
        "actor_note": actor_note,
    }


def store_pending_comment(user_id, *, candidate_id, chat_id, card_message_id, prompt_message_id):
    pending_actions[user_id] = {
        "action": "comment",
        "candidate_id": candidate_id,
        "chat_id": chat_id,
        "card_message_id": card_message_id,
        "prompt_message_id": prompt_message_id,
    }


def pop_pending_action(user_id):
    return pending_actions.pop(user_id, None)


def get_pending_action(user_id):
    return pending_actions.get(user_id)


async def try_handle_pending_action(message):
    """Обрабатывает ожидающий комментарий к статусу или отдельный комментарий."""
    user_id = message.from_user.id
    state = pop_pending_action(user_id)
    if not state:
        return False

    text = (message.text or "").strip()
    action = state.get("action")

    if action == "status":
        if not text:
            await message.reply("⚠️ Комментарий обязателен для этого статуса. Напишите текст.")
            pending_actions[user_id] = state
            return True
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
        return True

    if action == "comment":
        from telegram_bot_handlers import _finalize_comment

        await _finalize_comment(
            message.bot,
            chat_id=state.get("chat_id", message.chat.id),
            candidate_id=state["candidate_id"],
            comment_text=text,
            user_message=message,
            prompt_message_id=state.get("prompt_message_id"),
            card_message_id=state.get("card_message_id"),
        )
        return True

    return False
