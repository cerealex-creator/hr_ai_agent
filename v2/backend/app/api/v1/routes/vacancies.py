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
    require_intake_channel,
)
from app.core.auth import AuthUser, require_platform_owner, user_is_platform_owner
from app.core.config import get_settings
from app.services import jobs as job_svc
from app.services.candidate_fields import candidate_public_fields
from app.services.candidate_query import serialize_list_item
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
    ResumePreviewIncludeIn,
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
    VacancyPatchIn,
    VacancyDocumentGenerateIn,
    VacancyDocumentsFromBriefIn,
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


def _owner_resume_preview(requested: bool) -> bool:
    from app.services.tenancy import current_user

    user = current_user()
    return bool(requested) and bool(user and user_is_platform_owner(user))

@router.get("/vacancies", response_model=list[VacancyListItem])
def list_vacancies(
    active: bool | None = Query(default=None),
    client_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VacancyListItem]:
    from app.services.tenancy import org_client_ids, require_org_id
    from app.services.resume_preview import sql_not_resume_preview

    org_id = require_org_id()
    allowed = org_client_ids(db, org_id)
    cand_count = (
        select(models.Candidate.vacancy_id, func.count().label("cnt"))
        .where(sql_not_resume_preview())
        .group_by(models.Candidate.vacancy_id)
        .subquery()
    )
    hire_count = (
        select(models.Candidate.vacancy_id, func.count().label("hire_cnt"))
        .where(models.Candidate.hr_stage.in_(HIRE_STAGES))
        .group_by(models.Candidate.vacancy_id)
        .subquery()
    )
    q = (
        select(models.Vacancy, models.Client.name, cand_count.c.cnt, hire_count.c.hire_cnt)
        .outerjoin(models.Client, models.Client.id == models.Vacancy.client_id)
        .outerjoin(cand_count, cand_count.c.vacancy_id == models.Vacancy.id)
        .outerjoin(hire_count, hire_count.c.vacancy_id == models.Vacancy.id)
        .where(models.Vacancy.client_id.in_(allowed) if allowed else models.Vacancy.id == -1)
        .order_by(models.Vacancy.id)
    )
    if active is not None:
        q = q.where(models.Vacancy.active.is_(active))
    if client_id is not None:
        if client_id not in allowed:
            return []
        q = q.where(models.Vacancy.client_id == client_id)
    result: list[VacancyListItem] = []
    from app.services.vacancy_avatar import resolve_avatar_key

    for vacancy, client_name, cnt, hire_cnt in db.execute(q).all():
        close_reason = close_reason_from_payload(vacancy.payload)
        has_hire = int(hire_cnt or 0) > 0
        result.append(
            VacancyListItem(
                id=vacancy.id,
                title=vacancy.title,
                active=vacancy.active,
                client_id=vacancy.client_id,
                client_name=client_name,
                chat_id=vacancy.chat_id,
                candidates_count=int(cnt or 0),
                created_at=vacancy.created_at,
                closed_at=vacancy.closed_at,
                close_reason=close_reason,
                has_hire=has_hire,
                outcome=soft_vacancy_outcome(
                    active=vacancy.active,
                    close_reason=close_reason,
                    has_hire=has_hire,
                ),
                avatar_key=resolve_avatar_key(vacancy.payload, vacancy.title),
            )
        )
    return result

@router.get("/vacancies/{vacancy_id}", response_model=VacancyDetail)
def get_vacancy(vacancy_id: int, db: Session = Depends(get_db)) -> VacancyDetail:
    vacancy = get_vacancy_or_404(db, vacancy_id)
    return _vacancy_detail(db, vacancy)

