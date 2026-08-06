"""v1 API routes (split from endpoints.py — audit M6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
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

@router.get("/jobs", response_model=JobsListOut)
def list_jobs(
    limit: int = Query(default=30, ge=1, le=100),
    vacancy_id: int | None = Query(default=None),
    job_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> JobsListOut:
    rows = job_svc.list_jobs(
        db, limit=limit, vacancy_id=vacancy_id, job_type=job_type, status=status
    )
    return JobsListOut(
        active_count=job_svc.count_active(db),
        items=[JobOut.model_validate(r) for r in rows],
    )

@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    try:
        from uuid import UUID

        jid = UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid job id") from exc
    job = job_svc.get_job(db, jid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)

@router.post("/jobs", response_model=JobCreateOut, status_code=202)
async def create_job(body: JobCreateIn, db: Session = Depends(get_db)) -> JobCreateOut:
    if body.job_type not in ALLOWED_JOB_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown job_type. Allowed: {', '.join(sorted(ALLOWED_JOB_TYPES))}",
        )
    payload = dict(body.payload or {})

    if body.job_type == "hh_cold_search":
        from app.services.app_settings import get_functions

        if not bool(get_functions().get("hh_search_enabled", True)):
            raise HTTPException(
                status_code=403,
                detail="Поиск резюме HH отключен в настройках (hh_search_enabled=false).",
            )
    if body.job_type == "transcribe_media":
        source_url = str(payload.get("source_url") or "").strip()
        if not source_url:
            raise HTTPException(
                status_code=400,
                detail="Для transcribe_media нужен payload.source_url",
            )
        payload["source_url"] = source_url
    if body.job_type == "hh_cold_search":
        from app.services.hh_preset import (
            criteria_view_from_preset,
            ensure_soft_portrait,
            normalize_preset,
            preset_from_vacancy_documents,
            save_preset_to_documents,
        )

        vacancy_id = body.vacancy_id or payload.get("vacancy_id")
        if vacancy_id is None:
            raise HTTPException(
                status_code=400,
                detail="Для hh_cold_search нужен vacancy_id",
            )
        vacancy = db.get(models.Vacancy, int(vacancy_id))
        if not vacancy:
            raise HTTPException(status_code=404, detail="Vacancy not found")
        preset = normalize_preset(payload.get("preset") or {})
        texts_ok = any((t.get("text") or "").strip() for t in preset["api"]["texts"])
        if not texts_ok:
            preset = preset_from_vacancy_documents(vacancy.documents, title=vacancy.title)
        texts_ok = any((t.get("text") or "").strip() for t in preset["api"]["texts"])
        if not texts_ok:
            raise HTTPException(
                status_code=400,
                detail="Нет ключевых слов в пресете поиска HH",
            )
        preset = ensure_soft_portrait(preset)
        vacancy.documents = save_preset_to_documents(vacancy.documents, preset)
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(vacancy, "documents")
        db.add(vacancy)
        db.commit()
        criteria = criteria_view_from_preset(preset)
        payload["preset"] = preset
        payload["criteria"] = criteria
        payload["keywords"] = criteria["keywords"]
        payload["vacancy_id"] = int(vacancy_id)
        body = body.model_copy(update={"vacancy_id": int(vacancy_id)})
        existing_hh = job_svc.find_active_job_for_vacancy(
            db,
            job_type="hh_cold_search",
            vacancy_id=int(vacancy_id),
        )
        if existing_hh:
            return JobCreateOut(
                id=existing_hh.id,
                status=existing_hh.status,
                job_type=existing_hh.job_type,
                reused=True,
                progress_label=existing_hh.progress_label,
            )
    if body.job_type == "yandex_disk_sync":
        vacancy_id = body.vacancy_id or payload.get("vacancy_id")
        if vacancy_id is None:
            raise HTTPException(
                status_code=400,
                detail="Для yandex_disk_sync нужен vacancy_id",
            )
        vacancy = db.get(models.Vacancy, int(vacancy_id))
        if not vacancy:
            raise HTTPException(status_code=404, detail="Vacancy not found")
        from app.services.yandex_disk_sync import ensure_yandex_config

        cfg = ensure_yandex_config(vacancy)
        db.commit()
        if not str(cfg.get("root_url") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Укажите root_url папки Яндекс.Диска (PATCH /yandex-disk)",
            )
        payload["vacancy_id"] = int(vacancy_id)
        body = body.model_copy(update={"vacancy_id": int(vacancy_id)})
    job = job_svc.create_job_row(
        db,
        job_type=body.job_type,
        client_id=body.client_id,
        vacancy_id=body.vacancy_id,
        payload=payload,
    )
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(
            ARQ_FUNCTION_BY_TYPE[body.job_type],
            str(job.id),
            _job_id=str(job.id),
        )
    except Exception as exc:  # noqa: BLE001
        job_svc.update_job(
            db,
            job.id,
            status="failed",
            progress_label="Не удалось поставить в очередь",
            error=str(exc),
        )
        raise HTTPException(status_code=503, detail=f"Redis/ARQ unavailable: {exc}") from exc
    return JobCreateOut(id=job.id, status=job.status, job_type=job.job_type)

@router.delete("/jobs/{job_id}", status_code=204)
def delete_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> None:
    try:
        from uuid import UUID

        jid = UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid job id") from exc
    job = job_svc.get_job(db, jid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=400, detail="Сначала отмените активный job")
    if not job_svc.delete_job(db, jid):
        raise HTTPException(status_code=404, detail="Job not found")
    return None

@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    try:
        from uuid import UUID

        jid = UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid job id") from exc
    job = job_svc.get_job(db, jid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in job_svc.TERMINAL:
        return JobOut.model_validate(job)
    updated = job_svc.update_job(
        db,
        jid,
        status="cancelled",
        progress_label="Отмена запрошена",
    )
    return JobOut.model_validate(updated)

