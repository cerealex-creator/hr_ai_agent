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
from app.core.auth import AuthUser, require_auth, require_platform_owner
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
    OfferTemplateInfoOut,
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

@router.get("/settings/test-chat", response_model=TestChatOut)
def get_test_chat(db: Session = Depends(get_db)) -> TestChatOut:
    from app.services import clients_write as cw
    from app.services.tenancy import is_demo_user

    if is_demo_user():
        return TestChatOut()
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

@router.get("/settings/app")
def get_settings_app(
    user: AuthUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    from app.core.auth import user_is_platform_owner
    from app.services.app_settings import get_app_settings
    from app.services.candidate_intake import (
        DEFAULT_CANDIDATE_INTAKE,
        effective_candidate_intake,
        get_user_candidate_intake,
        normalize_candidate_intake,
    )

    if user.is_demo:
        stored = normalize_candidate_intake(DEFAULT_CANDIDATE_INTAKE)
        return {
            "default_warranty_months": 3,
            "ai_model": "",
            "ai_provider": {},
            "provider_links": [],
            "candidate_comms": {},
            "functions": {},
            "client_notify": {},
            "messaging_providers": [],
            "bitrix": {"enabled": False, "decide_secret_set": False, "decide_secret": ""},
            "yandex_disk_root": "",
            "yandex_disk_inbox": "",
            "yandex_disk_client_id": "",
            "path": "",
            "candidate_intake": stored,
            "candidate_intake_effective": effective_candidate_intake(
                is_owner=False, stored=stored
            ),
            "is_platform_owner": False,
        }

    out = get_app_settings()
    owner = user_is_platform_owner(user)
    if user.auth_disabled:
        stored = normalize_candidate_intake(DEFAULT_CANDIDATE_INTAKE)
    else:
        try:
            stored = get_user_candidate_intake(db, user.id)
        except LookupError:
            stored = normalize_candidate_intake(None)
    out["candidate_intake"] = stored
    out["candidate_intake_effective"] = effective_candidate_intake(
        is_owner=owner, stored=stored
    )
    out["is_platform_owner"] = owner
    return out


@router.patch("/settings/app")
def patch_settings_app(
    body: AppSettingsPatchIn,
    user: AuthUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    from app.core.auth import user_is_platform_owner
    from app.services.app_settings import (
        get_app_settings,
        set_ai_provider,
        set_bitrix,
        set_candidate_comms,
        set_client_notify,
        set_default_warranty_months,
        set_provider_links,
        set_functions,
    )
    from app.services.candidate_intake import (
        DEFAULT_CANDIDATE_INTAKE,
        effective_candidate_intake,
        get_user_candidate_intake,
        normalize_candidate_intake,
        set_user_candidate_intake,
    )
    from app.services.yandex_disk_oauth import set_disk_client_id, set_disk_paths

    data = body.model_dump(exclude_unset=True)
    owner_keys = {
        "default_warranty_months",
        "ai_provider",
        "ai_model",
        "provider_links",
        "functions",
    }
    if any(k in data for k in owner_keys) and not user_is_platform_owner(user):
        raise HTTPException(
            status_code=403,
            detail="Изменение системных настроек доступно только platform_owner",
        )

    if "default_warranty_months" in data:
        try:
            set_default_warranty_months(int(data["default_warranty_months"]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "ai_provider" in data and isinstance(data.get("ai_provider"), dict):
        set_ai_provider(data["ai_provider"])
    elif "ai_model" in data:
        set_ai_provider({"model": data.get("ai_model")})
    if "provider_links" in data and isinstance(data.get("provider_links"), list):
        set_provider_links(data["provider_links"])
    if "candidate_comms" in data and isinstance(data.get("candidate_comms"), dict):
        set_candidate_comms(data["candidate_comms"])
    if "candidate_intake" in data and isinstance(data.get("candidate_intake"), dict):
        if user.auth_disabled:
            raise HTTPException(
                status_code=400,
                detail="При AUTH_DISABLED личные каналы intake не сохраняются в БД",
            )
        try:
            set_user_candidate_intake(db, user.id, data.get("candidate_intake") or {})
            db.commit()
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
    if "yandex_disk_root" in data or "yandex_disk_inbox" in data:
        set_disk_paths(
            root=data.get("yandex_disk_root") if "yandex_disk_root" in data else None,
            inbox_name=data.get("yandex_disk_inbox") if "yandex_disk_inbox" in data else None,
        )
    if "yandex_disk_client_id" in data:
        set_disk_client_id(str(data.get("yandex_disk_client_id") or ""))
    if "functions" in data and isinstance(data.get("functions"), dict):
        set_functions(data.get("functions") or {})
    if "client_notify" in data and isinstance(data.get("client_notify"), dict):
        set_client_notify(data.get("client_notify") or {})
    if "bitrix" in data and isinstance(data.get("bitrix"), dict):
        set_bitrix(data.get("bitrix") or {})
    out = get_app_settings()
    owner = user_is_platform_owner(user)
    if user.auth_disabled:
        stored = normalize_candidate_intake(DEFAULT_CANDIDATE_INTAKE)
    else:
        try:
            stored = get_user_candidate_intake(db, user.id)
        except LookupError:
            stored = normalize_candidate_intake(None)
    out["candidate_intake"] = stored
    out["candidate_intake_effective"] = effective_candidate_intake(
        is_owner=owner, stored=stored
    )
    out["is_platform_owner"] = owner
    return out


@router.get("/settings/offer-template", response_model=OfferTemplateInfoOut)
def get_offer_template_info(_user: AuthUser = Depends(require_auth)) -> OfferTemplateInfoOut:
    from app.services.offer_docx import offer_template_info

    return OfferTemplateInfoOut.model_validate(offer_template_info())


@router.post("/settings/offer-template", response_model=OfferTemplateInfoOut)
async def upload_offer_template(
    file: UploadFile = File(...),
    _user: AuthUser = Depends(require_platform_owner),
) -> OfferTemplateInfoOut:
    from app.services.offer_docx import offer_template_info, save_custom_offer_template

    raw = await file.read()
    try:
        save_custom_offer_template(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OfferTemplateInfoOut.model_validate(offer_template_info())


@router.delete("/settings/offer-template", response_model=OfferTemplateInfoOut)
def delete_offer_template(_user: AuthUser = Depends(require_platform_owner)) -> OfferTemplateInfoOut:
    from app.services.offer_docx import clear_custom_offer_template, offer_template_info

    clear_custom_offer_template()
    return OfferTemplateInfoOut.model_validate(offer_template_info())


@router.post("/settings/bitrix/test-task")
def bitrix_test_task(_user: AuthUser = Depends(require_platform_owner)) -> dict:
    """Smoke: create a minimal Bitrix task with current settings."""
    from app.services.bitrix.client import BitrixError
    from app.services.bitrix.outbound import send_bitrix_smoke_task

    try:
        return send_bitrix_smoke_task()
    except BitrixError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

