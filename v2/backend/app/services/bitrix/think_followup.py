"""Bitrix follow-up when decision task closed while candidate is still «Подумать»."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.app_settings import get_bitrix, resolve_bitrix_responsible_id
from app.services.bitrix.client import BitrixError, create_task, get_task
from app.services.bitrix.outbound import build_task_description, ensure_bitrix_channel
from app.services.bitrix.tokens import public_api_base
from app.services.candidate_fields import candidate_public_fields

logger = logging.getLogger(__name__)

THINK_FOLLOWUP_BUSINESS_DAYS = 3


def _tz() -> ZoneInfo:
    return ZoneInfo("Europe/Moscow")


def _now() -> datetime:
    return datetime.now(_tz())


def add_business_days(start: datetime, days: int) -> datetime:
    """Add N business days (Mon–Fri), keeping time-of-day."""
    if days <= 0:
        return start
    local = start.astimezone(_tz())
    d = local.date()
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return datetime.combine(d, local.time(), tzinfo=_tz()).replace(microsecond=0)


def _think_state(candidate: models.Candidate) -> dict[str, Any]:
    raw = (candidate.payload or {}).get("bitrix_think")
    return dict(raw) if isinstance(raw, dict) else {}


def _save_think_state(candidate: models.Candidate, state: dict[str, Any]) -> None:
    payload = dict(candidate.payload or {})
    payload["bitrix_think"] = state
    candidate.payload = payload
    flag_modified(candidate, "payload")


def clear_think_state(candidate: models.Candidate) -> None:
    payload = dict(candidate.payload or {})
    if "bitrix_think" in payload:
        payload.pop("bitrix_think", None)
        candidate.payload = payload
        flag_modified(candidate, "payload")


def is_task_completed(task: dict[str, Any]) -> bool:
    status = task.get("status")
    if status is None:
        status = task.get("STATUS")
    return str(status).strip() == "5"


def register_think_decision_task(
    db: Session,
    candidate: models.Candidate,
    *,
    task_id: str,
) -> None:
    """Track which Bitrix task was open when client chose «Подумать»."""
    tid = str(task_id or "").strip()
    if not tid:
        return
    _save_think_state(
        candidate,
        {
            "tracked_task_id": tid,
            "closed_at": None,
            "followup_at": None,
        },
    )


def _latest_bitrix_decision_post(db: Session, candidate_id) -> models.MessagingPost | None:
    posts = list(
        db.scalars(
            select(models.MessagingPost)
            .where(
                models.MessagingPost.candidate_id == candidate_id,
                models.MessagingPost.kind.in_(("primary", "think_followup")),
            )
            .order_by(models.MessagingPost.created_at.desc())
            .limit(20)
        ).all()
    )
    for p in posts:
        if str((p.payload or {}).get("provider") or "") == "bitrix":
            return p
    return posts[0] if posts else None


def schedule_think_followup(candidate: models.Candidate, *, closed_at: datetime | None = None) -> str:
    when = closed_at or _now()
    followup = add_business_days(when, THINK_FOLLOWUP_BUSINESS_DAYS)
    state = _think_state(candidate)
    state["closed_at"] = when.isoformat()
    state["followup_at"] = followup.isoformat()
    _save_think_state(candidate, state)
    return followup.isoformat()


def handle_decision_task_closed(
    db: Session,
    candidate: models.Candidate,
    *,
    task_id: str,
) -> dict[str, Any] | None:
    """Task completed while candidate still «Подумать» → schedule follow-up in 3 business days."""
    if (candidate.client_status or "").strip() != "think":
        return None
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy or not vacancy.active:
        return None

    state = _think_state(candidate)
    tracked = str(state.get("tracked_task_id") or "").strip()
    tid = str(task_id).strip()
    if tracked and tracked != tid:
        return None
    if state.get("followup_at"):
        return None

    followup_at = schedule_think_followup(candidate)
    db.add(candidate)
    db.commit()
    return {
        "type": "bitrix.think_scheduled",
        "candidate_id": str(candidate.id),
        "task_id": tid,
        "followup_at": followup_at,
    }


def _build_followup_description(candidate: models.Candidate, vacancy: models.Vacancy) -> str:
    fields_pub = candidate_public_fields(candidate.payload)
    base = build_task_description(
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
    header = (
        "[b]Принять решение[/b]\n"
        "Заказчик ранее выбрал «Подумать». Срок размышления истёк — нужно финальное решение.\n\n"
    )
    return header + base


def create_think_followup_task(db: Session, candidate: models.Candidate) -> dict[str, Any] | None:
    cfg = get_bitrix()
    if not cfg.get("enabled"):
        return None
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy or not vacancy.active:
        clear_think_state(candidate)
        return None
    if (candidate.client_status or "").strip() != "think":
        clear_think_state(candidate)
        return None

    responsible = resolve_bitrix_responsible_id(vacancy.payload)
    if not responsible or not responsible.isdigit():
        logger.warning("think followup: no responsible for candidate %s", candidate.id)
        return None
    if not public_api_base():
        logger.warning("think followup: no public_api_base")
        return None

    hours = int(cfg.get("task_deadline_hours") or 24)
    description = _build_followup_description(candidate, vacancy)
    deadline = add_business_days(_now(), 1).isoformat()

    fields: dict[str, Any] = {
        "TITLE": f"Принять решение: {candidate.name} · {vacancy.title or 'вакансия'}",
        "DESCRIPTION": description,
        "DESCRIPTION_IN_BBCODE": "Y",
        "RESPONSIBLE_ID": int(responsible),
        "DEADLINE": deadline,
        "PRIORITY": "1",
    }
    try:
        task_id = create_task(fields)
    except BitrixError as exc:
        logger.warning("think followup task failed: %s", exc.message)
        return None

    channel = ensure_bitrix_channel(db, vacancy)
    db.add(
        models.MessagingPost(
            channel_id=channel.id,
            candidate_id=candidate.id,
            vacancy_id=vacancy.id,
            kind="think_followup",
            external_message_id=str(task_id),
            text_snapshot=description,
            payload={
                "provider": "bitrix",
                "task_id": str(task_id),
                "think_followup": True,
            },
        )
    )
    _save_think_state(
        candidate,
        {
            "tracked_task_id": str(task_id),
            "closed_at": None,
            "followup_at": None,
        },
    )
    db.add(candidate)
    db.commit()
    return {
        "type": "bitrix.think_followup_created",
        "candidate_id": str(candidate.id),
        "task_id": str(task_id),
    }


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz())
        return dt.astimezone(_tz())
    except (ValueError, TypeError):
        return None


def run_think_followup_tick(db: Session) -> dict[str, int]:
    """Poll think candidates: detect closed tasks, create follow-up tasks on schedule."""
    cfg = get_bitrix()
    if not cfg.get("enabled"):
        return {"checked": 0, "scheduled": 0, "created": 0, "skipped": 0}

    now = _now()
    stats = {"checked": 0, "scheduled": 0, "created": 0, "skipped": 0}

    candidates = list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.client_status == "think").limit(500)
        ).all()
    )

    for cand in candidates:
        vacancy = db.get(models.Vacancy, cand.vacancy_id)
        if not vacancy or not vacancy.active:
            clear_think_state(cand)
            stats["skipped"] += 1
            continue

        state = _think_state(cand)
        followup_at = _parse_iso(state.get("followup_at"))
        if followup_at and followup_at <= now:
            result = create_think_followup_task(db, cand)
            if result:
                stats["created"] += 1
            continue

        if followup_at:
            continue

        tid = str(state.get("tracked_task_id") or "").strip()
        if not tid:
            post = _latest_bitrix_decision_post(db, cand.id)
            if post and (cand.client_status or "") == "think":
                tid = str(post.external_message_id or (post.payload or {}).get("task_id") or "")
                if tid:
                    register_think_decision_task(db, cand, task_id=tid)
                    db.commit()
            if not tid:
                stats["skipped"] += 1
                continue

        stats["checked"] += 1
        try:
            task = get_task(tid)
        except BitrixError:
            stats["skipped"] += 1
            continue

        if not is_task_completed(task):
            continue

        if state.get("closed_at"):
            continue

        handle_decision_task_closed(db, cand, task_id=tid)
        stats["scheduled"] += 1

    return stats


def run_bitrix_maintenance_tick(db: Session) -> dict[str, Any]:
    think = run_think_followup_tick(db)
    return {"think_followup": think}
