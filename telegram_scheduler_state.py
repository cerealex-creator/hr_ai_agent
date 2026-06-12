"""Состояние планировщика Telegram (сводки по расписанию)."""

import json
import os

from vacancy_store import DATA_DIR

STATE_FILE = os.path.join(DATA_DIR, "telegram_scheduler_state.json")


def _default_state():
    return {"chat_digests": {}}


def load_scheduler_state():
    if not os.path.exists(STATE_FILE):
        return _default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_state()
        data.setdefault("chat_digests", {})
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def save_scheduler_state(state):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def digest_already_sent_today(chat_id, slot_key, today_iso):
    from telegram_notify import normalize_chat_id

    state = load_scheduler_state()
    chat_key = str(normalize_chat_id(chat_id))
    last = state.get("chat_digests", {}).get(chat_key, {}).get(slot_key)
    return last == today_iso


def mark_digest_sent(chat_id, slot_key, today_iso):
    from telegram_notify import normalize_chat_id

    state = load_scheduler_state()
    chat_key = str(normalize_chat_id(chat_id))
    digests = state.setdefault("chat_digests", {})
    chat_state = digests.setdefault(chat_key, {})
    chat_state[slot_key] = today_iso
    save_scheduler_state(state)
