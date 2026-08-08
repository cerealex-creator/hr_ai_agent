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
    DashboardStatsOut,
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

@router.get("/stats/import", response_model=ImportStatsOut)
def import_stats(db: Session = Depends(get_db)) -> ImportStatsOut:
    from app.services.tenancy import org_client_ids, org_vacancy_ids, require_org_id

    org_id = require_org_id()
    client_ids = org_client_ids(db, org_id)
    vac_ids = org_vacancy_ids(db, org_id)

    def _count_clients() -> int:
        return len(client_ids)

    def _count_vacancies() -> int:
        return len(vac_ids)

    def _count_candidates() -> int:
        if not vac_ids:
            return 0
        return int(
            db.scalar(
                select(func.count())
                .select_from(models.Candidate)
                .where(models.Candidate.vacancy_id.in_(vac_ids))
            )
            or 0
        )

    def _count_docs() -> int:
        if not vac_ids and not client_ids:
            return 0
        q = select(func.count()).select_from(models.DocumentGeneration)
        if vac_ids and client_ids:
            q = q.where(
                (models.DocumentGeneration.vacancy_id.in_(vac_ids))
                | (models.DocumentGeneration.client_id.in_(client_ids))
            )
        elif vac_ids:
            q = q.where(models.DocumentGeneration.vacancy_id.in_(vac_ids))
        else:
            q = q.where(models.DocumentGeneration.client_id.in_(client_ids))
        return int(db.scalar(q) or 0)

    def _count_channels() -> int:
        if not client_ids:
            return 0
        return int(
            db.scalar(
                select(func.count())
                .select_from(models.MessagingChannel)
                .where(models.MessagingChannel.client_id.in_(client_ids))
            )
            or 0
        )

    def _count_templates() -> int:
        if not client_ids:
            # templates without client are global legacy — hide for empty org
            return 0
        return int(
            db.scalar(
                select(func.count())
                .select_from(models.VacancyTemplate)
                .where(models.VacancyTemplate.client_id.in_(client_ids))
            )
            or 0
        )

    def _count_jobs() -> int:
        if not vac_ids and not client_ids:
            return 0
        q = select(func.count()).select_from(models.Job)
        if vac_ids and client_ids:
            q = q.where(
                (models.Job.vacancy_id.in_(vac_ids)) | (models.Job.client_id.in_(client_ids))
            )
        elif vac_ids:
            q = q.where(models.Job.vacancy_id.in_(vac_ids))
        else:
            q = q.where(models.Job.client_id.in_(client_ids))
        return int(db.scalar(q) or 0)

    last = db.scalar(select(models.ImportRun).order_by(models.ImportRun.created_at.desc()).limit(1))
    counts = {
        "clients": _count_clients(),
        "vacancies": _count_vacancies(),
        "candidates": _count_candidates(),
        "document_generations": _count_docs(),
        "messaging_channels": _count_channels(),
        "vacancy_templates": _count_templates(),
        "jobs": _count_jobs(),
    }
    if not last:
        return ImportStatsOut(counts=counts)
    return ImportStatsOut(
        last_import_at=last.created_at,
        source_dir=last.source_dir,
        stats=last.stats or {},
        counts=counts,
    )

@router.get("/warranty/registry")
def warranty_registry(db: Session = Depends(get_db)) -> list[dict]:
    from app.services.warranty import collect_warranty_registry

    return collect_warranty_registry(db)

