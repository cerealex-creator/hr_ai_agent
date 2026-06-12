"""Telegram-клиентская зона: кнопки статуса и отправка карточек."""

from datetime import datetime, timedelta

import requests

from client_actions import find_candidate_by_id, find_candidate_by_tg_callback_id
from models import CLIENT_ZONE_ENTRY_STAGE, set_hr_stage
from vacancy_store import get_status_meta, load_vacancies, migrate_candidate, save_vacancies
from interview_schedule import (
    build_time_options,
    format_interview_display,
    get_timezone,
    validate_interview_schedule,
)
from telegram_notify import (
    build_primary_candidate_message,
    build_task_completed_message,
    get_bot_token,
    normalize_chat_id,
    send_telegram_html,
)

WEEKDAY_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

# Статусы, доступные в кнопках Telegram-чата (без «Вышел» и «Ждёт оценки»)
TELEGRAM_CHAT_STATUS_KEYS = frozenset({"ready", "think", "reject", "offer"})

TELEGRAM_STATUS_BUTTONS = (
    ("ready", "🟢 Встреча"),
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


def _interview_format_label(candidate):
    parts = []
    if candidate.get("remote_interview"):
        parts.append("удалённо")
    if candidate.get("office_interview"):
        parts.append("офис")
    return ", ".join(parts)


def _append_interview_block(text, candidate, status_key):
    date_str = (candidate.get("office_interview_date") or "").strip()
    time_str = (candidate.get("office_interview_time") or "").strip()
    if date_str and time_str:
        when = format_interview_display(date_str, time_str)
        fmt = _interview_format_label(candidate)
        line = f"\n<b>Встреча:</b> {when}"
        if fmt:
            line += f" ({fmt})"
        text += line
        if not candidate.get("meeting_hr_confirmed", False):
            text += "\n<i>⏳ Требуется подтверждение HR</i>"
    elif status_key == "ready":
        text += "\n<i>Укажите дату встречи кнопкой 📅 ниже</i>"
    return text


def build_candidate_card_html(
    candidate,
    vacancy_title,
    *,
    status_key=None,
    locked=False,
    kind="primary",
    interview_prompt=None,
):
    builder = build_task_completed_message if kind == "task" else build_primary_candidate_message
    text = builder(candidate, vacancy_title)
    if locked and status_key:
        meta = get_status_meta(status_key)
        text += f"\n\n<b>Текущий статус:</b> {meta['icon']} {meta['label']}"
        text = _append_interview_block(text, candidate, status_key)
        client_comment = (candidate.get("client_comment") or "").strip()
        if client_comment:
            from telegram_notify import _esc
            text += f"\n<b>Комментарий:</b> {_esc(client_comment)}"
        if interview_prompt:
            text += f"\n\n{interview_prompt}"
    elif not locked:
        text += "\n\n👇 <i>Выберите статус кнопками ниже</i>"
    return text


def parse_interview_date_token(date_token):
    return datetime.strptime(date_token, "%Y%m%d").strftime("%Y-%m-%d")


def parse_interview_time_token(time_token):
    return datetime.strptime(time_token, "%H%M").strftime("%H:%M")


def interview_format_flags(flag):
    if flag == "r":
        return True, False
    if flag == "b":
        return True, True
    return False, True


def needs_interview_schedule(candidate):
    if candidate.get("client_status") != "ready":
        return False
    return bool(validate_interview_schedule(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    ))


def build_interview_date_keyboard(candidate, *, days=14):
    callback_id = get_telegram_callback_id(candidate)
    start = datetime.now(get_timezone()).date()
    rows = []
    row = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        label = f"{WEEKDAY_SHORT[day.weekday()]} {day.strftime('%d.%m')}"
        row.append({
            "text": label,
            "callback_data": f"ivd:{callback_id}:{day.strftime('%Y%m%d')}",
        })
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "↩️ Отмена", "callback_data": f"ivc:{callback_id}"}])
    return {"inline_keyboard": rows}


def build_interview_time_keyboard(candidate, date_token):
    callback_id = get_telegram_callback_id(candidate)
    rows = []
    row = []
    for slot in build_time_options():
        if not slot:
            continue
        row.append({
            "text": slot,
            "callback_data": f"ivt:{callback_id}:{date_token}:{slot.replace(':', '')}",
        })
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        {"text": "↩️ Назад", "callback_data": f"ivi:{callback_id}"},
        {"text": "✖️ Отмена", "callback_data": f"ivc:{callback_id}"},
    ])
    return {"inline_keyboard": rows}


def build_interview_format_keyboard(candidate, date_token, time_token):
    callback_id = get_telegram_callback_id(candidate)
    base = f"ivf:{callback_id}:{date_token}:{time_token}"
    return {
        "inline_keyboard": [
            [
                {"text": "🏢 В офисе", "callback_data": f"{base}:o"},
                {"text": "💻 Удалённо", "callback_data": f"{base}:r"},
            ],
            [{"text": "🏢+💻 Оба", "callback_data": f"{base}:b"}],
            [
                {"text": "↩️ Назад", "callback_data": f"ivd:{callback_id}:{date_token}"},
                {"text": "✖️ Отмена", "callback_data": f"ivc:{callback_id}"},
            ],
        ]
    }


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
    """После выбора статуса: комментарий, смена статуса, собеседование."""
    callback_id = get_telegram_callback_id(candidate)
    rows = [[
        {"text": "💬 Комментарий", "callback_data": f"cc:{callback_id}"},
        {"text": "🔄 Сменить статус", "callback_data": f"cchg:{callback_id}"},
    ]]
    status = candidate.get("client_status", "wait")
    has_schedule = not validate_interview_schedule(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    )
    if status == "ready" or has_schedule:
        label = "📅 Изменить встречу" if has_schedule else "📅 Встреча"
        rows.append([{"text": label, "callback_data": f"ivi:{callback_id}"}])
    if has_schedule:
        rows.append([{"text": "❌ Отменить встречу", "callback_data": f"ivx:{callback_id}"}])
    return {"inline_keyboard": rows}


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


def _persist_telegram_post(
    vacancy,
    candidate,
    chat_id,
    message_id,
    kind="primary",
    *,
    with_client_actions=False,
):
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
                if with_client_actions:
                    set_hr_stage(c, CLIENT_ZONE_ENTRY_STAGE, "отправка в Telegram")
                    set_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE, "отправка в Telegram")
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
        _persist_telegram_post(
            vacancy,
            candidate,
            chat_id,
            message_id,
            kind=kind,
            with_client_actions=with_actions,
        )

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
