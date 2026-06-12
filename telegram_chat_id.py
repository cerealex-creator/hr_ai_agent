"""Привязка вакансий к Telegram-чатам (без циклических импортов)."""


def get_department_chat_id(client_id):
    from telegram_notify import normalize_chat_id
    from vacancy_store import load_chats

    if client_id is None:
        return None
    for chat in load_chats():
        if chat.get("department_id") == client_id:
            return normalize_chat_id(chat.get("id"))
    return None


def resolve_vacancy_chat_id(vacancy, runtime_chat_id=None):
    """Куда слать сообщения: chats_db → runtime-чат → поле вакансии."""
    from telegram_notify import chat_ids_equal, normalize_chat_id

    runtime_norm = normalize_chat_id(runtime_chat_id)
    canonical = get_department_chat_id(vacancy.get("client_id"))
    if canonical is not None:
        if runtime_norm is not None and chat_ids_equal(runtime_norm, canonical):
            return runtime_norm
        return canonical
    if runtime_norm is not None:
        return runtime_norm
    return normalize_chat_id(vacancy.get("chat_id"))
