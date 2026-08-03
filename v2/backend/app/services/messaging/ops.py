"""Outbound ops: remind, digest, instruction, extra materials, refresh card."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.messaging.inbound import find_post_for_candidate, refresh_card_message
from app.services.messaging.reminders import (
    build_manual_decide_reminder,
    build_manual_evaluate_reminder,
    format_vacancy_digest_html,
)
from app.services.messaging.telegram_provider import send_html_message

CARD_LINK_FIELDS = (
    ("task_link", "Задание"),
    ("resume_link", "Резюме PDF"),
    ("hh_resume_link", "Резюме HH"),
    ("video_link", "Запись"),
    ("portfolio_link", "Портфолио"),
)


def _esc(text: Any) -> str:
    return html.escape(str(text or "").strip())


def _telegram_message_link(chat_id: str | int | None, message_id: str | int | None) -> str | None:
    if chat_id is None or message_id is None:
        return None
    mid = str(message_id).strip()
    if not mid.isdigit():
        return None
    raw = str(chat_id).strip()
    if raw.startswith("-100") and raw[4:].isdigit():
        return f"https://t.me/c/{raw[4:]}/{mid}"
    return None


def primary_post(db: Session, candidate: models.Candidate) -> models.MessagingPost | None:
    vac = db.get(models.Vacancy, candidate.vacancy_id)
    chat_id = vac.chat_id if vac else None
    return find_post_for_candidate(db, candidate.id, chat_id)


def _days_since_status(candidate: models.Candidate) -> int | None:
    raw = (candidate.status_updated_at or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    return max(0, delta.days)


def _diff_card_fields(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> list[str]:
    b = before or {}
    a = after or {}
    lines: list[str] = []
    for key, label in CARD_LINK_FIELDS:
        old = str(b.get(key) or "").strip()
        new = str(a.get(key) or "").strip()
        if old == new:
            continue
        if not old and new:
            lines.append(f"➕ {label}: добавлено")
        elif old and not new:
            lines.append(f"➖ {label}: удалено")
        else:
            lines.append(f"🔄 {label}: обновлено")
    return lines


def refresh_candidate_telegram(
    db: Session,
    candidate: models.Candidate,
    *,
    notify: bool = False,
    changes: list[str] | None = None,
    before_payload: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    post = primary_post(db, candidate)
    if not post:
        return False, "Нет карточки в чате"
    ok, msg = refresh_card_message(db, candidate, post, mode="auto")
    if not ok:
        return False, msg

    notice = ""
    if notify:
        vac = db.get(models.Vacancy, candidate.vacancy_id)
        chat_id = vac.chat_id if vac else None
        change_lines = list(changes or [])
        if not change_lines and before_payload is not None:
            change_lines = _diff_card_fields(before_payload, candidate.payload or {})
        if not change_lines:
            change_lines = ["Карточка обновлена актуальными данными"]
        link = _telegram_message_link(chat_id, post.external_message_id)
        body_lines = [
            f"🔄 <b>Обновлены данные по кандидату</b> {_esc(candidate.name)}",
            "",
            *[f"• {_esc(x)}" for x in change_lines],
        ]
        if link:
            body_lines.append("")
            body_lines.append(
                f'<a href="{html.escape(link, quote=True)}">Открыть карточку в чате</a>'
            )
        else:
            body_lines.append("")
            body_lines.append("<i>Карточка выше ↑</i>")
        n_ok, n_msg, _ = send_html_message(
            chat_id or "",
            "\n".join(body_lines),
            reply_to_message_id=post.external_message_id,
        )
        notice = n_msg if n_ok else f"карточка обновлена, уведомление: {n_msg}"

    db.commit()
    return True, notice or msg


def send_manual_reminder(
    db: Session, candidate: models.Candidate, *, kind: str = "evaluate"
) -> tuple[bool, str]:
    vac = db.get(models.Vacancy, candidate.vacancy_id)
    if not vac or not (vac.chat_id or "").strip():
        return False, "Нет chat_id у вакансии"
    post = primary_post(db, candidate)
    if not post:
        return False, "Нет карточки в чате"
    days = _days_since_status(candidate)
    if kind == "decide":
        text = build_manual_decide_reminder(
            candidate.name, vac.title or "", days_waiting=days
        )
    else:
        text = build_manual_evaluate_reminder(
            candidate.name, vac.title or "", days_waiting=days
        )
    ok, msg, _ = send_html_message(
        vac.chat_id,
        text,
        reply_to_message_id=post.external_message_id,
    )
    return ok, msg


def send_vacancy_digest(db: Session, vacancy: models.Vacancy) -> tuple[bool, str]:
    if not (vacancy.chat_id or "").strip():
        return False, "Нет chat_id"
    text = format_vacancy_digest_html([vacancy], db)
    ok, msg, _ = send_html_message(vacancy.chat_id, text)
    return ok, msg


def send_client_instruction(db: Session, chat_id: str, text: str | None = None) -> tuple[bool, str]:
    body = (text or "").strip() or (
        "<b>Инструкция для заказчика</b>\n\n"
        "1. Откройте карточку кандидата в этом чате.\n"
        "2. Выберите статус кнопками.\n"
        "3. Для «Подумать» / «Отказ» напишите короткую причину reply на карточку.\n"
        "4. Для встречи укажите дату, время и формат."
    )
    ok, msg, _ = send_html_message(chat_id, body)
    return ok, msg


def send_extra_material(
    db: Session,
    candidate: models.Candidate,
    *,
    title: str,
    url: str,
) -> tuple[bool, str]:
    vac = db.get(models.Vacancy, candidate.vacancy_id)
    if not vac or not (vac.chat_id or "").strip():
        return False, "Нет chat_id"
    post = primary_post(db, candidate)
    if not post:
        return False, "Нет карточки в чате"
    title_c = (title or "Материал").strip()
    url_c = (url or "").strip()
    if not url_c:
        return False, "Нужна ссылка"
    text = (
        f"<b>📎 {_esc(title_c)}</b>\n"
        f"Кандидат: <b>{_esc(candidate.name)}</b>\n"
        f'<a href="{_esc(url_c)}">Открыть</a>'
    )
    ok, msg, mid = send_html_message(
        vac.chat_id,
        text,
        reply_to_message_id=post.external_message_id,
    )
    if not ok:
        return False, msg
    payload = dict(candidate.payload or {})
    materials = list(payload.get("extra_materials") or [])
    materials.append(
        {
            "title": title_c,
            "url": url_c,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "message_id": mid,
            "chat_id": vac.chat_id,
        }
    )
    payload["extra_materials"] = materials
    candidate.payload = payload
    flag_modified(candidate, "payload")
    if mid:
        ch = db.get(models.MessagingChannel, post.channel_id)
        if ch:
            db.add(
                models.MessagingPost(
                    channel_id=ch.id,
                    candidate_id=candidate.id,
                    vacancy_id=candidate.vacancy_id,
                    kind="extra",
                    external_message_id=str(mid),
                    text_snapshot=text,
                    payload={"chat_id": vac.chat_id, "title": title_c, "url": url_c},
                )
            )
    db.commit()
    return True, "Материал отправлен"


def snapshot_card_payload(candidate: models.Candidate) -> dict[str, Any]:
    p = candidate.payload or {}
    return {k: p.get(k) for k, _ in CARD_LINK_FIELDS}
