"""v1 API routes (split from endpoints.py — audit M6)."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
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
    CheckDuplicateIn,
    CheckDuplicateOut,
    DupHitOut,
    RelatedCandidateOut,
    RelatedVacanciesOut,
    CandidateStageIn,
    CandidateOfferDraftIn,
    CandidateOfferDraftOut,
    CompanyOfferLogoIn,
    CandidateSendToChatIn,
    CandidateSendToChatOut,
    CandidateEvaluateOut,
    EvaluateResumeIn,
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
    ZoomMeetingScheduleIn,
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


@router.post("/candidates/check-duplicate", response_model=CheckDuplicateOut)
def check_duplicate_endpoint(
    body: CheckDuplicateIn,
    db: Session = Depends(get_db),
) -> CheckDuplicateOut:
    from app.services.person_match import check_duplicates
    from app.services.tenancy import require_org_id

    org_id = require_org_id()
    result = check_duplicates(
        db,
        org_id=org_id,
        phone=body.phone,
        email=body.email,
        name=body.name,
        exclude_candidate_id=body.candidate_id,
    )
    return CheckDuplicateOut(
        hard=[DupHitOut(**vars(h)) for h in result["hard"]],
        soft=[DupHitOut(**vars(h)) for h in result["soft"]],
    )


@router.get("/candidates/{candidate_id}/related", response_model=RelatedVacanciesOut)
def get_candidate_related(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> RelatedVacanciesOut:
    from app.services.person_match import get_related_candidates

    try:
        from uuid import UUID
        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    siblings = get_related_candidates(db, candidate)
    return RelatedVacanciesOut(
        person_id=str(candidate.person_id) if candidate.person_id else None,
        siblings=[RelatedCandidateOut(**s) for s in siblings],
    )


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
        last_contact_map,
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
        from app.services.tenancy import require_org_id

        rows, vacancies, _label = list_candidates_filtered(
            db,
            client_id=client_id,
            vacancy_id=vacancy_id,
            active_vacancies_only=active_vacancies_only,
            hr_stage=hr_stage,
            client_status=client_status,
            preset=preset,
            organization_id=require_org_id(),
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

    posts = last_contact_map(db, [c.id for c in rows])
    return [
        CandidateListItem(
            **serialize_list_item(
                c,
                vacancy_title=titles.get(c.vacancy_id),
                client_name=client_names.get(c.vacancy_id),
                last_contact_at=posts.get(c.id),
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
    from app.services.tenancy import require_org_id

    return search_candidates(
        db, q, include_test=include_test, limit=limit, organization_id=require_org_id()
    )

@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)) -> CandidateDetail:
    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    return _candidate_detail(db, candidate)


@router.get("/candidates/{candidate_id}/offer.docx")
def download_candidate_offer(candidate_id: str, db: Session = Depends(get_db)) -> Response:
    from uuid import UUID

    from app.services.offer_docx import attachment_content_disposition, generate_candidate_offer_docx

    try:
        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    try:
        data, filename = generate_candidate_offer_docx(db, candidate, settings=get_settings())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось собрать Word: {exc}") from exc
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": attachment_content_disposition(filename)},
    )


def _offer_out(db: Session, candidate: models.Candidate, draft: dict) -> CandidateOfferDraftOut:
    from app.services.offer_draft import OFFER_KEYS, company_logo_data_url, resolve_company_client

    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    company = resolve_company_client(db, vacancy)
    payload = {k: str(draft.get(k) or "") for k in OFFER_KEYS}
    return CandidateOfferDraftOut(
        **payload,
        logo_data_url=company_logo_data_url(db, vacancy),
        company_client_id=int(company.id) if company else None,
    )


@router.get("/candidates/{candidate_id}/offer", response_model=CandidateOfferDraftOut)
def get_candidate_offer(candidate_id: str, db: Session = Depends(get_db)) -> CandidateOfferDraftOut:
    from uuid import UUID

    from app.services.offer_draft import get_offer_draft, prefill_offer_draft

    try:
        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    draft = get_offer_draft(candidate)
    if not any(draft.values()):
        draft = prefill_offer_draft(db, candidate)
    return _offer_out(db, candidate, draft)


@router.put("/candidates/{candidate_id}/offer", response_model=CandidateOfferDraftOut)
def put_candidate_offer(
    candidate_id: str,
    body: CandidateOfferDraftIn,
    db: Session = Depends(get_db),
) -> CandidateOfferDraftOut:
    from uuid import UUID

    from app.services.offer_draft import save_offer_draft

    try:
        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    draft = save_offer_draft(db, candidate, body.model_dump(exclude_unset=True))
    return _offer_out(db, candidate, draft)


@router.post("/candidates/{candidate_id}/offer/prefill", response_model=CandidateOfferDraftOut)
def prefill_candidate_offer(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> CandidateOfferDraftOut:
    from uuid import UUID

    from app.services.offer_draft import prefill_offer_draft, save_offer_draft

    try:
        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    draft = prefill_offer_draft(db, candidate)
    draft = save_offer_draft(db, candidate, draft)
    return _offer_out(db, candidate, draft)


@router.post("/candidates/{candidate_id}/offer/ai-fill", response_model=CandidateOfferDraftOut)
def ai_fill_candidate_offer(
    candidate_id: str,
    db: Session = Depends(get_db),
) -> CandidateOfferDraftOut:
    from uuid import UUID

    from app.services.offer_draft import ai_fill_offer_fields

    try:
        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    try:
        draft = ai_fill_offer_fields(db, candidate, settings=get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось дописать оффер ИИ: {exc}",
        ) from exc
    return _offer_out(db, candidate, draft)


@router.patch("/clients/{client_id}/offer-branding", response_model=ClientOut)
def patch_client_offer_branding(
    client_id: int,
    body: CompanyOfferLogoIn,
    db: Session = Depends(get_db),
) -> ClientOut:
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.tenancy import get_client_or_404

    client = get_client_or_404(db, client_id)
    payload = dict(client.payload or {})
    data = body.model_dump(exclude_unset=True)
    if "logo_data_url" in data:
        logo = data.get("logo_data_url")
        if logo is None or str(logo).strip() == "":
            payload.pop("offer_logo_data_url", None)
        else:
            s = str(logo).strip()
            if len(s) > 2_000_000:
                raise HTTPException(status_code=400, detail="Логотип слишком большой (макс. ~1.5 МБ)")
            if not s.startswith("data:image/"):
                raise HTTPException(status_code=400, detail="Нужен data URL изображения")
            payload["offer_logo_data_url"] = s
    if "office_address" in data and data.get("office_address") is not None:
        payload["office_address"] = str(data.get("office_address") or "").strip()
    if "offer_manager_name" in data and data.get("offer_manager_name") is not None:
        payload["offer_manager_name"] = str(data.get("offer_manager_name") or "").strip()
    if "default_work_schedule" in data and data.get("default_work_schedule") is not None:
        payload["default_work_schedule"] = str(data.get("default_work_schedule") or "").strip()
    client.payload = payload
    flag_modified(client, "payload")
    db.add(client)
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


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
    candidate = get_candidate_or_404(db, cid)
    data = body.model_dump(exclude_unset=True)
    from app.core.auth import user_is_platform_owner
    from app.services.tenancy import current_user

    user = current_user()
    if not user or not user_is_platform_owner(user):
        data.pop("resume_preview_included", None)
        data.pop("resume_preview_visible", None)
    name = data.pop("name", None)
    if "liked" in data:
        from datetime import datetime, timezone

        if data["liked"]:
            data["liked_at"] = datetime.now(timezone.utc).astimezone().isoformat()
        else:
            data["liked_at"] = ""
    if "talent_reserve" in data:
        from datetime import datetime, timezone

        if data["talent_reserve"]:
            data["talent_reserve_at"] = datetime.now(timezone.utc).astimezone().isoformat()
            data["talent_reserve_by"] = (
                (user.email or user.full_name or "").strip() if user else ""
            )
    from app.services.messaging.ops import refresh_candidate_telegram, snapshot_card_payload

    from app.services.tenancy import require_org_id

    before = snapshot_card_payload(candidate)
    force_dup = data.pop("force_duplicate", False)

    if not force_dup and any(k in data for k in ("phone", "email")):
        from app.services.person_match import check_duplicates

        dups = check_duplicates(
            db,
            org_id=require_org_id(),
            phone=data.get("phone") or str((candidate.payload or {}).get("phone") or ""),
            email=data.get("email") or str((candidate.payload or {}).get("email") or ""),
            name=name or candidate.name,
            exclude_candidate_id=candidate.id,
        )
        if dups["hard"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate_hard",
                    "duplicates": {
                        "hard": [vars(h) for h in dups["hard"]],
                        "soft": [vars(s) for s in dups["soft"]],
                    },
                },
            )

    patch_candidate(candidate, name=name, fields=data, db=db, org_id=require_org_id())
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
    candidate = get_candidate_or_404(db, cid)
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
    candidate = get_candidate_or_404(db, cid)
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
    body: CandidateCopyIn,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from app.services.candidate_copy import copy_candidate_to_vacancy

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    target_id = int(body.target_vacancy_id)
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
    candidate = get_candidate_or_404(db, cid)
    delete_candidate(db, candidate)
    return None

@router.post("/candidates/{candidate_id}/attach-resume", response_model=CandidateDetail)
async def attach_resume_to_candidate_endpoint(
    candidate_id: str,
    file: UploadFile | None = File(default=None),
    resume_link: str = Form(default=""),
    db: Session = Depends(get_db),
) -> CandidateDetail:
    """Attach a resume file or PDF URL to an existing candidate (no new card)."""
    from app.services.candidate_resume_eval import attach_resume_to_candidate

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    raw = await file.read() if file and file.filename else b""
    filename = (file.filename or "").strip() if file else ""
    try:
        cand = attach_resume_to_candidate(
            db,
            candidate,
            filename=filename or None,
            content=raw or None,
            resume_link=resume_link,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _candidate_detail(db, cand)


@router.post(
    "/candidates/{candidate_id}/evaluate-resume",
    response_model=JobCreateOut,
    status_code=202,
)
async def evaluate_candidate_resume_endpoint(
    candidate_id: str,
    body: EvaluateResumeIn = Body(default_factory=EvaluateResumeIn),
    db: Session = Depends(get_db),
) -> JobCreateOut:
    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    existing = job_svc.find_active_job_for_candidate(
        db,
        job_type="candidate_evaluate_resume",
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
        job_type="candidate_evaluate_resume",
        vacancy_id=candidate.vacancy_id,
        payload={
            "candidate_id": str(candidate.id),
            "candidate_name": candidate.name,
            "skip_questionnaire": bool(body.skip_questionnaire),
        },
    )
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job("candidate_evaluate_resume", str(job.id), _job_id=str(job.id))
    except Exception as exc:  # noqa: BLE001
        job_svc.update_job(
            db,
            job.id,
            status="failed",
            progress_label="Не удалось поставить в очередь",
            error=str(exc),
        )
        raise HTTPException(status_code=503, detail=f"Redis/ARQ unavailable: {exc}") from exc
    return JobCreateOut(
        id=job.id,
        status=job.status,
        job_type=job.job_type,
        progress_label=job.progress_label
        or (
            "Оценка резюме в очереди (без опросника)"
            if body.skip_questionnaire
            else "Оценка резюме в очереди"
        ),
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
    candidate = get_candidate_or_404(db, cid)
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
    candidate = get_candidate_or_404(db, cid)
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
    candidate = get_candidate_or_404(db, cid)
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
    candidate = get_candidate_or_404(db, cid)
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
    candidate = get_candidate_or_404(db, cid)
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
    candidate = get_candidate_or_404(db, cid)
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
    candidate = get_candidate_or_404(db, cid)
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

@router.post(
    "/candidates/{candidate_id}/send-to-chat",
    response_model=CandidateSendToChatOut,
)
def send_candidate_to_chat(
    candidate_id: str,
    body: CandidateSendToChatIn | None = None,
    db: Session = Depends(get_db),
) -> CandidateSendToChatOut:
    from app.services.messaging.gateway import MessagingError, send_candidate_to_client

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    opts = body or CandidateSendToChatIn()
    try:
        result = send_candidate_to_client(
            db,
            candidate,
            move_to_client_review=opts.move_to_client_review,
        )
    except MessagingError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.refresh(candidate)
    return CandidateSendToChatOut(
        ok=bool(result.get("ok", True)),
        message=str(result.get("message") or ""),
        post_id=str(result.get("post_id") or ""),
        external_message_id=str(result.get("external_message_id") or ""),
        channel_id=str(result.get("channel_id") or ""),
        chat_id=str(result.get("chat_id") or ""),
        stage_changed=bool(result.get("stage_changed")),
        hr_stage=str(result.get("hr_stage") or candidate.hr_stage),
        results=list(result.get("results") or []),
        errors=list(result.get("errors") or []),
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
    candidate = get_candidate_or_404(db, cid)
    ok, msg = send_manual_reminder(db, candidate, kind=kind if kind in ("evaluate", "decide") else "evaluate")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}

@router.post("/candidates/{candidate_id}/extra-material")
def send_candidate_extra_material(
    candidate_id: str,
    body: ExtraMaterialIn,
    db: Session = Depends(get_db),
) -> dict:
    from app.services.messaging.ops import send_extra_material

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    ok, msg = send_extra_material(
        db,
        candidate,
        title=str(body.title or "Материал"),
        url=str(body.url or ""),
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
    candidate = get_candidate_or_404(db, cid)
    ok, msg = refresh_candidate_telegram(db, candidate, notify=notify)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}

@router.post("/candidates/{candidate_id}/zoom-meeting", response_model=CandidateDetail)
def schedule_candidate_zoom_meeting(
    candidate_id: str,
    body: ZoomMeetingScheduleIn,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from app.services.zoom_meetings import ZoomMeetingError, schedule_zoom_for_candidate

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    try:
        schedule_zoom_for_candidate(
            db,
            candidate,
            start_date=str(body.start_date or ""),
            start_time=str(body.start_time or ""),
            duration_minutes=int(body.duration_minutes or 60),
        )
    except ZoomMeetingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.refresh(candidate)
    return _candidate_detail(db, candidate)


@router.post("/candidates/{candidate_id}/confirm-meeting", response_model=CandidateDetail)
def confirm_candidate_meeting(candidate_id: str, db: Session = Depends(get_db)) -> CandidateDetail:
    from app.services.messaging.attendance import set_meeting_hr_confirmed

    try:
        from uuid import UUID

        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    p = candidate.payload or {}
    if not str(p.get("office_interview_date") or "").strip() or not str(p.get("office_interview_time") or "").strip():
        raise HTTPException(status_code=400, detail="Встреча не назначена")
    set_meeting_hr_confirmed(candidate, True)
    try:
        from app.services.bitrix.task_sync import sync_meeting_task_hr_status

        sync_meeting_task_hr_status(db, candidate, confirmed=True)
    except Exception:  # noqa: BLE001
        pass
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _candidate_detail(db, candidate)

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
    get_candidate_or_404(db, cid)
    return [MessagingPostOut.model_validate(p) for p in list_candidate_posts(db, cid)]


# --- YAKOR PR2: stage durations + tags + segments ---

from app.schemas import (
    CandidateTagsPatchIn,
    SegmentCopyIn,
    SegmentIn,
    SegmentOut,
    StageDurationsOut,
    StageDurationSummary,
    TagsListOut,
)


@router.get("/stats/stage-durations", response_model=StageDurationsOut)
def stage_durations_endpoint(
    vacancy_id: int | None = Query(default=None),
    client_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StageDurationsOut:
    from app.services.stage_duration import aggregate_stage_timing, stale_candidates
    from app.services.tenancy import require_org_id

    org_id = require_org_id()
    summary = aggregate_stage_timing(
        db, organization_id=org_id, vacancy_id=vacancy_id, client_id=client_id,
    )
    stale = stale_candidates(db, organization_id=org_id, vacancy_id=vacancy_id)
    return StageDurationsOut(
        summary=[StageDurationSummary(**s) for s in summary],
        stale=stale,
    )


@router.get("/tags", response_model=TagsListOut)
def list_tags_endpoint(
    q: str = Query(default=""),
    db: Session = Depends(get_db),
) -> TagsListOut:
    from app.services.tenancy import require_org_id

    org_id = require_org_id()
    query = select(models.OrganizationTag.tag).where(
        models.OrganizationTag.organization_id == org_id,
    ).order_by(models.OrganizationTag.usage_count.desc())
    if q:
        query = query.where(models.OrganizationTag.tag.ilike(f"%{q}%"))
    tags = list(db.scalars(query).all())
    return TagsListOut(tags=tags)


@router.patch("/candidates/{candidate_id}/tags", response_model=CandidateDetail)
def patch_candidate_tags(
    candidate_id: str,
    body: CandidateTagsPatchIn,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from uuid import UUID
    from sqlalchemy.orm.attributes import flag_modified
    from app.services.tenancy import require_org_id

    try:
        cid = UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    candidate = get_candidate_or_404(db, cid)
    org_id = require_org_id()

    new_tags = sorted(set(t.strip() for t in body.tags if t.strip()))
    old_tags = set(candidate.tags or [])
    candidate.tags = new_tags
    flag_modified(candidate, "tags")

    # Update person tags (union)
    if candidate.person_id:
        person = db.get(models.Person, candidate.person_id)
        if person:
            person_tags = set(person.tags or [])
            person_tags.update(new_tags)
            person.tags = sorted(person_tags)
            flag_modified(person, "tags")

    # Update org tag counters
    added = set(new_tags) - old_tags
    removed = old_tags - set(new_tags)
    for tag in added:
        existing = db.get(models.OrganizationTag, (org_id, tag))
        if existing:
            existing.usage_count = (existing.usage_count or 0) + 1
        else:
            db.add(models.OrganizationTag(organization_id=org_id, tag=tag, usage_count=1))
    for tag in removed:
        existing = db.get(models.OrganizationTag, (org_id, tag))
        if existing:
            existing.usage_count = max(0, (existing.usage_count or 0) - 1)

    db.commit()
    db.refresh(candidate)
    return _candidate_detail(db, candidate)


@router.get("/candidate-segments", response_model=list[SegmentOut])
def list_segments(db: Session = Depends(get_db)) -> list[SegmentOut]:
    from app.services.tenancy import current_user, require_org_id

    org_id = require_org_id()
    user = current_user()
    q = select(models.CandidateSegment).where(
        models.CandidateSegment.organization_id == org_id,
    )
    if user:
        q = q.where(models.CandidateSegment.user_id == user.id)
    return [SegmentOut.model_validate(s) for s in db.scalars(q).all()]


@router.post("/candidate-segments", response_model=SegmentOut, status_code=201)
def create_segment(body: SegmentIn, db: Session = Depends(get_db)) -> SegmentOut:
    from app.services.tenancy import current_user, require_org_id
    import uuid

    org_id = require_org_id()
    user = current_user()
    if not user:
        raise HTTPException(status_code=401, detail="Auth required")

    seg = models.CandidateSegment(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=user.id,
        name=body.name,
        filter=body.filter,
        scope=body.scope,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return SegmentOut.model_validate(seg)


@router.delete("/candidate-segments/{segment_id}", status_code=204)
def delete_segment(segment_id: str, db: Session = Depends(get_db)) -> None:
    from uuid import UUID
    try:
        sid = UUID(segment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid segment id") from exc
    seg = db.get(models.CandidateSegment, sid)
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    db.delete(seg)
    db.commit()

