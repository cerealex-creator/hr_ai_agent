"""Telegram bot commands registration and group command handlers."""

from __future__ import annotations

import logging
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.messaging.reminders import _esc, format_vacancy_digest_html
from app.services.messaging.telegram_provider import get_bot_token, send_html_message

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    {"command": "chatid", "description": "Показать chat_id этого чата"},
    {"command": "meetings", "description": "Встречи на ближайшие дни"},
    {"command": "pending", "description": "Кандидаты, ждущие оценки"},
    {"command": "candidates", "description": "Кандидаты в клиентской зоне"},
]


def ensure_bot_commands(bot_token: str | None = None) -> tuple[bool, str]:
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return False, "no token"
    r = requests.post(
        f"https://api.telegram.org/bot{token}/setMyCommands",
        json={"commands": BOT_COMMANDS},
        timeout=20,
    )
    data = r.json()
    if data.get("ok"):
        return True, "ok"
    return False, str(data.get("description") or "error")


def _vacancies_for_chat(db: Session, chat_id: str | int) -> list[models.Vacancy]:
    cid = str(chat_id)
    return list(
        db.scalars(
            select(models.Vacancy).where(
                models.Vacancy.active.is_(True),
                models.Vacancy.chat_id == cid,
            )
        ).all()
    )


def handle_group_command(db: Session, message: dict) -> dict[str, Any] | None:
    text = (message.get("text") or "").strip()
    if not text.startswith("/"):
        return None
    cmd = text.split()[0].split("@")[0].lower()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None

    if cmd == "/chatid":
        send_html_message(chat_id, f"chat_id: <code>{chat_id}</code>")
        return {"type": "command", "handled": True, "command": "chatid"}

    vacs = _vacancies_for_chat(db, chat_id)
    if cmd == "/pending":
        lines = ["<b>⏳ Ждут оценки</b>", ""]
        n = 0
        for v in vacs:
            for c in db.scalars(
                select(models.Candidate).where(models.Candidate.vacancy_id == v.id)
            ).all():
                if c.client_status == "wait" and c.hr_stage in (
                    "client_review",
                    "client_pause",
                    "client_meeting",
                ):
                    lines.append(f"• {_esc(c.name)} · {_esc(v.title)}")
                    n += 1
        if n == 0:
            lines.append("Нет кандидатов в ожидании.")
        send_html_message(chat_id, "\n".join(lines))
        return {"type": "command", "handled": True, "command": "pending", "count": n}

    if cmd == "/candidates":
        lines = ["<b>👥 Кандидаты в зоне заказчика</b>", ""]
        n = 0
        for v in vacs:
            for c in db.scalars(
                select(models.Candidate).where(models.Candidate.vacancy_id == v.id)
            ).all():
                if c.hr_stage in ("client_review", "client_pause", "client_meeting", "offer"):
                    lines.append(
                        f"• {_esc(c.name)} · {_esc(c.client_status)} · {_esc(v.title)}"
                    )
                    n += 1
        if n == 0:
            lines.append("Пусто.")
        send_html_message(chat_id, "\n".join(lines))
        return {"type": "command", "handled": True, "command": "candidates", "count": n}

    if cmd == "/meetings":
        lines = ["<b>📅 Встречи</b>", ""]
        n = 0
        for v in vacs:
            for c in db.scalars(
                select(models.Candidate).where(models.Candidate.vacancy_id == v.id)
            ).all():
                p = c.payload or {}
                d = str(p.get("office_interview_date") or "").strip()
                t = str(p.get("office_interview_time") or "").strip()
                if d and t:
                    conf = "✅" if p.get("meeting_hr_confirmed") else "⏳"
                    lines.append(f"• {conf} {_esc(c.name)} — {d} {t} · {_esc(v.title)}")
                    n += 1
        if n == 0:
            lines.append("Нет назначенных встреч.")
        send_html_message(chat_id, "\n".join(lines))
        return {"type": "command", "handled": True, "command": "meetings", "count": n}

    if cmd == "/digest":
        if not vacs:
            send_html_message(chat_id, "Нет активных вакансий в этом чате.")
            return {"type": "command", "handled": True, "command": "digest"}
        send_html_message(chat_id, format_vacancy_digest_html(vacs, db))
        return {"type": "command", "handled": True, "command": "digest"}

    return None