@router.get("/stats/funnel", response_model=FunnelStatsOut)
def funnel_stats(
    client_id: int | None = Query(default=None),
    vacancy_id: int | None = Query(default=None),
    active_vacancies_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> FunnelStatsOut:
    from app.services.stats_service import build_funnel_stats
    from app.services.tenancy import require_org_id

    data = build_funnel_stats(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
        organization_id=require_org_id(),
    )
    return FunnelStatsOut(
        vacancies_active=data["vacancies_active"],
        vacancies_archive=data["vacancies_archive"],
        candidates_total=data["candidates_total"],
        by_hr_stage=[StageCount(**x) for x in data["by_hr_stage"]],
        by_client_status=[StageCount(**x) for x in data["by_client_status"]],
        by_client=[ClientCount(**x) for x in data["by_client"]],
        hires=data["hires"],
        in_client_zone=data["in_client_zone"],
        sent_to_client=data["sent_to_client"],
        vacancy_id=data.get("vacancy_id"),
        vacancy_title=data.get("vacancy_title"),
    )

@router.get("/stats/hh", response_model=HhEfficiencyStatsOut)
def hh_efficiency_stats(
    client_id: int | None = Query(default=None),
    vacancy_id: int | None = Query(default=None),
    active_vacancies_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> HhEfficiencyStatsOut:
    from app.services.stats_service import build_hh_stats
    from app.services.tenancy import require_org_id

    return HhEfficiencyStatsOut(
        **build_hh_stats(
            db,
            client_id=client_id,
            vacancy_id=vacancy_id,
            active_vacancies_only=active_vacancies_only,
            organization_id=require_org_id(),
        )
    )

@router.get("/stats/activity", response_model=ActivityStatsOut)
def activity_stats(
    client_id: int | None = Query(default=None),
    vacancy_id: int | None = Query(default=None),
    active_vacancies_only: bool = Query(default=False),
    period: str = Query(default="month"),
    db: Session = Depends(get_db),
) -> ActivityStatsOut:
    from app.services.stats_service import PERIOD_PRESETS, build_activity_stats
    from app.services.tenancy import require_org_id

    if period not in PERIOD_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"period: {', '.join(PERIOD_PRESETS)}",
        )
    data = build_activity_stats(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
        period=period,
        organization_id=require_org_id(),
    )
    return ActivityStatsOut.model_validate(data)


@router.get("/stats/dashboard", response_model=DashboardStatsOut)
def dashboard_stats(
    mode: str = Query(default="operational"),
    period: str = Query(default="week"),
    client_id: int | None = Query(default=None),
    vacancy_id: int | None = Query(default=None),
    active_vacancies_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> DashboardStatsOut:
    from app.services.stats_service import (
        DASHBOARD_MODES,
        DASHBOARD_PERIODS,
        build_dashboard_stats,
    )
    from app.services.tenancy import require_org_id

    if mode not in DASHBOARD_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"mode: {', '.join(sorted(DASHBOARD_MODES))}",
        )
    if period not in DASHBOARD_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"period: {', '.join(sorted(DASHBOARD_PERIODS))}",
        )
    try:
        data = build_dashboard_stats(
            db,
            mode=mode,
            period=period,
            client_id=client_id,
            vacancy_id=vacancy_id,
            active_vacancies_only=active_vacancies_only,
            organization_id=require_org_id(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DashboardStatsOut.model_validate(data)


@router.get("/history", response_model=list[DocumentGenerationOut])
def list_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[DocumentGenerationOut]:
    from app.services.tenancy import org_client_ids, org_vacancy_ids, require_org_id

    org_id = require_org_id()
    vac_ids = org_vacancy_ids(db, org_id)
    client_ids = org_client_ids(db, org_id)
    q = select(models.DocumentGeneration)
    clauses = []
    if vac_ids:
        clauses.append(models.DocumentGeneration.vacancy_id.in_(vac_ids))
    if client_ids:
        clauses.append(models.DocumentGeneration.client_id.in_(client_ids))
    if not clauses:
        return []
    from sqlalchemy import or_

    q = q.where(or_(*clauses))
    rows = db.scalars(
        q.order_by(models.DocumentGeneration.created_at_legacy.desc().nulls_last()).limit(limit)
    ).all()
    return [
        DocumentGenerationOut(
            id=r.id,
            source_filename=r.source_filename,
            title=r.title,
            mode=r.mode,
            created_at_legacy=r.created_at_legacy,
            imported_at=r.imported_at,
            preview=history_preview(r.documents_snapshot),
            vacancy_id=r.vacancy_id,
        )
        for r in rows
    ]

@router.get("/history/{generation_id}", response_model=DocumentGenerationDetail)
def get_history_item(generation_id: str, db: Session = Depends(get_db)) -> DocumentGenerationDetail:
    from app.services.tenancy import org_client_ids, org_vacancy_ids, require_org_id

    try:
        from uuid import UUID

        gid = UUID(generation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid history id") from exc
    row = db.get(models.DocumentGeneration, gid)
    if not row:
        raise HTTPException(status_code=404, detail="History item not found")
    org_id = require_org_id()
    vac_ids = org_vacancy_ids(db, org_id)
    client_ids = org_client_ids(db, org_id)
    ok = (row.vacancy_id in vac_ids) or (row.client_id in client_ids)
    if not ok:
        raise HTTPException(status_code=404, detail="History item not found")
    return DocumentGenerationDetail(
        id=row.id,
        source_filename=row.source_filename,
        title=row.title,
        mode=row.mode,
        created_at_legacy=row.created_at_legacy,
        imported_at=row.imported_at,
        preview=history_preview(row.documents_snapshot),
        documents_snapshot=row.documents_snapshot or {},
        vacancy_id=row.vacancy_id,
    )

@router.post("/history/{generation_id}/apply")
def apply_history_to_vacancy(
    generation_id: str,
    body: HistoryApplyIn,
    db: Session = Depends(get_db),
) -> dict:
    """Apply a generation snapshot into a vacancy's documents."""
    from uuid import UUID

    from app.services.vacancy_docs_pack import apply_history_pack_to_vacancy

    try:
        gid = UUID(generation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid history id") from exc
    row = db.get(models.DocumentGeneration, gid)
    if not row:
        raise HTTPException(status_code=404, detail="History item not found")
    vacancy_id = body.vacancy_id if body.vacancy_id is not None else row.vacancy_id
    if vacancy_id is None:
        raise HTTPException(status_code=400, detail="Укажите vacancy_id")
    vacancy = get_vacancy_or_404(db, int(vacancy_id))
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    keys = body.keys if isinstance(body.keys, list) else None
    try:
        apply_history_pack_to_vacancy(db, vacancy, row, keys=keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "vacancy_id": vacancy.id,
        "generation_id": str(row.id),
        "title": vacancy.title,
    }

@router.get("/vacancy-templates")
def list_vacancy_templates(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(models.VacancyTemplate).order_by(models.VacancyTemplate.title.asc()).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": str(r.id),
                "legacy_key": r.legacy_key,
                "title": r.title,
                "client_id": r.client_id,
                "has_profile": bool((r.documents or {}).get("profile")),
                "has_questions": bool((r.documents or {}).get("questions")),
            }
            for r in rows
        ]
    }

@router.post("/vacancy-templates/{template_id}/create-vacancy", status_code=201)
def create_vacancy_from_template(
    template_id: str,
    body: TemplateCreateVacancyIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from uuid import UUID

    from app.services.vacancy_write import VacancyWriteError, create_vacancy
    from app.services.vacancy_documents_write import save_documents

    try:
        tid = UUID(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid template id") from exc
    tmpl = db.get(models.VacancyTemplate, tid)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    title = str(body.title or tmpl.title or "").strip()
    client_id = body.client_id
    if client_id is None:
        client_id = tmpl.client_id
    try:
        vacancy = create_vacancy(
            db,
            title=title,
            client_id=int(client_id) if client_id is not None else None,
            chat_id=str(body.chat_id or tmpl.chat_id or "") or None,
            is_test=bool(body.is_test),
        )
    except VacancyWriteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    docs = dict(tmpl.documents or {})
    updates = {
        k: docs[k]
        for k in ("profile", "vacancy_text", "questions", "keywords", "notes")
        if k in docs
    }
    if updates:
        save_documents(db, vacancy, updates)
    return _vacancy_detail(db, vacancy)

