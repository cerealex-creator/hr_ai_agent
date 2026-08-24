"""СУП — read-only preview документов ролей (L3, без persist / approve)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_assignments import list_roles


def build_l3_preview(db: Session, revision_id: uuid.UUID) -> dict:
    """Сборка preview L3: обязанности из шагов процессов, чек-листы из step_io.

    Не пишет в БД и не утверждает — только для мастера / эксперта (U3 preview, U4 persist).
    """
    roles = list_roles(db, revision_id)
    steps = list(
        db.scalars(
            select(m.MgmtProcessStep)
            .where(m.MgmtProcessStep.revision_id == revision_id)
            .order_by(m.MgmtProcessStep.sort_order)
        ).all()
    )
    maps = {
        pm.id: pm
        for pm in db.scalars(
            select(m.MgmtProcessMap).where(m.MgmtProcessMap.revision_id == revision_id)
        ).all()
    }
    step_ids = [s.id for s in steps]
    io_by_step: dict[uuid.UUID, list[m.MgmtStepIoItem]] = {sid: [] for sid in step_ids}
    if step_ids:
        for item in db.scalars(
            select(m.MgmtStepIoItem)
            .where(m.MgmtStepIoItem.step_id.in_(step_ids))
            .order_by(m.MgmtStepIoItem.sort_order)
        ).all():
            io_by_step.setdefault(item.step_id, []).append(item)

    steps_by_role: dict[uuid.UUID | None, list[m.MgmtProcessStep]] = {}
    for step in steps:
        steps_by_role.setdefault(step.role_id, []).append(step)

    documents: list[dict] = []
    for role in roles:
        role_steps = steps_by_role.get(role.id, [])
        duties = [
            {
                "title": step.title,
                "process_map": maps[step.process_map_id].title if step.process_map_id in maps else None,
                "frequency": step.frequency,
                "step_id": str(step.id),
            }
            for step in role_steps
        ]
        checklist: list[dict] = []
        for step in role_steps:
            for io in io_by_step.get(step.id, []):
                checklist.append(
                    {
                        "title": io.title,
                        "direction": io.direction,
                        "from_step": step.title,
                    }
                )
            if not io_by_step.get(step.id):
                checklist.append(
                    {
                        "title": f"Выполнить: {step.title}",
                        "direction": "out",
                        "from_step": step.title,
                    }
                )

        documents.append(
            {
                "role_id": str(role.id),
                "role_title": role.title,
                "role_status": role.status,
                "external_key": role.external_key,
                "duties": duties,
                "checklist": checklist,
                "kpi_hints": [],
                "is_preview": True,
                "approvable": False,
            }
        )

    unassigned = steps_by_role.get(None, [])
    return {
        "revision_id": str(revision_id),
        "is_preview": True,
        "note": "Черновик L3 из процессов и ролей. Утверждение документов — в U4 (режим «Документ»).",
        "documents": documents,
        "unassigned_steps": [
            {
                "title": s.title,
                "process_map": maps[s.process_map_id].title if s.process_map_id in maps else None,
                "step_id": str(s.id),
            }
            for s in unassigned
        ],
        "summary": {
            "roles": len(roles),
            "documents": len(documents),
            "duties_total": sum(len(d["duties"]) for d in documents),
            "unassigned_steps": len(unassigned),
        },
    }
