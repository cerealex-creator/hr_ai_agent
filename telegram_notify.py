"""Telegram API и сообщения о кандидатах."""

import html
import os

import network_ipv4  # noqa: F401 — requests → IPv4
from network_ipv4 import get_requests_session
from dotenv import load_dotenv

load_dotenv()


def _esc(text):
    return html.escape(str(text or "").strip())


def _link(url, label):
    u = _esc(url)
    return f'<a href="{u}"><b>{label}</b></a>'


def get_bot_token():
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def normalize_chat_id(chat_id):
    """Приводит chat_id к int (без смены формата — для отправки в API)."""
    if chat_id is None:
        return None
    s = str(chat_id).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return s


def chat_id_variants(chat_id):
    """Варианты одного чата: legacy-группа и супергруппа (-100…)."""
    cid = normalize_chat_id(chat_id)
    if cid is None or not isinstance(cid, int):
        return set()
    variants = {cid}
    text = str(cid)
    if text.startswith("-100"):
        variants.add(int("-" + text[4:]))
    elif cid < 0:
        variants.add(int("-100" + text[1:]))
    return variants


def chat_ids_equal(a, b):
    """Сравнение chat_id с учётом legacy и супергруппы."""
    if a is None or b is None:
        return False
    return bool(chat_id_variants(a) & chat_id_variants(b))


def get_hr_user_id():
    for key in ("TELEGRAM_HR_USER_ID", "TELEGRAM_ADMIN_USER_ID"):
        val = os.getenv(key, "").strip()
        if val:
            return normalize_chat_id(val)
    return None


def get_bot_status():
    """Проверка токена через getMe. Возвращает (ok, message, info_dict)."""
    token = get_bot_token()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN в .env", {}
    try:
        r = get_requests_session().get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=15,
        )
        data = r.json()
        if data.get("ok"):
            bot = data["result"]
            return (
                True,
                f"Бот @{bot.get('username', '?')} подключён",
                bot,
            )
        return False, data.get("description", "Ошибка getMe"), {}
    except Exception as e:
        return False, f"Сетевая ошибка: {e}", {}


def send_telegram_html(
    chat_id,
    text,
    bot_token=None,
    reply_markup=None,
    reply_to_message_id=None,
):
    """Отправка HTML-сообщения. Возвращает (ok, message, message_id)."""
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN в .env", None

    normalized = normalize_chat_id(chat_id)
    if normalized is None:
        return False, "Не указан chat_id", None

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": normalized,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        response = get_requests_session().post(url, json=payload, timeout=30)
        data = response.json()
        if data.get("ok"):
            message_id = data.get("result", {}).get("message_id")
            return True, "Уведомление доставлено в Telegram", message_id
        desc = data.get("description", "неизвестно")
        if "chat not found" in desc.lower():
            desc += ". Проверьте Chat ID и что бот добавлен в чат."
        if "bot was blocked" in desc.lower():
            desc += ". Напишите боту /start в личке."
        return False, f"Ошибка Telegram: {desc}", None
    except Exception as e:
        return False, f"Сетевая ошибка: {e}", None


def validate_primary_fields(cand):
    """Обязательные поля для первичного сообщения (кроме тестового задания)."""
    missing = []
    if not (cand.get("name") or "").strip():
        missing.append("ФИО")
    if not (cand.get("resume_link") or "").strip():
        missing.append("Ссылка на резюме")
    if not (cand.get("video_link") or "").strip():
        missing.append("Запись собеседования")
    return missing


def validate_task_message_fields(cand):
    missing = []
    if not (cand.get("name") or "").strip():
        missing.append("ФИО")
    if not (cand.get("task_link") or "").strip():
        missing.append("Тестовое задание")
    return missing


def build_primary_candidate_message(cand, vacancy_title, *, show_portfolio=False):
    name = _esc(cand.get("name", ""))
    vac = _esc(vacancy_title)
    lines = [
        "<b>🆕 Новый кандидат:</b>",
        "",
        f"<b>👤 {name}</b>",
        "",
        f"<b>🏢 Вакансия:</b> {vac}",
        "",
        f"📄 {_link(cand['resume_link'], 'Резюме')}",
        "",
        f"🎥 {_link(cand['video_link'], 'Запись собеседования')}",
    ]
    if show_portfolio:
        portfolio = (cand.get("portfolio_link") or "").strip()
        if portfolio:
            lines.extend(["", f"🎨 {_link(portfolio, 'Портфолио кандидата')}"])
    task = (cand.get("task_link") or "").strip()
    if task:
        lines.extend(["", f"✅ {_link(task, 'Выполненное задание')}"])
    hr_comment = (cand.get("hr_comment") or "").strip()
    if hr_comment:
        lines.extend(["", "<b>Комментарий HR:</b>", _esc(hr_comment)])
    return "\n".join(lines)


def build_task_completed_message(cand, vacancy_title):
    name = (cand.get("name") or "").strip()
    vac = _esc(vacancy_title)
    task = cand.get("task_link", "")
    resume = (cand.get("resume_link") or "").strip()
    if resume:
        name_line = f"👤 {_link(resume, _esc(name))}"
    else:
        name_line = f"<b>👤 {_esc(name)}</b>"
    lines = [
        "<b>✅ Выполнено тестовое задание</b>",
        "",
        f"{_link(task, 'Выполненное задание')}",
        "",
        name_line,
        "",
        f"<b>🏢 Вакансия:</b> {vac}",
    ]
    return "\n".join(lines)


def get_telegram_credentials():
    return get_bot_token()


def send_to_vacancy_chat(vacancy, message, send_fn=None):
    """Отправка в чат вакансии. send_fn: (bot_token, chat_id, text) → (ok, msg)."""
    from telegram_chat_id import resolve_vacancy_chat_id

    chat_id = resolve_vacancy_chat_id(vacancy)
    token = get_bot_token()
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN в .env"
    if not chat_id:
        return False, "У вакансии не указан Chat ID (настройте чат в «Настройках»)"
    if send_fn:
        return send_fn(token, chat_id, message)
    return send_telegram_html(chat_id, message, bot_token=token)
