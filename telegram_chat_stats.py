"""Сводка по кандидатам для Telegram-чатов."""

import html
from collections import defaultdict

from models import is_visible_in_client_zone
from vacancy_store import migrate_candidate
from telegram_notify import normalize_chat_id

_DIGEST_EXCLUDED = frozenset({"reject", "offer"})


def _esc(text):
    return html.escape(str(text or "").strip())


def vacancy_digest_metrics(vacancy):
    """Метрики сводки по одной вакансии."""
    candidates = vacancy.get("candidates", [])
    for cand in candidates:
        migrate_candidate(cand)

    visible = [c for c in candidates if is_visible_in_client_zone(c)]
    on_review = sum(
        1 for c in visible if c.get("client_status", "wait") not in _DIGEST_EXCLUDED
    )
    offered = sum(1 for c in visible if c.get("client_status") == "offer")
    meeting = sum(1 for c in visible if c.get("client_status") == "ready")
    no_answer = sum(1 for c in visible if c.get("client_status") == "wait")

    return {
        "on_review": on_review,
        "offered": offered,
        "meeting": meeting,
        "no_answer": no_answer,
    }


def format_vacancy_digest_block(vacancy):
    title = _esc(vacancy.get("title", "Вакансия"))
    m = vacancy_digest_metrics(vacancy)
    return (
        f"🏢 <b>{title}</b>\n"
        f"• Находится на оценке: <b>{m['on_review']}</b>\n"
        f"• Приглашено на работу/стажировку: <b>{m['offered']}</b>\n"
        f"• Назначена встреча: <b>{m['meeting']}</b>\n"
        f"• Без ответа: <b>{m['no_answer']}</b>"
    )


def format_vacancy_digest_html(vacancy, *, title_prefix="📊 Сводка по кандидатам"):
    lines = [f"<b>{title_prefix}</b>", "", format_vacancy_digest_block(vacancy)]
    return "\n".join(lines)


def format_chat_digest_html(vacancies):
    """Сводка по всем активным вакансиям одного чата."""
    lines = ["<b>📊 Сводка по кандидатам</b>", ""]
    for idx, vacancy in enumerate(vacancies):
        if idx:
            lines.append("")
        lines.append(format_vacancy_digest_block(vacancy))
    return "\n".join(lines)


def group_active_vacancies_by_chat(vacancies):
    """Группирует активные вакансии с chat_id по чату."""
    from telegram_chat_id import resolve_vacancy_chat_id

    by_chat = defaultdict(list)
    for vacancy in vacancies:
        if not vacancy.get("active", True):
            continue
        chat_id = resolve_vacancy_chat_id(vacancy)
        if not chat_id:
            continue
        by_chat[normalize_chat_id(chat_id)].append(vacancy)
    return dict(by_chat)


# Совместимость с личным меню бота (одна вакансия)
def format_vacancy_stats_html(vacancy):
    return format_vacancy_digest_html(vacancy)


def format_all_vacancies_stats_html(vacancies):
    return format_chat_digest_html(vacancies)
