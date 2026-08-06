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
def messaging_test_message(body: MessagingTestMessageIn, db: Session = Depends(get_db)) -> dict:
    from app.services.messaging.telegram_provider import send_html_message

    chat_id = str(body.chat_id or "").strip()
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id required")
    text = str(body.text or "Тестовое сообщение от HR AI Agent v2").strip()
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

@router.post("/messaging/send-instruction")
def messaging_send_instruction(body: MessagingTestMessageIn, db: Session = Depends(get_db)) -> dict:
    from app.services.messaging.ops import send_client_instruction

    chat_id = str(body.chat_id or "").strip()
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id required")
    ok, msg = send_client_instruction(db, chat_id, body.text)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}

