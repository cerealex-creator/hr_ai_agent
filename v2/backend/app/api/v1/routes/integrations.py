"""v1 API routes (split from endpoints.py — audit M6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, require_auth, require_platform_owner
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
    require_intake_channel,
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
    ZoomOAuthCompleteIn,
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
public_router = APIRouter()


@router.get("/integrations/yandex-disk/status")
def yandex_disk_oauth_status() -> dict:
    from app.services.tenancy import is_demo_user
    from app.services.yandex_disk_oauth import disk_status

    if is_demo_user():
        return {
            "connected": False,
            "token_path": "",
            "token_from_env": False,
            "client_id": "",
            "client_id_configured": False,
            "authorize_url": None,
            "create_app_url": "",
            "root": "",
            "inbox_path": "",
            "login": None,
            "message": "В демо Диск не подключается",
        }
    return disk_status()

@router.post("/integrations/yandex-disk/token")
def yandex_disk_save_token(body: OauthTokenIn) -> dict:
    from app.services.yandex_disk_oauth import DiskApiError, disk_status, ensure_app_root, save_disk_token

    token = str(body.token or body.access_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token обязателен")
    save_disk_token(token)
    try:
        ensure_app_root(token)
    except DiskApiError as exc:
        return {**disk_status(), "warning": str(exc)}
    return disk_status()

@router.delete("/integrations/yandex-disk/token")
def yandex_disk_clear_token() -> dict:
    from app.services.yandex_disk_oauth import clear_disk_token, disk_status

    clear_disk_token()
    return disk_status()


@router.post("/integrations/yandex-disk/disconnect")
def yandex_disk_disconnect() -> dict:
    """Clear local Disk settings (token, client id, paths). Does not delete remote folders."""
    from app.services.yandex_disk_oauth import reset_disk_connection

    return reset_disk_connection()


@router.post("/integrations/yandex-disk/ensure-root")
def yandex_disk_ensure_root() -> dict:
    from app.services.yandex_disk_oauth import DiskApiError, ensure_app_root

    try:
        return ensure_app_root()
    except DiskApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/integrations/yandex-disk/inbox")
def yandex_disk_inbox(db: Session = Depends(get_db)) -> dict:
    from app.services.disk_inbox_router import inbox_settings, list_inbox_db
    from app.services.tenancy import is_demo_user
    from app.services.yandex_disk_oauth import DiskApiError, suggest_inbox_routes

    if is_demo_user():
        return {
            "items": [],
            "message": "В демо Диск не подключается",
            "inbox_path": "",
            "db_items": [],
            "unsorted": [],
            "settings": {"auto": False, "confidence": 0.75, "evaluate_on_route": False},
        }
    try:
        live = suggest_inbox_routes(db)
    except DiskApiError as exc:
        live = {"items": [], "message": str(exc), "inbox_path": ""}
    return {
        **live,
        "db_items": list_inbox_db(db, limit=80),
        "unsorted": list_inbox_db(db, status="unsorted", limit=50),
        "settings": inbox_settings(),
    }

@router.post("/integrations/yandex-disk/inbox/process")
def yandex_disk_inbox_process(body: InboxProcessIn | None = None, db: Session = Depends(get_db)) -> dict:
    from app.services.disk_inbox_router import process_inbox
    from app.services.yandex_disk_oauth import DiskApiError

    require_intake_channel("disk_inbox")
    body = body or InboxProcessIn()
    try:
        return process_inbox(db, limit=int(body.limit or 20))
    except (DiskApiError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/integrations/yandex-disk/inbox/{item_id}/bind")
def yandex_disk_inbox_bind(item_id: str, body: InboxBindIn, db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    from app.services.disk_inbox_router import bind_unsorted
    from app.services.yandex_disk_oauth import DiskApiError

    require_intake_channel("disk_inbox")
    try:
        iid = UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid id") from exc
    try:
        return bind_unsorted(db, iid, int(body.vacancy_id))
    except (DiskApiError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.patch("/integrations/yandex-disk/inbox/settings")
def yandex_disk_inbox_settings_patch(body: InboxSettingsPatchIn) -> dict:
    from app.services.disk_inbox_router import set_inbox_settings

    data = body.model_dump(exclude_unset=True)
    conf = data.get("confidence")
    return set_inbox_settings(
        auto=data.get("auto") if "auto" in data else None,
        confidence=float(conf) if conf is not None else None,
        evaluate_on_route=data.get("evaluate_on_route") if "evaluate_on_route" in data else None,
    )

@router.get("/integrations/google-calendar/status")
def google_calendar_status(user: AuthUser = Depends(require_auth)) -> dict:
    from app.core.auth import user_is_platform_owner
    from app.services.google_calendar import (
        get_calendar_status,
        get_credentials_path,
        get_token_path,
    )

    if user.is_demo:
        return {
            "status": "demo",
            "message": "В демо календарь не подключается",
            "credentials_path": "",
            "token_path": "",
        }
    status, message = get_calendar_status()
    out = {
        "status": status,
        "message": message,
        "credentials_path": "",
        "token_path": "",
    }
    if user_is_platform_owner(user):
        out["credentials_path"] = get_credentials_path()
        out["token_path"] = get_token_path()
    return out

@router.post("/integrations/google-calendar/oauth/start")
def google_calendar_oauth_start() -> dict:
    from app.services.google_calendar import oauth_auth_url

    ok, msg, url = oauth_auth_url()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg, "auth_url": url}

@router.post("/integrations/google-calendar/oauth/complete")
def google_calendar_oauth_complete(body: GoogleOAuthCompleteIn) -> dict:
    from app.services.google_calendar import oauth_complete_with_code

    ok, msg = oauth_complete_with_code(str(body.code or ""))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.get("/integrations/zoom/status")
def zoom_status(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_platform_owner),
) -> dict:
    from app.services.zoom_oauth import get_redirect_uri, get_zoom_status, legacy_token_path

    status, message = get_zoom_status(db, user.org_id)
    return {
        "status": status,
        "message": message,
        "redirect_uri": get_redirect_uri(),
        "scope": "organization",
        "org_id": str(user.org_id),
        # diagnostics only — tokens live in organizations.integrations
        "legacy_token_path": legacy_token_path(),
    }


@router.post("/integrations/zoom/oauth/start")
def zoom_oauth_start(_user: AuthUser = Depends(require_platform_owner)) -> dict:
    from app.services.zoom_oauth import oauth_auth_url

    ok, msg, url = oauth_auth_url()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg, "auth_url": url}


@router.post("/integrations/zoom/oauth/complete")
def zoom_oauth_complete(
    body: ZoomOAuthCompleteIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_platform_owner),
) -> dict:
    from app.services.zoom_oauth import oauth_complete_with_code

    ok, msg = oauth_complete_with_code(db, user.org_id, str(body.code or ""))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@public_router.post("/integrations/{provider}/webhook", response_model=WebhookAckOut)
async def integrations_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
) -> WebhookAckOut:
    """Telegram / Bitrix webhook. Telegram no-op while MESSAGING_INBOUND_ENABLED=false."""
    from app.core.config import get_settings
    from app.services.messaging.gateway import parse_inbound_webhook

    settings = get_settings()
    payload = await _parse_webhook_payload(request)
    events = parse_inbound_webhook(provider, payload or {}, db=db)
    handled = any(bool(e.get("handled")) for e in events)
    provider_l = (provider or "").strip().lower()
    if provider_l in ("bitrix", "bitrix24"):
        note = "bitrix inbound"
    elif settings.messaging_inbound_enabled:
        note = "inbound enabled"
    else:
        note = "inbound disabled — Streamlit bot keeps polling until cutover"
    return WebhookAckOut(
        ok=True,
        handled=handled,
        provider=provider,
        events=events,
        note=note,
    )

