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

@router.get("/vacancies/{vacancy_id}/hh-search-defaults")
def vacancy_hh_search_defaults(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.hh_preset import (
        form_options,
        preset_from_vacancy_documents,
        save_preset_to_documents,
        warnings_for_preset,
    )
    from app.services.hh_search_plan import get_plan_from_vacancy, mark_plan_stale_if_needed
    from sqlalchemy.orm.attributes import flag_modified

    vacancy = get_vacancy_or_404(db, vacancy_id)
    if mark_plan_stale_if_needed(vacancy):
        db.commit()
        db.refresh(vacancy)
    criteria = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    preset = preset_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    # Persist migration so UI and worker share one SoT
    if not isinstance((vacancy.documents or {}).get("hh_preset"), dict):
        vacancy.documents = save_preset_to_documents(vacancy.documents, preset)
        flag_modified(vacancy, "documents")
        db.add(vacancy)
        db.commit()
        db.refresh(vacancy)
    return {
        "vacancy_id": vacancy.id,
        "title": vacancy.title,
        "criteria": criteria,
        "preset": preset,
        "plan": get_plan_from_vacancy(vacancy),
        "warnings": warnings_for_preset(preset),
        "needs_prefill": needs_ai_prefill(vacancy.documents),
        "schedule_options": SCHEDULE_OPTIONS,
        "area_presets": AREA_PRESETS,
        "form_options": form_options(),
        "keywords": criteria.get("keywords") or "",
        "max_search_default": preset["run"].get("max_search") or 40,
        "max_evaluate_default": preset["run"].get("max_evaluate") or 15,
    }

@router.get("/vacancies/{vacancy_id}/hh-preset")
def get_hh_preset(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.hh_preset import (
        form_options,
        preset_from_vacancy_documents,
        save_preset_to_documents,
        warnings_for_preset,
    )
    from sqlalchemy.orm.attributes import flag_modified

    vacancy = get_vacancy_or_404(db, vacancy_id)
    preset = preset_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    if not isinstance((vacancy.documents or {}).get("hh_preset"), dict):
        vacancy.documents = save_preset_to_documents(vacancy.documents, preset)
        flag_modified(vacancy, "documents")
        db.add(vacancy)
        db.commit()
        db.refresh(vacancy)
    return {
        "vacancy_id": vacancy.id,
        "preset": preset,
        "warnings": warnings_for_preset(preset),
        "form_options": form_options(),
    }

@router.put("/vacancies/{vacancy_id}/hh-preset")
def upsert_hh_preset(
    vacancy_id: int,
    body: HhPresetIn,
    db: Session = Depends(get_db),
) -> dict:
    from app.services.hh_preset import (
        approve_preset,
        ensure_soft_portrait,
        form_options,
        normalize_preset,
        save_preset_to_documents,
        warnings_for_preset,
    )
    from sqlalchemy.orm.attributes import flag_modified

    vacancy = get_vacancy_or_404(db, vacancy_id)
    preset = ensure_soft_portrait(normalize_preset(body.preset), rebuild=body.rebuild_portrait)
    if body.approve:
        try:
            preset = approve_preset(preset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    vacancy.documents = save_preset_to_documents(vacancy.documents, preset)
    flag_modified(vacancy, "documents")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return {
        "vacancy_id": vacancy.id,
        "preset": preset,
        "warnings": warnings_for_preset(preset),
        "form_options": form_options(),
    }

@router.get("/vacancies/{vacancy_id}/hh-search-plan")
def get_hh_search_plan(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.hh_search_plan import get_plan_from_vacancy, mark_plan_stale_if_needed

    vacancy = get_vacancy_or_404(db, vacancy_id)
    if mark_plan_stale_if_needed(vacancy):
        db.commit()
        db.refresh(vacancy)
    return {"vacancy_id": vacancy.id, "plan": get_plan_from_vacancy(vacancy)}

@router.post("/vacancies/{vacancy_id}/hh-search-plan/generate")
def generate_hh_search_plan(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.hh_search_plan import generate_plan

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        plan = generate_plan(db, vacancy, settings=get_settings())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"vacancy_id": vacancy.id, "plan": plan}

@router.post("/vacancies/{vacancy_id}/hh-search-plan/revise")
def revise_hh_search_plan(vacancy_id: int, body: HhSearchPlanReviseIn, db: Session = Depends(get_db)) -> dict:
    from app.services.hh_search_plan import revise_plan

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        plan = revise_plan(db, vacancy, str(body.note or ""), settings=get_settings())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"vacancy_id": vacancy.id, "plan": plan}

@router.post("/vacancies/{vacancy_id}/hh-search-plan/approve")
def approve_hh_search_plan(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.hh_search_plan import approve_plan

    vacancy = get_vacancy_or_404(db, vacancy_id)
    try:
        result = approve_plan(db, vacancy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "vacancy_id": vacancy.id,
        "plan": result["plan"],
        "criteria": result["criteria"],
        "warnings": warnings_for(result["criteria"]),
    }

@router.post("/vacancies/{vacancy_id}/hh-search-criteria/prefill")
def prefill_hh_search_criteria(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    vacancy = get_vacancy_or_404(db, vacancy_id)
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
    vacancy = get_vacancy_or_404(db, vacancy_id)
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
    vacancy = get_vacancy_or_404(db, vacancy_id)
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
    vacancy = get_vacancy_or_404(db, vacancy_id)
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
def hh_manual_evaluate(vacancy_id: int, body: HhManualEvaluateIn, db: Session = Depends(get_db)) -> dict:
    """Evaluate recruiter-provided HH resume URLs/ids; return comparison rows."""
    from app.services.hh_manual_eval import evaluate_manual_hh_resumes

    vacancy = get_vacancy_or_404(db, vacancy_id)
    text = str(body.text or body.refs or "").strip()
    criteria = body.criteria if isinstance(body.criteria, dict) else None
    try:
        return evaluate_manual_hh_resumes(db, vacancy, text, criteria=criteria)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@router.post("/vacancies/{vacancy_id}/hh-soften-suggestions")
def hh_soften_suggestions(vacancy_id: int, body: HhSoftenSuggestionsIn, db: Session = Depends(get_db)) -> dict:
    """AI checklist: what filters/requirements to soften after search or good resumes."""
    from app.services.hh_manual_eval import suggest_criteria_softening
    from app.services.hh_search_criteria import criteria_from_vacancy_documents, normalize_criteria

    vacancy = get_vacancy_or_404(db, vacancy_id)
    criteria = body.criteria if isinstance(body.criteria, dict) else None
    if not criteria:
        criteria = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    criteria = normalize_criteria(criteria)
    search_results = body.search_results if isinstance(body.search_results, list) else None
    good_resumes = body.good_resumes if isinstance(body.good_resumes, list) else None
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
def hh_soften_apply(vacancy_id: int, body: HhSoftenApplyIn, db: Session = Depends(get_db)) -> dict:
    """Apply selected soften suggestions; optionally persist into vacancy documents."""
    from app.services.hh_manual_eval import apply_soften_suggestions
    from app.services.hh_search_criteria import (
        DOC_KEY,
        criteria_from_vacancy_documents,
        normalize_criteria,
        warnings_for,
    )

    vacancy = get_vacancy_or_404(db, vacancy_id)
    criteria = body.criteria if isinstance(body.criteria, dict) else None
    if not criteria:
        criteria = criteria_from_vacancy_documents(vacancy.documents, title=vacancy.title)
    suggestions = body.suggestions if isinstance(body.suggestions, list) else []
    selected_ids = body.selected_ids if isinstance(body.selected_ids, list) else []
    next_c = apply_soften_suggestions(criteria, suggestions, [str(x) for x in selected_ids])
    persist = bool(body.persist)
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

    vacancy = get_vacancy_or_404(db, vacancy_id)
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
    vacancy = get_vacancy_or_404(db, vacancy_id)
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

    vacancy = get_vacancy_or_404(db, vacancy_id)
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

    vacancy = get_vacancy_or_404(db, vacancy_id)
    if not delete_seen(db, vacancy_id, hh_resume_id):
        raise HTTPException(status_code=404, detail="Not found")
    return None

@router.get("/vacancies/{vacancy_id}/hh-search-history", response_model=JobHistoryListOut)
def hh_search_history(
    vacancy_id: int,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> JobHistoryListOut:
    vacancy = get_vacancy_or_404(db, vacancy_id)
    rows = job_svc.list_jobs(
        db, limit=limit, vacancy_id=vacancy_id, job_type="hh_cold_search"
    )
    return JobHistoryListOut(
        items=[JobHistoryItemOut(**job_svc.job_history_summary(r)) for r in rows]
    )

@router.post("/vacancies/{vacancy_id}/hh-search-history/cleanup")
def cleanup_hh_search_history(vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    """Remove failed/cancelled/stuck-queued HH searches from DB."""
    vacancy = get_vacancy_or_404(db, vacancy_id)
    deleted = job_svc.delete_hh_jobs(db, vacancy_id=vacancy_id, only_problematic=True)
    return {"deleted": deleted}