@router.post("/vacancies", response_model=VacancyDetail, status_code=201)
def create_vacancy_endpoint(
    body: VacancyCreateIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from app.services.vacancy_write import VacancyWriteError, create_vacancy

    try:
        vac = create_vacancy(
            db,
            title=body.title,
            client_id=body.client_id,
            chat_id=body.chat_id,
            is_test=body.is_test,
            source_vacancy_id=body.source_vacancy_id,
        )
    except VacancyWriteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _vacancy_detail(db, vac)

@router.post("/vacancies/{vacancy_id}/close", response_model=VacancyDetail)
def close_vacancy_endpoint(
    vacancy_id: int,
    body: VacancyCloseIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from app.services.vacancy_write import VacancyWriteError, close_vacancy

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        vac = close_vacancy(db, vacancy, close_reason=body.close_reason)
    except VacancyWriteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _vacancy_detail(db, vac)

@router.post("/vacancies/{vacancy_id}/reopen", response_model=VacancyDetail)
def reopen_vacancy_endpoint(
    vacancy_id: int,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from app.services.vacancy_write import VacancyWriteError, reopen_vacancy

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        vac = reopen_vacancy(db, vacancy)
    except VacancyWriteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _vacancy_detail(db, vac)

@router.delete("/vacancies/{vacancy_id}", status_code=204)
def delete_vacancy_endpoint(vacancy_id: int, db: Session = Depends(get_db)) -> None:
    from app.services.vacancy_write import delete_vacancy

    vacancy = get_vacancy_or_404(db, vacancy_id)
    delete_vacancy(db, vacancy)
    return None

@router.patch("/vacancies/{vacancy_id}", response_model=VacancyDetail)
def patch_vacancy(
    vacancy_id: int,
    body: VacancyPatchIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from app.services.vacancy_write import VacancyWriteError, rename_vacancy

    vacancy = get_vacancy_or_404(db, vacancy_id)
    data = body.model_dump(exclude_unset=True)
    if "title" in data:
        try:
            vacancy = rename_vacancy(db, vacancy, str(data.get("title") or ""))
        except VacancyWriteError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _vacancy_detail(db, vacancy)


@router.patch("/vacancies/{vacancy_id}/settings", response_model=VacancyDetail)
def patch_vacancy_settings(
    vacancy_id: int,
    body: VacancySettingsPatchIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from sqlalchemy.orm.attributes import flag_modified

    vacancy = get_vacancy_or_404(db, vacancy_id)
    payload = dict(vacancy.payload or {})
    data = body.model_dump(exclude_unset=True)
    if "is_test" in data:
        payload["is_test"] = bool(data.get("is_test"))
    if "show_portfolio_field" in data:
        payload["show_portfolio_field"] = bool(data.get("show_portfolio_field"))
    if "control_word_enabled" in data:
        payload["control_word_enabled"] = bool(data.get("control_word_enabled"))
    if "control_word" in data:
        payload["control_word"] = str(data.get("control_word") or "").strip()
    if "chat_id" in data:
        vacancy.chat_id = str(data.get("chat_id") or "").strip() or None
    if "avatar_key" in data:
        from app.services.vacancy_avatar import normalize_avatar_key

        key = normalize_avatar_key(data.get("avatar_key"))
        if key:
            payload["avatar_key"] = key
        else:
            payload.pop("avatar_key", None)
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return _vacancy_detail(db, vacancy)

@router.post("/vacancies/{vacancy_id}/warranty/apply", response_model=VacancyDetail)
def warranty_apply(
    vacancy_id: int,
    body: WarrantyApplyIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from app.services.app_settings import get_default_warranty_months
    from app.services.warranty import apply_warranty_to_vacancy

    vacancy = get_vacancy_or_404(db, vacancy_id)
    cid = body.candidate_id
    candidate = get_candidate_or_404(db, cid)
    if not candidate or candidate.vacancy_id != vacancy_id:
        raise HTTPException(status_code=404, detail="Candidate not found on vacancy")
    start = (body.start_date or "").strip()
    if not start:
        raise HTTPException(status_code=400, detail="start_date required")
    months = body.months
    try:
        months_i = int(months) if months is not None else get_default_warranty_months()
    except (TypeError, ValueError):
        months_i = get_default_warranty_months()
    apply_warranty_to_vacancy(
        vacancy,
        candidate,
        start,
        months_i,
        str(body.get("start_kind") or candidate.hr_stage),
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return _vacancy_detail(db, vacancy)

@router.post("/vacancies/{vacancy_id}/warranty/create-search", response_model=VacancyDetail)
def warranty_create_search(vacancy_id: int, db: Session = Depends(get_db)) -> VacancyDetail:
    from app.services.vacancy_write import VacancyWriteError
    from app.services.warranty import create_warranty_search_vacancy

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        new_v = create_warranty_search_vacancy(db, vacancy)
    except VacancyWriteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vacancy_detail(db, new_v)

@router.post("/vacancies/{vacancy_id}/yandex-disk/ensure-folders")
def yandex_disk_ensure_vacancy_folders(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.yandex_disk_oauth import DiskApiError, ensure_vacancy_folders

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        return ensure_vacancy_folders(db, vacancy, publish=True)
    except DiskApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/vacancies/{vacancy_id}/stage-schema")
def get_stage_schema(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.stage_schema import catalog, get_vacancy_stage_schema

    vacancy = get_vacancy_or_404(db, vacancy_id)
    return {"schema": get_vacancy_stage_schema(db, vacancy), "catalog": catalog()}

@router.patch("/vacancies/{vacancy_id}/stage-schema")
def patch_stage_schema(vacancy_id: int, body: StageSchemaPatchIn, db: Session = Depends(get_db)) -> dict:
    from app.services.stage_schema import catalog, set_vacancy_stage_schema

    vacancy = get_vacancy_or_404(db, vacancy_id)
    schema = set_vacancy_stage_schema(db, vacancy, body.model_dump())
    return {"schema": schema, "catalog": catalog()}

@router.patch("/vacancies/{vacancy_id}/documents", response_model=VacancyDetail)
def patch_vacancy_documents(
    vacancy_id: int,
    body: VacancyDocumentsPatchIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    """Merge editable document keys; never replaces whole blob (keeps hh_search_criteria)."""
    from app.services.vacancy_documents_write import EDITABLE_DOCUMENT_KEYS, save_documents

    vacancy = get_vacancy_or_404(db, vacancy_id)
    updates = body.model_dump(exclude_unset=True)
    unknown = set(updates) - set(EDITABLE_DOCUMENT_KEYS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Неизвестные ключи: {sorted(unknown)}")
    save_documents(db, vacancy, updates)
    return _vacancy_detail(db, vacancy)

@router.get("/vacancies/{vacancy_id}/documents/editor")
def vacancy_documents_editor(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.vacancy_documents_write import EDITABLE_DOCUMENT_KEYS, documents_for_editor

    vacancy = get_vacancy_or_404(db, vacancy_id)
    docs = documents_for_editor(vacancy.documents)
    from app.services.tenancy import current_user
    from app.services.documents_preview import strip_keyword_docs

    user = current_user()
    if user and user.is_demo:
        docs = strip_keyword_docs(docs)
        keys = [k for k in EDITABLE_DOCUMENT_KEYS if k != "keywords"]
    else:
        keys = list(EDITABLE_DOCUMENT_KEYS)
    return {
        "vacancy_id": vacancy.id,
        "keys": keys,
        "documents": docs,
        "meeting_brief": (vacancy.documents or {}).get("meeting_brief") or {},
        "meeting_transcript": str((vacancy.documents or {}).get("meeting_transcript") or ""),
        "meeting_conflicts": list((vacancy.documents or {}).get("meeting_conflicts") or []),
    }

@router.post(
    "/vacancies/{vacancy_id}/documents/generate",
    response_model=JobCreateOut,
    status_code=202,
)
async def generate_vacancy_document(
    vacancy_id: int,
    body: VacancyDocumentGenerateIn,
    db: Session = Depends(get_db),
) -> JobCreateOut:
    """Enqueue generate/regenerate of one document section (AI can take 1–2 min)."""
    from app.services.document_generate import GENERATABLE_KEYS

    vacancy = get_vacancy_or_404(db, vacancy_id)
    key = (body.key or "").strip()
    if key not in GENERATABLE_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Ключ «{key}» нельзя генерировать. Доступно: {', '.join(GENERATABLE_KEYS)}",
        )

    payload = {
        "vacancy_id": vacancy_id,
        "key": key,
        "corrections": body.corrections or "",
        "apply": bool(body.apply),
    }
    job = job_svc.create_job_row(
        db,
        job_type="vacancy_docs_generate",
        vacancy_id=vacancy_id,
        client_id=vacancy.client_id,
        payload=payload,
    )
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "vacancy_docs_generate",
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
        raise HTTPException(status_code=503, detail=f"Очередь задач недоступна: {exc}") from exc
    return JobCreateOut(id=job.id, status=job.status, job_type=job.job_type)


@router.post(
    "/vacancies/{vacancy_id}/documents/from-brief",
    response_model=JobCreateOut,
    status_code=202,
)
async def vacancy_documents_from_brief(
    vacancy_id: int,
    body: VacancyDocumentsFromBriefIn,
    db: Session = Depends(get_db),
) -> JobCreateOut:
    """Enqueue AI pack generation from short manual answers (background job)."""
    vacancy = get_vacancy_or_404(db, vacancy_id)
    tasks = (body.tasks or "").strip()
    must_have = (body.must_have or "").strip()
    if not tasks and not must_have:
        raise HTTPException(
            status_code=400,
            detail="Заполните хотя бы «задачи» или «обязательные требования»",
        )

    payload = {
        "vacancy_id": vacancy_id,
        "title": str(body.title or vacancy.title or "").strip(),
        "tasks": body.tasks or "",
        "must_have": body.must_have or "",
        "conditions": body.conditions or "",
        "interview_questions": body.interview_questions or "",
    }
    job = job_svc.create_job_row(
        db,
        job_type="vacancy_docs_from_brief",
        vacancy_id=vacancy_id,
        client_id=vacancy.client_id,
        payload=payload,
    )
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "vacancy_docs_from_brief",
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
        raise HTTPException(status_code=503, detail=f"Очередь задач недоступна: {exc}") from exc
    return JobCreateOut(id=job.id, status=job.status, job_type=job.job_type)


@router.post("/vacancies/{vacancy_id}/documents/from-materials", status_code=202)
async def vacancy_documents_from_materials(
    vacancy_id: int,
    files: list[UploadFile] | None = File(default=None),
    source_urls: str = Form(default=""),
    hr_instructions: str = Form(default=""),
    notes: str = Form(default=""),
    profile_text: str = Form(default=""),
    use_existing_profile: bool = Form(default=True),
    gen_profile: bool = Form(default=True),
    gen_questions: bool = Form(default=True),
    gen_vacancy_text: bool = Form(default=True),
    gen_keywords: bool = Form(default=True),
    db: Session = Depends(get_db),
) -> JobCreateOut:
    """Upload media/docs and/or Yandex Disk URLs → ARQ pack generation into vacancy docs."""
    import uuid as uuid_mod
    from pathlib import Path

    vacancy = get_vacancy_or_404(db, vacancy_id)

    urls = [u.strip() for u in (source_urls or "").replace(";", "\n").splitlines() if u.strip()]
    file_list = list(files or [])
    if not file_list and not urls and not (profile_text or "").strip() and not use_existing_profile:
        raise HTTPException(status_code=400, detail="Добавьте файлы, ссылки или текст профиля")

    settings = get_settings()
    base = settings.resolved_legacy_data_dir() / "tmp" / "vacancy_docs" / str(uuid_mod.uuid4())
    base.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    try:
        for up in file_list:
            raw_name = Path(up.filename or "upload.bin").name
            safe = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in raw_name)[:180]
            dest = base / safe
            content = await up.read()
            if len(content) > 600 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"Файл слишком большой: {safe}")
            dest.write_bytes(content)
            saved_paths.append(str(dest))
    except HTTPException:
        import shutil

        shutil.rmtree(base, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        import shutil

        shutil.rmtree(base, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Не удалось сохранить файлы: {exc}") from exc

    payload = {
        "vacancy_id": vacancy_id,
        "upload_dir": str(base),
        "file_paths": saved_paths,
        "source_urls": urls,
        "hr_instructions": hr_instructions or "",
        "notes": notes or "",
        "profile_text": profile_text or "",
        "use_existing_profile": bool(use_existing_profile),
        "doc_flags": {
            "profile": bool(gen_profile),
            "questions": bool(gen_questions),
            "vacancy_text": bool(gen_vacancy_text),
            "keywords": bool(gen_keywords),
        },
    }
    job = job_svc.create_job_row(
        db,
        job_type="vacancy_docs_from_materials",
        vacancy_id=vacancy_id,
        client_id=vacancy.client_id,
        payload=payload,
    )
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "vacancy_docs_from_materials",
            str(job.id),
            _job_id=str(job.id),
        )
    except Exception as exc:  # noqa: BLE001
        import shutil

        shutil.rmtree(base, ignore_errors=True)
        job_svc.update_job(
            db,
            job.id,
            status="failed",
            progress_label="Не удалось поставить в очередь",
            error=str(exc),
        )
        raise HTTPException(status_code=503, detail=f"Redis/ARQ unavailable: {exc}") from exc
    return JobCreateOut(id=job.id, status=job.status, job_type=job.job_type)

@router.get("/vacancies/{vacancy_id}/yandex-disk", response_model=YandexDiskConfigOut)
def get_vacancy_yandex_disk(vacancy_id: int, db: Session = Depends(get_db)) -> YandexDiskConfigOut:
    from app.services.tenancy import is_demo_user
    from app.services.yandex_disk_sync import default_yandex_disk_config, ensure_yandex_config

    vacancy = get_vacancy_or_404(db, vacancy_id)
    if is_demo_user():
        cfg = default_yandex_disk_config()
    else:
        cfg = ensure_yandex_config(vacancy)
        db.commit()
    return YandexDiskConfigOut(
        vacancy_id=vacancy.id,
        root_url=str(cfg.get("root_url") or ""),
        ingest_new_resumes=bool(cfg.get("ingest_new_resumes", True)),
        subfolders=dict(cfg.get("subfolders") or {}),
        last_sync_at=str(cfg.get("last_sync_at") or "") or None,
        seen_count=len(cfg.get("seen_paths") or []),
    )

@router.patch("/vacancies/{vacancy_id}/yandex-disk", response_model=YandexDiskConfigOut)
def patch_vacancy_yandex_disk(
    vacancy_id: int,
    body: YandexDiskConfigPatchIn,
    db: Session = Depends(get_db),
) -> YandexDiskConfigOut:
    from app.services.yandex_disk_sync import update_yandex_config

    vacancy = get_vacancy_or_404(db, vacancy_id)
    cfg = update_yandex_config(
        vacancy,
        root_url=body.root_url,
        ingest_new_resumes=body.ingest_new_resumes,
        subfolders=body.subfolders,
        reset_seen=body.reset_seen,
    )
    db.commit()
    return YandexDiskConfigOut(
        vacancy_id=vacancy.id,
        root_url=str(cfg.get("root_url") or ""),
        ingest_new_resumes=bool(cfg.get("ingest_new_resumes", True)),
        subfolders=dict(cfg.get("subfolders") or {}),
        last_sync_at=str(cfg.get("last_sync_at") or "") or None,
        seen_count=len(cfg.get("seen_paths") or []),
    )

@router.post("/vacancies/{vacancy_id}/yandex-disk/sync", response_model=YandexDiskSyncOut)
async def sync_vacancy_yandex_disk_now(
    vacancy_id: int,
    db: Session = Depends(get_db),
) -> YandexDiskSyncOut:
    """Synchronous sync (folder listing). Prefer ARQ job for large folders."""
    from app.services.yandex_disk_sync import sync_vacancy_yandex_disk

    require_intake_channel("disk_public_sync")
    vacancy = get_vacancy_or_404(db, vacancy_id)
    result = sync_vacancy_yandex_disk(db, vacancy)
    data = result.as_dict()
    job_ids = await _enqueue_resume_evals(db, data.get("evaluate_candidate_ids") or [])
    if job_ids and not any("очереди" in m for m in data.get("messages") or []):
        data.setdefault("messages", []).append(f"Оценка ИИ: задач в очереди {len(job_ids)}")
    cfg = (vacancy.payload or {}).get("yandex_disk") or {}
    return YandexDiskSyncOut(
        vacancy_id=vacancy.id,
        last_sync_at=str(cfg.get("last_sync_at") or "") or None,
        evaluate_job_ids=job_ids,
        **data,
    )

@router.get("/vacancies/{vacancy_id}/candidates", response_model=list[CandidateListItem])
def list_vacancy_candidates(vacancy_id: int, db: Session = Depends(get_db)) -> list[CandidateListItem]:
    get_vacancy_or_404(db, vacancy_id)
    # Same order as Streamlit LIST_DISPLAY_STAGE_ORDER (top → bottom)
    stage_order = [
        "resume_screening",
        "started_work",
        "internship",
        "offer",
        "client_meeting",
        "client_review",
        "client_pause",
        "test_task",
        "interview_done",
        "interview_scheduled",
        "primary_contact",
        "no_response_3d",
        "rejected_vacancy_closed",
        "rejected_hr",
        "rejected_client",
        "rejected_candidate",
        "rejected",
        "archived",
    ]
    rank = {s: i for i, s in enumerate(stage_order)}
    from app.services.resume_preview import is_resume_preview_included

    rows = list(
        db.scalars(select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)).all()
    )
    rows = [c for c in rows if not is_resume_preview_included(c.payload)]
    rows.sort(
        key=lambda c: (
            rank.get(c.hr_stage or "resume_screening", len(stage_order)),
            c.created_at or "",
            c.name or "",
        )
    )
    return [
        CandidateListItem(**serialize_list_item(c))
        for c in rows
    ]

@router.post(
    "/vacancies/{vacancy_id}/candidates",
    response_model=CandidateDetail,
    status_code=201,
)
def create_vacancy_candidate(
    vacancy_id: int,
    body: CandidateCreateIn,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from app.services.candidate_write import create_candidate

    require_intake_channel("manual")
    get_vacancy_or_404(db, vacancy_id)
    fields = body.model_dump(exclude={"name"}, exclude_none=True)
    cand = create_candidate(db, vacancy_id=vacancy_id, name=body.name, fields=fields)
    return _candidate_detail(db, cand)

@router.post(
    "/vacancies/{vacancy_id}/candidates/bulk-links",
    response_model=BulkLinksOut,
)
async def bulk_candidates_from_links(
    vacancy_id: int,
    body: BulkLinksIn,
    db: Session = Depends(get_db),
) -> BulkLinksOut:
    from app.services.candidate_resume_eval import bulk_add_from_resume_links, parse_bulk_link_lines

    require_intake_channel("file_link")
    vacancy = get_vacancy_or_404(db, vacancy_id)
    links = list(body.links or [])
    if body.text:
        links.extend(parse_bulk_link_lines(body.text))
    # dedupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            uniq.append(link)
    if not uniq:
        raise HTTPException(status_code=400, detail="Нет ссылок")
    if len(uniq) > 30:
        raise HTTPException(status_code=400, detail="Максимум 30 ссылок за раз")
    preview = _owner_resume_preview(bool(body.for_resume_preview))
    result = bulk_add_from_resume_links(
        db,
        vacancy,
        uniq,
        evaluate=bool(body.evaluate),
        for_resume_preview=preview,
    )
    job_ids = await _enqueue_resume_evals(
        db,
        result.get("evaluate_candidate_ids") or [],
        skip_questionnaire=preview,
    )
    result["evaluate_job_ids"] = job_ids
    if job_ids and not any("очереди" in m for m in result.get("messages") or []):
        hint = "лёгкая оценка для макетов" if preview else "Оценка ИИ"
        result.setdefault("messages", []).append(f"{hint}: задач в очереди {len(job_ids)}")
    return BulkLinksOut(**result)


@router.post(
    "/vacancies/{vacancy_id}/candidates/from-file",
    response_model=BulkLinksOut,
)
async def candidate_from_resume_file(
    vacancy_id: int,
    file: UploadFile = File(...),
    evaluate: str = Form(default="false"),
    for_resume_preview: str = Form(default="false"),
    db: Session = Depends(get_db),
) -> BulkLinksOut:
    from app.services.candidate_resume_eval import add_candidate_from_resume_file

    require_intake_channel("file_upload")
    vacancy = get_vacancy_or_404(db, vacancy_id)
    raw = await file.read()
    filename = (file.filename or "resume.pdf").strip() or "resume.pdf"
    do_eval = str(evaluate).strip().lower() in ("1", "true", "yes", "on")
    do_preview = _owner_resume_preview(
        str(for_resume_preview).strip().lower() in ("1", "true", "yes", "on")
    )
    try:
        result = add_candidate_from_resume_file(
            db,
            vacancy,
            filename=filename,
            content=raw,
            evaluate=do_eval,
            for_resume_preview=do_preview,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job_ids = await _enqueue_resume_evals(
        db,
        result.get("evaluate_candidate_ids") or [],
        skip_questionnaire=do_preview,
    )
    result["evaluate_job_ids"] = job_ids
    return BulkLinksOut(**result)


async def _enqueue_resume_evals(
    db: Session,
    candidate_ids: list[str],
    *,
    skip_questionnaire: bool = False,
) -> list[str]:
    """Queue background resume evaluation for newly added candidates."""
    try:
        return await job_svc.enqueue_candidate_resume_evals(
            db,
            candidate_ids,
            skip_questionnaire=skip_questionnaire,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Кандидаты добавлены, но очередь оценки недоступна (Redis/worker): {exc}",
        ) from exc


@router.post("/vacancies/{vacancy_id}/digest-to-chat")
def vacancy_digest_to_chat(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.messaging.ops import send_vacancy_digest

    vacancy = get_vacancy_or_404(db, vacancy_id)
    ok, msg = send_vacancy_digest(db, vacancy)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.get("/vacancies/{vacancy_id}/resume-preview")
def vacancy_resume_preview(
    vacancy_id: int,
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(require_platform_owner),
) -> dict:
    from app.services.resume_preview import pack_status

    vacancy = get_vacancy_or_404(db, vacancy_id)
    return pack_status(db, vacancy)


@router.post("/vacancies/{vacancy_id}/resume-preview/ensure")
def vacancy_resume_preview_ensure(
    vacancy_id: int,
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(require_platform_owner),
) -> dict:
    from app.services.resume_preview import ensure_preview_token, pack_status

    vacancy = get_vacancy_or_404(db, vacancy_id)
    ensure_preview_token(db, vacancy)
    return pack_status(db, vacancy)


@router.post("/vacancies/{vacancy_id}/resume-preview/send")
def vacancy_resume_preview_send(
    vacancy_id: int,
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(require_platform_owner),
) -> dict:
    from app.services.messaging.gateway import MessagingError
    from app.services.resume_preview import send_preview_pack

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        return send_preview_pack(db, vacancy)
    except MessagingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/vacancies/{vacancy_id}/resume-preview/candidates/{candidate_id}")
def vacancy_resume_preview_include(
    vacancy_id: int,
    candidate_id: str,
    body: ResumePreviewIncludeIn,
    db: Session = Depends(get_db),
    _user: AuthUser = Depends(require_platform_owner),
) -> dict:
    from app.services.resume_preview import set_included

    vacancy = get_vacancy_or_404(db, vacancy_id)
    return set_included(
        db,
        vacancy,
        candidate_id,
        included=body.included,
        visible=body.visible,
        pdf_url=body.pdf_url,
        hr_comment=body.hr_comment,
    )

