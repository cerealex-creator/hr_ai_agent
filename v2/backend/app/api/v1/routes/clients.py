"""v1 API routes (split from endpoints.py — audit M6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.services.tenancy import get_candidate_or_404, get_client_or_404, get_vacancy_or_404
from app.api.v1.common import (
    ALLOWED_JOB_TYPES,
    ARQ_FUNCTION_BY_TYPE,
    _vacancy_detail,
    _candidate_detail,
    _channel_out,
    _nest_form_key,
    _parse_webhook_payload,
)
from app.core.config import get_settings
from app.services import jobs as job_svc
from app.services.candidate_fields import candidate_public_fields
from app.services.documents_preview import history_preview, nonempty_document_keys
from app.services.hh_search_criteria import (
    AREA_PRESETS,
    SCHEDULE_OPTIONS,
    criteria_from_vacancy_documents,
    ensure_portrait,
    normalize_criteria,
    save_criteria_to_documents,
    warnings_for,
)
from app.services.hh_criteria_prefill import needs_ai_prefill, prefill_criteria_with_ai
from app.services.vacancy_outcome import (
    HIRE_STAGES,
    close_reason_from_payload,
    soft_vacancy_outcome,
)
from app.workers.redis_pool import get_arq_pool
from app.schemas import (
    CandidateCreateIn,
    CandidateDetail,
    CandidateListItem,
    CandidatePatchIn,
    CandidateStageIn,
    CandidateSendToChatIn,
    CandidateSendToChatOut,
    CandidateEvaluateOut,
    BulkLinksIn,
    BulkLinksOut,
    QuestionnaireOut,
    QuestionnaireRegenerateIn,
    QuestionnairePutIn,
    ClientCount,
    ClientCreateIn,
    ClientOut,
    ClientPatchIn,
    CompaniesTreeOut,
    ClientTreeNodeOut,
    CompanyCreateIn,
    DepartmentCreateIn,
    TestChatIn,
    TestChatOut,
    MessagingChannelCreateIn,
    MessagingChannelDeleteOut,
    MessagingChannelPatchIn,
    DocumentGenerationDetail,
    DocumentGenerationOut,
    FunnelStatsOut,
    HhEfficiencyStatsOut,
    ActivityStatsOut,
    HealthOut,
    HhSearchCriteriaIn,
    HhPresetIn,
    HhSeenItemOut,
    HhSeenRejectIn,
    HhShortlistCreateIn,
    HhShortlistItemOut,
    HhShortlistToCandidateOut,
    ImportStatsOut,
    JobCreateIn,
    JobCreateOut,
    JobHistoryItemOut,
    JobHistoryListOut,
    JobOut,
    JobsListOut,
    MessagingChannelOut,
    MessagingChannelsSyncOut,
    MessagingPostOut,
    StageCount,
    StageOptionOut,
    VacancyDetail,
    VacancyCreateIn,
    VacancyCloseIn,
    VacancyDocumentGenerateIn,
    VacancyDocumentGenerateOut,
    VacancyDocumentsPatchIn,
    VacancyListItem,
    WebhookAckOut,
    YandexDiskConfigOut,
    YandexDiskConfigPatchIn,
    YandexDiskSyncOut,
    VacancySettingsPatchIn,
    WarrantyApplyIn,
    AppSettingsPatchIn,
    OauthTokenIn,
    InboxProcessIn,
    InboxBindIn,
    InboxSettingsPatchIn,
    StageSchemaPatchIn,
    GoogleOAuthCompleteIn,
    HhSearchPlanReviseIn,
    HhManualEvaluateIn,
    HhSoftenSuggestionsIn,
    HhSoftenApplyIn,
    CandidateCopyIn,
    MessagingTestMessageIn,
    ExtraMaterialIn,
    HistoryApplyIn,
    TemplateCreateVacancyIn,
)

router = APIRouter()

@router.get("/clients", response_model=list[ClientOut])
def list_clients(
    for_vacancies: bool = Query(default=False),
    include_test: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ClientOut]:
    """Flat list. for_vacancies=true → selectable leaves (no company shells, no test)."""
    from app.services import clients_write as cw
    from app.services.tenancy import require_org_id

    org_id = require_org_id()
    cw.ensure_client_schema(db)
    if for_vacancies:
        rows = cw.selectable_clients_for_vacancies(db, organization_id=org_id)
    else:
        rows = list(
            db.scalars(
                select(models.Client)
                .where(models.Client.organization_id == org_id)
                .order_by(models.Client.id)
            ).all()
        )
        if not include_test:
            rows = [r for r in rows if r.kind != cw.KIND_TEST]
    return [ClientOut.model_validate(r) for r in rows]

@router.get("/companies", response_model=CompaniesTreeOut)
def list_companies_tree(
    migrate: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> CompaniesTreeOut:
    from app.services import clients_write as cw
    from app.services.tenancy import require_org_id

    org_id = require_org_id()
    migration: dict = {}
    if migrate:
        migration = cw.migrate_legacy_clients(db)
    else:
        cw.ensure_client_schema(db)
    return CompaniesTreeOut(items=cw.company_tree(db, organization_id=org_id), migration=migration)

@router.get("/companies/{company_id}", response_model=ClientTreeNodeOut)
def get_company(company_id: int, db: Session = Depends(get_db)) -> ClientTreeNodeOut:
    from app.services import clients_write as cw

    cw.ensure_client_schema(db)
    company = get_client_or_404(db, company_id)
    if not company or company.kind != cw.KIND_COMPANY:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    node = cw.client_to_dict(db, company)
    node["departments"] = [cw.client_to_dict(db, d) for d in cw.list_departments(db, company.id)]
    return ClientTreeNodeOut.model_validate(node)

@router.post("/companies", response_model=ClientOut, status_code=201)
def create_company_endpoint(body: CompanyCreateIn, db: Session = Depends(get_db)) -> ClientOut:
    from app.services import clients_write as cw

    try:
        cw.ensure_client_schema(db)
        row = cw.create_company(db, body.name, chat_mode=body.chat_mode)
    except cw.ClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return ClientOut.model_validate(row)

@router.post("/clients", response_model=ClientOut)
def create_client_endpoint(body: ClientCreateIn, db: Session = Depends(get_db)) -> ClientOut:
    from app.services import clients_write as cw

    try:
        cw.ensure_client_schema(db)
        row = cw.create_client(
            db,
            body.name,
            parent_id=body.parent_id,
            chat_mode=body.chat_mode,
        )
        db.commit()
        db.refresh(row)
    except cw.ClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return ClientOut.model_validate(row)

@router.patch("/clients/{client_id}", response_model=ClientOut)
def patch_client_endpoint(
    client_id: int, body: ClientPatchIn, db: Session = Depends(get_db)
) -> ClientOut:
    from app.services import clients_write as cw

    client = get_client_or_404(db, client_id)
    try:
        row = cw.patch_client(db, client, name=body.name, chat_mode=body.chat_mode)
    except cw.ClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return ClientOut.model_validate(row)

@router.delete("/clients/{client_id}", status_code=204)
def delete_client_endpoint(client_id: int, db: Session = Depends(get_db)) -> None:
    from app.services import clients_write as cw

    client = get_client_or_404(db, client_id)
    try:
        cw.delete_client(db, client)
    except cw.ClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

@router.post("/companies/{company_id}/departments", response_model=ClientOut, status_code=201)
def create_department_endpoint(
    company_id: int, body: DepartmentCreateIn, db: Session = Depends(get_db)
) -> ClientOut:
    from app.services import clients_write as cw
    from app.services.messaging.channels import ChannelError, create_channel

    company = get_client_or_404(db, company_id)
    if not company or company.kind != cw.KIND_COMPANY:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    try:
        row = cw.create_client(db, body.name, parent_id=company_id)
        if company.chat_mode != cw.CHAT_MODE_DEPARTMENTS:
            company.chat_mode = cw.CHAT_MODE_DEPARTMENTS
        if (body.chat_id or "").strip():
            create_channel(
                db,
                name=(body.chat_name or body.name).strip(),
                chat_id=body.chat_id.strip(),
                client_id=row.id,
            )
        else:
            db.commit()
            db.refresh(row)
    except (cw.ClientError, ChannelError) as exc:
        code = getattr(exc, "status_code", 400)
        msg = getattr(exc, "message", str(exc))
        raise HTTPException(status_code=code, detail=msg) from exc
    return ClientOut.model_validate(row)


@router.get("/companies/{company_id}/client-zone")
def get_company_client_zone(company_id: int, db: Session = Depends(get_db)) -> dict:
    owner = get_client_or_404(db, company_id)
    token = owner.client_zone_token or ""
    return {
        "company_id": owner.id,
        "company_name": owner.name,
        "token": token or None,
        "path": f"/c/{token}" if token else None,
    }


@router.post("/companies/{company_id}/client-zone/rotate")
def rotate_company_client_zone(company_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.tenancy import rotate_client_zone_token

    owner = get_client_or_404(db, company_id)
    token = rotate_client_zone_token(db, owner)
    return {
        "company_id": owner.id,
        "company_name": owner.name,
        "token": token,
        "path": f"/c/{token}",
    }

