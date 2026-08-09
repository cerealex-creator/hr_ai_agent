"""Shared helpers / constants for v1 API routers (audit M6)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
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
        "disk_inbox_router",
        "vacancy_docs_from_materials",
        "vacancy_docs_from_brief",
        "vacancy_docs_generate",
    }
)
ARQ_FUNCTION_BY_TYPE = {
    "demo_progress": "demo_progress",
    "import_legacy": "import_legacy",
    "transcribe_media": "transcribe_media",
    "candidate_interview_process": "candidate_interview_process",
    "hh_cold_search": "hh_cold_search",
    "yandex_disk_sync": "yandex_disk_sync",
    "disk_inbox_router": "disk_inbox_router",
    "vacancy_docs_from_materials": "vacancy_docs_from_materials",
    "vacancy_docs_from_brief": "vacancy_docs_from_brief",
    "vacancy_docs_generate": "vacancy_docs_generate",
}


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


def _channel_out(r: models.MessagingChannel) -> MessagingChannelOut:
    return MessagingChannelOut(
        id=r.id,
        provider=r.provider,
        external_id=r.external_id,
        client_id=r.client_id,
        name=r.name or r.external_id,
        metadata=r.metadata_json or {},
    )


def _nest_form_key(root: dict, key: str, value: str) -> None:
    """Parse Bitrix form keys like data[FIELDS_AFTER][ID] into nested dicts."""
    parts: list[str] = []
    buf = ""
    i = 0
    while i < len(key):
        ch = key[i]
        if ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            i += 1
            inner = ""
            while i < len(key) and key[i] != "]":
                inner += key[i]
                i += 1
            parts.append(inner)
            i += 1  # skip ]
        else:
            buf += ch
            i += 1
    if buf:
        parts.append(buf)
    if not parts:
        return
    cur: dict = root
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


async def _parse_webhook_payload(request: Request) -> dict:
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {"raw": data}
        except Exception:  # noqa: BLE001
            return {}
    form = await request.form()
    out: dict = {}
    for k, v in form.multi_items():
        _nest_form_key(out, str(k), str(v))
    if out:
        return out
    # Empty form — try JSON body anyway
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def require_intake_channel(channel: str) -> None:
    """HTTP 403 if candidate intake channel is off for the current user."""
    from app.core.auth import user_is_platform_owner
    from app.db.session import SessionLocal
    from app.services.candidate_intake import (
        get_user_candidate_intake,
        normalize_candidate_intake,
        require_candidate_intake_channel,
    )
    from app.services.tenancy import require_current_user

    user = require_current_user()
    stored = None
    if not user.auth_disabled:
        db = SessionLocal()
        try:
            stored = get_user_candidate_intake(db, user.id)
        except LookupError:
            stored = normalize_candidate_intake(None)
        finally:
            db.close()
    else:
        stored = normalize_candidate_intake(None)
    try:
        require_candidate_intake_channel(
            channel,
            is_owner=user_is_platform_owner(user),
            stored=stored,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


