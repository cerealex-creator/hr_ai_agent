"""Telegram-клиентская зона: кнопки статуса и отправка карточек."""

import os
from datetime import datetime, timedelta

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
    chat_ids_equal,
    normalize_chat_id,
    send_telegram_html,
)
from network_ipv4 import get_requests_session

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
    from client_actions import post_kind as _post_kind

    for post in candidate.get("telegram_posts", []):
        if (
            post.get("message_id") == message_id
            and chat_ids_equal(post.get("chat_id"), chat_id)
        ):
            return _post_kind(post)
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
    vacancy=None,
    status_key=None,
    locked=False,
    kind="primary",
    interview_prompt=None,
    show_action_prompt=True,
):
    from vacancy_store import vacancy_show_portfolio_field

    show_portfolio = vacancy_show_portfolio_field(vacancy) if vacancy else False
    builder = build_task_completed_message if kind == "task" else build_primary_candidate_message
    if kind == "task":
        text = builder(candidate, vacancy_title)
    else:
        text = builder(candidate, vacancy_title, show_portfolio=show_portfolio)
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
    elif not locked and show_action_prompt:
        text += "\n\n👇 <i>Выберите статус кнопками ниже</i>"
    return text


def _append_client_zone_link(text, vacancy, candidate):
    from client_access import build_client_candidate_href, get_department_for_vacancy
    from telegram_notify import _esc

    dept = get_department_for_vacancy(vacancy)
    if not dept:
        return text
    href = build_client_candidate_href(dept, vacancy, candidate)
    if not href.startswith("http"):
        base = (os.getenv("PUBLIC_APP_BASE_URL") or "").strip().rstrip("/")
        if base:
            href = f"{base}{href}"
        else:
            return (
                text
                + "\n\n<i>⚠️ Для ссылки на карточку задайте PUBLIC_APP_BASE_URL в .env</i>"
            )
    return text + (
        f'\n\n<b>👥 Оценка кандидата:</b> <a href="{_esc(href)}">Открыть карточку</a>'
    )


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
        response = get_requests_session().post(
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
        response = get_requests_session().post(
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


def register_telegram_post(candidate, chat_id, message_id, kind="primary", vacancy_id=None):
    from client_actions import post_belongs_to_vacancy, post_kind as _post_kind

    migrate_candidate(candidate)
    posts = candidate.setdefault("telegram_posts", [])
    norm_chat = normalize_chat_id(chat_id)

    def _same_vacancy(post):
        return vacancy_id is None or post_belongs_to_vacancy(post, vacancy_id)

    for post in posts:
        if post.get("message_id") == message_id and chat_ids_equal(post.get("chat_id"), chat_id):
            post["kind"] = kind
            if vacancy_id is not None:
                post["vacancy_id"] = vacancy_id
            return

    if kind == "primary":
        posts[:] = [
            p
            for p in posts
            if not (_same_vacancy(p) and _post_kind(p) == "primary")
        ]

    entry = {
        "chat_id": norm_chat,
        "message_id": message_id,
        "sent_at": datetime.now().isoformat(),
        "kind": kind,
    }
    if vacancy_id is not None:
        entry["vacancy_id"] = vacancy_id
    posts.append(entry)


def anchor_candidate_card_message(
    vacancy, candidate, chat_id, message_id, *, kind="primary"
):
    """Синхронизирует telegram_posts с реальным message_id карточки в чате."""
    if not vacancy or not candidate or message_id is None:
        return False
    data = load_vacancies()
    vac_id = vacancy.get("id")
    changed = False
    for v in data.get("vacancies", []):
        if v.get("id") != vac_id:
            continue
        for c in v.get("candidates", []):
            if c.get("id") != candidate.get("id"):
                continue
            migrate_candidate(c)
            register_telegram_post(
                c, chat_id, int(message_id), kind=kind, vacancy_id=vac_id
            )
            register_telegram_post(
                candidate, chat_id, int(message_id), kind=kind, vacancy_id=vac_id
            )
            changed = True
            break
        break
    if changed:
        save_vacancies(data)
    return changed


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
                vac_id = vacancy.get("id")
                register_telegram_post(
                    c, chat_id, message_id, kind=kind, vacancy_id=vac_id
                )
                register_telegram_post(
                    candidate, chat_id, message_id, kind=kind, vacancy_id=vac_id
                )
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
    from telegram_chat_id import resolve_vacancy_chat_id

    chat_id = resolve_vacancy_chat_id(vacancy)
    if not chat_id:
        return False, "У вакансии не указан Chat ID"

    migrate_candidate(candidate)
    if not candidate.get("id"):
        return False, "У кандидата нет id — нажмите «Сохранить изменения» и повторите"

    if message_builder is not None:
        kind = "task"

    status = candidate.get("client_status", "wait")
    locked = with_actions and status not in (None, "", "wait")
    text = build_candidate_card_html(
        candidate,
        vacancy["title"],
        vacancy=vacancy,
        status_key=status if locked else None,
        locked=locked,
        kind=kind,
        show_action_prompt=with_actions,
    )
    if kind == "primary" and not with_actions:
        text = _append_client_zone_link(text, vacancy, candidate)

    if with_actions:
        keyboard = (
            build_locked_keyboard(candidate)
            if locked
            else build_initial_status_keyboard(candidate)
        )
    else:
        keyboard = None

    ok, msg, message_id = send_telegram_html(chat_id, text, reply_markup=keyboard)
    buttons_ok = bool(ok and keyboard)

    if not ok and keyboard:
        plain_text = build_candidate_card_html(
            candidate, vacancy["title"], vacancy=vacancy, locked=False, kind=kind
        )
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

    if ok and kind == "primary" and not with_actions:
        return True, "Кандидат отправлен в чат со ссылкой на карточку"

    return ok, msg or "Ошибка отправки"


def send_primary_candidate_to_chat(vacancy, candidate):
    return send_candidate_card_to_chat(
        vacancy, candidate, with_actions=False, kind="primary"
    )


def _keyboard_for_candidate_card(candidate):
    status = candidate.get("client_status", "wait")
    locked = status not in (None, "", "wait")
    if locked:
        return build_locked_keyboard(candidate), True
    return build_initial_status_keyboard(candidate), False


def refresh_primary_candidate_card_in_chat(vacancy, candidate):
    """Добавляет в primary-карточку актуальные данные (например, ссылку на задание)."""
    from client_actions import get_primary_telegram_post
    from telegram_chat_id import resolve_vacancy_chat_id

    chat_id = resolve_vacancy_chat_id(vacancy)
    if not chat_id:
        return False, "У вакансии не указан Chat ID"

    migrate_candidate(candidate)
    post = get_primary_telegram_post(
        candidate, chat_id, kind="primary", vacancy_id=vacancy.get("id")
    )
    if not post or not post.get("message_id"):
        return False, "Нет основной карточки кандидата в чате"

    keyboard, locked = _keyboard_for_candidate_card(candidate)
    status = candidate.get("client_status", "wait")
    text = build_candidate_card_html(
        candidate,
        vacancy["title"],
        vacancy=vacancy,
        status_key=status if locked else None,
        locked=locked,
        kind="primary",
    )
    message_id = post["message_id"]
    ok, msg = edit_telegram_message(chat_id, message_id, text, reply_markup=keyboard)
    if not ok and keyboard:
        plain_text = build_candidate_card_html(
            candidate, vacancy["title"], vacancy=vacancy, locked=False, kind="primary"
        )
        ok, msg = edit_telegram_message(chat_id, message_id, plain_text)
        if ok:
            k_ok, k_msg = edit_message_keyboard(chat_id, message_id, keyboard)
            if not k_ok:
                return True, f"Карточка обновлена, но кнопки не восстановлены: {k_msg}"
    if ok:
        return True, "основная карточка обновлена"
    return False, msg or "Не удалось обновить карточку"


def send_task_completed_to_chat(vacancy, candidate):
    ok, msg = send_candidate_card_to_chat(
        vacancy,
        candidate,
        with_actions=True,
        message_builder=build_task_completed_message,
        kind="task",
    )
    if not ok:
        return ok, msg

    card_ok, card_msg = refresh_primary_candidate_card_in_chat(vacancy, candidate)
    if card_ok:
        return True, "Сообщение о задании отправлено, основная карточка обновлена"
    if card_msg == "Нет основной карточки кандидата в чате":
        return True, "Сообщение о задании отправлено (основная карточка в чате не найдена)"
    return True, f"Сообщение о задании отправлено, но карточка не обновлена: {card_msg}"


def send_vacancy_digest_to_chat(vacancy):
    """Ручная отправка сводки по одной вакансии в её Telegram-чат."""
    from telegram_chat_stats import format_vacancy_digest_html

    from telegram_chat_id import resolve_vacancy_chat_id

    chat_id = resolve_vacancy_chat_id(vacancy)
    if not chat_id:
        return False, "У вакансии не указан Chat ID"
    text = format_vacancy_digest_html(vacancy, title_prefix="📊 Сводка по вакансии")
    ok, msg, _ = send_telegram_html(chat_id, text)
    return ok, msg


def build_candidate_reminder_html(candidate, kind="evaluate"):
    from telegram_notify import _esc

    name = _esc(candidate.get("name", "кандидатом"))
    if kind == "decide":
        return (
            f"🟡 <b>{name}</b>\n"
            f"Кандидат в статусе «Подумать» — пожалуйста, примите решение "
            f"по карточке выше 👆"
        )
    return (
        f"⏳ <b>{name}</b>\n"
        f"Пожалуйста, изучите информацию о кандидате выше и выберите статус 👆"
    )


def send_candidate_reminder_to_chat(vacancy, candidate, kind="evaluate"):
    """Напоминание в чат ответом на карточку кандидата."""
    from client_actions import get_primary_telegram_post
    from telegram_chat_id import resolve_vacancy_chat_id

    migrate_candidate(candidate)
    chat_id = resolve_vacancy_chat_id(vacancy)
    if not chat_id:
        return False, "У вакансии не указан Chat ID"
    post = get_primary_telegram_post(candidate, chat_id, vacancy_id=vacancy.get("id"))
    if not post or not post.get("message_id"):
        return False, "Нет карточки кандидата в чате — сначала отправьте кандидата"
    text = build_candidate_reminder_html(candidate, kind=kind)
    ok, msg, _ = send_telegram_html(
        chat_id,
        text,
        reply_to_message_id=post["message_id"],
    )
    return ok, msg


def refresh_keyboard_for_message(chat_id, message_id, candidate_or_callback_id, bot_token=None):
    if isinstance(candidate_or_callback_id, str) and len(candidate_or_callback_id) <= 8:
        _, candidate, _ = find_candidate_by_tg_callback_id(candidate_or_callback_id)
    else:
        _, candidate, _ = find_candidate_by_id(candidate_or_callback_id)
    if not candidate:
        return False, "Кандидат не найден"
    keyboard = build_locked_keyboard(candidate)
    return edit_message_keyboard(chat_id, message_id, keyboard, bot_token=bot_token)
