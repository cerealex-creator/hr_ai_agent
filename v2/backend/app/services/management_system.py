"""СУП domain service — system/revision CRUD and graph export (U1)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m


def get_or_create_system(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID | None) -> m.MgmtSystem:
    system = db.scalar(
        select(m.MgmtSystem).where(m.MgmtSystem.organization_id == organization_id)
    )
    if system:
        if not system.draft_revision_id:
            rev = _create_revision(db, system, user_id, version_number=1)
            system.draft_revision_id = rev.id
            db.flush()
        return system

    system = m.MgmtSystem(organization_id=organization_id, status="draft")
    db.add(system)
    db.flush()
    rev = _create_revision(db, system, user_id, version_number=1)
    system.draft_revision_id = rev.id
    db.flush()
    return system


def _create_revision(
    db: Session,
    system: m.MgmtSystem,
    user_id: uuid.UUID | None,
    *,
    version_number: int,
    parent_revision_id: uuid.UUID | None = None,
) -> m.MgmtRevision:
    rev = m.MgmtRevision(
        system_id=system.id,
        version_number=version_number,
        parent_revision_id=parent_revision_id,
        status="draft",
        created_by=user_id,
    )
    db.add(rev)
    db.flush()
    return rev


def get_draft_revision(db: Session, system: m.MgmtSystem) -> m.MgmtRevision | None:
    if not system.draft_revision_id:
        return None
    return db.get(m.MgmtRevision, system.draft_revision_id)


def list_goals(db: Session, revision_id: uuid.UUID) -> list[m.MgmtGoal]:
    return list(
        db.scalars(
            select(m.MgmtGoal)
            .where(m.MgmtGoal.revision_id == revision_id)
            .order_by(m.MgmtGoal.sort_order, m.MgmtGoal.created_at)
        ).all()
    )


def list_tasks(db: Session, revision_id: uuid.UUID) -> list[m.MgmtTask]:
    return list(
        db.scalars(
            select(m.MgmtTask)
            .where(m.MgmtTask.revision_id == revision_id)
            .order_by(m.MgmtTask.sort_order, m.MgmtTask.created_at)
        ).all()
    )


def list_links(db: Session, revision_id: uuid.UUID) -> list[m.MgmtEntityLink]:
    return list(
        db.scalars(select(m.MgmtEntityLink).where(m.MgmtEntityLink.revision_id == revision_id)).all()
    )


def list_current_positions(db: Session, revision_id: uuid.UUID) -> list[m.MgmtCurrentPosition]:
    return list(
        db.scalars(
            select(m.MgmtCurrentPosition)
            .where(m.MgmtCurrentPosition.revision_id == revision_id)
            .order_by(m.MgmtCurrentPosition.sort_order)
        ).all()
    )


def list_goal_dimensions(db: Session) -> list[m.MgmtGoalDimension]:
    return list(
        db.scalars(
            select(m.MgmtGoalDimension).order_by(m.MgmtGoalDimension.sort_order, m.MgmtGoalDimension.code)
        ).all()
    )


def _numeric_gap(goal: m.MgmtGoal) -> Decimal | None:
    if goal.baseline_value is None or goal.target_value is None:
        return None
    return goal.target_value - goal.baseline_value


def goal_dimensions_map(db: Session, goal_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    if not goal_ids:
        return {}
    rows = db.execute(
        select(
            m.MgmtGoalDimensionLink.goal_id,
            m.MgmtGoalDimensionLink.is_primary,
            m.MgmtGoalDimension.id,
            m.MgmtGoalDimension.code,
            m.MgmtGoalDimension.title,
            m.MgmtGoalDimension.icon,
        )
        .join(m.MgmtGoalDimension, m.MgmtGoalDimension.id == m.MgmtGoalDimensionLink.dimension_id)
        .where(m.MgmtGoalDimensionLink.goal_id.in_(goal_ids))
        .order_by(m.MgmtGoalDimension.sort_order)
    ).all()
    out: dict[uuid.UUID, list[dict]] = {}
    for row in rows:
        out.setdefault(row.goal_id, []).append(
            {
                "dimension_id": row.id,
                "code": row.code,
                "title": row.title,
                "icon": row.icon,
                "is_primary": row.is_primary,
            }
        )
    return out


def set_goal_dimensions(
    db: Session,
    goal: m.MgmtGoal,
    *,
    dimension_codes: list[str],
    primary_dimension_code: str | None = None,
) -> None:
    if not dimension_codes:
        return
    dims = {
        d.code: d
        for d in db.scalars(
            select(m.MgmtGoalDimension).where(m.MgmtGoalDimension.code.in_(dimension_codes))
        ).all()
    }
    existing = {
        link.dimension_id: link
        for link in db.scalars(
            select(m.MgmtGoalDimensionLink).where(m.MgmtGoalDimensionLink.goal_id == goal.id)
        ).all()
    }
    primary_id = dims[primary_dimension_code].id if primary_dimension_code and primary_dimension_code in dims else None
    for code in dimension_codes:
        dim = dims.get(code)
        if not dim:
            continue
        if dim.id in existing:
            existing[dim.id].is_primary = dim.id == primary_id
        else:
            db.add(
                m.MgmtGoalDimensionLink(
                    goal_id=goal.id,
                    dimension_id=dim.id,
                    is_primary=dim.id == primary_id,
                )
            )
    db.flush()


def check_dimension_balance_warning(db: Session, revision_id: uuid.UUID) -> str | None:
    """Warning (не блокер): ни одна из 4 BSC-измерений не покрыта целями."""
    goals = list_goals(db, revision_id)
    if not goals:
        return None
    covered = set(
        db.scalars(
            select(m.MgmtGoalDimension.code)
            .join(m.MgmtGoalDimensionLink, m.MgmtGoalDimensionLink.dimension_id == m.MgmtGoalDimension.id)
            .join(m.MgmtGoal, m.MgmtGoal.id == m.MgmtGoalDimensionLink.goal_id)
            .where(m.MgmtGoal.revision_id == revision_id)
        ).all()
    )
    missing = [code for code in ("finance", "customers", "processes", "people") if code not in covered]
    if missing:
        return f"DIMENSION_BALANCE: не покрыты измерения {', '.join(missing)}"
    return None


def create_goal(
    db: Session,
    revision_id: uuid.UUID,
    *,
    title: str,
    weight: Decimal | None = None,
    metric_unit: str | None = None,
    baseline_value: Decimal | None = None,
    baseline_date=None,
    target_value: Decimal | None = None,
    target_date=None,
    metric_source: str | None = None,
    dimension_codes: list[str] | None = None,
    primary_dimension_code: str | None = None,
    cited_answer_ids: list[str] | None = None,
) -> m.MgmtGoal:
    count = len(list_goals(db, revision_id))
    goal = m.MgmtGoal(
        revision_id=revision_id,
        title=title.strip(),
        weight=weight,
        metric_unit=metric_unit,
        baseline_value=baseline_value,
        baseline_date=baseline_date,
        target_value=target_value,
        target_date=target_date,
        metric_source=metric_source or ("owner" if baseline_value is not None else None),
        cited_answer_ids=cited_answer_ids or [],
        sort_order=count,
    )
    db.add(goal)
    db.flush()
    if dimension_codes:
        set_goal_dimensions(
            db,
            goal,
            dimension_codes=dimension_codes,
            primary_dimension_code=primary_dimension_code,
        )
    return goal


def create_task(
    db: Session,
    revision_id: uuid.UUID,
    *,
    title: str,
    deadline=None,
    metric_target: Decimal | None = None,
    metric_unit: str | None = None,
) -> m.MgmtTask:
    count = len(list_tasks(db, revision_id))
    task = m.MgmtTask(
        revision_id=revision_id,
        title=title.strip(),
        deadline=deadline,
        metric_target=metric_target,
        metric_unit=metric_unit,
        sort_order=count,
    )
    db.add(task)
    db.flush()
    return task


def create_link(
    db: Session,
    revision_id: uuid.UUID,
    *,
    source_type: str,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    link_kind: str,
    meta: dict | None = None,
) -> m.MgmtEntityLink:
    from app.services.management_graph import GraphCycleError, check_hierarchical_cycle

    check_hierarchical_cycle(
        db,
        revision_id=revision_id,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        link_kind=link_kind,
    )
    link = m.MgmtEntityLink(
        revision_id=revision_id,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        link_kind=link_kind,
        meta=meta or {},
    )
    db.add(link)
    db.flush()
    return link


def build_flow_graph(db: Session, revision_id: uuid.UUID) -> dict:
    """React Flow nodes + edges for draft revision."""
    goals = list_goals(db, revision_id)
    tasks = list_tasks(db, revision_id)
    roles = list(
        db.scalars(select(m.MgmtRole).where(m.MgmtRole.revision_id == revision_id)).all()
    )
    maps = list(
        db.scalars(select(m.MgmtProcessMap).where(m.MgmtProcessMap.revision_id == revision_id)).all()
    )
    positions = list_current_positions(db, revision_id)
    links = list_links(db, revision_id)
    layouts = {
        (row.node_type, row.node_id): (float(row.x), float(row.y))
        for row in db.scalars(
            select(m.MgmtNodeLayout).where(m.MgmtNodeLayout.revision_id == revision_id)
        ).all()
    }

    nodes: list[dict] = []
    y = 0.0
    for g in goals:
        pos = layouts.get(("goal", g.id), (0.0, y))
        nodes.append(
            {
                "id": f"goal-{g.id}",
                "type": "mgmtNode",
                "position": {"x": pos[0], "y": pos[1]},
                "data": {
                    "label": g.title,
                    "entityType": "goal",
                    "entityId": str(g.id),
                    "status": g.status,
                    "stale": g.stale,
                },
            }
        )
        y += 80
    for t in tasks:
        pos = layouts.get(("task", t.id), (280.0, y))
        nodes.append(
            {
                "id": f"task-{t.id}",
                "type": "mgmtNode",
                "position": {"x": pos[0], "y": pos[1]},
                "data": {
                    "label": t.title,
                    "entityType": "task",
                    "entityId": str(t.id),
                    "status": t.status,
                    "stale": t.stale,
                },
            }
        )
        y += 80
    for r in roles:
        pos = layouts.get(("role", r.id), (560.0, y))
        nodes.append(
            {
                "id": f"role-{r.id}",
                "type": "mgmtNode",
                "position": {"x": pos[0], "y": pos[1]},
                "data": {
                    "label": r.title,
                    "entityType": "role",
                    "entityId": str(r.id),
                    "status": r.status,
                    "stale": r.stale,
                },
            }
        )
        y += 80
    for pm in maps:
        pos = layouts.get(("process_map", pm.id), (840.0, y))
        nodes.append(
            {
                "id": f"process_map-{pm.id}",
                "type": "mgmtNode",
                "position": {"x": pos[0], "y": pos[1]},
                "data": {
                    "label": pm.title,
                    "entityType": "process_map",
                    "entityId": str(pm.id),
                    "status": pm.status,
                    "stale": pm.stale,
                },
            }
        )
        y += 80
    for cp in positions:
        pos = layouts.get(("current_position", cp.id), (0.0, y + 200))
        nodes.append(
            {
                "id": f"current_position-{cp.id}",
                "type": "mgmtNode",
                "position": {"x": pos[0], "y": pos[1]},
                "data": {
                    "label": cp.title,
                    "entityType": "current_position",
                    "entityId": str(cp.id),
                    "status": "draft",
                    "stale": cp.stale,
                },
            }
        )

    edges = []
    for link in links:
        edges.append(
            {
                "id": str(link.id),
                "source": f"{link.source_type}-{link.source_id}",
                "target": f"{link.target_type}-{link.target_id}",
                "label": link.link_kind,
                "data": {"linkKind": link.link_kind},
            }
        )

    return {"nodes": nodes, "edges": edges}
