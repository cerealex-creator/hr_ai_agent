from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
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
)
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
from app.core.config import get_settings
from app.services.vacancy_outcome import (
    HIRE_STAGES,
    close_reason_from_payload,
    soft_vacancy_outcome,
)
from app.workers.redis_pool import get_arq_pool

ALLOWED_JOB_TYPES = frozenset(
    {
        "demo_progress",
        "import_legacy",
        "transcribe_media",
        "candidate_interview_process",
        "hh_cold_search",
        "yandex_disk_sync",
    }
)
ARQ_FUNCTION_BY_TYPE = {
    "demo_progress": "demo_progress",
    "import_legacy": "import_legacy",
    "transcribe_media": "transcribe_media",
    "candidate_interview_process": "candidate_interview_process",
    "hh_cold_search": "hh_cold_search",
    "yandex_disk_sync": "yandex_disk_sync",
}

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    db.execute(select(func.now()))
    return HealthOut(status="ok", database="up")


@router.get("/stats/import", response_model=ImportStatsOut)
def import_stats(db: Session = Depends(get_db)) -> ImportStatsOut:
    last = db.scalar(select(models.ImportRun).order_by(models.ImportRun.created_at.desc()).limit(1))
    counts = {
        "clients": db.scalar(select(func.count()).select_from(models.Client)) or 0,
        "vacancies": db.scalar(select(func.count()).select_from(models.Vacancy)) or 0,
        "candidates": db.scalar(select(func.count()).select_from(models.Candidate)) or 0,
        "document_generations": db.scalar(select(func.count()).select_from(models.DocumentGeneration))
        or 0,
        "messaging_channels": db.scalar(select(func.count()).select_from(models.MessagingChannel)) or 0,
        "vacancy_templates": db.scalar(select(func.count()).select_from(models.VacancyTemplate)) or 0,
        "jobs": db.scalar(select(func.count()).select_from(models.Job)) or 0,
    }
    if not last:
        return ImportStatsOut(counts=counts)
    return ImportStatsOut(
        last_import_at=last.created_at,
        source_dir=last.source_dir,
        stats=last.stats or {},
        counts=counts,
    )


@router.get("/clients", response_model=list[ClientOut])
def list_clients(
    for_vacancies: bool = Query(default=False),
    include_test: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ClientOut]:
    """Flat list. for_vacancies=true → selectable leaves (no company shells, no test)."""
    from app.services import clients_write as cw

    cw.ensure_client_schema(db)
    if for_vacancies:
        rows = cw.selectable_clients_for_vacancies(db)
    else:
        rows = list(db.scalars(select(models.Client).order_by(models.Client.id)).all())
        if not include_test:
            rows = [r for r in rows if r.kind != cw.KIND_TEST]
    return [ClientOut.model_validate(r) for r in rows]


