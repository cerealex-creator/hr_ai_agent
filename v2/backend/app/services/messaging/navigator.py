"""Simple prev/next candidate navigator in a vacancy chat."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.messaging.client_apply import ensure_tg_callback_id
from app.services.messaging.reminders import _esc
from app.services.messaging.telegram_provider import (
    answer_callback_query,
    edit_html_message,
    send_html_message,
)


def _zone_candidates(db: Session, vacancy_id: int) -> list[models.Candidate]:
    rows = list(
        db.scalars(
            select(models.Candidate)
            .where(models.Candidate.vacancy_id == vacancy_id)
            .order_by(models.Candidate.created_at.desc())
        ).all()
    )
    return [
        c
        for c in rows
        if c.hr_stage in ("client_review", "client_pause", "client_meeting", "offer")
    ]


def nav_keyboard(callback_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "◀️ Пред", "callback_data": f"cnp:{callback_id}"},
                {"text": "▶️ След", "callback_data": f"cnn:{callback_id}"},
            ]
        ]
    }


def handle_nav_callback(
    db: Session,
    cq: dict,
    event: dict[str, Any],
    prefix: str,
    callback_id: str,
    candidate: models.Candidate,
    post: models.MessagingPost | None,
) -> dict[str, Any]:
    cq_id = str(cq.get("id") or "")
    message = cq.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    peers = _zone_candidates(db, candidate.vacancy_id)
    if not peers:
        answer_callback_query(cq_id, text="Нет кандидатов", show_alert=True)
        return {**event, "handled": False}
    ids = [c.id for c in peers]
    try:
        idx = ids.index(candidate.id)
    except ValueError:
        idx = 0
    if prefix == "cnp":
        idx = (idx - 1) % len(peers)
    elif prefix == "cnn":
        idx = (idx + 1) % len(peers)
    nxt = peers[idx]
    cid = ensure_tg_callback_id(nxt)
    vac = db.get(models.Vacancy, nxt.vacancy_id)
    text = (
        f"<b>🧭 Навигатор</b>\n"
        f"👤 <b>{_esc(nxt.name)}</b>\n"
        f"🏢 {_esc(vac.title if vac else '')}\n"
        f"Статус: {_esc(nxt.client_status)} · этап: {_esc(nxt.hr_stage)}\n"
        f"{idx + 1}/{len(peers)}"
    )
    mid = message.get("message_id")
    if chat_id is not None and mid is not None:
        edit_html_message(chat_id, mid, text, reply_markup=nav_keyboard(cid))
    else:
        send_html_message(chat_id, text, reply_markup=nav_keyboard(cid))
    answer_callback_query(cq_id)
    return {**event, "handled": True, "nav": str(nxt.id)}
