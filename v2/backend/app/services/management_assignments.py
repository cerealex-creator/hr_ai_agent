"""СУП — сопоставление as-is должностей и целевых ролей (U3)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m

COVERAGE_VALUES = ("full", "partial", "none")


def list_roles(db: Session, revision_id: uuid.UUID) -> list[m.MgmtRole]:
    return list(
        db.scalars(
            select(m.MgmtRole)
            .where(m.MgmtRole.revision_id == revision_id)
            .order_by(m.MgmtRole.sort_order, m.MgmtRole.title)
        ).all()
    )


def list_role_assignments(db: Session, revision_id: uuid.UUID) -> list[m.MgmtRoleAssignment]:
    return list(
        db.scalars(
            select(m.MgmtRoleAssignment).where(m.MgmtRoleAssignment.revision_id == revision_id)
        ).all()
    )


def _get_role(db: Session, revision_id: uuid.UUID, role_id: uuid.UUID) -> m.MgmtRole | None:
    role = db.get(m.MgmtRole, role_id)
    if not role or role.revision_id != revision_id:
        return None
    return role


def _get_position(db: Session, revision_id: uuid.UUID, position_id: uuid.UUID) -> m.MgmtCurrentPosition | None:
    pos = db.get(m.MgmtCurrentPosition, position_id)
    if not pos or pos.revision_id != revision_id:
        return None
    return pos


def assignment_out(db: Session, row: m.MgmtRoleAssignment) -> dict:
    role = db.get(m.MgmtRole, row.target_role_id)
    pos = db.get(m.MgmtCurrentPosition, row.current_position_id)
    return {
        "id": row.id,
        "revision_id": row.revision_id,
        "target_role_id": row.target_role_id,
        "target_role_title": role.title if role else "",
        "current_position_id": row.current_position_id,
        "current_position_title": pos.title if pos else "",
        "coverage": row.coverage,
        "note": row.note,
        "stale": row.stale,
    }


def create_role_assignment(
    db: Session,
    revision_id: uuid.UUID,
    *,
    target_role_id: uuid.UUID,
    current_position_id: uuid.UUID,
    coverage: str = "partial",
    note: str | None = None,
) -> m.MgmtRoleAssignment:
    if coverage not in COVERAGE_VALUES:
        raise ValueError(f"coverage must be one of {COVERAGE_VALUES}")
    if not _get_role(db, revision_id, target_role_id):
        raise ValueError("Target role not found in revision")
    if not _get_position(db, revision_id, current_position_id):
        raise ValueError("Current position not found in revision")

    row = m.MgmtRoleAssignment(
        revision_id=revision_id,
        target_role_id=target_role_id,
        current_position_id=current_position_id,
        coverage=coverage,
        note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def update_role_assignment(
    db: Session,
    row: m.MgmtRoleAssignment,
    *,
    coverage: str | None = None,
    note: str | None = None,
    clear_note: bool = False,
) -> m.MgmtRoleAssignment:
    if coverage is not None:
        if coverage not in COVERAGE_VALUES:
            raise ValueError(f"coverage must be one of {COVERAGE_VALUES}")
        row.coverage = coverage
    if clear_note:
        row.note = None
    elif note is not None:
        row.note = note.strip() or None
    row.stale = False
    db.flush()
    return row


def delete_role_assignment(db: Session, row: m.MgmtRoleAssignment) -> None:
    db.delete(row)
