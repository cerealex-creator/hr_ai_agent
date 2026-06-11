"""Telegram-клиентская зона: кнопки статуса и отправка карточек."""

from datetime import datetime

import requests

from client_actions import find_candidate_by_id, find_candidate_by_tg_callback_id
from vacancy_store import get_status_meta, load_vacancies, migrate_candidate, save_vacancies
from telegram_notify import (
    build_primary_candidate_message,
    build_task_completed_message,
    get_bot_token,
    normalize_chat_id,
    send_telegram_html,
)

# Статусы, доступные в кнопках Telegram-чата (без «Вышел» и «Ждёт оценки»)
TELEGRAM_CHAT_STATUS_KEYS = frozenset({"ready", "think", "reject", "offer"})

TELEGRAM_STATUS_BUTTONS = (
    ("ready", "🟢 Рассматриваем"),
    ("think", "🟡 Подумать"),
    ("reject", "🔴 Отказ"),
    ("offer", "🟢 Оффер"),
)


def iter_chat_status_buttons():
    for key, label in TELEGRAM_STATUS_BUTTONS:
        if key in TELEGRAM_CHAT_STATUS_KEYS:
            yield key, label


def get_telegram_callback_id(candidate):
    migrate_candidate(candidate)
    return candidate["tg_callback_id"]


def get_post_kind(candidate, chat_id, message_id):
    norm_chat = normalize_chat_id(chat_id)
    for post in candidate.get("telegram_posts", []):
        if (
            post.get("message_id") == message_id
            and normalize_chat_id(post.get("chat_id")) == norm_chat
        ):
            return post.get("kind", "primary")
    return "primary"


def build_candidate_card_html(
    candidate,
    vacancy_title,
    *,
    status_key=None,
    locked=False,
    kind="primary",
):
    builder = build_task_completed_message if kind == "task" else build_primary_candidate_message
    text = builder(candidate, vacancy_title)
    if locked and status_key:
        meta = get_status_meta(status_key)
        text += f"\n\n<b>Текущий статус:</b> {meta['icon']} {meta['label']}"
        client_comment = (candidate.get("client_comment") or "").strip()
        if client_comment:
            from telegram_notify import _esc
            text += f"\n<b>Комментарий:</b> {_esc(client_comment)}"
    elif not locked:
        text += "\n\n👇 <i>Выберите статус кнопками ниже</i>"
    return text


