"""Consulting projects: passport, folders, plan, registry, wave 1."""

from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, user_is_platform_owner
from app.db import consulting_models as m
from app.services.consulting_folders import (
    DEFAULT_BES,
    DEFAULT_DIRECTORATES,
    FOLDER_TEMPLATE,
    MILESTONES,
    PLAN_TEMPLATE,
    RESULT_CODES,
    parent_code,
)

ROW_STATUSES = ("draft", "recommended", "confirmed", "sent", "approved", "disputed")
MARKS = ("pending", "working", "doubtful", "rejected")

# Возврат заказчика не откатывает подтверждение.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("recommended", "confirmed"),
    "recommended": ("confirmed", "draft"),
    "confirmed": ("sent",),
    "sent": ("approved", "disputed"),
    "approved": ("sent",),
    "disputed": ("sent",),
}


def deny_if_not_owner(user: AuthUser) -> None:
    if user.is_demo:
        raise HTTPException(status_code=403, detail="Недоступно в демо-режиме")
    if not user_is_platform_owner(user):
        raise HTTPException(status_code=403, detail="Только для владельца платформы")


def traces_are_independent(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Независимость по полям, не по тексту ИИ."""
    if a.get("meeting_id") and a.get("meeting_id") == b.get("meeting_id"):
        return False
    if a.get("source_id") and a.get("source_id") == b.get("source_id"):
        return False
    type_diff = bool(a.get("source_type") and b.get("source_type") and a["source_type"] != b["source_type"])
    unit_diff = bool(a.get("unit_id") and b.get("unit_id") and a["unit_id"] != b["unit_id"])
    level_diff = bool(a.get("level") and b.get("level") and a["level"] != b["level"])
    return type_diff or unit_diff or level_diff


def apply_row_status(row: m.ConsultingRegistryRow, next_status: str) -> None:
    if next_status not in ROW_STATUSES:
        raise HTTPException(status_code=400, detail="Неизвестный статус")
    allowed = TRANSITIONS.get(row.status, ())
    if next_status == row.status:
        return
    if next_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя сменить статус «{row.status}» на «{next_status}»",
        )
    row.status = next_status


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def create_project(
    db: Session,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    customer_name: str,
    started_on: date | None = None,
) -> m.ConsultingProject:
    start = started_on or date.today()
    project = m.ConsultingProject(
        organization_id=org_id,
        title=title.strip() or "Диагностика",
        customer_name=customer_name.strip() or title.strip(),
        started_on=start,
        due_on=start + timedelta(days=27),
        plan_status="draft",
        payload={"results": {code: "empty" for code, _ in RESULT_CODES}},
    )
    db.add(project)
    db.flush()

    db.add(
        m.ConsultingMember(project_id=project.id, user_id=user_id, role="owner")
    )
    db.add(m.ConsultingUnit(project_id=project.id, kind="uk", name="Управляющая компания", sort_order=0))
    for i, name in enumerate(DEFAULT_DIRECTORATES, start=1):
        db.add(m.ConsultingUnit(project_id=project.id, kind="directorate", name=name, sort_order=i))
    for i, name in enumerate(DEFAULT_BES, start=1):
        db.add(m.ConsultingUnit(project_id=project.id, kind="be", name=name, sort_order=20 + i))

    for i, (code, title_m, offset) in enumerate(MILESTONES):
        db.add(
            m.ConsultingMilestone(
                project_id=project.id,
                code=code,
                title=title_m,
                due_on=start + timedelta(days=offset),
                sort_order=i,
            )
        )

    for i, (level, code, name, purpose) in enumerate(FOLDER_TEMPLATE):
        db.add(
            m.ConsultingFolder(
                project_id=project.id,
                code=code,
                name=name,
                purpose=purpose,
                level=level,
                parent_code=parent_code(code),
                sort_order=i,
            )
        )

    seed_plan_items(db, project)
    db.commit()
    db.refresh(project)
    return project


def seed_plan_items(db: Session, project: m.ConsultingProject) -> None:
    existing = db.scalar(
        select(func.count()).select_from(m.ConsultingPlanItem).where(
            m.ConsultingPlanItem.project_id == project.id
        )
    )
    if existing:
        return
    for i, (code, title) in enumerate(PLAN_TEMPLATE):
        db.add(
            m.ConsultingPlanItem(
                project_id=project.id,
                title=title,
                status="todo",
                sort_order=i,
                milestone_code=code,
            )
        )


def list_projects(db: Session, org_id: uuid.UUID) -> list[m.ConsultingProject]:
    return list(
        db.scalars(
            select(m.ConsultingProject)
            .where(m.ConsultingProject.organization_id == org_id)
            .order_by(m.ConsultingProject.created_at.desc())
        )
    )


def get_project(db: Session, org_id: uuid.UUID, project_id: uuid.UUID) -> m.ConsultingProject:
    row = db.get(m.ConsultingProject, project_id)
    if not row or row.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return row


def unit_out(u: m.ConsultingUnit) -> dict:
    return {"id": str(u.id), "kind": u.kind, "name": u.name, "sort_order": u.sort_order}


def person_out(p: m.ConsultingPerson) -> dict:
    return {
        "id": str(p.id),
        "full_name": p.full_name,
        "title": p.title,
        "unit_id": str(p.unit_id) if p.unit_id else None,
        "interview": p.interview,
        "survey": p.survey,
        "level": p.level,
    }


def milestone_out(x: m.ConsultingMilestone) -> dict:
    return {
        "id": str(x.id),
        "code": x.code,
        "title": x.title,
        "due_on": _iso(x.due_on),
        "sort_order": x.sort_order,
    }


def plan_item_out(x: m.ConsultingPlanItem) -> dict:
    return {
        "id": str(x.id),
        "title": x.title,
        "status": x.status,
        "sort_order": x.sort_order,
        "milestone_code": x.milestone_code,
    }


def folder_out(f: m.ConsultingFolder, file_count: int = 0) -> dict:
    return {
        "id": str(f.id),
        "code": f.code,
        "name": f.name,
        "purpose": f.purpose,
        "level": f.level,
        "parent_code": f.parent_code,
        "sort_order": f.sort_order,
        "file_count": file_count,
        "empty": file_count == 0,
    }


def source_out(s: m.ConsultingSource) -> dict:
    extracted = s.extracted_text or ""
    return {
        "id": str(s.id),
        "folder_id": str(s.folder_id) if s.folder_id else None,
        "kind": s.kind,
        "title": s.title,
        "url": s.url,
        "quoted_text": s.quoted_text,
        "mark": s.mark,
        "file_name": s.file_name,
        "has_quote": bool((s.quoted_text or "").strip()),
        "extracted_preview": extracted[:400],
        "extract_status": getattr(s, "extract_status", None) or "none",
        "space": getattr(s, "space", None) or "evidence",
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def registry_out(r: m.ConsultingRegistryRow) -> dict:
    payload = dict(r.payload or {})
    traces = list(payload.get("traces") or [])
    blocking = bool(payload.get("blocking_contradiction"))
    from app.services.consulting_coverage import confidence_from_traces

    return {
        "id": str(r.id),
        "source_id": str(r.source_id) if r.source_id else None,
        "title": r.title,
        "owner_name": r.owner_name,
        "unit_name": r.unit_name,
        "status": r.status,
        "action": r.action,
        "priority": r.priority,
        "target_system": r.target_system,
        "note": r.note,
        "confidence": confidence_from_traces(traces, blocking=blocking),
    }


def project_out(db: Session, project: m.ConsultingProject) -> dict:
    units = list(
        db.scalars(
            select(m.ConsultingUnit)
            .where(m.ConsultingUnit.project_id == project.id)
            .order_by(m.ConsultingUnit.sort_order)
        )
    )
    people = list(
        db.scalars(
            select(m.ConsultingPerson)
            .where(m.ConsultingPerson.project_id == project.id)
            .order_by(m.ConsultingPerson.full_name)
        )
    )
    milestones = list(
        db.scalars(
            select(m.ConsultingMilestone)
            .where(m.ConsultingMilestone.project_id == project.id)
            .order_by(m.ConsultingMilestone.sort_order)
        )
    )
    members = list(
        db.scalars(select(m.ConsultingMember).where(m.ConsultingMember.project_id == project.id))
    )
    return {
        "id": str(project.id),
        "title": project.title,
        "customer_name": project.customer_name,
        "started_on": _iso(project.started_on),
        "due_on": _iso(project.due_on),
        "plan_status": project.plan_status,
        "results": dict((project.payload or {}).get("results") or {}),
        "result_labels": [{"code": c, "title": t} for c, t in RESULT_CODES],
        "showcase_token": project.showcase_token,
        "showcase": dict((project.payload or {}).get("showcase") or {}),
        "units": [unit_out(u) for u in units],
        "people": [person_out(p) for p in people],
        "milestones": [milestone_out(x) for x in milestones],
        "members": [{"id": str(x.id), "user_id": str(x.user_id), "role": x.role} for x in members],
    }


def hub_out(db: Session, project: m.ConsultingProject) -> dict:
    source_count = db.scalar(
        select(func.count()).select_from(m.ConsultingSource).where(
            m.ConsultingSource.project_id == project.id
        )
    ) or 0
    pending_mark = db.scalar(
        select(func.count()).select_from(m.ConsultingSource).where(
            m.ConsultingSource.project_id == project.id,
            m.ConsultingSource.mark == "pending",
        )
    ) or 0
    recommended = db.scalar(
        select(func.count()).select_from(m.ConsultingRegistryRow).where(
            m.ConsultingRegistryRow.project_id == project.id,
            m.ConsultingRegistryRow.status == "recommended",
        )
    ) or 0
    disputed = db.scalar(
        select(func.count()).select_from(m.ConsultingRegistryRow).where(
            m.ConsultingRegistryRow.project_id == project.id,
            m.ConsultingRegistryRow.status == "disputed",
        )
    ) or 0
    plan_total = db.scalar(
        select(func.count()).select_from(m.ConsultingPlanItem).where(
            m.ConsultingPlanItem.project_id == project.id
        )
    ) or 0
    plan_done = db.scalar(
        select(func.count()).select_from(m.ConsultingPlanItem).where(
            m.ConsultingPlanItem.project_id == project.id,
            m.ConsultingPlanItem.status == "done",
        )
    ) or 0
    empty_folders = _empty_folder_count(db, project.id)
    people_n = db.scalar(
        select(func.count()).select_from(m.ConsultingPerson).where(
            m.ConsultingPerson.project_id == project.id
        )
    ) or 0
    meetings_pending = db.scalar(
        select(func.count()).select_from(m.ConsultingMeeting).where(
            m.ConsultingMeeting.project_id == project.id,
            m.ConsultingMeeting.transcript == "",
            m.ConsultingMeeting.digest == "",
        )
    ) or 0
    open_contr = db.scalar(
        select(func.count()).select_from(m.ConsultingContradiction).where(
            m.ConsultingContradiction.project_id == project.id,
            m.ConsultingContradiction.status == "open",
        )
    ) or 0
    surveys_draft = db.scalar(
        select(func.count()).select_from(m.ConsultingSurvey).where(
            m.ConsultingSurvey.project_id == project.id,
            m.ConsultingSurvey.status == "draft",
        )
    ) or 0
    coverage = coverage_out(db, project)
    results = dict((project.payload or {}).get("results") or {})
    filled_results = sum(1 for v in results.values() if v not in ("", "empty"))
    showcase = dict((project.payload or {}).get("showcase") or {})
    return {
        "project": project_out(db, project),
        "collect": {
            "sources": source_count,
            "pending_review": pending_mark,
            "people": people_n,
            "meetings_pending": meetings_pending,
            "surveys_pending": int(surveys_draft),
        },
        "attention": {
            "empty_folders": empty_folders,
            "recommended": recommended,
            "disputed": disputed,
            "contradictions": open_contr,
            "shadows": 0,
            "white_spots": coverage["open"],
        },
        "output": {
            "plan_done": plan_done,
            "plan_total": plan_total,
            "results_ready": filled_results,
            "results_total": len(RESULT_CODES),
            "showcase_ready": bool(project.showcase_token and showcase.get("published_at")),
        },
    }


def _empty_folder_count(db: Session, project_id: uuid.UUID) -> int:
    folders = list(
        db.scalars(select(m.ConsultingFolder).where(m.ConsultingFolder.project_id == project_id))
    )
    counts: dict[uuid.UUID, int] = {}
    for folder_id, n in db.execute(
        select(m.ConsultingSource.folder_id, func.count())
        .where(m.ConsultingSource.project_id == project_id)
        .group_by(m.ConsultingSource.folder_id)
    ):
        if folder_id:
            counts[folder_id] = int(n)
    return sum(1 for f in folders if f.level >= 2 and counts.get(f.id, 0) == 0)


def list_folders(db: Session, project: m.ConsultingProject) -> list[dict]:
    folders = list(
        db.scalars(
            select(m.ConsultingFolder)
            .where(m.ConsultingFolder.project_id == project.id)
            .order_by(m.ConsultingFolder.sort_order)
        )
    )
    counts: dict[uuid.UUID, int] = {}
    for folder_id, n in db.execute(
        select(m.ConsultingSource.folder_id, func.count())
        .where(m.ConsultingSource.project_id == project.id)
        .group_by(m.ConsultingSource.folder_id)
    ):
        if folder_id:
            counts[folder_id] = int(n)
    return [folder_out(f, counts.get(f.id, 0)) for f in folders]


def add_source(
    db: Session,
    project: m.ConsultingProject,
    *,
    kind: str,
    title: str,
    folder_id: uuid.UUID | None,
    url: str | None,
    quoted_text: str,
    mark: str,
    file_name: str | None = None,
) -> m.ConsultingSource:
    if kind not in ("file", "url"):
        raise HTTPException(status_code=400, detail="Тип источника: файл или ссылка")
    if mark not in MARKS:
        raise HTTPException(status_code=400, detail="Неверная метка")
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Нужно название")
    quote = (quoted_text or "").strip()
    link = (url or "").strip() or None
    if kind == "url" and not link:
        raise HTTPException(status_code=400, detail="Нужна ссылка")
    if kind == "url" and not quote and not _looks_public_yandex(link or ""):
        raise HTTPException(
            status_code=400,
            detail="Закрытую ссылку разберём только с цитируемым текстом",
        )
    if folder_id:
        folder = db.get(m.ConsultingFolder, folder_id)
        if not folder or folder.project_id != project.id:
            raise HTTPException(status_code=400, detail="Папка не из этого проекта")
    extracted = ""
    extract_status = "none"
    if kind == "url" and link and _looks_public_yandex(link):
        from app.services.consulting_extract import extract_public_source

        extracted, extract_status = extract_public_source(link)
    source = m.ConsultingSource(
        project_id=project.id,
        folder_id=folder_id,
        kind=kind,
        title=title,
        url=link,
        quoted_text=quote,
        mark=mark,
        file_name=file_name,
        extracted_text=extracted,
        extract_status=extract_status,
        space="evidence",
    )
    db.add(source)
    db.flush()
    db.add(
        m.ConsultingRegistryRow(
            project_id=project.id,
            source_id=source.id,
            title=title,
            status="draft",
            payload={"traces": [{"source_type": kind, "source_id": str(source.id)}]},
        )
    )
    db.commit()
    db.refresh(source)
    return source


def _looks_public_yandex(url: str) -> bool:
    low = url.lower()
    return "disk.yandex" in low or "yadi.sk" in low


def patch_project(db: Session, project: m.ConsultingProject, body: dict[str, Any]) -> m.ConsultingProject:
    if "title" in body and body["title"] is not None:
        project.title = str(body["title"]).strip() or project.title
    if "customer_name" in body and body["customer_name"] is not None:
        project.customer_name = str(body["customer_name"]).strip()
    if "started_on" in body:
        project.started_on = _parse_date(body.get("started_on"))
    if "due_on" in body:
        project.due_on = _parse_date(body.get("due_on"))
    db.commit()
    db.refresh(project)
    return project


def _parse_date(raw: Any) -> date | None:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw)[:10])


MEETING_LEVELS = ("owner", "directors", "executors")


def meeting_out(row: m.ConsultingMeeting) -> dict:
    return {
        "id": str(row.id),
        "title": row.title,
        "held_on": _iso(row.held_on),
        "level": row.level,
        "notes": row.notes,
        "transcript": row.transcript,
        "digest": row.digest,
        "url": row.url,
        "folder_id": str(row.folder_id) if row.folder_id else None,
        "has_text": bool((row.transcript or "").strip() or (row.digest or "").strip()),
    }


def list_meetings(db: Session, project: m.ConsultingProject) -> list[dict]:
    rows = list(
        db.scalars(
            select(m.ConsultingMeeting)
            .where(m.ConsultingMeeting.project_id == project.id)
            .order_by(m.ConsultingMeeting.created_at.desc())
        )
    )
    return [meeting_out(x) for x in rows]


def add_meeting(
    db: Session,
    project: m.ConsultingProject,
    *,
    title: str,
    held_on: date | None,
    level: str,
    notes: str,
    transcript: str,
    url: str | None,
    folder_id: uuid.UUID | None,
) -> m.ConsultingMeeting:
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Нужно название встречи")
    if level not in MEETING_LEVELS:
        raise HTTPException(status_code=400, detail="Уровень: собственник, директора или исполнители")
    if folder_id:
        folder = db.get(m.ConsultingFolder, folder_id)
        if not folder or folder.project_id != project.id:
            raise HTTPException(status_code=400, detail="Папка не из этого проекта")
    row = m.ConsultingMeeting(
        project_id=project.id,
        title=title,
        held_on=held_on,
        level=level,
        notes=(notes or "").strip(),
        transcript=(transcript or "").strip(),
        digest="",
        url=(url or "").strip() or None,
        folder_id=folder_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def patch_meeting(db: Session, project: m.ConsultingProject, meeting_id: uuid.UUID, body: dict[str, Any]) -> m.ConsultingMeeting:
    row = db.get(m.ConsultingMeeting, meeting_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Встреча не найдена")
    if "title" in body and body["title"] is not None:
        row.title = str(body["title"]).strip() or row.title
    if "held_on" in body:
        row.held_on = _parse_date(body.get("held_on"))
    if "level" in body and body["level"] in MEETING_LEVELS:
        row.level = body["level"]
    if "notes" in body and body["notes"] is not None:
        row.notes = str(body["notes"])
    if "transcript" in body and body["transcript"] is not None:
        row.transcript = str(body["transcript"])
    if "digest" in body and body["digest"] is not None:
        row.digest = str(body["digest"])
    if "url" in body:
        row.url = str(body["url"]).strip() or None
    if "folder_id" in body:
        folder_id = body.get("folder_id")
        if folder_id:
            folder = db.get(m.ConsultingFolder, folder_id)
            if not folder or folder.project_id != project.id:
                raise HTTPException(status_code=400, detail="Папка не из этого проекта")
            row.folder_id = folder.id
        else:
            row.folder_id = None
    db.commit()
    db.refresh(row)
    return row


def contradiction_out(row: m.ConsultingContradiction) -> dict:
    return {
        "id": str(row.id),
        "title": row.title,
        "left_text": row.left_text,
        "right_text": row.right_text,
        "status": row.status,
        "registry_row_id": str(row.registry_row_id) if row.registry_row_id else None,
    }


def list_contradictions(db: Session, project: m.ConsultingProject) -> list[dict]:
    rows = list(
        db.scalars(
            select(m.ConsultingContradiction)
            .where(m.ConsultingContradiction.project_id == project.id)
            .order_by(m.ConsultingContradiction.created_at.desc())
        )
    )
    return [contradiction_out(x) for x in rows]


def add_contradiction(
    db: Session,
    project: m.ConsultingProject,
    *,
    title: str,
    left_text: str,
    right_text: str,
    registry_row_id: uuid.UUID | None = None,
) -> m.ConsultingContradiction:
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Нужно название")
    row = m.ConsultingContradiction(
        project_id=project.id,
        title=title,
        left_text=(left_text or "").strip(),
        right_text=(right_text or "").strip(),
        status="open",
        registry_row_id=registry_row_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ensure_dispute_contradiction(db: Session, project: m.ConsultingProject, registry_row: m.ConsultingRegistryRow) -> None:
    existing = db.scalar(
        select(m.ConsultingContradiction).where(
            m.ConsultingContradiction.project_id == project.id,
            m.ConsultingContradiction.registry_row_id == registry_row.id,
            m.ConsultingContradiction.status == "open",
        )
    )
    if existing:
        return
    db.add(
        m.ConsultingContradiction(
            project_id=project.id,
            title=f"Оспорено: {registry_row.title}",
            left_text="Подтверждено исполнителем",
            right_text="Заказчик не согласен",
            status="open",
            registry_row_id=registry_row.id,
        )
    )


def patch_contradiction(
    db: Session, project: m.ConsultingProject, row_id: uuid.UUID, status: str
) -> m.ConsultingContradiction:
    row = db.get(m.ConsultingContradiction, row_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Противоречие не найдено")
    if status not in ("open", "resolved"):
        raise HTTPException(status_code=400, detail="Статус: открыто или снято")
    row.status = status
    db.commit()
    db.refresh(row)
    return row


def _folder_code_map(db: Session, project_id: uuid.UUID) -> dict[uuid.UUID, str]:
    folders = list(db.scalars(select(m.ConsultingFolder).where(m.ConsultingFolder.project_id == project_id)))
    return {f.id: f.code for f in folders}


def coverage_out(db: Session, project: m.ConsultingProject) -> dict:
    from app.services.consulting_coverage import COMPANY_FRAME, cell_closed
    from app.services.consulting_wave2 import response_coverage_codes

    codes = _folder_code_map(db, project.id)
    survey_codes = response_coverage_codes(db, project.id)
    sources = []
    for s in db.scalars(select(m.ConsultingSource).where(m.ConsultingSource.project_id == project.id)):
        sources.append(
            {
                "folder_code": codes.get(s.folder_id) if s.folder_id else None,
                "mark": s.mark,
                "quoted_text": s.quoted_text,
                "extracted_text": getattr(s, "extracted_text", "") or "",
                "extract_status": getattr(s, "extract_status", "") or "",
            }
        )
    meetings = []
    for meet in db.scalars(select(m.ConsultingMeeting).where(m.ConsultingMeeting.project_id == project.id)):
        meetings.append(
            {
                "folder_code": codes.get(meet.folder_id) if meet.folder_id else None,
                "transcript": meet.transcript,
                "digest": meet.digest,
            }
        )
    registry = []
    for row in db.scalars(select(m.ConsultingRegistryRow).where(m.ConsultingRegistryRow.project_id == project.id)):
        src = db.get(m.ConsultingSource, row.source_id) if row.source_id else None
        folder_code = codes.get(src.folder_id) if src and src.folder_id else None
        registry.append({"status": row.status, "folder_code": folder_code})
    items = []
    open_n = 0
    for code, title, prefixes in COMPANY_FRAME:
        closed = cell_closed(prefixes=prefixes, sources=sources, meetings=meetings, registry=registry)
        if not closed and code in survey_codes:
            closed = True
        if not closed:
            open_n += 1
        items.append({"code": code, "title": title, "closed": closed, "kind": "no_data" if not closed else "ok"})
    return {"open": open_n, "total": len(COMPANY_FRAME), "items": items}


def publish_showcase(db: Session, project: m.ConsultingProject) -> dict:
    if not project.showcase_token:
        project.showcase_token = secrets.token_urlsafe(24)
    payload = dict(project.payload or {})
    show = dict(payload.get("showcase") or {})
    show["version"] = int(show.get("version") or 0) + 1
    show["published_at"] = datetime.now(timezone.utc).isoformat()
    show["guest_approved"] = False
    payload["showcase"] = show
    project.payload = payload
    db.commit()
    db.refresh(project)
    return showcase_owner_out(project)


def showcase_owner_out(project: m.ConsultingProject) -> dict:
    show = dict((project.payload or {}).get("showcase") or {})
    return {
        "token": project.showcase_token,
        "url": f"/consulting/p/{project.showcase_token}" if project.showcase_token else None,
        "version": show.get("version") or 0,
        "published_at": show.get("published_at"),
        "guest_approved": bool(show.get("guest_approved")),
    }


def get_project_by_token(db: Session, token: str) -> m.ConsultingProject:
    row = db.scalar(select(m.ConsultingProject).where(m.ConsultingProject.showcase_token == token))
    if not row:
        raise HTTPException(status_code=404, detail="Ссылка недействительна")
    show = dict((row.payload or {}).get("showcase") or {})
    if not show.get("published_at"):
        raise HTTPException(status_code=404, detail="Снимок ещё не опубликован")
    return row


def showcase_public_out(db: Session, project: m.ConsultingProject) -> dict:
    folders = list_folders(db, project)
    confirmed = list(
        db.scalars(
            select(m.ConsultingRegistryRow)
            .where(
                m.ConsultingRegistryRow.project_id == project.id,
                m.ConsultingRegistryRow.status.in_(("confirmed", "sent", "approved")),
            )
            .order_by(m.ConsultingRegistryRow.created_at.desc())
        )
    )
    comments = list(
        db.scalars(
            select(m.ConsultingComment)
            .where(m.ConsultingComment.project_id == project.id)
            .order_by(m.ConsultingComment.created_at.asc())
        )
    )
    plan_total = db.scalar(
        select(func.count()).select_from(m.ConsultingPlanItem).where(m.ConsultingPlanItem.project_id == project.id)
    ) or 0
    plan_done = db.scalar(
        select(func.count()).select_from(m.ConsultingPlanItem).where(
            m.ConsultingPlanItem.project_id == project.id,
            m.ConsultingPlanItem.status == "done",
        )
    ) or 0
    show = dict((project.payload or {}).get("showcase") or {})
    return {
        "title": project.title,
        "customer_name": project.customer_name,
        "version": show.get("version") or 1,
        "published_at": show.get("published_at"),
        "guest_approved": bool(show.get("guest_approved")),
        "plan_done": plan_done,
        "plan_total": plan_total,
        "folders": [{"code": f["code"], "name": f["name"], "file_count": f["file_count"]} for f in folders],
        "facts": [{"id": str(r.id), "title": r.title, "status": r.status} for r in confirmed],
        "comments": [
            {
                "id": str(c.id),
                "author_name": c.author_name,
                "body": c.body,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ],
        "forms_note": "Формы результата ещё не загружены — итог по клеткам не собираем.",
    }


def add_comment(db: Session, project: m.ConsultingProject, *, author_name: str, body: str) -> m.ConsultingComment:
    body = (body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Нужен комментарий")
    row = m.ConsultingComment(
        project_id=project.id,
        author_name=(author_name or "").strip() or "Гость",
        body=body,
        target_kind="project",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def approve_showcase(db: Session, project: m.ConsultingProject) -> dict:
    payload = dict(project.payload or {})
    show = dict(payload.get("showcase") or {})
    show["guest_approved"] = True
    show["guest_approved_at"] = datetime.now(timezone.utc).isoformat()
    payload["showcase"] = show
    project.payload = payload
    db.commit()
    return showcase_public_out(db, project)

