"""СУП domain service — system/revision CRUD and graph export (U1)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m

SYSTEM_KINDS = ("company", "holding", "demo")


def list_systems(
    db: Session, organization_id: uuid.UUID, *, include_archived: bool = False
) -> list[m.MgmtSystem]:
    q = select(m.MgmtSystem).where(m.MgmtSystem.organization_id == organization_id)
    if not include_archived:
        q = q.where(m.MgmtSystem.is_archived.is_(False))
    q = q.order_by(m.MgmtSystem.created_at.asc())
    return list(db.scalars(q).all())


def _get_pref(
    db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID | None
) -> m.MgmtWorkspacePref | None:
    if not user_id:
        return None
    return db.scalar(
        select(m.MgmtWorkspacePref).where(
            m.MgmtWorkspacePref.organization_id == organization_id,
            m.MgmtWorkspacePref.user_id == user_id,
        )
    )


def get_or_create_pref(
    db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID
) -> m.MgmtWorkspacePref:
    pref = _get_pref(db, organization_id=organization_id, user_id=user_id)
    if pref:
        return pref
    pref = m.MgmtWorkspacePref(organization_id=organization_id, user_id=user_id)
    db.add(pref)
    db.flush()
    return pref


def set_active_system(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    system_id: uuid.UUID,
) -> m.MgmtSystem:
    system = db.get(m.MgmtSystem, system_id)
    if not system or system.organization_id != organization_id:
        raise ValueError("System not found")
    if system.is_archived:
        raise ValueError("System is archived")
    pref = get_or_create_pref(db, organization_id=organization_id, user_id=user_id)
    pref.active_system_id = system.id
    db.flush()
    return system


def create_system(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    *,
    title: str,
    kind: str = "company",
    parent_system_id: uuid.UUID | None = None,
    activate: bool = True,
) -> m.MgmtSystem:
    kind = (kind or "company").strip().lower()
    if kind not in SYSTEM_KINDS:
        raise ValueError(f"Unknown kind: {kind}")
    title = (title or "").strip() or "Новая система"
    if parent_system_id:
        parent = db.get(m.MgmtSystem, parent_system_id)
        if not parent or parent.organization_id != organization_id:
            raise ValueError("Parent system not found")
        if parent.kind != "holding":
            raise ValueError("Parent must be a holding system")

    system = m.MgmtSystem(
        organization_id=organization_id,
        title=title,
        kind=kind,
        parent_system_id=parent_system_id,
        status="draft",
    )
    db.add(system)
    db.flush()
    rev = _create_revision(db, system, user_id, version_number=1)
    system.draft_revision_id = rev.id
    db.flush()
    if activate and user_id:
        set_active_system(
            db, organization_id=organization_id, user_id=user_id, system_id=system.id
        )
    return system


def get_or_create_system(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID | None) -> m.MgmtSystem:
    """Активная система пользователя или первая в org; иначе создать «Основная система»."""
    systems = list_systems(db, organization_id)
    if systems:
        if user_id:
            pref = _get_pref(db, organization_id=organization_id, user_id=user_id)
            if pref and pref.active_system_id:
                active = next((s for s in systems if s.id == pref.active_system_id), None)
                if active:
                    if not active.draft_revision_id:
                        rev = _create_revision(db, active, user_id, version_number=1)
                        active.draft_revision_id = rev.id
                        db.flush()
                    return active
            # авто-выбор первой при отсутствии prefs
            preferred = systems[0]
            set_active_system(
                db, organization_id=organization_id, user_id=user_id, system_id=preferred.id
            )
            return preferred
        system = systems[0]
        if not system.draft_revision_id:
            rev = _create_revision(db, system, user_id, version_number=1)
            system.draft_revision_id = rev.id
            db.flush()
        return system

    system = create_system(
        db,
        organization_id,
        user_id,
        title="Основная система",
        kind="company",
        activate=bool(user_id),
    )
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


ALLOWED_LAYOUT_NODE_TYPES = (
    "goal",
    "task",
    "role",
    "process_map",
    "process_step",
    "current_position",
    "org_node",
)


def upsert_node_layouts(
    db: Session,
    revision_id: uuid.UUID,
    items: list[dict],
) -> int:
    """Сохранить позиции узлов карты (draft revision). Возвращает число upsert."""
    if not items:
        return 0
    existing = {
        (row.node_type, row.node_id): row
        for row in db.scalars(
            select(m.MgmtNodeLayout).where(m.MgmtNodeLayout.revision_id == revision_id)
        ).all()
    }
    n = 0
    for item in items:
        node_type = str(item.get("node_type") or "").strip()
        if node_type not in ALLOWED_LAYOUT_NODE_TYPES:
            continue
        try:
            node_id = item["node_id"] if isinstance(item.get("node_id"), uuid.UUID) else uuid.UUID(str(item["node_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        try:
            x = float(item.get("x", 0))
            y = float(item.get("y", 0))
        except (TypeError, ValueError):
            continue
        key = (node_type, node_id)
        row = existing.get(key)
        if row:
            row.x = x
            row.y = y
        else:
            row = m.MgmtNodeLayout(
                revision_id=revision_id,
                node_type=node_type,
                node_id=node_id,
                x=x,
                y=y,
            )
            db.add(row)
            existing[key] = row
        n += 1
    db.flush()
    return n


def clear_draft_l0_l1(db: Session, revision_id: uuid.UUID) -> None:
    """Удалить черновики L0/L1 перед повторной генерацией из интервью."""
    goals = [g for g in list_goals(db, revision_id) if g.status == "draft"]
    _delete_draft_goals_and_tasks(db, revision_id, goals)


def clear_draft_goals_for_dimension(db: Session, revision_id: uuid.UUID, dimension_code: str) -> None:
    """Удалить черновые цели только одного BSC-блока (scoped merge)."""
    goals = list_goals(db, revision_id)
    dim_map = goal_dimensions_map(db, [g.id for g in goals])
    to_delete: list[m.MgmtGoal] = []
    for g in goals:
        if g.status != "draft":
            continue
        dims = dim_map.get(g.id, [])
        primary = next((d for d in dims if d.get("is_primary")), None)
        if primary and primary["code"] == dimension_code:
            to_delete.append(g)
        elif not primary and any(d["code"] == dimension_code for d in dims):
            to_delete.append(g)
    _delete_draft_goals_and_tasks(db, revision_id, to_delete)


def _delete_draft_goals_and_tasks(db: Session, revision_id: uuid.UUID, goals: list[m.MgmtGoal]) -> None:
    tasks = [t for t in list_tasks(db, revision_id) if t.status == "draft"]
    goal_ids = {g.id for g in goals}
    task_ids = {t.id for t in tasks}

    for link in list_links(db, revision_id):
        if link.link_kind == "decomposes" and (
            (link.source_type == "goal" and link.source_id in goal_ids)
            or (link.target_type == "task" and link.target_id in task_ids and link.source_id in goal_ids)
        ):
            db.delete(link)

    for gid in goal_ids:
        for link in db.scalars(
            select(m.MgmtGoalDimensionLink).where(m.MgmtGoalDimensionLink.goal_id == gid)
        ).all():
            db.delete(link)

    linked_task_ids = set()
    for link in list_links(db, revision_id):
        if link.link_kind == "decomposes" and link.source_type == "goal" and link.source_id in goal_ids:
            linked_task_ids.add(link.target_id)
    for tid in linked_task_ids:
        task = db.get(m.MgmtTask, tid)
        if task and task.status == "draft":
            db.delete(task)

    for g in goals:
        db.delete(g)
    db.flush()


def update_goal(
    db: Session,
    goal: m.MgmtGoal,
    *,
    title: str | None = None,
    baseline_value: Decimal | None = None,
    target_value: Decimal | None = None,
    metric_unit: str | None = None,
    metric_source: str | None = None,
    fields_set: set[str] | None = None,
) -> m.MgmtGoal:
    fs = fields_set or set()
    if "title" in fs and title is not None:
        goal.title = title.strip()
    if "baseline_value" in fs:
        goal.baseline_value = baseline_value
        if baseline_value is not None and not goal.metric_source:
            goal.metric_source = "owner"
    if "target_value" in fs:
        goal.target_value = target_value
        if target_value is not None and not goal.metric_source:
            goal.metric_source = "owner"
    if "metric_unit" in fs:
        goal.metric_unit = metric_unit.strip() if metric_unit else None
    if "metric_source" in fs:
        goal.metric_source = metric_source
    db.flush()
    return goal


def approve_goal(db: Session, goal: m.MgmtGoal) -> m.MgmtGoal:
    if goal.status == "approved":
        return goal
    goal.status = "approved"
    db.flush()
    return goal


def approve_task(db: Session, task: m.MgmtTask) -> m.MgmtTask:
    if task.status == "approved":
        return task
    task.status = "approved"
    db.flush()
    return task


def approve_all_draft_goals(db: Session, revision_id: uuid.UUID) -> int:
    """Утвердить draft и suggested (подсказки пакета)."""
    n = 0
    for g in list_goals(db, revision_id):
        if g.status in ("draft", "suggested"):
            approve_goal(db, g)
            n += 1
    return n


def approve_all_draft_tasks(db: Session, revision_id: uuid.UUID) -> int:
    """Утвердить draft и suggested (подсказки пакета)."""
    n = 0
    for t in list_tasks(db, revision_id):
        if t.status in ("draft", "suggested"):
            approve_task(db, t)
            n += 1
    return n


def import_positions_from_text(db: Session, revision_id: uuid.UUID, text: str) -> list[m.MgmtCurrentPosition]:
    """CSV/paste: «должность;headcount» или «должность» (headcount=1)."""
    import csv
    import io

    rows: list[tuple[str, int]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("title"):
            continue
        if ";" in line or "\t" in line:
            delim = ";" if ";" in line else "\t"
            parts = [p.strip() for p in line.split(delim)]
            title = parts[0]
            hc = 1
            if len(parts) > 1 and parts[1].isdigit():
                hc = max(1, int(parts[1]))
            if title:
                rows.append((title, hc))
        else:
            reader = csv.reader(io.StringIO(line))
            for row in reader:
                if not row:
                    continue
                title = row[0].strip()
                hc = 1
                if len(row) > 1 and str(row[1]).strip().isdigit():
                    hc = max(1, int(str(row[1]).strip()))
                if title:
                    rows.append((title, hc))

    created: list[m.MgmtCurrentPosition] = []
    base = len(list_current_positions(db, revision_id))
    for i, (title, hc) in enumerate(rows):
        pos = m.MgmtCurrentPosition(
            revision_id=revision_id,
            title=title,
            headcount=hc,
            sort_order=base + i,
        )
        db.add(pos)
        created.append(pos)
    db.flush()
    return created


def list_inherited_goals(db: Session, system: m.MgmtSystem) -> list[m.MgmtGoal]:
    """Утверждённые цели родительского холдинга (read-only контекст)."""
    if not system.parent_system_id:
        return []
    parent = db.get(m.MgmtSystem, system.parent_system_id)
    if not parent or not parent.draft_revision_id:
        return []
    return [g for g in list_goals(db, parent.draft_revision_id) if g.status == "approved"]


def goal_to_out_dict(db: Session, goal: m.MgmtGoal, *, scope: str = "own") -> dict:
    dim_map = goal_dimensions_map(db, [goal.id])
    gap = _numeric_gap(goal)
    return {
        "id": goal.id,
        "revision_id": goal.revision_id,
        "title": goal.title,
        "weight": float(goal.weight) if goal.weight is not None else None,
        "metric_unit": goal.metric_unit,
        "baseline_value": float(goal.baseline_value) if goal.baseline_value is not None else None,
        "baseline_date": goal.baseline_date,
        "target_value": float(goal.target_value) if goal.target_value is not None else None,
        "target_date": goal.target_date,
        "metric_source": goal.metric_source,
        "numeric_gap": float(gap) if gap is not None else None,
        "dimensions": dim_map.get(goal.id, []),
        "status": goal.status,
        "stale": goal.stale,
        "cited_answer_ids": goal.cited_answer_ids or [],
        "sort_order": goal.sort_order,
        "scope": scope,
    }
