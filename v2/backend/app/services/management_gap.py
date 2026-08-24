"""СУП — детерминированный gap-отчёт (U3, без ИИ)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_packs import load_pack_manifest
from app.services.management_system import list_current_positions, list_goals, list_tasks

DEFAULT_OVERLOAD_ROLES = 2


def _overload_limit(db: Session, revision_id: uuid.UUID) -> int:
    rev = db.get(m.MgmtRevision, revision_id)
    if not rev:
        return DEFAULT_OVERLOAD_ROLES
    system = db.get(m.MgmtSystem, rev.system_id)
    if not system or not system.industry_pack_id:
        return DEFAULT_OVERLOAD_ROLES
    try:
        manifest = load_pack_manifest(system.industry_pack_id)
        return int(manifest.get("defaults", {}).get("overload_roles", DEFAULT_OVERLOAD_ROLES))
    except (ValueError, TypeError, KeyError, OSError):
        return DEFAULT_OVERLOAD_ROLES


def build_gap_report(db: Session, revision_id: uuid.UUID) -> dict:
    goals = list_goals(db, revision_id)
    tasks = list_tasks(db, revision_id)
    roles = list(db.scalars(select(m.MgmtRole).where(m.MgmtRole.revision_id == revision_id)).all())
    steps = list(
        db.scalars(select(m.MgmtProcessStep).where(m.MgmtProcessStep.revision_id == revision_id)).all()
    )
    positions = list_current_positions(db, revision_id)
    assignments = list(
        db.scalars(select(m.MgmtRoleAssignment).where(m.MgmtRoleAssignment.revision_id == revision_id)).all()
    )

    items: list[dict] = []

    for g in goals:
        gap = None
        if g.baseline_value is not None and g.target_value is not None:
            gap = g.target_value - g.baseline_value
        if gap is not None:
            items.append(
                {
                    "code": "GOAL_NUMERIC_GAP",
                    "severity": "info",
                    "title": g.title,
                    "message": f"Разрыв по метрике: {g.baseline_value} → {g.target_value} (Δ {gap})",
                    "entity_type": "goal",
                    "entity_id": str(g.id),
                }
            )
        elif g.status == "approved" and g.baseline_value is None and g.target_value is None:
            items.append(
                {
                    "code": "GOAL_QUALITATIVE",
                    "severity": "info",
                    "title": g.title,
                    "message": "Качественная цель без числового разрыва — нормально для MVP",
                    "entity_type": "goal",
                    "entity_id": str(g.id),
                }
            )

    suggested_goals = [g for g in goals if g.status == "suggested"]
    if suggested_goals:
        items.append(
            {
                "code": "PACK_SUGGESTED_GOALS",
                "severity": "warning",
                "title": "Подсказки из пакета",
                "message": f"{len(suggested_goals)} целей из отраслевого пакета ждут принятия или отклонения",
                "entity_type": None,
                "entity_id": None,
            }
        )

    for step in steps:
        if not step.role_id and step.status != "approved":
            items.append(
                {
                    "code": "STEP_NO_ROLE",
                    "severity": "warning",
                    "title": step.title,
                    "message": "Шаг процесса без назначенной роли",
                    "entity_type": "process_step",
                    "entity_id": str(step.id),
                }
            )

    if roles and positions and not assignments:
        items.append(
            {
                "code": "NO_ASSIGNMENTS",
                "severity": "warning",
                "title": "As-is → to-be",
                "message": "Есть целевые роли и текущие должности, но нет сопоставления (role_assignments)",
                "entity_type": None,
                "entity_id": None,
            }
        )

    role_titles = {r.id: r.title for r in roles}
    pos_titles = {p.id: p.title for p in positions}
    role_coverage: dict[uuid.UUID, list[str]] = {r.id: [] for r in roles}
    pos_role_counts: dict[uuid.UUID, set[uuid.UUID]] = {}

    for a in assignments:
        role_coverage.setdefault(a.target_role_id, []).append(a.coverage)
        pos_role_counts.setdefault(a.current_position_id, set()).add(a.target_role_id)

    overload_limit = _overload_limit(db, revision_id)
    for pos_id, role_ids in pos_role_counts.items():
        if len(role_ids) > overload_limit:
            items.append(
                {
                    "code": "OVERLOAD",
                    "severity": "warning",
                    "title": pos_titles.get(pos_id, "Должность"),
                    "message": (
                        f"Одна текущая должность закрывает {len(role_ids)} целевых ролей "
                        f"(лимит {overload_limit}) — возможна перегрузка"
                    ),
                    "entity_type": "current_position",
                    "entity_id": str(pos_id),
                }
            )

    for role_id, coverages in role_coverage.items():
        if not coverages or all(c == "none" for c in coverages):
            items.append(
                {
                    "code": "COVERAGE_NONE",
                    "severity": "warning",
                    "title": role_titles.get(role_id, "Роль"),
                    "message": "Целевая роль без покрытия — нужен найм или перераспределение",
                    "entity_type": "role",
                    "entity_id": str(role_id),
                }
            )
        elif all(c != "full" for c in coverages):
            items.append(
                {
                    "code": "COVERAGE_PARTIAL",
                    "severity": "info",
                    "title": role_titles.get(role_id, "Роль"),
                    "message": "Роль закрыта частично — проверьте headcount или усиление",
                    "entity_type": "role",
                    "entity_id": str(role_id),
                }
            )

    return {
        "revision_id": str(revision_id),
        "summary": {
            "goals": len(goals),
            "tasks": len(tasks),
            "roles": len(roles),
            "process_steps": len(steps),
            "current_positions": len(positions),
            "assignments": len(assignments),
            "gap_items": len(items),
        },
        "items": items,
    }
