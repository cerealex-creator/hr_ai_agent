"""СУП — ворота утверждения L0–L2 (U3 gate mode)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_system import approve_goal, approve_task, list_goals, list_tasks
from app.services.management_validators import validate_l2a_process_map

APPROVABLE_TYPES = ("goal", "task", "process_map", "role", "process_step")
REJECTABLE_TYPES = ("goal", "task")
PENDING_STATUSES = ("draft", "suggested")


class GateError(Exception):
    def __init__(self, code: str, message: str, details: list[str] | None = None):
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)


def _get_entity(db: Session, entity_type: str, entity_id: uuid.UUID):
    mapping = {
        "goal": m.MgmtGoal,
        "task": m.MgmtTask,
        "process_map": m.MgmtProcessMap,
        "role": m.MgmtRole,
        "process_step": m.MgmtProcessStep,
    }
    model = mapping.get(entity_type)
    if not model:
        return None
    return db.get(model, entity_id)


def approve_entity(
    db: Session,
    revision_id: uuid.UUID,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
) -> dict:
    if entity_type not in APPROVABLE_TYPES:
        raise GateError("UNSUPPORTED", f"Тип «{entity_type}» нельзя утвердить на карте")

    entity = _get_entity(db, entity_type, entity_id)
    if not entity or getattr(entity, "revision_id", None) != revision_id:
        raise GateError("NOT_FOUND", "Сущность не найдена в черновой ревизии")

    status = getattr(entity, "status", None)
    if status == "approved":
        return {"id": str(entity_id), "entity_type": entity_type, "status": "approved", "already": True}
    if status not in PENDING_STATUSES:
        raise GateError("BAD_STATUS", f"Статус «{status}» нельзя утвердить")

    if entity_type == "goal":
        approve_goal(db, entity)
    elif entity_type == "task":
        approve_task(db, entity)
    elif entity_type == "process_map":
        errors = validate_l2a_process_map(db, revision_id, entity.id)
        if errors:
            raise GateError("STEP_NO_ROLE", "Нельзя утвердить процесс: есть шаги без роли", errors)
        entity.status = "approved"
        for step in db.scalars(
            select(m.MgmtProcessStep).where(
                m.MgmtProcessStep.revision_id == revision_id,
                m.MgmtProcessStep.process_map_id == entity.id,
            )
        ).all():
            if step.status in PENDING_STATUSES:
                step.status = "approved"
        db.flush()
    elif entity_type == "role":
        entity.status = "approved"
        db.flush()
    elif entity_type == "process_step":
        if not entity.role_id:
            raise GateError("STEP_NO_ROLE", "Шаг процесса без назначенной роли")
        entity.status = "approved"
        db.flush()

    return {"id": str(entity_id), "entity_type": entity_type, "status": "approved", "already": False}


def reject_entity(
    db: Session,
    revision_id: uuid.UUID,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
) -> dict:
    if entity_type not in REJECTABLE_TYPES:
        raise GateError("UNSUPPORTED", f"Тип «{entity_type}» нельзя отклонить (только цели/задачи из пакета)")

    entity = _get_entity(db, entity_type, entity_id)
    if not entity or getattr(entity, "revision_id", None) != revision_id:
        raise GateError("NOT_FOUND", "Сущность не найдена в черновой ревизии")

    status = getattr(entity, "status", None)
    if status == "rejected":
        return {"id": str(entity_id), "entity_type": entity_type, "status": "rejected", "already": True}
    if status not in ("suggested", "draft"):
        raise GateError("BAD_STATUS", f"Статус «{status}» нельзя отклонить")

    entity.status = "rejected"
    db.flush()
    return {"id": str(entity_id), "entity_type": entity_type, "status": "rejected", "already": False}


def approve_all_l2a(db: Session, revision_id: uuid.UUID) -> dict:
    maps = list(
        db.scalars(
            select(m.MgmtProcessMap)
            .where(m.MgmtProcessMap.revision_id == revision_id)
            .order_by(m.MgmtProcessMap.sort_order)
        ).all()
    )
    approved = 0
    errors: list[str] = []
    for pm in maps:
        if pm.status == "approved":
            continue
        if pm.status not in PENDING_STATUSES:
            continue
        try:
            approve_entity(db, revision_id, entity_type="process_map", entity_id=pm.id)
            approved += 1
        except GateError as exc:
            errors.extend(exc.details or [exc.message])
    return {"approved_count": approved, "errors": errors, "level": "l2a"}


def approve_all_l2b(db: Session, revision_id: uuid.UUID) -> dict:
    roles = list(
        db.scalars(
            select(m.MgmtRole)
            .where(m.MgmtRole.revision_id == revision_id)
            .order_by(m.MgmtRole.sort_order)
        ).all()
    )
    approved = 0
    for role in roles:
        if role.status in PENDING_STATUSES:
            role.status = "approved"
            approved += 1
    db.flush()
    return {"approved_count": approved, "errors": [], "level": "l2b"}


def list_process_maps(db: Session, revision_id: uuid.UUID) -> list[m.MgmtProcessMap]:
    return list(
        db.scalars(
            select(m.MgmtProcessMap)
            .where(m.MgmtProcessMap.revision_id == revision_id)
            .order_by(m.MgmtProcessMap.sort_order, m.MgmtProcessMap.title)
        ).all()
    )


def gate_summary(db: Session, revision_id: uuid.UUID) -> dict:
    goals = list_goals(db, revision_id)
    tasks = list_tasks(db, revision_id)
    maps = list_process_maps(db, revision_id)
    roles = list(
        db.scalars(select(m.MgmtRole).where(m.MgmtRole.revision_id == revision_id)).all()
    )

    def pending(rows: list) -> int:
        return sum(1 for r in rows if getattr(r, "status", None) in PENDING_STATUSES)

    return {
        "l0_pending": pending(goals),
        "l1_pending": pending(tasks),
        "l2a_pending": pending(maps),
        "l2b_pending": pending(roles),
        "suggested_goals": sum(1 for g in goals if g.status == "suggested"),
        "suggested_tasks": sum(1 for t in tasks if t.status == "suggested"),
    }
