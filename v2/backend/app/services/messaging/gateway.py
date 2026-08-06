"""Messaging Gateway orchestration (outbound + inbound slice 2)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.app_settings import client_notify_has, get_bitrix, get_client_notify
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
        "provider": "telegram",
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


def _short_channel_error(channel: str, message: str) -> str:
    m = (message or "").strip()
    low = m.lower()
    if channel == "telegram" and ("timed out" in low or "connecttimeout" in low.replace(" ", "")):
        return "Telegram: нет связи с api.telegram.org (таймаут)."
    if channel == "bitrix" and "public_api_base" in low:
        return "Bitrix: не задан или недоступен публичный URL API (ngrok должен быть запущен)."
    if len(m) > 120:
        return m[:117] + "…"
    return m


def _format_client_notify_message(
    results: list[dict[str, Any]], errors: list[str]
) -> str:
    lines: list[str] = []
    for r in results:
        text = str(r.get("message") or "").strip()
        if text:
            lines.append(text)
    if errors:
        if lines:
            lines.append("")
        lines.append("Не доставлено:")
        for err in errors:
            lines.append(f"• {err}")
    return "\n".join(lines) if lines else "Отправлено"


def send_candidate_to_client(
    db: Session,
    candidate: models.Candidate,
    *,
    move_to_client_review: bool = True,
) -> dict[str, Any]:
    """
    Dispatch send-to-chat according to client_notify.channels (telegram / bitrix).
    Channels run in parallel (separate DB sessions). Stage move at most once on main row.
    """
    notify = get_client_notify()
    channels = [c for c in (notify.get("channels") or []) if c in ("telegram", "bitrix")]
    if not channels:
        raise MessagingError("Не выбран ни один канал уведомления заказчика", 400)

    bitrix_cfg = get_bitrix()
    candidate_id: UUID = candidate.id
    work_channels: list[str] = []
    for ch in channels:
        if ch == "telegram" and client_notify_has("telegram"):
            work_channels.append("telegram")
        elif ch == "bitrix" and client_notify_has("bitrix") and bitrix_cfg.get("enabled"):
            work_channels.append("bitrix")

    skipped_errors: list[str] = []
    if "bitrix" in channels and not bitrix_cfg.get("enabled"):
        skipped_errors.append("Bitrix: отключён в настройках (bitrix.enabled=false)")
    for ch in channels:
        if ch not in ("telegram", "bitrix"):
            skipped_errors.append(f"Неизвестный канал: {ch}")

    results: list[dict[str, Any]] = []
    errors: list[str] = list(skipped_errors)

    def _run_telegram() -> tuple[str, dict[str, Any] | None, str | None]:
        from app.db.session import SessionLocal

        session = SessionLocal()
        try:
            row = session.get(models.Candidate, candidate_id)
            if not row:
                return "telegram", None, "Telegram: кандидат не найден"
            r = send_candidate_card(session, row, move_to_client_review=False)
            return "telegram", r, None
        except MessagingError as exc:
            session.rollback()
            return "telegram", None, _short_channel_error("telegram", exc.message)
        finally:
            session.close()

    def _run_bitrix() -> tuple[str, dict[str, Any] | None, str | None]:
        from app.db.session import SessionLocal
        from app.services.bitrix.client import BitrixError
        from app.services.bitrix.outbound import send_candidate_bitrix_task

        session = SessionLocal()
        try:
            row = session.get(models.Candidate, candidate_id)
            if not row:
                return "bitrix", None, "Bitrix: кандидат не найден"
            r = send_candidate_bitrix_task(session, row, move_to_client_review=False)
            return "bitrix", r, None
        except BitrixError as exc:
            session.rollback()
            return "bitrix", None, _short_channel_error("bitrix", exc.message)
        finally:
            session.close()

    runners = {
        "telegram": _run_telegram,
        "bitrix": _run_bitrix,
    }
    if work_channels:
        with ThreadPoolExecutor(max_workers=min(2, len(work_channels))) as pool:
            futures = {pool.submit(runners[ch]): ch for ch in work_channels if ch in runners}
            for fut in as_completed(futures):
                _ch, r, err = fut.result()
                if r:
                    results.append(r)
                if err:
                    errors.append(err)

    if not results:
        detail = "\n".join(errors) if errors else "Нет каналов для отправки"
        raise MessagingError(detail, 400)

    db.refresh(candidate)
    stage_changed = False
    if move_to_client_review and candidate.hr_stage != CLIENT_ZONE_ENTRY_STAGE:
        apply_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE, note="отправка заказчику")
        stage_changed = True
        db.commit()
        db.refresh(candidate)

    # Prefer Bitrix post as primary when both succeeded.
    primary = results[0]
    for r in results:
        if r.get("provider") == "bitrix":
            primary = r
            break

    return {
        "ok": True,
        "message": _format_client_notify_message(results, errors),
        "post_id": str(primary.get("post_id") or ""),
        "external_message_id": str(primary.get("external_message_id") or ""),
        "channel_id": str(primary.get("channel_id") or ""),
        "chat_id": str(primary.get("chat_id") or ""),
        "stage_changed": stage_changed,
        "hr_stage": candidate.hr_stage,
        "results": results,
        "errors": errors,
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
    Process provider webhook/update payload when inbound is enabled.
    Telegram: gated by MESSAGING_INBOUND_ENABLED.
    Bitrix: gated by bitrix.enabled in app_settings.
    """
    settings = get_settings()
    events: list[dict[str, Any]] = []
    provider_l = (provider or "").strip().lower()

    if provider_l in ("bitrix", "bitrix24"):
        if db is None:
            return [
                {
                    "type": "error",
                    "handled": False,
                    "note": "db session required for bitrix inbound",
                }
            ]
        from app.services.bitrix.inbound import process_bitrix_webhook

        return process_bitrix_webhook(db, payload or {})

    if provider_l != "telegram":
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
