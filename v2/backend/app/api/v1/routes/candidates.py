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
    candidate = get_candidate_or_404(db, cid)
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

