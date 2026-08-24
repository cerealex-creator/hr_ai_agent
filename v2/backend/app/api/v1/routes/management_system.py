"""СУП — API routes (U1 skeleton)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    MgmtApproveOut,
    MgmtBulkApproveOut,
    MgmtBusinessProfileIn,
    MgmtBusinessProfileOut,
    MgmtBusinessProfileSchemaOut,
    MgmtCurrentPositionIn,
    MgmtCurrentPositionOut,
    MgmtEntityLinkIn,
    MgmtEntityLinkOut,
    MgmtFlowGraphOut,
    MgmtGateActionIn,
    MgmtGateActionOut,
    MgmtGateLevelOut,
    MgmtGateSummaryOut,
    MgmtGoalBlockAnswerIn,
    MgmtL3PreviewOut,
    MgmtNodeLayoutBatchIn,
    MgmtNodeLayoutBatchOut,
    MgmtImpactOut,
    MgmtChangesSummaryOut,
    MgmtCoverageTrackerOut,
    MgmtCriticOut,
    MgmtGapItemStoredOut,
    MgmtPolishIn,
    MgmtPolishOut,
    MgmtPublishIn,
    MgmtPublishOut,
    MgmtRoleVacancyApplyIn,
    MgmtRoleVacancyApplyOut,
    MgmtRoleVacancyPreviewOut,
    MgmtTransitionDraftOut,
    MgmtTransitionStepOut,
    MgmtTransitionStepUpdateIn,
    MgmtRoleDocLineIn,
    MgmtRoleDocumentOut,
    MgmtRoleDocsMaterializeIn,
    MgmtRoleDocsMaterializeOut,
    MgmtGoalBlockAnswerOut,
    MgmtGoalBlockApproveIn,
    MgmtGoalBlockGenerateOut,
    MgmtGoalBlockOut,
    MgmtGoalBlockQuestionOut,
    MgmtGoalDimensionLinkOut,
    MgmtGoalDimensionOut,
    MgmtGoalIn,
    MgmtGoalOut,
    MgmtGoalUpdateIn,
    MgmtGapReportOut,
    MgmtImplementationOut,
    MgmtIndustryPackOut,
    MgmtPackApplyIn,
    MgmtPackApplyOut,
    MgmtInterviewAnswerOut,
    MgmtInterviewQuestionOut,
    MgmtInterviewSessionOut,
    MgmtOverviewOut,
    MgmtProcessMapOut,
    MgmtRoleAssignmentIn,
    MgmtRoleAssignmentOut,
    MgmtRoleAssignmentUpdateIn,
    MgmtRoleOut,
    MgmtSystemCreateIn,
    MgmtSystemOut,
    MgmtSystemsListOut,
    MgmtTaskIn,
    MgmtTaskOut,
    MgmtTraceLinkOut,
    MgmtWizardAnswerIn,
    MgmtWizardApproveOut,
    MgmtWizardGenerateOut,
    MgmtWizardSessionOut,
    MgmtWizardStateOut,
    MgmtWizardStep1In,
)
from app.services.management_graph import GraphCycleError, get_ancestors
from app.services.management_system import (
    approve_all_draft_goals,
    approve_all_draft_tasks,
    approve_goal,
    approve_task,
    check_dimension_balance_warning,
    goal_dimensions_map,
    goal_to_out_dict,
    list_goal_dimensions,
)

router = APIRouter(prefix="/management", tags=["management"])


def _goal_out(db, g, *, scope: str = "own") -> MgmtGoalOut:
    d = goal_to_out_dict(db, g, scope=scope)
    return MgmtGoalOut(
        **{
            **d,
            "dimensions": [MgmtGoalDimensionLinkOut(**x) for x in d["dimensions"]],
        }
    )


def _goal_block_out(db, block: dict) -> MgmtGoalBlockOut:
    return MgmtGoalBlockOut(
        code=block["code"],
        title=block["title"],
        subtitle=block["subtitle"],
        sort_order=block["sort_order"],
        status=block["status"],
        questions=[MgmtGoalBlockQuestionOut(**q) for q in block["questions"]],
        answers=[MgmtGoalBlockAnswerOut.model_validate(a) for a in block["answers"]],
        goals=[_goal_out(db, g) for g in block["goals"]],
        goals_count=block["goals_count"],
        approved_count=block["approved_count"],
    )


def _require_mgmt_access():
    from app.core.auth import ROLE_PLATFORM_OWNER
    from app.services.tenancy import current_org_integrations, require_current_user, require_org_id

    user = require_current_user()
    org_id = require_org_id()
    features = (current_org_integrations() or {}).get("features") or {}
    is_owner = user.auth_disabled or ROLE_PLATFORM_OWNER in (user.roles or ())
    if not features.get("management_system") and not is_owner:
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


@router.get("/systems", response_model=MgmtSystemsListOut)
def list_mgmt_systems(db: Session = Depends(get_db)) -> MgmtSystemsListOut:
    from app.services.management_system import get_or_create_system, list_systems

    user, org_id = _require_mgmt_access()
    active = get_or_create_system(db, org_id, user.id)
    systems = list_systems(db, org_id)
    db.commit()
    return MgmtSystemsListOut(
        systems=[MgmtSystemOut.model_validate(s) for s in systems],
        active_system_id=active.id,
    )


@router.post("/systems", response_model=MgmtSystemOut, status_code=201)
def create_mgmt_system(body: MgmtSystemCreateIn, db: Session = Depends(get_db)) -> MgmtSystemOut:
    from app.services.management_system import create_system

    user, org_id = _require_mgmt_access()
    try:
        system = create_system(
            db,
            org_id,
            user.id,
            title=body.title,
            kind=body.kind,
            parent_system_id=body.parent_system_id,
            activate=body.activate,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(system)
    return MgmtSystemOut.model_validate(system)


@router.post("/systems/{system_id}/activate", response_model=MgmtSystemOut)
def activate_mgmt_system(system_id: str, db: Session = Depends(get_db)) -> MgmtSystemOut:
    from app.services.management_system import set_active_system

    user, org_id = _require_mgmt_access()
    try:
        sid = uuid.UUID(system_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid system id") from exc
    try:
        system = set_active_system(
            db, organization_id=org_id, user_id=user.id, system_id=sid
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return MgmtSystemOut.model_validate(system)


@router.get("/export/goals.html")
def export_goals_html(db: Session = Depends(get_db)):
    from fastapi.responses import HTMLResponse

    from app.services.management_export import build_goals_pack_html
    from app.services.management_system import get_draft_revision, get_or_create_system

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")
    html_body = build_goals_pack_html(db, system=system, revision_id=rev.id)
    db.commit()
    return HTMLResponse(content=html_body)


@router.get("/export/goals.docx")
def export_goals_docx(db: Session = Depends(get_db)):
    from fastapi.responses import Response

    from app.services.management_export import build_goals_pack_docx, safe_filename
    from app.services.management_system import get_draft_revision, get_or_create_system

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")
    data = build_goals_pack_docx(db, system=system, revision_id=rev.id)
    filename = safe_filename(system.title, ".docx")
    db.commit()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/overview", response_model=MgmtOverviewOut)
def get_overview(db: Session = Depends(get_db)) -> MgmtOverviewOut:
    from app.db import management_models as m
    from sqlalchemy import select
    from app.services.management_system import (
        get_draft_revision,
        get_or_create_system,
        list_current_positions,
        list_goals,
        list_inherited_goals,
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
            m.MgmtWizardSession.revision_id == rev.id,
        )
        .order_by(m.MgmtWizardSession.updated_at.desc())
        .limit(1)
    )

    warnings: list[str] = []
    balance = check_dimension_balance_warning(db, rev.id)
    if balance:
        warnings.append(balance)

    return MgmtOverviewOut(
        system=MgmtSystemOut.model_validate(system),
        goals=[_goal_out(db, g) for g in list_goals(db, rev.id)],
        inherited_goals=[_goal_out(db, g, scope="holding") for g in list_inherited_goals(db, system)],
        tasks=[MgmtTaskOut.model_validate(t) for t in list_tasks(db, rev.id)],
        links=[MgmtEntityLinkOut.model_validate(l) for l in list_links(db, rev.id)],
        current_positions=[
            MgmtCurrentPositionOut.model_validate(p) for p in list_current_positions(db, rev.id)
        ],
        wizard=MgmtWizardSessionOut.model_validate(wizard) if wizard else None,
        warnings=warnings,
    )
    db.commit()


@router.get("/graph", response_model=MgmtFlowGraphOut)
def get_graph(db: Session = Depends(get_db)) -> MgmtFlowGraphOut:
    from app.services.management_system import build_flow_graph

    user, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    data = build_flow_graph(db, rev_id)
    db.commit()
    return MgmtFlowGraphOut(**data)


@router.put("/graph/layout", response_model=MgmtNodeLayoutBatchOut)
def save_graph_layout(body: MgmtNodeLayoutBatchIn, db: Session = Depends(get_db)) -> MgmtNodeLayoutBatchOut:
    from app.services.management_system import upsert_node_layouts

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    saved = upsert_node_layouts(
        db,
        rev_id,
        [item.model_dump() for item in body.items],
    )
    db.commit()
    return MgmtNodeLayoutBatchOut(saved=saved)


@router.get("/l3-preview", response_model=MgmtL3PreviewOut)
def get_l3_preview(db: Session = Depends(get_db)) -> MgmtL3PreviewOut:
    from app.services.management_l3_preview import build_l3_preview
    from app.services.management_system import get_draft_revision, get_or_create_system

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")
    data = build_l3_preview(db, rev.id)
    db.commit()
    return MgmtL3PreviewOut(**data)


@router.get("/role-documents", response_model=list[MgmtRoleDocumentOut])
def get_role_documents(db: Session = Depends(get_db)) -> list[MgmtRoleDocumentOut]:
    from app.services.management_role_docs import document_out, list_role_documents

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    docs = list_role_documents(db, rev_id)
    db.commit()
    return [MgmtRoleDocumentOut(**document_out(db, d)) for d in docs]


@router.post("/role-documents/materialize", response_model=MgmtRoleDocsMaterializeOut)
def materialize_role_documents_route(
    body: MgmtRoleDocsMaterializeIn, db: Session = Depends(get_db)
) -> MgmtRoleDocsMaterializeOut:
    from app.services.management_role_docs import RoleDocError, materialize_role_documents

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        result = materialize_role_documents(db, rev_id, role_id=body.role_id)
    except RoleDocError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    db.commit()
    return MgmtRoleDocsMaterializeOut(**result)


@router.post("/role-documents/{document_id}/approve", response_model=MgmtRoleDocumentOut)
def approve_role_document_route(document_id: str, db: Session = Depends(get_db)) -> MgmtRoleDocumentOut:
    from app.services.management_role_docs import RoleDocError, approve_role_document, document_out

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        did = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document id") from exc
    try:
        doc = approve_role_document(db, rev_id, did)
    except RoleDocError as exc:
        db.rollback()
        status = 404 if exc.code == "NOT_FOUND" else 422
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": exc.message, "errors": exc.errors},
        ) from exc
    db.commit()
    db.refresh(doc)
    return MgmtRoleDocumentOut(**document_out(db, doc))


@router.post("/role-documents/{document_id}/lines", response_model=MgmtRoleDocumentOut, status_code=201)
def add_role_document_line_route(
    document_id: str, body: MgmtRoleDocLineIn, db: Session = Depends(get_db)
) -> MgmtRoleDocumentOut:
    from decimal import Decimal

    from app.db import management_models as m
    from app.services.management_role_docs import RoleDocError, add_manual_line, document_out

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        did = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document id") from exc
    try:
        add_manual_line(
            db,
            rev_id,
            did,
            title=body.title,
            target_value=Decimal(str(body.target_value)) if body.target_value is not None else None,
            metric_unit=body.metric_unit,
            source_task_id=body.source_task_id,
        )
    except RoleDocError as exc:
        db.rollback()
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": exc.message, "errors": exc.errors},
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    doc = db.get(m.MgmtRoleDocument, did)
    return MgmtRoleDocumentOut(**document_out(db, doc))


@router.post("/role-documents/polish", response_model=MgmtPolishOut)
def polish_role_documents_route(
    body: MgmtPolishIn, db: Session = Depends(get_db)
) -> MgmtPolishOut:
    from app.core.config import get_settings
    from app.services.management_l3_polish import polish_revision_documents

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        result = polish_revision_documents(
            get_settings(),
            db,
            rev_id,
            document_id=body.document_id,
            use_ai=body.use_ai,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return MgmtPolishOut(**result)


@router.post("/role-documents/critic", response_model=MgmtCriticOut)
def critic_role_documents_route(
    use_llm: bool = False, db: Session = Depends(get_db)
) -> MgmtCriticOut:
    from app.core.config import get_settings
    from app.services.management_l3_critic import run_l3_publish_critic

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    result = run_l3_publish_critic(
        get_settings() if use_llm else None,
        db,
        rev_id,
        use_llm=use_llm,
    )
    db.commit()
    return MgmtCriticOut(**result)


@router.post("/role-documents/publish", response_model=MgmtPublishOut)
def publish_role_documents_route(
    body: MgmtPublishIn, db: Session = Depends(get_db)
) -> MgmtPublishOut:
    from app.core.config import get_settings
    from app.services.management_l3_critic import run_l3_publish_critic
    from app.services.management_role_docs import publish_role_documents

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    critic = run_l3_publish_critic(
        get_settings() if body.use_llm_critic else None,
        db,
        rev_id,
        use_llm=body.use_llm_critic,
    )
    critic_out = MgmtCriticOut(**critic)
    if not critic["ok"] and not body.force:
        db.rollback()
        return MgmtPublishOut(ok=False, published_count=0, skipped=[], critic=critic_out)
    if not critic["ok"] and body.force:
        # force не обходит blocking
        db.rollback()
        return MgmtPublishOut(ok=False, published_count=0, skipped=["blocking_present"], critic=critic_out)

    result = publish_role_documents(db, rev_id, document_ids=body.document_ids)
    db.commit()
    return MgmtPublishOut(ok=True, critic=critic_out, **result)


@router.get("/changes", response_model=MgmtChangesSummaryOut)
def get_changes_summary(db: Session = Depends(get_db)) -> MgmtChangesSummaryOut:
    from app.services.management_role_docs import build_changes_summary

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    data = build_changes_summary(db, rev_id)
    db.commit()
    return MgmtChangesSummaryOut(**data)


@router.post("/transition/draft", response_model=MgmtTransitionDraftOut)
def draft_transition_plan(db: Session = Depends(get_db)) -> MgmtTransitionDraftOut:
    from app.services.management_transition import draft_transition_steps_from_gap

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    result = draft_transition_steps_from_gap(db, rev_id)
    db.commit()
    return MgmtTransitionDraftOut(**result)


@router.get("/transition/steps", response_model=list[MgmtTransitionStepOut])
def get_transition_steps(db: Session = Depends(get_db)) -> list[MgmtTransitionStepOut]:
    from app.services.management_transition import list_transition_steps, transition_step_out

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    steps = list_transition_steps(db, rev_id)
    db.commit()
    return [MgmtTransitionStepOut(**transition_step_out(s)) for s in steps]


@router.get("/transition/gap-items", response_model=list[MgmtGapItemStoredOut])
def get_stored_gap_items(db: Session = Depends(get_db)) -> list[MgmtGapItemStoredOut]:
    from app.services.management_transition import gap_item_out, list_gap_items

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    items = list_gap_items(db, rev_id)
    db.commit()
    return [MgmtGapItemStoredOut(**gap_item_out(i)) for i in items]


@router.post("/transition/steps/{step_id}/approve", response_model=MgmtTransitionStepOut)
def approve_transition_step_route(step_id: str, db: Session = Depends(get_db)) -> MgmtTransitionStepOut:
    from app.services.management_transition import (
        TransitionError,
        approve_transition_step,
        transition_step_out,
    )

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        sid = uuid.UUID(step_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid step id") from exc
    try:
        step = approve_transition_step(db, rev_id, sid)
    except TransitionError as exc:
        db.rollback()
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message}) from exc
    db.commit()
    return MgmtTransitionStepOut(**transition_step_out(step))


@router.post("/transition/steps/{step_id}/reject", response_model=MgmtTransitionStepOut)
def reject_transition_step_route(step_id: str, db: Session = Depends(get_db)) -> MgmtTransitionStepOut:
    from app.services.management_transition import (
        TransitionError,
        reject_transition_step,
        transition_step_out,
    )

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        sid = uuid.UUID(step_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid step id") from exc
    try:
        step = reject_transition_step(db, rev_id, sid)
    except TransitionError as exc:
        db.rollback()
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message}) from exc
    db.commit()
    return MgmtTransitionStepOut(**transition_step_out(step))


@router.patch("/transition/steps/{step_id}", response_model=MgmtTransitionStepOut)
def update_transition_step_route(
    step_id: str, body: MgmtTransitionStepUpdateIn, db: Session = Depends(get_db)
) -> MgmtTransitionStepOut:
    from app.services.management_transition import (
        TransitionError,
        transition_step_out,
        update_transition_step,
    )

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        sid = uuid.UUID(step_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid step id") from exc
    try:
        step = update_transition_step(
            db,
            rev_id,
            sid,
            title=body.title,
            description=body.description,
            horizon=body.horizon,
        )
    except TransitionError as exc:
        db.rollback()
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message}) from exc
    db.commit()
    return MgmtTransitionStepOut(**transition_step_out(step))


@router.get("/coverage", response_model=MgmtCoverageTrackerOut)
def get_coverage_tracker(db: Session = Depends(get_db)) -> MgmtCoverageTrackerOut:
    from app.services.management_transition import build_coverage_tracker

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    data = build_coverage_tracker(db, rev_id)
    db.commit()
    return MgmtCoverageTrackerOut(**data)


@router.get("/roles/{role_id}/vacancy-profile-preview", response_model=MgmtRoleVacancyPreviewOut)
def preview_role_vacancy_profile(role_id: str, db: Session = Depends(get_db)) -> MgmtRoleVacancyPreviewOut:
    from app.services.management_transition import TransitionError, build_role_vacancy_profile_preview

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        rid = uuid.UUID(role_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid role id") from exc
    try:
        data = build_role_vacancy_profile_preview(db, rev_id, rid)
    except TransitionError as exc:
        raise HTTPException(
            status_code=404 if exc.code == "NOT_FOUND" else 400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    db.commit()
    return MgmtRoleVacancyPreviewOut(**data)


@router.post("/roles/apply-vacancy-profile", response_model=MgmtRoleVacancyApplyOut)
def apply_role_vacancy_profile(
    body: MgmtRoleVacancyApplyIn, db: Session = Depends(get_db)
) -> MgmtRoleVacancyApplyOut:
    from app.services.management_transition import TransitionError, apply_role_profile_to_vacancy

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        data = apply_role_profile_to_vacancy(
            db,
            organization_id=org_id,
            vacancy_id=body.vacancy_id,
            revision_id=rev_id,
            role_id=body.role_id,
        )
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=404 if exc.code == "NOT_FOUND" else 400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    db.commit()
    return MgmtRoleVacancyApplyOut(**data)


@router.get("/impact/{entity_type}/{entity_id}", response_model=MgmtImpactOut)
def get_impact(entity_type: str, entity_id: str, db: Session = Depends(get_db)) -> MgmtImpactOut:
    from app.services.management_role_docs import get_impact_set

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        eid = uuid.UUID(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid entity id") from exc
    items = get_impact_set(db, revision_id=rev_id, entity_type=entity_type, entity_id=eid)
    db.commit()
    return MgmtImpactOut(items=items, stale_marked=0)


@router.post("/impact/{entity_type}/{entity_id}/mark-stale", response_model=MgmtImpactOut)
def mark_impact_stale(entity_type: str, entity_id: str, db: Session = Depends(get_db)) -> MgmtImpactOut:
    from app.services.management_role_docs import get_impact_set, mark_stale_downstream

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        eid = uuid.UUID(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid entity id") from exc
    n = mark_stale_downstream(db, revision_id=rev_id, entity_type=entity_type, entity_id=eid)
    items = get_impact_set(db, revision_id=rev_id, entity_type=entity_type, entity_id=eid)
    db.commit()
    return MgmtImpactOut(items=items, stale_marked=n)


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
    from app.services.management_system import create_goal as svc_create_goal

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
    return _goal_out(db, goal)


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
    from app.services.management_wizard import get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)


@router.get("/industry-packs", response_model=list[MgmtIndustryPackOut])
def get_industry_packs(db: Session = Depends(get_db)) -> list[MgmtIndustryPackOut]:
    from app.services.management_packs import list_industry_packs

    _require_mgmt_access()
    db.commit()
    return [MgmtIndustryPackOut(**p) for p in list_industry_packs()]


@router.post("/industry-packs/apply", response_model=MgmtPackApplyOut)
def apply_industry_pack_route(
    body: MgmtPackApplyIn, db: Session = Depends(get_db)
) -> MgmtPackApplyOut:
    from app.services.management_packs import apply_industry_pack
    from app.services.management_system import get_draft_revision, get_or_create_system

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")
    try:
        result = apply_industry_pack(db, system=system, revision_id=rev.id, pack_id=body.pack_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return MgmtPackApplyOut(**result)


@router.get("/gap-report", response_model=MgmtGapReportOut)
def get_gap_report(db: Session = Depends(get_db)) -> MgmtGapReportOut:
    from app.services.management_gap import build_gap_report
    from app.services.management_system import get_draft_revision, get_or_create_system

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")
    report = build_gap_report(db, rev.id)
    db.commit()
    return MgmtGapReportOut(**report)


@router.get("/implementation", response_model=MgmtImplementationOut)
def get_implementation_state(db: Session = Depends(get_db)) -> MgmtImplementationOut:
    from app.services.management_assignments import assignment_out, list_role_assignments, list_roles
    from app.services.management_gap import build_gap_report
    from app.services.management_system import get_draft_revision, get_or_create_system, list_current_positions

    user, org_id = _require_mgmt_access()
    system = get_or_create_system(db, org_id, user.id)
    rev = get_draft_revision(db, system)
    if not rev:
        raise HTTPException(status_code=500, detail="Draft revision missing")
    report = build_gap_report(db, rev.id)
    db.commit()
    return MgmtImplementationOut(
        roles=[MgmtRoleOut.model_validate(r) for r in list_roles(db, rev.id)],
        current_positions=[
            MgmtCurrentPositionOut.model_validate(p) for p in list_current_positions(db, rev.id)
        ],
        role_assignments=[
            MgmtRoleAssignmentOut(**assignment_out(db, row))
            for row in list_role_assignments(db, rev.id)
        ],
        gap_report=MgmtGapReportOut(**report),
    )


@router.get("/roles", response_model=list[MgmtRoleOut])
def get_roles(db: Session = Depends(get_db)) -> list[MgmtRoleOut]:
    from app.services.management_assignments import list_roles

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    db.commit()
    return [MgmtRoleOut.model_validate(r) for r in list_roles(db, rev_id)]


@router.get("/role-assignments", response_model=list[MgmtRoleAssignmentOut])
def get_role_assignments(db: Session = Depends(get_db)) -> list[MgmtRoleAssignmentOut]:
    from app.services.management_assignments import assignment_out, list_role_assignments

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    rows = list_role_assignments(db, rev_id)
    db.commit()
    return [MgmtRoleAssignmentOut(**assignment_out(db, row)) for row in rows]


@router.post("/role-assignments", response_model=MgmtRoleAssignmentOut, status_code=201)
def create_role_assignment_route(
    body: MgmtRoleAssignmentIn, db: Session = Depends(get_db)
) -> MgmtRoleAssignmentOut:
    from app.services.management_assignments import assignment_out, create_role_assignment

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        row = create_role_assignment(
            db,
            rev_id,
            target_role_id=body.target_role_id,
            current_position_id=body.current_position_id,
            coverage=body.coverage,
            note=body.note,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return MgmtRoleAssignmentOut(**assignment_out(db, row))


@router.patch("/role-assignments/{assignment_id}", response_model=MgmtRoleAssignmentOut)
def update_role_assignment_route(
    assignment_id: str, body: MgmtRoleAssignmentUpdateIn, db: Session = Depends(get_db)
) -> MgmtRoleAssignmentOut:
    from app.db import management_models as m
    from app.services.management_assignments import assignment_out, update_role_assignment

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        aid = uuid.UUID(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid assignment id") from exc
    row = db.get(m.MgmtRoleAssignment, aid)
    if not row or row.revision_id != rev_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    try:
        update_role_assignment(
            db,
            row,
            coverage=body.coverage,
            note=body.note,
            clear_note=body.clear_note,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return MgmtRoleAssignmentOut(**assignment_out(db, row))


@router.delete("/role-assignments/{assignment_id}", status_code=204)
def delete_role_assignment_route(assignment_id: str, db: Session = Depends(get_db)) -> None:
    from app.db import management_models as m
    from app.services.management_assignments import delete_role_assignment

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        aid = uuid.UUID(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid assignment id") from exc
    row = db.get(m.MgmtRoleAssignment, aid)
    if not row or row.revision_id != rev_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    delete_role_assignment(db, row)
    db.commit()


@router.get("/gates/summary", response_model=MgmtGateSummaryOut)
def get_gates_summary(db: Session = Depends(get_db)) -> MgmtGateSummaryOut:
    from app.services.management_assignments import list_roles
    from app.services.management_gates import gate_summary, list_process_maps

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    summary = gate_summary(db, rev_id)
    db.commit()
    return MgmtGateSummaryOut(
        **summary,
        process_maps=[MgmtProcessMapOut.model_validate(pm) for pm in list_process_maps(db, rev_id)],
        roles=[MgmtRoleOut.model_validate(r) for r in list_roles(db, rev_id)],
    )


@router.post("/gates/approve", response_model=MgmtGateActionOut)
def gate_approve(body: MgmtGateActionIn, db: Session = Depends(get_db)) -> MgmtGateActionOut:
    from app.services.management_gates import GateError, approve_entity

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        result = approve_entity(
            db, rev_id, entity_type=body.entity_type, entity_id=body.entity_id
        )
    except GateError as exc:
        db.rollback()
        status = 404 if exc.code == "NOT_FOUND" else 422 if exc.code == "STEP_NO_ROLE" else 400
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": exc.message, "errors": exc.details},
        ) from exc
    db.commit()
    return MgmtGateActionOut(**result)


@router.post("/gates/reject", response_model=MgmtGateActionOut)
def gate_reject(body: MgmtGateActionIn, db: Session = Depends(get_db)) -> MgmtGateActionOut:
    from app.services.management_gates import GateError, reject_entity

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        result = reject_entity(
            db, rev_id, entity_type=body.entity_type, entity_id=body.entity_id
        )
    except GateError as exc:
        db.rollback()
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": exc.message, "errors": exc.details},
        ) from exc
    db.commit()
    return MgmtGateActionOut(**result)


@router.post("/gates/l2a/approve-all", response_model=MgmtGateLevelOut)
def gate_approve_l2a_all(db: Session = Depends(get_db)) -> MgmtGateLevelOut:
    from app.services.management_gates import approve_all_l2a

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    result = approve_all_l2a(db, rev_id)
    if result.get("errors") and result.get("approved_count", 0) == 0:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "STEP_NO_ROLE", "message": "L2a не утверждён", "errors": result["errors"]},
        )
    db.commit()
    return MgmtGateLevelOut(**result)


@router.post("/gates/l2b/approve-all", response_model=MgmtGateLevelOut)
def gate_approve_l2b_all(db: Session = Depends(get_db)) -> MgmtGateLevelOut:
    from app.services.management_gates import approve_all_l2b

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    result = approve_all_l2b(db, rev_id)
    db.commit()
    return MgmtGateLevelOut(**result)


@router.post("/wizard/step/4/complete", response_model=MgmtWizardSessionOut)
def wizard_complete_step4(db: Session = Depends(get_db)) -> MgmtWizardSessionOut:
    from app.services.management_wizard import complete_wizard_step4_pack, get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    try:
        complete_wizard_step4_pack(db, session)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)


@router.post("/wizard/step/5/complete", response_model=MgmtWizardSessionOut)
def wizard_complete_step5(db: Session = Depends(get_db)) -> MgmtWizardSessionOut:
    from app.services.management_wizard import complete_wizard_step5_summary, get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    try:
        complete_wizard_step5_summary(db, session)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)


@router.get("/wizard/state", response_model=MgmtWizardStateOut)
def get_wizard_state(db: Session = Depends(get_db)) -> MgmtWizardStateOut:
    from app.services.management_wizard import wizard_state

    user, org_id = _require_mgmt_access()
    state = wizard_state(db, organization_id=org_id, user_id=user.id)
    db.commit()
    return MgmtWizardStateOut(
        session=MgmtWizardSessionOut.model_validate(state["session"]),
        step=state["step"],
        questions=[MgmtInterviewQuestionOut(**q) for q in state.get("questions", [])],
        answers=[MgmtInterviewAnswerOut.model_validate(a) for a in state.get("answers", [])],
        interview=None,
        positions=[MgmtCurrentPositionOut.model_validate(p) for p in state["positions"]],
        business_profile=MgmtBusinessProfileOut.model_validate(state["business_profile"])
        if state.get("business_profile")
        else None,
        goal_blocks=[_goal_block_out(db, b) for b in state.get("goal_blocks", [])],
        skipped_blocks=state.get("skipped_blocks") or [],
        industry_packs=[MgmtIndustryPackOut(**p) for p in state.get("industry_packs", [])],
        industry_pack_id=state.get("industry_pack_id"),
        inherited_goals=[_goal_out(db, g, scope="holding") for g in state.get("inherited_goals", [])],
        gap_report=MgmtGapReportOut(**state["gap_report"]) if state.get("gap_report") else None,
        goals=[_goal_out(db, g) for g in state["goals"]],
        warnings=state["warnings"],
    )


@router.post("/wizard/step/1", response_model=MgmtWizardSessionOut)
def wizard_complete_step1(body: MgmtWizardStep1In, db: Session = Depends(get_db)) -> MgmtWizardSessionOut:
    from app.services.management_wizard import complete_wizard_step1, get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    try:
        complete_wizard_step1(
            db, session, skipped=body.skipped, import_text=body.import_text
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)


@router.get("/business-profile/schema", response_model=MgmtBusinessProfileSchemaOut)
def get_business_profile_schema(db: Session = Depends(get_db)) -> MgmtBusinessProfileSchemaOut:
    from app.services.management_business_profile import business_profile_schema

    _require_mgmt_access()
    db.commit()
    return MgmtBusinessProfileSchemaOut(**business_profile_schema())


@router.get("/business-profile", response_model=MgmtBusinessProfileOut)
def get_business_profile_route(db: Session = Depends(get_db)) -> MgmtBusinessProfileOut:
    from app.services.management_business_profile import get_or_create_business_profile

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    profile = get_or_create_business_profile(db, rev_id)
    db.commit()
    return MgmtBusinessProfileOut.model_validate(profile)


@router.put("/business-profile", response_model=MgmtBusinessProfileOut)
def save_business_profile_route(
    body: MgmtBusinessProfileIn, db: Session = Depends(get_db)
) -> MgmtBusinessProfileOut:
    from app.services.management_business_profile import save_business_profile

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    profile = save_business_profile(
        db,
        rev_id,
        industry_code=body.industry_code,
        industry_custom=body.industry_custom,
        business_model=body.business_model,
        market_type=body.market_type,
        scale_band=body.scale_band,
        maturity_stage=body.maturity_stage,
        horizon_months=body.horizon_months,
        priorities=body.priorities,
        constraints_text=body.constraints_text,
        sensitive_metrics_opt_out=body.sensitive_metrics_opt_out,
        optional_metrics=body.optional_metrics,
    )
    db.commit()
    db.refresh(profile)
    return MgmtBusinessProfileOut.model_validate(profile)


@router.post("/wizard/step/2/complete", response_model=MgmtWizardSessionOut)
def wizard_complete_step2_profile(db: Session = Depends(get_db)) -> MgmtWizardSessionOut:
    from app.services.management_wizard import complete_wizard_step2_profile, get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    try:
        complete_wizard_step2_profile(db, session)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)


@router.get("/goal-blocks", response_model=list[MgmtGoalBlockOut])
def get_goal_blocks(db: Session = Depends(get_db)) -> list[MgmtGoalBlockOut]:
    from app.services.management_goal_blocks import goal_blocks_state
    from app.services.management_wizard import get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    payload = dict(session.payload or {})
    blocks = goal_blocks_state(
        db,
        rev_id,
        organization_id=org_id,
        skipped_blocks=list(payload.get("skipped_blocks") or []),
    )
    db.commit()
    return [_goal_block_out(db, b) for b in blocks]


@router.post("/goal-blocks/{block_code}/answer", response_model=MgmtGoalBlockAnswerOut)
def goal_block_answer(
    block_code: str, body: MgmtGoalBlockAnswerIn, db: Session = Depends(get_db)
) -> MgmtGoalBlockAnswerOut:
    from app.services.management_goal_blocks import submit_block_answer
    from app.services.management_wizard import get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    try:
        answer = submit_block_answer(
            db,
            organization_id=org_id,
            revision_id=rev_id,
            wizard_session_id=session.id,
            block_code=block_code,
            question_key=body.question_key,
            answer_text=body.answer_text,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(answer)
    return MgmtGoalBlockAnswerOut.model_validate(answer)


@router.post("/goal-blocks/{block_code}/generate", response_model=MgmtGoalBlockGenerateOut)
def goal_block_generate(block_code: str, db: Session = Depends(get_db)) -> MgmtGoalBlockGenerateOut:
    from app.core.config import get_settings
    from app.services.management_goal_blocks import generate_block_goals

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    result = generate_block_goals(
        db,
        get_settings(),
        organization_id=org_id,
        revision_id=rev_id,
        block_code=block_code,
    )
    if result.get("ok"):
        db.commit()
    else:
        db.rollback()
    return MgmtGoalBlockGenerateOut(**result)


@router.post("/goal-blocks/{block_code}/approve", response_model=MgmtWizardApproveOut)
def goal_block_approve(
    block_code: str, body: MgmtGoalBlockApproveIn, db: Session = Depends(get_db)
) -> MgmtWizardApproveOut:
    from app.services.management_goal_blocks import approve_block_goals

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    result = approve_block_goals(db, rev_id, block_code, goal_ids=body.goal_ids or None)
    if not result.get("ok"):
        db.rollback()
        return MgmtWizardApproveOut(**result)
    db.commit()
    return MgmtWizardApproveOut(**result)


@router.post("/goal-blocks/{block_code}/skip", response_model=MgmtWizardSessionOut)
def goal_block_skip(block_code: str, db: Session = Depends(get_db)) -> MgmtWizardSessionOut:
    from app.services.management_wizard import get_or_create_wizard_session, skip_goal_block

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    try:
        skip_goal_block(db, session, block_code)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)


@router.post("/wizard/step/3/complete", response_model=MgmtWizardSessionOut)
def wizard_complete_step3_blocks(db: Session = Depends(get_db)) -> MgmtWizardSessionOut:
    from app.services.management_wizard import complete_wizard_step3_blocks, get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    try:
        complete_wizard_step3_blocks(db, session)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(session)
    return MgmtWizardSessionOut.model_validate(session)


@router.patch("/goals/{goal_id}", response_model=MgmtGoalOut)
def update_goal_route(goal_id: str, body: MgmtGoalUpdateIn, db: Session = Depends(get_db)) -> MgmtGoalOut:
    from decimal import Decimal

    from app.db import management_models as m
    from app.services.management_system import update_goal

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        gid = uuid.UUID(goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid goal id") from exc
    goal = db.get(m.MgmtGoal, gid)
    if not goal or goal.revision_id != rev_id:
        raise HTTPException(status_code=404, detail="Goal not found")
    fields = body.model_fields_set
    update_goal(
        db,
        goal,
        title=body.title,
        baseline_value=Decimal(str(body.baseline_value)) if body.baseline_value is not None else None,
        target_value=Decimal(str(body.target_value)) if body.target_value is not None else None,
        metric_unit=body.metric_unit,
        metric_source=body.metric_source,
        fields_set=fields,
    )
    db.commit()
    return _goal_out(db, goal)


@router.post("/wizard/step/2/answer", response_model=MgmtInterviewAnswerOut)
def wizard_submit_answer(body: MgmtWizardAnswerIn, db: Session = Depends(get_db)) -> MgmtInterviewAnswerOut:
    from app.services.management_wizard import get_or_create_wizard_session, submit_interview_answer

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    if not session.revision_id:
        raise HTTPException(status_code=400, detail="Draft revision missing")
    try:
        answer = submit_interview_answer(
            db,
            organization_id=org_id,
            revision_id=session.revision_id,
            wizard_session_id=session.id,
            question_key=body.question_key,
            answer_text=body.answer_text,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(answer)
    return MgmtInterviewAnswerOut.model_validate(answer)


@router.post("/wizard/step/2/generate", response_model=MgmtWizardGenerateOut)
def wizard_generate_l0_l1(db: Session = Depends(get_db)) -> MgmtWizardGenerateOut:
    from app.core.config import get_settings
    from app.services.management_wizard import generate_from_interview, get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    if not session.revision_id:
        raise HTTPException(status_code=400, detail="Draft revision missing")
    result = generate_from_interview(
        db,
        get_settings(),
        organization_id=org_id,
        revision_id=session.revision_id,
    )
    if result.get("ok"):
        db.commit()
    else:
        db.rollback()
    return MgmtWizardGenerateOut(**result)


@router.post("/wizard/step/2/approve-goals", response_model=MgmtWizardApproveOut)
def wizard_approve_goals(db: Session = Depends(get_db)) -> MgmtWizardApproveOut:
    from app.services.management_wizard import approve_wizard_step2_goals, get_or_create_wizard_session

    user, org_id = _require_mgmt_access()
    session = get_or_create_wizard_session(db, organization_id=org_id, user_id=user.id)
    if not session.revision_id:
        raise HTTPException(status_code=400, detail="Draft revision missing")
    result = approve_wizard_step2_goals(db, session.revision_id)
    if not result.get("ok"):
        db.rollback()
        return MgmtWizardApproveOut(**result)
    db.commit()
    return MgmtWizardApproveOut(**result)


@router.post("/goals/{goal_id}/approve", response_model=MgmtApproveOut)
def approve_goal_route(goal_id: str, db: Session = Depends(get_db)) -> MgmtApproveOut:
    from app.db import management_models as m

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        gid = uuid.UUID(goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid goal id") from exc
    goal = db.get(m.MgmtGoal, gid)
    if not goal or goal.revision_id != rev_id:
        raise HTTPException(status_code=404, detail="Goal not found")
    approve_goal(db, goal)
    db.commit()
    return MgmtApproveOut(id=goal.id, status=goal.status)


@router.post("/tasks/{task_id}/approve", response_model=MgmtApproveOut)
def approve_task_route(task_id: str, db: Session = Depends(get_db)) -> MgmtApproveOut:
    from app.db import management_models as m

    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    try:
        tid = uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid task id") from exc
    task = db.get(m.MgmtTask, tid)
    if not task or task.revision_id != rev_id:
        raise HTTPException(status_code=404, detail="Task not found")
    approve_task(db, task)
    db.commit()
    return MgmtApproveOut(id=task.id, status=task.status)


@router.post("/goals/approve-all-draft", response_model=MgmtBulkApproveOut)
def approve_all_goals_draft(db: Session = Depends(get_db)) -> MgmtBulkApproveOut:
    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    n = approve_all_draft_goals(db, rev_id)
    db.commit()
    return MgmtBulkApproveOut(approved_count=n)


@router.post("/tasks/approve-all-draft", response_model=MgmtBulkApproveOut)
def approve_all_tasks_draft(db: Session = Depends(get_db)) -> MgmtBulkApproveOut:
    _, org_id = _require_mgmt_access()
    rev_id = _draft_revision_id(db, org_id)
    n = approve_all_draft_tasks(db, rev_id)
    db.commit()
    return MgmtBulkApproveOut(approved_count=n)
