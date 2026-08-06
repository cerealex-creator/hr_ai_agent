"""Create Bitrix24 task for a candidate (client notify)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db import models
from app.services.app_settings import get_bitrix, resolve_bitrix_responsible_id
from app.services.bitrix.client import BitrixError, create_task
from app.services.bitrix.tokens import (
    STATUS_ICONS,
    STATUS_LABELS,
    build_decide_url,
    public_api_base,
)
from app.services.candidate_fields import candidate_public_fields
from app.services.candidate_write import CLIENT_ZONE_ENTRY_STAGE, apply_hr_stage
from app.services.messaging.client_apply import clear_client_meeting
from app.services.messaging.card_html import validate_send_fields
from app.services.yandex_public import yandex_link_for_display


def _tz() -> ZoneInfo:
    return ZoneInfo("Europe/Moscow")


def _deadline_iso(hours: int) -> str:
    when = datetime.now(_tz()) + timedelta(hours=max(1, hours))
    return when.replace(microsecond=0).isoformat()


def _bb_esc(text: str) -> str:
    """Keep user text from breaking BB-code tags."""
    return (text or "").replace("[", "(").replace("]", ")")


def _bb_link(url: str | None, label: str) -> str | None:
    u = (url or "").strip()
    if not u:
        return None
    display = yandex_link_for_display(u) or u
    return f"[url={display}]{_bb_esc(label)}[/url]"


def build_task_description(
    *,
    name: str,
    vacancy_title: str,
    resume_link: str | None,
    hh_resume_link: str | None,
    video_link: str | None,
    portfolio_link: str | None,
    task_link: str | None,
    hr_comment: str | None,
    candidate_id: str,
) -> str:
    lines = [
        f"[b]Новый кандидат:[/b] {_bb_esc(name)}",
        f"[b]Вакансия:[/b] {_bb_esc(vacancy_title)}",
        "",
    ]
    from app.services.bitrix.task_sync import initial_decision_status_block

    lines.extend([initial_decision_status_block(), ""])

    material_rows: list[str] = []
    for label, url in (
        ("📄 Резюме PDF", resume_link),
        ("📄 Резюме HH", hh_resume_link if not (resume_link or "").strip() else None),
        ("🎥 Запись собеседования", video_link),
        ("🎨 Портфолио", portfolio_link),
        ("✅ Задание", task_link),
    ):
        row = _bb_link(url, label)
        if row:
            material_rows.append(row)
    if material_rows:
        lines.append("[b]Материалы[/b]")
        lines.extend(material_rows)
        lines.append("")

    comment = (hr_comment or "").strip()
    if comment:
        lines.extend(["[b]Комментарий HR[/b]", _bb_esc(comment), ""])

    lines.extend(["[b]Ваше решение[/b]", "Выберите один вариант (откроется в браузере):", ""])

    any_decide = False
    for key in ("ready", "think", "reject", "offer"):
        url = build_decide_url(candidate_id=candidate_id, status_key=key)
        icon = STATUS_ICONS.get(key) or ""
        label = STATUS_LABELS.get(key) or key
        button_label = f"{icon} {label}".strip()
        if url:
            lines.append(_bb_link(url, button_label) or f"• {button_label}")
            any_decide = True
        else:
            lines.append(f"• {button_label} — [i]ссылка недоступна[/i]")

    if not any_decide:
        lines.extend(
            [
                "",
                "[color=red]⚠ Не задан публичный URL API (public_api_base) — "
                "заказчик не сможет выбрать статус.[/color]",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "[i]Для «Подумать» и «Отказ» после перехода укажите краткую причину.[/i]",
            ]
        )

    lines.extend(["", "[i]HR AI Agent[/i]"])
    return "\n".join(lines)


def ensure_bitrix_channel(db: Session, vacancy: models.Vacancy) -> models.MessagingChannel:
    """One logical Bitrix channel per vacancy (external_id = vacancy id)."""
    ext = f"vacancy:{vacancy.id}"
    from sqlalchemy import select

    existing = db.scalar(
        select(models.MessagingChannel).where(
            models.MessagingChannel.provider == "bitrix",
            models.MessagingChannel.external_id == ext,
        )
    )
    if existing:
        return existing
    ch = models.MessagingChannel(
        provider="bitrix",
        external_id=ext,
        client_id=vacancy.client_id,
        name=(vacancy.title or "").strip() or f"Bitrix · vacancy {vacancy.id}",
        metadata_json={"source": "bitrix_outbound", "vacancy_ids": [vacancy.id]},
    )
    db.add(ch)
    db.flush()
    return ch


def send_candidate_bitrix_task(
    db: Session,
    candidate: models.Candidate,
    *,
    move_to_client_review: bool = True,
    kind: str = "primary",
) -> dict[str, Any]:
    cfg = get_bitrix()
    if not cfg.get("enabled"):
        raise BitrixError("Bitrix отключён в настройках", 403)
    if not (cfg.get("incoming_webhook_url") or "").strip():
        raise BitrixError("Не задан Bitrix incoming webhook URL", 400)

    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy:
        raise BitrixError("Вакансия не найдена", 404)

    responsible = resolve_bitrix_responsible_id(vacancy.payload)
    if not responsible:
        raise BitrixError(
            "Не задан ответственный Bitrix (default_responsible_id или vacancy.payload.bitrix_responsible_id)",
            400,
        )
    if not responsible.isdigit():
        raise BitrixError("responsible_id должен быть числовым ID пользователя Bitrix24", 400)

    fields_pub = candidate_public_fields(candidate.payload)
    missing = validate_send_fields(
        name=candidate.name,
        resume_link=fields_pub.get("resume_link"),
        hh_resume_link=fields_pub.get("hh_resume_link"),
    )
    if missing:
        raise BitrixError("Заполните: " + ", ".join(missing), 400)

    if not public_api_base():
        raise BitrixError(
            "Не задан public_api_base (публичный HTTPS URL API) — нужны ссылки решения в задаче",
            400,
        )

    # New Bitrix task = new client evaluation round; drop stale meeting/status.
    clear_client_meeting(candidate)
    if (candidate.client_status or "wait") != "wait":
        candidate.client_status = "wait"
        candidate.status_updated_at = datetime.now(ZoneInfo("UTC")).replace(microsecond=0).isoformat()

    hours = int(cfg.get("task_deadline_hours") or 24)
    description = build_task_description(
        name=candidate.name,
        vacancy_title=vacancy.title or "",
        resume_link=fields_pub.get("resume_link"),
        hh_resume_link=fields_pub.get("hh_resume_link"),
        video_link=fields_pub.get("video_link"),
        portfolio_link=fields_pub.get("portfolio_link"),
        task_link=fields_pub.get("task_link"),
        hr_comment=(candidate.payload or {}).get("hr_comment"),
        candidate_id=str(candidate.id),
    )

    task_fields: dict[str, Any] = {
        "TITLE": f"Кандидат: {candidate.name} · {vacancy.title or 'вакансия'}",
        "DESCRIPTION": description,
        "DESCRIPTION_IN_BBCODE": "Y",
        "RESPONSIBLE_ID": int(responsible),
        "DEADLINE": _deadline_iso(hours),
        "PRIORITY": "1",
    }

    task_id = create_task(task_fields)
    channel = ensure_bitrix_channel(db, vacancy)

    post = models.MessagingPost(
        channel_id=channel.id,
        candidate_id=candidate.id,
        vacancy_id=vacancy.id,
        kind=kind,
        external_message_id=str(task_id),
        text_snapshot=description,
        payload={
            "provider": "bitrix",
            "task_id": str(task_id),
            "responsible_id": responsible,
            "deadline_hours": hours,
            "decide_links": True,
            "public_api_base": public_api_base(),
            "description_bbcode": True,
        },
    )
    db.add(post)
    db.flush()

    stage_changed = False
    if move_to_client_review and candidate.hr_stage != CLIENT_ZONE_ENTRY_STAGE:
        apply_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE, note="отправка в Bitrix24 (задача)")
        stage_changed = True

    db.commit()
    db.refresh(post)
    db.refresh(candidate)

    return {
        "ok": True,
        "provider": "bitrix",
        "message": f"Задача Bitrix24 создана (#{task_id})",
        "post_id": str(post.id),
        "external_message_id": str(task_id),
        "channel_id": str(channel.id),
        "chat_id": channel.external_id,
        "stage_changed": stage_changed,
        "hr_stage": candidate.hr_stage,
        "task_id": str(task_id),
    }
