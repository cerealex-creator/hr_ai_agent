"""Web client zone (D2): token URL access, minimal decide actions."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.messaging.client_apply import apply_client_update
from app.services.messaging.keyboards import interview_format_flags
from app.services.stats_service import CLIENT_ZONE_STAGES
from app.services.tenancy import resolve_client_zone_root, root_company_scope_ids

# Approve / think / reject (+ meeting on ready)
ZONE_ACTIONS = frozenset({"ready", "think", "reject"})
ACTIONABLE_STATUSES = frozenset({"wait", "think"})


def _parse_meeting(
    meeting_date: str | None,
    meeting_time: str | None,
    meeting_format: str | None,
) -> tuple[str, str, bool, bool]:
    date_s = (meeting_date or "").strip()
    time_s = (meeting_time or "").strip()
    if not date_s or not time_s:
        raise HTTPException(status_code=400, detail="Укажите дату и время встречи")
    try:
        datetime.strptime(date_s, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректная дата") from exc
    try:
        datetime.strptime(time_s, "%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректное время") from exc
    fmt = (meeting_format or "o").strip() or "o"
    if fmt not in ("o", "r", "b"):
        fmt = "o"
    remote, office = interview_format_flags(fmt)
    return date_s, time_s, remote, office


def zone_context(db: Session, token: str) -> tuple[models.Client, set[int]]:
    root = resolve_client_zone_root(db, token)
    return root, root_company_scope_ids(db, root)


def list_zone_candidates(db: Session, token: str) -> dict[str, Any]:
    root, scope = zone_context(db, token)
    vacancies = list(
        db.scalars(
            select(models.Vacancy).where(
                models.Vacancy.client_id.in_(scope),
                models.Vacancy.active.is_(True),
            )
        ).all()
    )
    vac_map = {v.id: v for v in vacancies}
    if not vac_map:
        return {
            "company": {"id": root.id, "name": root.name},
            "candidates": [],
        }

    clients = {
        c.id: c.name
        for c in db.scalars(select(models.Client).where(models.Client.id.in_(scope))).all()
    }
    rows = list(
        db.scalars(
            select(models.Candidate).where(
                models.Candidate.vacancy_id.in_(list(vac_map.keys())),
                models.Candidate.hr_stage.in_(CLIENT_ZONE_STAGES),
            )
        ).all()
    )
    # Actionable first (wait/think), then recent decided
    actionable: list[dict] = []
    others: list[dict] = []
    for c in rows:
        vac = vac_map.get(c.vacancy_id)
        if not vac:
            continue
        payload = c.payload or {}
        item = {
            "id": str(c.id),
            "name": c.name or "Без имени",
            "vacancy_id": c.vacancy_id,
            "vacancy_title": vac.title,
            "client_id": vac.client_id,
            "client_name": clients.get(vac.client_id) if vac.client_id else root.name,
            "hr_stage": c.hr_stage,
            "client_status": c.client_status or "wait",
            "ai_score": payload.get("ai_score"),
            "ai_comment": (str(payload.get("ai_comment") or "")[:800] or None),
            "client_comment": (str(payload.get("client_comment") or "")[:500] or None),
            "office_interview_date": str(payload.get("office_interview_date") or "") or None,
            "office_interview_time": str(payload.get("office_interview_time") or "") or None,
            "actionable": (c.client_status or "wait") in ACTIONABLE_STATUSES,
        }
        if item["actionable"]:
            actionable.append(item)
        else:
            others.append(item)
    actionable.sort(key=lambda x: (x["name"] or "").casefold())
    others.sort(key=lambda x: (x["name"] or "").casefold())
    return {
        "company": {"id": root.id, "name": root.name},
        "candidates": actionable + others[:30],
    }


def apply_zone_decision(
    db: Session,
    token: str,
    candidate_id: str | UUID,
    *,
    status_key: str,
    comment: str | None = None,
    meeting_date: str | None = None,
    meeting_time: str | None = None,
    meeting_format: str | None = None,
) -> dict[str, Any]:
    root, scope = zone_context(db, token)
    status = (status_key or "").strip()
    if status not in ZONE_ACTIONS:
        raise HTTPException(status_code=400, detail="status: ready | think | reject")

    try:
        cid = candidate_id if isinstance(candidate_id, UUID) else UUID(str(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Candidate not found") from exc

    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy or vacancy.client_id not in scope:
        raise HTTPException(status_code=404, detail="Candidate not found")

    clean_comment = (comment or "").strip()
    if status in ("think", "reject") and not clean_comment:
        raise HTTPException(status_code=400, detail="Нужен комментарий")

    meeting_kwargs: dict[str, Any] = {}
    if status == "ready":
        date_s, time_s, remote, office = _parse_meeting(meeting_date, meeting_time, meeting_format)
        meeting_kwargs = {
            "office_interview_date": date_s,
            "office_interview_time": time_s,
            "remote_interview": remote,
            "office_interview": office,
        }
    elif status in ("think", "reject"):
        meeting_kwargs = {
            "office_interview_date": "",
            "office_interview_time": "",
            "remote_interview": False,
            "office_interview": False,
        }

    apply_client_update(
        candidate,
        status_key=status,
        comment=clean_comment or None,
        append_comment=True,
        actor="client_zone",
        actor_note=root.name,
        **meeting_kwargs,
    )
    db.commit()
    db.refresh(candidate)
    return {
        "ok": True,
        "candidate_id": str(candidate.id),
        "client_status": candidate.client_status,
        "hr_stage": candidate.hr_stage,
        "company_id": root.id,
    }
