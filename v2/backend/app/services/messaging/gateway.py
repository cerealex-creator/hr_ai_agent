"""Messaging Gateway orchestration (outbound + inbound slice 2)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.candidate_fields import candidate_public_fields
from app.services.candidate_write import CLIENT_ZONE_ENTRY_STAGE, apply_hr_stage
from app.services.messaging.card_html import build_candidate_card_html, validate_send_fields
from app.services.messaging.channels import ensure_channel_for_vacancy
from app.services.messaging.client_apply import ensure_tg_callback_id
from app.services.messaging.keyboards import build_initial_status_keyboard
from app.services.messaging.telegram_provider import send_html_message


class MessagingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def send_candidate_card(
    db: Session,
    candidate: models.Candidate,
    *,
    move_to_client_review: bool = True,
    kind: str = "primary",
) -> dict[str, Any]:
    """
    Send candidate card to vacancy Telegram chat with inline status buttons.
    Inbound processing is gated by MESSAGING_INBOUND_ENABLED (do not share token
    with Streamlit polling until cutover).
    """
    settings = get_settings()
    if not settings.messaging_outbound_enabled:
        raise MessagingError("Отправка в мессенджер отключена (MESSAGING_OUTBOUND_ENABLED=false)", 403)
    if not (settings.telegram_bot_token or "").strip():
        raise MessagingError("Не задан TELEGRAM_BOT_TOKEN", 400)

    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy:
        raise MessagingError("Вакансия не найдена", 404)
    if not (vacancy.chat_id or "").strip():
        raise MessagingError("У вакансии не указан Chat ID", 400)

    fields = candidate_public_fields(candidate.payload)
    missing = validate_send_fields(
        name=candidate.name,
        resume_link=fields.get("resume_link"),
        hh_resume_link=fields.get("hh_resume_link"),
    )
    if missing:
        raise MessagingError("Заполните: " + ", ".join(missing), 400)

    channel = ensure_channel_for_vacancy(db, vacancy)
    if not channel:
        raise MessagingError("Не удалось создать messaging channel", 500)

    callback_id = ensure_tg_callback_id(candidate)
    text = build_candidate_card_html(
        name=candidate.name,
        vacancy_title=vacancy.title,
        resume_link=fields.get("resume_link"),
        hh_resume_link=fields.get("hh_resume_link"),
        video_link=fields.get("video_link"),
        portfolio_link=fields.get("portfolio_link"),
        task_link=fields.get("task_link"),
        hr_comment=(candidate.payload or {}).get("hr_comment"),
        locked=False,
    )
    reply_markup = build_initial_status_keyboard(callback_id, candidate.client_status or "wait")

    ok, msg, message_id = send_html_message(channel.external_id, text, reply_markup=reply_markup)
    if not ok or not message_id:
        raise MessagingError(msg or "Ошибка отправки", 502)

    post = models.MessagingPost(
        channel_id=channel.id,
        candidate_id=candidate.id,
        vacancy_id=vacancy.id,
        kind=kind,
        external_message_id=str(message_id),
        text_snapshot=text,
        payload={
            "provider": "telegram",
            "chat_id": channel.external_id,
            "tg_callback_id": callback_id,
            "has_buttons": True,
        },
    )
    db.add(post)
    db.flush()

    stage_changed = False
    if move_to_client_review and candidate.hr_stage != CLIENT_ZONE_ENTRY_STAGE:
        apply_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE, note="отправка в Telegram (v2)")
        stage_changed = True

    db.commit()
    db.refresh(post)
    db.refresh(candidate)

    return {
        "ok": True,
        "message": msg,
        "post_id": str(post.id),
        "external_message_id": post.external_message_id,
        "channel_id": str(channel.id),
        "chat_id": channel.external_id,
        "stage_changed": stage_changed,
        "hr_stage": candidate.hr_stage,
        "tg_callback_id": callback_id,
        "inbound_enabled": bool(settings.messaging_inbound_enabled),
    }


def list_candidate_posts(db: Session, candidate_id) -> list[models.MessagingPost]:
    return list(
        db.scalars(
            select(models.MessagingPost)
            .where(models.MessagingPost.candidate_id == candidate_id)
            .order_by(models.MessagingPost.created_at.desc())
        ).all()
    )


def parse_inbound_webhook(provider: str, payload: dict, db: Session | None = None) -> list[dict[str, Any]]:
    """
    Process Telegram webhook/update payload when inbound is enabled.
    If disabled, acknowledge shape only (Streamlit bot keeps polling).
    """
    settings = get_settings()
    events: list[dict[str, Any]] = []
    if provider != "telegram":
        return events
    if not isinstance(payload, dict):
        return events

    if not settings.messaging_inbound_enabled:
        if payload.get("callback_query"):
            events.append(
                {
                    "type": "telegram.callback_query",
                    "handled": False,
                    "note": "MESSAGING_INBOUND_ENABLED=false — Streamlit bot owns polling",
                }
            )
        elif payload.get("message"):
            events.append(
                {
                    "type": "telegram.message",
                    "handled": False,
                    "note": "MESSAGING_INBOUND_ENABLED=false — Streamlit bot owns polling",
                }
            )
        return events

    if db is None:
        events.append(
            {
                "type": "error",
                "handled": False,
                "note": "db session required when inbound enabled",
            }
        )
        return events

    from app.services.messaging.inbound import process_telegram_update

    return process_telegram_update(db, payload)