@router.get("/companies", response_model=CompaniesTreeOut)
def list_companies_tree(
    migrate: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> CompaniesTreeOut:
    from app.services import clients_write as cw

    migration: dict = {}
    if migrate:
        migration = cw.migrate_legacy_clients(db)
    else:
        cw.ensure_client_schema(db)
    return CompaniesTreeOut(items=cw.company_tree(db), migration=migration)


@router.get("/companies/{company_id}", response_model=ClientTreeNodeOut)
def get_company(company_id: int, db: Session = Depends(get_db)) -> ClientTreeNodeOut:
    from app.services import clients_write as cw

    cw.ensure_client_schema(db)
    company = db.get(models.Client, company_id)
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

    client = db.get(models.Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    try:
        row = cw.patch_client(db, client, name=body.name, chat_mode=body.chat_mode)
    except cw.ClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return ClientOut.model_validate(row)


@router.delete("/clients/{client_id}", status_code=204)
def delete_client_endpoint(client_id: int, db: Session = Depends(get_db)) -> None:
    from app.services import clients_write as cw

    client = db.get(models.Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
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

    company = db.get(models.Client, company_id)
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


@router.get("/settings/test-chat", response_model=TestChatOut)
def get_test_chat(db: Session = Depends(get_db)) -> TestChatOut:
    from app.services import clients_write as cw

    cw.ensure_client_schema(db)
    client = cw.get_test_client(db)
    if not client:
        return TestChatOut()
    ch = cw.channel_for_client(db, client.id)
    return TestChatOut(
        client_id=client.id,
        name=client.name,
        chat_id=ch.external_id if ch else None,
        channel_id=str(ch.id) if ch else None,
    )


@router.put("/settings/test-chat", response_model=TestChatOut)
def put_test_chat(body: TestChatIn, db: Session = Depends(get_db)) -> TestChatOut:
    from app.services import clients_write as cw

    try:
        cw.ensure_client_schema(db)
        client, ch = cw.set_test_chat(db, name=body.name, chat_id=body.chat_id)
    except cw.ClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return TestChatOut(
        client_id=client.id,
        name=client.name,
        chat_id=ch.external_id,
        channel_id=str(ch.id),
    )


@router.delete("/settings/test-chat", status_code=204)
def delete_test_chat_binding(db: Session = Depends(get_db)) -> None:
    from app.services import clients_write as cw

    cw.clear_test_chat(db)


@router.get("/vacancies", response_model=list[VacancyListItem])
def list_vacancies(
    active: bool | None = Query(default=None),
    client_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VacancyListItem]:
    cand_count = (
        select(models.Candidate.vacancy_id, func.count().label("cnt"))
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
        .order_by(models.Vacancy.id)
    )
    if active is not None:
        q = q.where(models.Vacancy.active.is_(active))
    if client_id is not None:
        q = q.where(models.Vacancy.client_id == client_id)
    result: list[VacancyListItem] = []
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
            )
        )
    return result


@router.get("/vacancies/{vacancy_id}", response_model=VacancyDetail)
def get_vacancy(vacancy_id: int, db: Session = Depends(get_db)) -> VacancyDetail:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
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

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
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

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    try:
        vac = reopen_vacancy(db, vacancy)
    except VacancyWriteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _vacancy_detail(db, vac)


@router.delete("/vacancies/{vacancy_id}", status_code=204)
def delete_vacancy_endpoint(vacancy_id: int, db: Session = Depends(get_db)) -> None:
    from app.services.vacancy_write import delete_vacancy

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    delete_vacancy(db, vacancy)
    return None


def _vacancy_detail(db: Session, vacancy: models.Vacancy) -> VacancyDetail:
    client_name = None
    if vacancy.client_id is not None:
        client = db.get(models.Client, vacancy.client_id)
        client_name = client.name if client else None
    cnt = db.scalar(
        select(func.count())
        .select_from(models.Candidate)
        .where(models.Candidate.vacancy_id == vacancy.id)
    )
    hire_cnt = db.scalar(
        select(func.count())
        .select_from(models.Candidate)
        .where(
            models.Candidate.vacancy_id == vacancy.id,
            models.Candidate.hr_stage.in_(HIRE_STAGES),
        )
    )
    close_reason = close_reason_from_payload(vacancy.payload)
    has_hire = int(hire_cnt or 0) > 0
    return VacancyDetail(
        id=vacancy.id,
        title=vacancy.title,
        active=vacancy.active,
        client_id=vacancy.client_id,
        client_name=client_name,
        chat_id=vacancy.chat_id,
        documents=vacancy.documents or {},
        created_at=vacancy.created_at,
        closed_at=vacancy.closed_at,
        close_reason=close_reason,
        has_hire=has_hire,
        outcome=soft_vacancy_outcome(
            active=vacancy.active,
            close_reason=close_reason,
            has_hire=has_hire,
        ),
        payload=vacancy.payload or {},
        candidates_count=int(cnt or 0),
        document_keys=nonempty_document_keys(vacancy.documents),
    )


@router.patch("/vacancies/{vacancy_id}/settings", response_model=VacancyDetail)
def patch_vacancy_settings(
    vacancy_id: int,
    body: dict,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from sqlalchemy.orm.attributes import flag_modified

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    payload = dict(vacancy.payload or {})
    if "is_test" in body:
        payload["is_test"] = bool(body.get("is_test"))
    if "show_portfolio_field" in body:
        payload["show_portfolio_field"] = bool(body.get("show_portfolio_field"))
    if "control_word_enabled" in body:
        payload["control_word_enabled"] = bool(body.get("control_word_enabled"))
    if "control_word" in body:
        payload["control_word"] = str(body.get("control_word") or "").strip()
    if "chat_id" in body:
        vacancy.chat_id = str(body.get("chat_id") or "").strip() or None
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return _vacancy_detail(db, vacancy)


@router.get("/warranty/registry")
def warranty_registry(db: Session = Depends(get_db)) -> list[dict]:
    from app.services.warranty import collect_warranty_registry

    return collect_warranty_registry(db)


@router.post("/vacancies/{vacancy_id}/warranty/apply", response_model=VacancyDetail)
def warranty_apply(
    vacancy_id: int,
    body: dict,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    from uuid import UUID

    from app.services.app_settings import get_default_warranty_months
    from app.services.warranty import apply_warranty_to_vacancy

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    try:
        cid = UUID(str(body.get("candidate_id")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="candidate_id required") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate or candidate.vacancy_id != vacancy_id:
        raise HTTPException(status_code=404, detail="Candidate not found on vacancy")
    start = str(body.get("start_date") or "").strip()
    if not start:
        raise HTTPException(status_code=400, detail="start_date required")
    months = body.get("months")
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

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    try:
        new_v = create_warranty_search_vacancy(db, vacancy)
    except VacancyWriteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vacancy_detail(db, new_v)


@router.get("/settings/app")
def get_settings_app() -> dict:
    from app.services.app_settings import get_app_settings

    return get_app_settings()


@router.patch("/settings/app")
def patch_settings_app(body: dict) -> dict:
    from app.services.app_settings import (
        get_app_settings,
        set_ai_provider,
        set_candidate_comms,
        set_default_warranty_months,
        set_provider_links,
    )

    if "default_warranty_months" in body:
        try:
            set_default_warranty_months(int(body["default_warranty_months"]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "ai_provider" in body and isinstance(body.get("ai_provider"), dict):
        set_ai_provider(body["ai_provider"])
    elif "ai_model" in body:
        set_ai_provider({"model": body.get("ai_model")})
    if "provider_links" in body and isinstance(body.get("provider_links"), list):
        set_provider_links(body["provider_links"])
    if "candidate_comms" in body and isinstance(body.get("candidate_comms"), dict):
        set_candidate_comms(body["candidate_comms"])
    return get_app_settings()


@router.get("/integrations/google-calendar/status")
def google_calendar_status() -> dict:
    from app.services.google_calendar import (
        get_calendar_status,
        get_credentials_path,
        get_token_path,
    )

    status, message = get_calendar_status()
    return {
        "status": status,
        "message": message,
        "credentials_path": get_credentials_path(),
        "token_path": get_token_path(),
    }


@router.post("/integrations/google-calendar/oauth/start")
def google_calendar_oauth_start() -> dict:
    from app.services.google_calendar import oauth_auth_url

    ok, msg, url = oauth_auth_url()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg, "auth_url": url}


@router.post("/integrations/google-calendar/oauth/complete")
def google_calendar_oauth_complete(body: dict) -> dict:
    from app.services.google_calendar import oauth_complete_with_code

    ok, msg = oauth_complete_with_code(str(body.get("code") or ""))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.patch("/vacancies/{vacancy_id}/documents", response_model=VacancyDetail)
def patch_vacancy_documents(
    vacancy_id: int,
    body: VacancyDocumentsPatchIn,
    db: Session = Depends(get_db),
) -> VacancyDetail:
    """Merge editable document keys; never replaces whole blob (keeps hh_search_criteria)."""
    from app.services.vacancy_documents_write import EDITABLE_DOCUMENT_KEYS, save_documents

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    updates = body.model_dump(exclude_unset=True)
    unknown = set(updates) - set(EDITABLE_DOCUMENT_KEYS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Неизвестные ключи: {sorted(unknown)}")
    save_documents(db, vacancy, updates)
    return _vacancy_detail(db, vacancy)


@router.get("/vacancies/{vacancy_id}/documents/editor")
def vacancy_documents_editor(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.vacancy_documents_write import EDITABLE_DOCUMENT_KEYS, documents_for_editor

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return {
        "vacancy_id": vacancy.id,
        "keys": list(EDITABLE_DOCUMENT_KEYS),
        "documents": documents_for_editor(vacancy.documents),
    }


@router.post(
    "/vacancies/{vacancy_id}/documents/generate",
    response_model=VacancyDocumentGenerateOut,
)
def generate_vacancy_document(
    vacancy_id: int,
    body: VacancyDocumentGenerateIn,
    db: Session = Depends(get_db),
) -> VacancyDocumentGenerateOut:
    """Generate or regenerate one document section (profile / text / questions / keywords)."""
    from app.core.config import get_settings
    from app.services.document_generate import GENERATABLE_KEYS, generate_document_section
    from app.services.vacancy_documents_write import save_documents

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    key = (body.key or "").strip()
    if key not in GENERATABLE_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Ключ «{key}» нельзя генерировать. Доступно: {', '.join(GENERATABLE_KEYS)}",
        )
    try:
        result = generate_document_section(
            key=key,
            job_title=vacancy.title,
            documents=vacancy.documents or {},
            corrections=body.corrections,
            settings=get_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    value = result["value"]
    applied = False
    if body.apply:
        save_documents(db, vacancy, {key: value})
        applied = True
        db.refresh(vacancy)

    return VacancyDocumentGenerateOut(
        vacancy_id=vacancy.id,
        key=key,
        mode=str(result.get("mode") or "generate"),
        value=str(value) if not isinstance(value, str) else value,
        applied=applied,
        documents=vacancy.documents or {},
    )


@router.get("/vacancies/{vacancy_id}/yandex-disk", response_model=YandexDiskConfigOut)
def get_vacancy_yandex_disk(vacancy_id: int, db: Session = Depends(get_db)) -> YandexDiskConfigOut:
    from app.services.yandex_disk_sync import ensure_yandex_config

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
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

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
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
def sync_vacancy_yandex_disk_now(
    vacancy_id: int,
    db: Session = Depends(get_db),
) -> YandexDiskSyncOut:
    """Synchronous sync (folder listing). Prefer ARQ job for large folders."""
    from app.services.yandex_disk_sync import sync_vacancy_yandex_disk

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    result = sync_vacancy_yandex_disk(db, vacancy)
    cfg = (vacancy.payload or {}).get("yandex_disk") or {}
    return YandexDiskSyncOut(
        vacancy_id=vacancy.id,
        last_sync_at=str(cfg.get("last_sync_at") or "") or None,
        **result.as_dict(),
    )


@router.get("/vacancies/{vacancy_id}/candidates", response_model=list[CandidateListItem])
def list_vacancy_candidates(vacancy_id: int, db: Session = Depends(get_db)) -> list[CandidateListItem]:
    if not db.get(models.Vacancy, vacancy_id):
        raise HTTPException(status_code=404, detail="Vacancy not found")
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
        "rejected_hr",
        "rejected_client",
        "rejected_candidate",
        "rejected",
        "archived",
    ]
    rank = {s: i for i, s in enumerate(stage_order)}
    rows = list(
        db.scalars(select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)).all()
    )
    rows.sort(
        key=lambda c: (
            rank.get(c.hr_stage or "resume_screening", len(stage_order)),
            c.created_at or "",
            c.name or "",
        )
    )
    return [
        CandidateListItem(
            id=c.id,
            vacancy_id=c.vacancy_id,
            name=c.name,
            hr_stage=c.hr_stage,
            client_status=c.client_status,
            created_at=c.created_at,
            phone=(c.payload or {}).get("phone"),
            city=(c.payload or {}).get("city"),
        )
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

    if not db.get(models.Vacancy, vacancy_id):
        raise HTTPException(status_code=404, detail="Vacancy not found")
    fields = body.model_dump(exclude={"name"}, exclude_none=True)
    cand = create_candidate(db, vacancy_id=vacancy_id, name=body.name, fields=fields)
    return _candidate_detail(db, cand)


@router.get("/meta/hr-stages", response_model=list[StageOptionOut])
def list_hr_stages() -> list[StageOptionOut]:
    from app.services.candidate_write import HR_STAGES

    return [StageOptionOut(id=k, label=v) for k, v in HR_STAGES.items() if k != "rejected"]


@router.get("/vacancies/{vacancy_id}/hh-search-defaults")
def vacancy_hh_search_defaults(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    criteria = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    return {
        "vacancy_id": vacancy.id,
        "title": vacancy.title,
        "criteria": criteria,
        "warnings": warnings_for(criteria),
        "needs_prefill": needs_ai_prefill(vacancy.documents),
        "schedule_options": SCHEDULE_OPTIONS,
        "area_presets": AREA_PRESETS,
        "keywords": criteria.get("keywords") or "",
        "max_search_default": criteria.get("max_search") or 20,
        "max_evaluate_default": criteria.get("max_evaluate") or 10,
    }


@router.post("/vacancies/{vacancy_id}/hh-search-criteria/prefill")
def prefill_hh_search_criteria(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    try:
        result = prefill_criteria_with_ai(
            vacancy,
            db,
            get_settings(),
            existing=criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    criteria = result["criteria"]
    vacancy.documents = save_criteria_to_documents(vacancy.documents, criteria)
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(vacancy, "documents")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return {
        "vacancy_id": vacancy.id,
        "criteria": criteria,
        "warnings": warnings_for(criteria),
        "sources": result.get("sources") or [],
        "suggestion": result.get("suggestion") or "",
        "prefilled": True,
    }


@router.put("/vacancies/{vacancy_id}/hh-search-criteria")
def upsert_hh_search_criteria(
    vacancy_id: int,
    body: HhSearchCriteriaIn,
    db: Session = Depends(get_db),
) -> dict:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    criteria = ensure_portrait(normalize_criteria(body.criteria), rebuild=body.rebuild_portrait)
    vacancy.documents = save_criteria_to_documents(vacancy.documents, criteria)
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(vacancy, "documents")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return {
        "vacancy_id": vacancy.id,
        "criteria": criteria,
        "warnings": warnings_for(criteria),
    }


@router.get("/vacancies/{vacancy_id}/hh-shortlist", response_model=list[HhShortlistItemOut])
def list_hh_shortlist(vacancy_id: int, db: Session = Depends(get_db)) -> list[HhShortlistItemOut]:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    rows = (
        db.execute(
            select(models.HhShortlistItem)
            .where(models.HhShortlistItem.vacancy_id == vacancy_id)
            .order_by(models.HhShortlistItem.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [HhShortlistItemOut.model_validate(r) for r in rows]


@router.post(
    "/vacancies/{vacancy_id}/hh-shortlist",
    response_model=HhShortlistItemOut,
    status_code=201,
)
def add_hh_shortlist(
    vacancy_id: int,
    body: HhShortlistCreateIn,
    db: Session = Depends(get_db),
) -> HhShortlistItemOut:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    rid = (body.hh_resume_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="hh_resume_id обязателен")
    existing = db.execute(
        select(models.HhShortlistItem).where(
            models.HhShortlistItem.vacancy_id == vacancy_id,
            models.HhShortlistItem.hh_resume_id == rid,
        )
    ).scalar_one_or_none()
    if existing:
        existing.title = body.title or existing.title
        existing.url = body.url or existing.url
        existing.area = body.area or existing.area
        if body.ai_score is not None:
            existing.ai_score = body.ai_score
        if body.snapshot:
            existing.snapshot = body.snapshot
        if body.note is not None:
            existing.note = body.note
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return HhShortlistItemOut.model_validate(existing)
    row = models.HhShortlistItem(
        vacancy_id=vacancy_id,
        hh_resume_id=rid,
        title=body.title or "",
        url=body.url,
        area=body.area,
        ai_score=body.ai_score,
        snapshot=body.snapshot or {},
        note=body.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return HhShortlistItemOut.model_validate(row)


@router.delete("/vacancies/{vacancy_id}/hh-shortlist/{item_id}", status_code=204)
def delete_hh_shortlist(vacancy_id: int, item_id: str, db: Session = Depends(get_db)) -> None:
    try:
        from uuid import UUID

        iid = UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid id") from exc
    row = db.get(models.HhShortlistItem, iid)
    if not row or row.vacancy_id != vacancy_id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return None


@router.post("/vacancies/{vacancy_id}/hh-manual-evaluate")
def hh_manual_evaluate(vacancy_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    """Evaluate recruiter-provided HH resume URLs/ids; return comparison rows."""
    from app.services.hh_manual_eval import evaluate_manual_hh_resumes

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    text = str(body.get("text") or body.get("refs") or "").strip()
    criteria = body.get("criteria") if isinstance(body.get("criteria"), dict) else None
    try:
        return evaluate_manual_hh_resumes(db, vacancy, text, criteria=criteria)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/vacancies/{vacancy_id}/hh-soften-suggestions")
def hh_soften_suggestions(vacancy_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    """AI checklist: what filters/requirements to soften after search or good resumes."""
    from app.services.hh_manual_eval import suggest_criteria_softening
    from app.services.hh_search_criteria import criteria_from_vacancy_documents, normalize_criteria

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    criteria = body.get("criteria") if isinstance(body.get("criteria"), dict) else None
    if not criteria:
        criteria = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    criteria = normalize_criteria(criteria)
    search_results = body.get("search_results") if isinstance(body.get("search_results"), list) else None
    good_resumes = body.get("good_resumes") if isinstance(body.get("good_resumes"), list) else None
    try:
        return suggest_criteria_softening(
            vacancy_title=vacancy.title or "",
            criteria=criteria,
            search_results=search_results,
            good_resumes=good_resumes,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/vacancies/{vacancy_id}/hh-soften-apply")
def hh_soften_apply(vacancy_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    """Apply selected soften suggestions; optionally persist into vacancy documents."""
    from app.services.hh_manual_eval import apply_soften_suggestions
    from app.services.hh_search_criteria import (
        DOC_KEY,
        criteria_from_vacancy_documents,
        normalize_criteria,
        warnings_for,
    )

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    criteria = body.get("criteria") if isinstance(body.get("criteria"), dict) else None
    if not criteria:
        criteria = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    suggestions = body.get("suggestions") if isinstance(body.get("suggestions"), list) else []
    selected_ids = body.get("selected_ids") if isinstance(body.get("selected_ids"), list) else []
    next_c = apply_soften_suggestions(criteria, suggestions, [str(x) for x in selected_ids])
    persist = bool(body.get("persist", True))
    if persist:
        docs = dict(vacancy.documents or {})
        docs[DOC_KEY] = next_c
        vacancy.documents = docs
        db.add(vacancy)
        db.commit()
        db.refresh(vacancy)
    return {
        "criteria": normalize_criteria(next_c),
        "warnings": warnings_for(next_c),
        "persisted": persist,
    }


def _candidate_detail(db: Session, candidate: models.Candidate) -> CandidateDetail:
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    client_name = None
    client_id = vacancy.client_id if vacancy else None
    if client_id is not None:
        client = db.get(models.Client, client_id)
        client_name = client.name if client else None
    fields = candidate_public_fields(candidate.payload)
    return CandidateDetail(
        id=candidate.id,
        vacancy_id=candidate.vacancy_id,
        vacancy_title=vacancy.title if vacancy else None,
        client_id=client_id,
        client_name=client_name,
        name=candidate.name,
        hr_stage=candidate.hr_stage,
        client_status=candidate.client_status,
        created_at=candidate.created_at,
        status_updated_at=candidate.status_updated_at,
        payload=candidate.payload or {},
        **fields,
    )


@router.post(
    "/vacancies/{vacancy_id}/hh-shortlist/{item_id}/to-candidate",
    response_model=HhShortlistToCandidateOut,
)
def hh_shortlist_to_candidate(
    vacancy_id: int,
    item_id: str,
    remove_from_shortlist: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> HhShortlistToCandidateOut:
    """Create a funnel candidate from a shortlist item (cold HH, no contacts)."""
    from app.services.hh_to_candidate import create_candidate_from_shortlist

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    try:
        from uuid import UUID

        iid = UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid id") from exc
    row = db.get(models.HhShortlistItem, iid)
    if not row or row.vacancy_id != vacancy_id:
        raise HTTPException(status_code=404, detail="Shortlist item not found")
    try:
        candidate, created = create_candidate_from_shortlist(
            db,
            vacancy_id=vacancy_id,
            item=row,
            remove_from_shortlist=remove_from_shortlist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HhShortlistToCandidateOut(
        candidate=_candidate_detail(db, candidate),
        created=created,
        already_exists=not created,
    )


@router.get("/vacancies/{vacancy_id}/hh-seen", response_model=list[HhSeenItemOut])
def list_hh_seen(vacancy_id: int, db: Session = Depends(get_db)) -> list[HhSeenItemOut]:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    rows = (
        db.execute(
            select(models.HhSeenResume)
            .where(models.HhSeenResume.vacancy_id == vacancy_id)
            .order_by(models.HhSeenResume.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return [HhSeenItemOut.model_validate(r) for r in rows]


@router.post(
    "/vacancies/{vacancy_id}/hh-seen/reject",
    response_model=HhSeenItemOut,
    status_code=201,
)
def reject_hh_seen(
    vacancy_id: int,
    body: HhSeenRejectIn,
    db: Session = Depends(get_db),
) -> HhSeenItemOut:
    from app.services.hh_seen import REASON_RECRUITER, upsert_seen

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    try:
        row = upsert_seen(
            db,
            vacancy_id=vacancy_id,
            hh_resume_id=body.hh_resume_id,
            reason=REASON_RECRUITER,
            title=body.title,
            url=body.url,
            ai_score=body.ai_score,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HhSeenItemOut.model_validate(row)


@router.delete("/vacancies/{vacancy_id}/hh-seen/{hh_resume_id}", status_code=204)
def unban_hh_seen(vacancy_id: int, hh_resume_id: str, db: Session = Depends(get_db)) -> None:
    from app.services.hh_seen import delete_seen

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    if not delete_seen(db, vacancy_id, hh_resume_id):
        raise HTTPException(status_code=404, detail="Not found")
    return None


@router.get("/candidates", response_model=list[CandidateListItem])
def list_candidates(
    client_id: int | None = Query(default=None),
    vacancy_id: int | None = Query(default=None),
    active_vacancies_only: bool = Query(default=False),
    hr_stage: str | None = Query(default=None),
    client_status: str | None = Query(default=None),
    preset: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CandidateListItem]:
    """Drill-down list for stats (same scope/preset semantics as /stats/funnel)."""
    from app.services.candidate_query import (
        CANDIDATE_PRESETS,
        list_candidates_filtered,
        serialize_list_item,
        vacancy_meta_maps,
    )

    if preset and preset not in CANDIDATE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"preset: {', '.join(sorted(CANDIDATE_PRESETS))}",
        )
    try:
        rows, vacancies, _label = list_candidates_filtered(
            db,
            client_id=client_id,
            vacancy_id=vacancy_id,
            active_vacancies_only=active_vacancies_only,
            hr_stage=hr_stage,
            client_status=client_status,
            preset=preset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    titles, client_names = vacancy_meta_maps(db, vacancies)
    # Also resolve titles for vacancies not in filtered active set (shouldn't happen)
    missing = {c.vacancy_id for c in rows} - set(titles)
    if missing:
        extra = list(db.scalars(select(models.Vacancy).where(models.Vacancy.id.in_(missing))).all())
        more_titles, more_clients = vacancy_meta_maps(db, extra)
        titles.update(more_titles)
        client_names.update(more_clients)

    return [
        CandidateListItem(
            **serialize_list_item(
                c,
                vacancy_title=titles.get(c.vacancy_id),
                client_name=client_names.get(c.vacancy_id),
            )
        )
        for c in rows
    ]


@router.get("/candidates/search")
def search_candidates_endpoint(
    q: str = Query(default=""),
    include_test: bool = Query(default=False),
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    from app.services.candidate_search import search_candidates

    return search_candidates(db, q, include_test=include_test, limit=limit)


@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)) -> CandidateDetail:
    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _candidate_detail(db, candidate)


@router.patch("/candidates/{candidate_id}", response_model=CandidateDetail)
def patch_candidate_endpoint(
    candidate_id: str,
    body: CandidatePatchIn,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from app.services.candidate_write import patch_candidate

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    data = body.model_dump(exclude_unset=True)
    name = data.pop("name", None)
    from app.services.messaging.ops import refresh_candidate_telegram, snapshot_card_payload

    before = snapshot_card_payload(candidate)
    patch_candidate(candidate, name=name, fields=data)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    # Best-effort refresh of Telegram card after HR edits (links / анкета)
    try:
        after = snapshot_card_payload(candidate)
        changed = any(before.get(k) != after.get(k) for k in before)
        # Always try silent refresh; notify when link fields changed
        refresh_candidate_telegram(
            db,
            candidate,
            notify=changed,
            before_payload=before,
        )
    except Exception:  # noqa: BLE001
        pass
    return _candidate_detail(db, candidate)


@router.post("/candidates/{candidate_id}/stage", response_model=CandidateDetail)
def set_candidate_stage(
    candidate_id: str,
    body: CandidateStageIn,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from app.services.candidate_write import set_stage

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        set_stage(
            db,
            candidate,
            hr_stage=body.hr_stage,
            note=body.note,
            office_interview_date=body.office_interview_date,
            office_interview_time=body.office_interview_time,
            keep_calendar_event=body.keep_calendar_event,
            warranty_start_date=body.warranty_start_date,
            warranty_months=body.warranty_months,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Refresh TG card after stage change
    try:
        from app.services.messaging.ops import refresh_candidate_telegram

        refresh_candidate_telegram(db, candidate)
    except Exception:  # noqa: BLE001
        pass
    return _candidate_detail(db, candidate)


@router.post("/candidates/{candidate_id}/apply-client-stage", response_model=CandidateDetail)
def apply_client_stage_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from app.services.candidate_write import set_stage, suggested_hr_stage_from_client_status

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    suggested = suggested_hr_stage_from_client_status(candidate)
    if not suggested:
        raise HTTPException(status_code=400, detail="Нет расхождения этапа с статусом заказчика")
    try:
        set_stage(
            db,
            candidate,
            hr_stage=suggested,
            note="синхронизация с client_status",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _candidate_detail(db, candidate)


@router.post("/candidates/{candidate_id}/copy", response_model=CandidateDetail)
def copy_candidate_endpoint(
    candidate_id: str,
    body: dict,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from app.services.candidate_copy import copy_candidate_to_vacancy

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        target_id = int(body.get("target_vacancy_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="target_vacancy_id required") from exc
    try:
        copied = copy_candidate_to_vacancy(db, candidate, target_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _candidate_detail(db, copied)


@router.delete("/candidates/{candidate_id}", status_code=204)
def delete_candidate_endpoint(candidate_id: str, db: Session = Depends(get_db)) -> None:
    from app.services.candidate_write import delete_candidate

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    delete_candidate(db, candidate)
    return None


@router.post(
    "/candidates/{candidate_id}/evaluate-resume",
    response_model=CandidateEvaluateOut,
)
def evaluate_candidate_resume_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> CandidateEvaluateOut:
    from app.services.candidate_resume_eval import CandidateEvalError, evaluate_candidate_resume

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        result = evaluate_candidate_resume(db, candidate, populate_fields=True)
    except CandidateEvalError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.refresh(candidate)
    return CandidateEvaluateOut(
        ok=True,
        ai_score=result.get("ai_score"),
        extract_error=result.get("extract_error"),
        profile_present=bool(result.get("profile_present")),
        questionnaire_generated=bool(result.get("questionnaire_generated")),
        questionnaire_count=int(result.get("questionnaire_count") or 0),
        candidate=_candidate_detail(db, candidate),
    )


@router.post(
    "/candidates/{candidate_id}/evaluate-interview",
    response_model=CandidateEvaluateOut,
)
def evaluate_candidate_interview_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> CandidateEvaluateOut:
    from app.services.candidate_interview_eval import evaluate_candidate_interview
    from app.services.candidate_resume_eval import CandidateEvalError

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        result = evaluate_candidate_interview(db, candidate)
    except CandidateEvalError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.refresh(candidate)
    return CandidateEvaluateOut(
        ok=True,
        ai_score=result.get("ai_score"),
        extract_error=None,
        profile_present=bool(result.get("profile_present")),
        questionnaire_generated=False,
        questionnaire_count=len((candidate.payload or {}).get("interview_questionnaire") or []),
        candidate=_candidate_detail(db, candidate),
    )


@router.post(
    "/vacancies/{vacancy_id}/candidates/bulk-links",
    response_model=BulkLinksOut,
)
def bulk_candidates_from_links(
    vacancy_id: int,
    body: BulkLinksIn,
    db: Session = Depends(get_db),
) -> BulkLinksOut:
    from app.services.candidate_resume_eval import bulk_add_from_resume_links, parse_bulk_link_lines

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
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
    result = bulk_add_from_resume_links(
        db, vacancy, uniq, evaluate=bool(body.evaluate)
    )
    return BulkLinksOut(**result)


@router.get("/candidates/{candidate_id}/questionnaire", response_model=QuestionnaireOut)
def get_candidate_questionnaire_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> QuestionnaireOut:
    from app.services.candidate_questionnaire import get_candidate_questionnaire

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    items = get_candidate_questionnaire(candidate)
    return QuestionnaireOut(candidate_id=str(candidate.id), items=items, count=len(items))


@router.put("/candidates/{candidate_id}/questionnaire", response_model=QuestionnaireOut)
def put_candidate_questionnaire_endpoint(
    candidate_id: str,
    body: QuestionnairePutIn,
    db: Session = Depends(get_db),
) -> QuestionnaireOut:
    from app.services.candidate_questionnaire import save_candidate_questionnaire

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    items = save_candidate_questionnaire(db, candidate, body.items or [])
    return QuestionnaireOut(candidate_id=str(candidate.id), items=items, count=len(items))


@router.post(
    "/candidates/{candidate_id}/questionnaire/generate",
    response_model=QuestionnaireOut,
)
def generate_candidate_questionnaire_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> QuestionnaireOut:
    from app.services.candidate_questionnaire import (
        QuestionnaireError,
        generate_candidate_questionnaire,
    )

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        items = generate_candidate_questionnaire(db, candidate)
    except QuestionnaireError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return QuestionnaireOut(candidate_id=str(candidate.id), items=items, count=len(items))


@router.post(
    "/candidates/{candidate_id}/questionnaire/regenerate",
    response_model=QuestionnaireOut,
)
def regenerate_candidate_questionnaire_endpoint(
    candidate_id: str,
    body: QuestionnaireRegenerateIn,
    db: Session = Depends(get_db),
) -> QuestionnaireOut:
    from app.services.candidate_questionnaire import (
        QuestionnaireError,
        regenerate_candidate_questionnaire,
    )

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        items = regenerate_candidate_questionnaire(db, candidate, recruiter_notes=body.notes or "")
    except QuestionnaireError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return QuestionnaireOut(candidate_id=str(candidate.id), items=items, count=len(items))


@router.post(
    "/candidates/{candidate_id}/questionnaire/fill-from-transcript",
    response_model=QuestionnaireOut,
)
def fill_candidate_questionnaire_from_transcript_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> QuestionnaireOut:
    from app.services.candidate_questionnaire import (
        QuestionnaireError,
        fill_candidate_questionnaire_from_transcript,
    )

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    try:
        items = fill_candidate_questionnaire_from_transcript(db, candidate)
    except QuestionnaireError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return QuestionnaireOut(candidate_id=str(candidate.id), items=items, count=len(items))


@router.post("/candidates/{candidate_id}/transcribe-and-evaluate", response_model=JobCreateOut, status_code=202)
async def transcribe_candidate_and_evaluate(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> JobCreateOut:
    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    source_url = str((candidate.payload or {}).get("video_link") or "").strip()
    if not source_url:
        raise HTTPException(status_code=400, detail="Добавьте ссылку на запись собеседования")
    existing = job_svc.find_active_job_for_candidate(
        db,
        job_type="candidate_interview_process",
        candidate_id=str(candidate.id),
    )
    if existing:
        return JobCreateOut(
            id=existing.id,
            status=existing.status,
            job_type=existing.job_type,
            reused=True,
            progress_label=existing.progress_label,
        )
    job = job_svc.create_job_row(
        db,
        job_type="candidate_interview_process",
        vacancy_id=candidate.vacancy_id,
        payload={
            "candidate_id": str(candidate.id),
            "candidate_name": candidate.name,
            "source_url": source_url,
        },
    )
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job("candidate_interview_process", str(job.id), _job_id=str(job.id))
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


def _channel_out(r: models.MessagingChannel) -> MessagingChannelOut:
    return MessagingChannelOut(
        id=r.id,
        provider=r.provider,
        external_id=r.external_id,
        client_id=r.client_id,
        name=r.name or r.external_id,
        metadata=r.metadata_json or {},
    )


@router.get("/messaging/channels", response_model=list[MessagingChannelOut])
def messaging_list_channels(db: Session = Depends(get_db)) -> list[MessagingChannelOut]:
    from app.services.messaging.channels import list_channels

    return [_channel_out(r) for r in list_channels(db)]


@router.post("/messaging/channels", response_model=MessagingChannelOut)
def messaging_create_channel(
    body: MessagingChannelCreateIn,
    db: Session = Depends(get_db),
) -> MessagingChannelOut:
    from app.services.clients_write import ClientError, create_client
    from app.services.messaging.channels import ChannelError, create_channel

    client_id = body.client_id
    new_name = (body.new_client_name or "").strip()
    if new_name:
        try:
            client = create_client(db, new_name)
            client_id = client.id
        except ClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    try:
        row = create_channel(
            db,
            name=body.name,
            chat_id=body.chat_id,
            client_id=client_id,
        )
    except ChannelError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _channel_out(row)


@router.post("/messaging/channels/sync", response_model=MessagingChannelsSyncOut)
def messaging_sync_channels(db: Session = Depends(get_db)) -> MessagingChannelsSyncOut:
    from app.services.messaging.channels import sync_channels_from_vacancies

    return MessagingChannelsSyncOut(**sync_channels_from_vacancies(db))


@router.get("/messaging/status")
def messaging_status() -> dict:
    from app.core.config import get_settings
    from app.services.messaging.telegram_provider import get_me

    settings = get_settings()
    token_set = bool((settings.telegram_bot_token or "").strip())
    ok, msg, info = get_me() if token_set else (False, "token not set", {})
    return {
        "outbound_enabled": settings.messaging_outbound_enabled,
        "inbound_enabled": settings.messaging_inbound_enabled,
        "poll_enabled": settings.messaging_poll_enabled,
        "token_configured": token_set,
        "hr_user_id": settings.telegram_hr_user_id or None,
        "bot_ok": ok,
        "bot_message": msg,
        "bot": info,
        "note": (
            "Inbound off — Streamlit bot.py may keep polling. "
            "Do not enable MESSAGING_INBOUND_ENABLED on the same token while bot.py runs."
            if not settings.messaging_inbound_enabled
            else (
                "Inbound on + poll — run: python -m app.workers.telegram_poller"
                if settings.messaging_poll_enabled
                else "Inbound on — use HTTPS webhook, or set MESSAGING_POLL_ENABLED=true for getUpdates poller."
            )
        ),
    }


@router.post("/messaging/test-message")
def messaging_test_message(body: dict, db: Session = Depends(get_db)) -> dict:
    from app.services.messaging.telegram_provider import send_html_message

    chat_id = str(body.get("chat_id") or "").strip()
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id required")
    text = str(body.get("text") or "Тестовое сообщение от HR AI Agent v2").strip()
    ok, msg, mid = send_html_message(chat_id, text)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg, "message_id": mid}


@router.patch("/messaging/channels/{channel_id}", response_model=MessagingChannelOut)
def messaging_patch_channel(
    channel_id: str,
    body: MessagingChannelPatchIn,
    db: Session = Depends(get_db),
) -> MessagingChannelOut:
    from app.services.messaging.channels import ChannelError, update_channel

    try:
        from uuid import UUID

        cid = UUID(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid channel id") from exc
    row = db.get(models.MessagingChannel, cid)
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    client_arg: int | None | object = ...
    if body.clear_client:
        client_arg = None
    elif body.client_id is not None:
        client_arg = body.client_id
    try:
        row = update_channel(
            db,
            row,
            name=body.name,
            chat_id=body.chat_id,
            client_id=client_arg,
        )
    except ChannelError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _channel_out(row)


@router.delete("/messaging/channels/{channel_id}", response_model=MessagingChannelDeleteOut)
def messaging_delete_channel(
    channel_id: str, db: Session = Depends(get_db)
) -> MessagingChannelDeleteOut:
    from app.services.messaging.channels import ChannelError, delete_channel

    try:
        from uuid import UUID

        cid = UUID(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid channel id") from exc
    row = db.get(models.MessagingChannel, cid)
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    try:
        delete_channel(db, row)
    except ChannelError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return MessagingChannelDeleteOut(ok=True)


@router.post(
    "/candidates/{candidate_id}/send-to-chat",
    response_model=CandidateSendToChatOut,
)
def send_candidate_to_chat(
    candidate_id: str,
    body: CandidateSendToChatIn | None = None,
    db: Session = Depends(get_db),
) -> CandidateSendToChatOut:
    from app.services.messaging.gateway import MessagingError, send_candidate_card

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    opts = body or CandidateSendToChatIn()
    try:
        result = send_candidate_card(
            db,
            candidate,
            move_to_client_review=opts.move_to_client_review,
        )
    except MessagingError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.refresh(candidate)
    return CandidateSendToChatOut(
        **result,
        candidate=_candidate_detail(db, candidate),
    )


@router.post("/candidates/{candidate_id}/remind")
def remind_candidate(
    candidate_id: str,
    kind: str = Query(default="evaluate"),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.messaging.ops import send_manual_reminder

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    ok, msg = send_manual_reminder(db, candidate, kind=kind if kind in ("evaluate", "decide") else "evaluate")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.post("/candidates/{candidate_id}/extra-material")
def send_candidate_extra_material(
    candidate_id: str,
    body: dict,
    db: Session = Depends(get_db),
) -> dict:
    from app.services.messaging.ops import send_extra_material

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    ok, msg = send_extra_material(
        db,
        candidate,
        title=str(body.get("title") or "Материал"),
        url=str(body.get("url") or ""),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg, "candidate": _candidate_detail(db, candidate)}


@router.post("/candidates/{candidate_id}/refresh-telegram")
def refresh_candidate_telegram_endpoint(
    candidate_id: str,
    notify: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.messaging.ops import refresh_candidate_telegram

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    ok, msg = refresh_candidate_telegram(db, candidate, notify=notify)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.post("/vacancies/{vacancy_id}/digest-to-chat")
def vacancy_digest_to_chat(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.messaging.ops import send_vacancy_digest

    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    ok, msg = send_vacancy_digest(db, vacancy)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.post("/messaging/send-instruction")
def messaging_send_instruction(body: dict, db: Session = Depends(get_db)) -> dict:
    from app.services.messaging.ops import send_client_instruction

    chat_id = str(body.get("chat_id") or "").strip()
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id required")
    ok, msg = send_client_instruction(db, chat_id, body.get("text"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.get(
    "/candidates/{candidate_id}/messaging-posts",
    response_model=list[MessagingPostOut],
)
def list_candidate_messaging_posts(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> list[MessagingPostOut]:
    from app.services.messaging.gateway import list_candidate_posts

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    if not db.get(models.Candidate, cid):
        raise HTTPException(status_code=404, detail="Candidate not found")
    return [MessagingPostOut.model_validate(p) for p in list_candidate_posts(db, cid)]


@router.post("/integrations/{provider}/webhook", response_model=WebhookAckOut)
def integrations_webhook(
    provider: str,
    payload: dict,
    db: Session = Depends(get_db),
) -> WebhookAckOut:
    """Telegram webhook. Safe no-op while MESSAGING_INBOUND_ENABLED=false."""
    from app.core.config import get_settings
    from app.services.messaging.gateway import parse_inbound_webhook

    settings = get_settings()
    events = parse_inbound_webhook(provider, payload or {}, db=db)
    handled = any(bool(e.get("handled")) for e in events)
    note = (
        "inbound enabled"
        if settings.messaging_inbound_enabled
        else "inbound disabled — Streamlit bot keeps polling until cutover"
    )
    return WebhookAckOut(
        ok=True,
        handled=handled,
        provider=provider,
        events=events,
        note=note,
    )


@router.get("/stats/funnel", response_model=FunnelStatsOut)
def funnel_stats(
    client_id: int | None = Query(default=None),
    vacancy_id: int | None = Query(default=None),
    active_vacancies_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> FunnelStatsOut:
    from app.services.stats_service import build_funnel_stats

    data = build_funnel_stats(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
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

    return HhEfficiencyStatsOut(
        **build_hh_stats(
            db,
            client_id=client_id,
            vacancy_id=vacancy_id,
            active_vacancies_only=active_vacancies_only,
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
    )
    return ActivityStatsOut.model_validate(data)


@router.get("/history", response_model=list[DocumentGenerationOut])
def list_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[DocumentGenerationOut]:
    rows = db.scalars(
        select(models.DocumentGeneration)
        .order_by(models.DocumentGeneration.created_at_legacy.desc().nulls_last())
        .limit(limit)
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
        )
        for r in rows
    ]


@router.get("/history/{generation_id}", response_model=DocumentGenerationDetail)
def get_history_item(generation_id: str, db: Session = Depends(get_db)) -> DocumentGenerationDetail:
    try:
        from uuid import UUID

        gid = UUID(generation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid history id") from exc
    row = db.get(models.DocumentGeneration, gid)
    if not row:
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
    )


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


@router.get("/vacancies/{vacancy_id}/hh-search-history", response_model=JobHistoryListOut)
def hh_search_history(
    vacancy_id: int,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> JobHistoryListOut:
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    rows = job_svc.list_jobs(
        db, limit=limit, vacancy_id=vacancy_id, job_type="hh_cold_search"
    )
    return JobHistoryListOut(
        items=[JobHistoryItemOut(**job_svc.job_history_summary(r)) for r in rows]
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
    if body.job_type == "transcribe_media":
        source_url = str(payload.get("source_url") or "").strip()
        if not source_url:
            raise HTTPException(
                status_code=400,
                detail="Для transcribe_media нужен payload.source_url",
            )
        payload["source_url"] = source_url
    if body.job_type == "hh_cold_search":
        vacancy_id = body.vacancy_id or payload.get("vacancy_id")
        if vacancy_id is None:
            raise HTTPException(
                status_code=400,
                detail="Для hh_cold_search нужен vacancy_id",
            )
        vacancy = db.get(models.Vacancy, int(vacancy_id))
        if not vacancy:
            raise HTTPException(status_code=404, detail="Vacancy not found")
        criteria = normalize_criteria(payload.get("criteria") or {})
        if not criteria.get("keywords"):
            stored = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
            criteria = stored
        if not (criteria.get("keywords") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Нет keywords: заполните критерии поиска вакансии",
            )
        criteria = ensure_portrait(criteria)
        # Persist latest criteria used for search
        vacancy.documents = save_criteria_to_documents(vacancy.documents, criteria)
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(vacancy, "documents")
        db.add(vacancy)
        db.commit()
        payload["criteria"] = criteria
        payload["keywords"] = criteria["keywords"]
        payload["vacancy_id"] = int(vacancy_id)
        body = body.model_copy(update={"vacancy_id": int(vacancy_id)})
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