def build_initial_status_keyboard(candidate):
    """Первичная карточка: все статусы + комментарий."""
    callback_id = get_telegram_callback_id(candidate)
    current = candidate.get("client_status", "wait")
    rows = []
    row = []
    for key, label in iter_chat_status_buttons():
        text = f"• {label}" if key == current else label
        row.append({"text": text, "callback_data": f"cs:{callback_id}:{key}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "💬 Комментарий", "callback_data": f"cc:{callback_id}"}])
    return {"inline_keyboard": rows}


def build_locked_keyboard(candidate):
    """После выбора статуса: комментарий и смена статуса."""
    callback_id = get_telegram_callback_id(candidate)
    return {
        "inline_keyboard": [[
            {"text": "💬 Комментарий", "callback_data": f"cc:{callback_id}"},
            {"text": "🔄 Сменить статус", "callback_data": f"cchg:{callback_id}"},
        ]]
    }


def build_change_status_keyboard(candidate):
    """Режим смены статуса: кнопки статусов + отмена."""
    callback_id = get_telegram_callback_id(candidate)
    current = candidate.get("client_status", "wait")
    rows = []
    row = []
    for key, label in iter_chat_status_buttons():
        text = f"• {label}" if key == current else label
        row.append({"text": text, "callback_data": f"cs:{callback_id}:{key}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "↩️ Отмена", "callback_data": f"ccl:{callback_id}"}])
    return {"inline_keyboard": rows}


def build_client_status_keyboard(candidate, current_status=None):
    return build_initial_status_keyboard(candidate)


def edit_telegram_message(chat_id, message_id, text, reply_markup=None, bot_token=None):
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN"
    payload = {
        "chat_id": normalize_chat_id(chat_id),
        "message_id": message_id,
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
        if data.get("ok"):
            return True, "ok"
        return False, data.get("description", "ошибка")
    except Exception as e:
        return False, str(e)


def edit_message_keyboard(chat_id, message_id, reply_markup, bot_token=None):
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/editMessageReplyMarkup",
            json={
                "chat_id": normalize_chat_id(chat_id),
                "message_id": message_id,
                "reply_markup": reply_markup,
            },
            timeout=30,
        )
        data = response.json()
        if data.get("ok"):
            return True, "Клавиатура обновлена"
        return False, data.get("description", "ошибка")
    except Exception as e:
        return False, str(e)


def register_telegram_post(candidate, chat_id, message_id, kind="primary"):
    migrate_candidate(candidate)
    posts = candidate.setdefault("telegram_posts", [])
    norm_chat = normalize_chat_id(chat_id)
    for post in posts:
        if post.get("message_id") == message_id and normalize_chat_id(post.get("chat_id")) == norm_chat:
            post["kind"] = kind
            return
    posts.append({
        "chat_id": norm_chat,
        "message_id": message_id,
        "sent_at": datetime.now().isoformat(),
        "kind": kind,
    })


def _persist_telegram_post(vacancy, candidate, chat_id, message_id, kind="primary"):
    data = load_vacancies()
    for v in data.get("vacancies", []):
        if v.get("id") != vacancy.get("id"):
            continue
        for c in v.get("candidates", []):
            if c.get("id") == candidate.get("id"):
                migrate_candidate(c)
                migrate_candidate(candidate)
                register_telegram_post(c, chat_id, message_id, kind=kind)
                register_telegram_post(candidate, chat_id, message_id, kind=kind)
                save_vacancies(data)
                return True
    return False


def send_candidate_card_to_chat(
    vacancy,
    candidate,
    *,
    with_actions=True,
    message_builder=None,
    kind="primary",
):
    chat_id = vacancy.get("chat_id")
    if not chat_id:
        return False, "У вакансии не указан Chat ID"

    migrate_candidate(candidate)
    if not candidate.get("id"):
        return False, "У кандидата нет id — нажмите «Сохранить изменения» и повторите"

    if message_builder is not None:
        kind = "task"

    text = build_candidate_card_html(
        candidate,
        vacancy["title"],
        locked=False,
        kind=kind,
    )

    keyboard = build_initial_status_keyboard(candidate) if with_actions else None

    ok, msg, message_id = send_telegram_html(chat_id, text, reply_markup=keyboard)
    buttons_ok = bool(ok and keyboard)

    if not ok and keyboard:
        plain_text = build_candidate_card_html(candidate, vacancy["title"], locked=False, kind=kind)
        ok, msg, message_id = send_telegram_html(chat_id, plain_text)
        if ok and message_id:
            k_ok, k_msg = edit_message_keyboard(chat_id, message_id, keyboard)
            buttons_ok = k_ok
            if k_ok:
                msg = "Сообщение отправлено с кнопками статуса"
            else:
                msg = f"Сообщение отправлено без кнопок: {k_msg}"
        else:
            return False, msg or "Ошибка отправки в Telegram"

    if ok and message_id:
        _persist_telegram_post(vacancy, candidate, chat_id, message_id, kind=kind)

    if ok and with_actions:
        if buttons_ok:
            return True, "Кандидат отправлен в чат с кнопками статуса"
        return True, msg or "Сообщение отправлено, но кнопки не отобразились"

    return ok, msg or "Ошибка отправки"


def send_primary_candidate_to_chat(vacancy, candidate):
    return send_candidate_card_to_chat(vacancy, candidate, with_actions=True, kind="primary")


def send_task_completed_to_chat(vacancy, candidate):
    return send_candidate_card_to_chat(
        vacancy,
        candidate,
        with_actions=True,
        message_builder=build_task_completed_message,
        kind="task",
    )


def refresh_keyboard_for_message(chat_id, message_id, candidate_or_callback_id, bot_token=None):
    if isinstance(candidate_or_callback_id, str) and len(candidate_or_callback_id) <= 8:
        _, candidate, _ = find_candidate_by_tg_callback_id(candidate_or_callback_id)
    else:
        _, candidate, _ = find_candidate_by_id(candidate_or_callback_id)
    if not candidate:
        return False, "Кандидат не найден"
    keyboard = build_locked_keyboard(candidate)
    return edit_message_keyboard(chat_id, message_id, keyboard, bot_token=bot_token)
