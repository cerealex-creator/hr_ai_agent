"""Bitrix task on scheduled client meeting (deadline = meeting time)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db import models
from app.services.app_settings import resolve_bitrix_responsible_id
from app.services.bitrix.client import BitrixError, create_task
from app.services.bitrix.outbound import ensure_bitrix_channel


def _tz() -> ZoneInfo:
    return ZoneInfo("Europe/Moscow")


def _meeting_start_iso(date_s: str, time_s: str) -> str:
    dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M").replace(tzinfo=_tz())
    return dt.replace(microsecond=0).isoformat()


def _format_label(remote: bool, office: bool) -> str:
    if remote and office:
        return "онлайн / офис"
    if remote:
        return "онлайн"
    if office:
        return "в офисе"
    return "не указан"


def create_meeting_bitrix_task(
    db: Session,
    candidate: models.Candidate,
    *,
    meeting_date: str,
    meeting_time: str,
    remote_interview: bool = False,
    office_interview: bool = True,
) -> str | None:
    """Create Bitrix reminder task at meeting date/time. Returns task id or None if skipped."""
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy:
        return None
    responsible = resolve_bitrix_responsible_id(vacancy.payload)
    if not responsible or not responsible.isdigit():
        return None

    start_iso = _meeting_start_iso(meeting_date, meeting_time)
    display_date = datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    fmt = _format_label(remote_interview, office_interview)

    description = "\n".join(
        [
            f"[b]Встреча с кандидатом[/b] {candidate.name}",
            f"[b]Вакансия:[/b] {vacancy.title or '—'}",
            f"[b]Когда:[/b] {display_date} {meeting_time} ({fmt})",
            "",
        ]
    )
    from app.services.bitrix.task_sync import initial_meeting_status_block

    description += "\n" + initial_meeting_status_block() + "\n\n"
    description += (
        "[i]Напоминание Bitrix24 сработает по сроку задачи. "
        "Подтвердите встречу с кандидатом в HR AI Agent.[/i]\n\n"
        "[i]HR AI Agent[/i]"
    )

    fields: dict[str, Any] = {
        "TITLE": f"Встреча: {candidate.name} · {vacancy.title or 'вакансия'}",
        "DESCRIPTION": description,
        "DESCRIPTION_IN_BBCODE": "Y",
        "RESPONSIBLE_ID": int(responsible),
        "DEADLINE": start_iso,
        "START_DATE_PLAN": start_iso,
        "PRIORITY": "2",
    }
    try:
        task_id = create_task(fields)
    except BitrixError:
        raise

    channel = ensure_bitrix_channel(db, vacancy)
    db.add(
        models.MessagingPost(
            channel_id=channel.id,
            candidate_id=candidate.id,
            vacancy_id=vacancy.id,
            kind="meeting",
            external_message_id=str(task_id),
            text_snapshot=description,
            payload={
                "provider": "bitrix",
                "task_id": str(task_id),
                "meeting_date": meeting_date,
                "meeting_time": meeting_time,
                "remote": remote_interview,
                "office": office_interview,
            },
        )
    )
    payload = dict(candidate.payload or {})
    payload["bitrix_meeting_task_id"] = str(task_id)
    candidate.payload = payload
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(candidate, "payload")
    return str(task_id)
