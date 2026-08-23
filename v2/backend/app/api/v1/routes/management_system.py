"""СУП — API routes (U1 skeleton)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    MgmtCurrentPositionIn,
    MgmtCurrentPositionOut,
    MgmtEntityLinkIn,
    MgmtEntityLinkOut,
    MgmtFlowGraphOut,
    MgmtGoalDimensionLinkOut,
    MgmtGoalDimensionOut,
    MgmtGoalIn,
    MgmtGoalOut,
    MgmtOverviewOut,
    MgmtSystemOut,
    MgmtTaskIn,
    MgmtTaskOut,
    MgmtTraceLinkOut,
    MgmtWizardSessionOut,
)
from app.services.management_graph import GraphCycleError, get_ancestors
from app.services.management_system import (
    check_dimension_balance_warning,
    goal_dimensions_map,
    list_goal_dimensions,
)

router = APIRouter(prefix="/management", tags=["management"])


def _require_mgmt_access():
    from app.services.tenancy import current_org_integrations, require_current_user, require_org_id

    user = require_current_user()
    org_id = require_org_id()
    features = (current_org_integrations() or {}).get("features") or {}
    if not features.get("management_system") and user.role != "platform_owner":
        raise HTTPException(status_code=403, detail="management_system feature is not enabled")
    return user, org_id


def _draft_revision_id(db: Session, org_id: uuid.UUID) -> uuid.UUID:
    from app.services.management_system import get_draft_revision, get_or_create_system

    user, _ = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id if user else None)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")
    return rev.id


@router.get("/overview", response_model=MgmtOverviewOut)
def get_overview(db: Session = Depends(get_db)) -> MgmtOverviewOut:
    from app.db import management_models as m
    from sqlalchemy import select
    from app.services.management_system import (
        get_draft_revision,
        get_or_create_system,
        list_current_positions,
        list_goals,
        list_links,
        list_tasks,
    )

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")

    wizard = db.scalar(
        select(m.MgmtWizardSession)
        .where(
            m.MgmtWizardSession.organization_id == org_id,
            m.MgmtWizardSession.status == "in_progress",
        )
        .order_by(m.MgmtWizardSession.updated_at.desc())
        .limit(1)
    )

    db.commit()
    goal_ids = [g.id for g in list_goals(db, rev.id)]
    dim_map = goal_dimensions_map(db, goal_ids)
    warnings: list[str] = []
    balance = check_dimension_balance_warning(db, rev.id)
    if balance:
        warnings.append(balance)

    def _goal_out(g) -> MgmtGoalOut:
        gap = None
        if g.baseline_value is not None and g.target_value is not None:
            gap = float(g.target_value - g.baseline_value)
        return MgmtGoalOut(
            id=g.id,
            revision_id=g.revision_id,
            title=g.title,
            weight=float(g.weight) if g.weight is not None else None,
            metric_unit=g.metric_unit,
            baseline_value=float(g.baseline_value) if g.baseline_value is not None else None,
            baseline_date=g.baseline_date,
            target_value=float(g.target_value) if g.target_value is not None else None,
            target_date=g.target_date,
            metric_source=g.metric_source,
            numeric_gap=gap,
            dimensions=[MgmtGoalDimensionLinkOut(**d) for d in dim_map.get(g.id, [])],
            status=g.status,
            stale=g.stale,
            cited_answer_ids=g.cited_answer_ids or [],
            sort_order=g.sort_order,
        )

    return MgmtOverviewOut(
        system=MgmtSystemOut.model_validate(system),
        goals=[_goal_out(g) for g in list_goals(db, rev.id)],
        tasks=[MgmtTaskOut.model_validate(t) for t in list_tasks(db, rev.id)],
        links=[MgmtEntityLinkOut.model_validate(l) for l in list_links(db, rev.id)],
        current_positions=[
            MgmtCurrentPositionOut.model_validate(p) for p in list_current_positions(db, rev.id)
        ],
        wizard=MgmtWizardSessionOut.model_validate(wizard) if wizard else None,
        warnings=warnings,
    )


@router.get("/graph", response_model=MgmtFlowGraphOut)
def get_graph(db: Session = Depends(get_db)) -> MgmtFlowGraphOut:
    from app.services.management_system import build_flow_graph

    user, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    data = build_flow_graph(db, rev_id)
    db.commit()
    return MgmtFlowGraphOut(**data)


@router.get("/trace/{entity_type}/{entity_id}", response_model=list[MgmtTraceLinkOut])
def trace_entity(entity_type: str, entity_id: str, db: Session = Depends(get_db)) -> list[MgmtTraceLinkOut]:
    user, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        eid = uuid.UUID(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid entity id") from exc
    rows = get_ancestors(db, revision_id=rev_id, entity_type=entity_type, entity_id=eid)
    db.commit()
    return [
        MgmtTraceLinkOut(
            source_type=r.source_type,
            source_id=r.source_id,
            target_type=r.target_type,
            target_id=r.target_id,
            link_kind=r.link_kind,
            depth=r.depth,
        )
        for r in rows
    ]


@router.get("/goal-dimensions", response_model=list[MgmtGoalDimensionOut])
def get_goal_dimensions(db: Session = Depends(get_db)) -> list[MgmtGoalDimensionOut]:
    _require_mgmt_access()
    dims = list_goal_dimensions(db)
    db.commit()
    return [MgmtGoalDimensionOut.model_validate(d) for d in dims]


@router.post("/goals", response_model=MgmtGoalOut, status_code=201)
def create_goal(body: MgmtGoalIn, db: Session = Depends(get_db)) -> MgmtGoalOut:
    from app.services.management_system import _numeric_gap, create_goal as svc_create_goal

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    goal = svc_create_goal(
        db,
        rev_id,
        title=body.title,
        weight=body.weight,
        metric_unit=body.metric_unit,
        baseline_value=body.baseline_value,
        baseline_date=body.baseline_date,
        target_value=body.target_value,
        target_date=body.target_date,
        metric_source=body.metric_source,
        dimension_codes=body.dimension_codes,
        primary_dimension_code=body.primary_dimension_code,
        cited_answer_ids=body.cited_answer_ids,
    )
    db.commit()
    dim_map = goal_dimensions_map(db, [goal.id])
    gap = _numeric_gap(goal)
    return MgmtGoalOut(
        id=goal.id,
        revision_id=goal.revision_id,
        title=goal.title,
        weight=float(goal.weight) if goal.weight is not None else None,
        metric_unit=goal.metric_unit,
        baseline_value=float(goal.baseline_value) if goal.baseline_value is not None else None,
        baseline_date=goal.baseline_date,
        target_value=float(goal.target_value) if goal.target_value is not None else None,
        target_date=goal.target_date,
        metric_source=goal.metric_source,
        numeric_gap=float(gap) if gap is not None else None,
        dimensions=[MgmtGoalDimensionLinkOut(**d) for d in dim_map.get(goal.id, [])],
        status=goal.status,
        stale=goal.stale,
        cited_answer_ids=goal.cited_answer_ids or [],
        sort_order=goal.sort_order,
    )


@router.post("/tasks", response_model=MgmtTaskOut, status_code=201)
def create_task(body: MgmtTaskIn, db: Session = Depends(get_db)) -> MgmtTaskOut:
    from app.services.management_system import create_task as svc_create_task

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    task = svc_create_task(
        db,
        rev_id,
        title=body.title,
        deadline=body.deadline,
        metric_target=body.metric_target,
        metric_unit=body.metric_unit,
    )
    db.commit()
    return MgmtTaskOut.model_validate(task)


@router.post("/links", response_model=MgmtEntityLinkOut, status_code=201)
def create_link(body: MgmtEntityLinkIn, db: Session = Depends(get_db)) -> MgmtEntityLinkOut:
    from app.services.management_system import create_link as svc_create_link

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        link = svc_create_link(
            db,
            rev_id,
            source_type=body.source_type,
            source_id=body.source_id,
            target_type=body.target_type,
            target_id=body.target_id,
            link_kind=body.link_kind,
            meta=body.meta,
        )
    except GraphCycleError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "GRAPH_CYCLE", "path": exc.path},
        ) from exc
    db.commit()
    return MgmtEntityLinkOut.model_validate(link)


@router.post("/current-positions", response_model=MgmtCurrentPositionOut, status_code=201)
def create_current_position(
    body: MgmtCurrentPositionIn, db: Session = Depends(get_db)
) -> MgmtCurrentPositionOut:
    from app.db import management_models as m
    from app.services.management_system import list_current_positions

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    count = len(list_current_positions(db, rev_id))
    pos = m.MgmtCurrentPosition(
        revision_id=rev_id,
        title=body.title.strip(),
        headcount=body.headcount,
        sort_order=count,
    )
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return MgmtCurrentPositionOut.model_validate(pos)


@router.post("/wizard/resume", response_model=MgmtWizardSessionOut)
def resume_wizard(db: Session = Depends(get_db)) -> MgmtWizardSessionOut:
    from app.db import management_models as m
    from app.services.management_system import get_draft_revision, get_or_create_system
    from sqlalchemy import select

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    session = db.scalar(
        select(m.MgmtWizardSession)
        .where(
            m.MgmtWizardSession.organization_id == org_id,
            m.MgmtWizardSession.status == "in_progress",
        )
        .order_by(m.MgmtWizardSession.updated_at.desc())
        .limit(1)
    )
    if not session:
        session = m.MgmtWizardSession(
            organization_id=org_id,
            revision_id=rev.id if rev else None,
            step=1,
            status="in_progress",
        )
        db.add(session)
    elif rev and not session.revision_id:
        session.revision_id = rev.id
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)
