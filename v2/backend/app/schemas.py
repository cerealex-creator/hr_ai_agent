from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthOut(BaseModel):
    status: str
    version: str = "v2-mvp"
    database: str


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    parent_id: int | None = None
    chat_mode: str = "company"
    kind: str = "company"


class ClientChannelBrief(BaseModel):
    id: str
    name: str | None = None
    external_id: str


class ClientChannelTreeDeptOut(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: int | None = None
    chat_mode: str
    kind: str
    channel: ClientChannelBrief | None = None
    client_zone_token: str | None = None
    has_client_zone: bool = False


class ClientTreeNodeOut(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: int | None = None
    chat_mode: str
    kind: str
    channel: ClientChannelBrief | None = None
    departments: list[ClientChannelTreeDeptOut] = Field(default_factory=list)
    client_zone_token: str | None = None
    has_client_zone: bool = False


class ClientCreateIn(BaseModel):
    name: str
    chat_mode: str = "company"
    parent_id: int | None = None


class ClientPatchIn(BaseModel):
    name: str | None = None
    chat_mode: str | None = None


class CompanyCreateIn(BaseModel):
    name: str
    chat_mode: str = Field(default="company", description="company | departments")


class DepartmentCreateIn(BaseModel):
    name: str
    chat_name: str | None = None
    chat_id: str | None = None


class TestChatOut(BaseModel):
    client_id: int | None = None
    name: str | None = None
    chat_id: str | None = None
    channel_id: str | None = None


class TestChatIn(BaseModel):
    name: str = "Тестировочный"
    chat_id: str


class CompaniesTreeOut(BaseModel):
    items: list[ClientTreeNodeOut]
    migration: dict = Field(default_factory=dict)

class MessagingChannelCreateIn(BaseModel):
    name: str
    chat_id: str
    client_id: int | None = None
    new_client_name: str | None = None


class MessagingChannelPatchIn(BaseModel):
    name: str | None = None
    chat_id: str | None = None
    client_id: int | None = None
    clear_client: bool = False


class VacancyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    active: bool
    client_id: int | None
    client_name: str | None = None
    chat_id: str | None = None
    candidates_count: int = 0
    created_at: str | None = None
    closed_at: str | None = None
    close_reason: str | None = None
    has_hire: bool = False
    # Soft archive outcome for UI only (not final domain truth)
    outcome: str | None = None  # success | client_cancelled | no_result | None if active
    avatar_key: str | None = None


class VacancyDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    active: bool
    client_id: int | None
    client_name: str | None = None
    chat_id: str | None
    documents: dict
    created_at: str | None
    closed_at: str | None
    close_reason: str | None = None
    has_hire: bool = False
    outcome: str | None = None
    payload: dict
    candidates_count: int = 0
    document_keys: list[str] = Field(default_factory=list)
    avatar_key: str | None = None


class VacancyCreateIn(BaseModel):
    title: str
    client_id: int | None = None
    chat_id: str | None = None
    is_test: bool = False
    source_vacancy_id: int | None = None


class VacancyCloseIn(BaseModel):
    close_reason: str  # success | client_cancelled


class VacancyPatchIn(BaseModel):
    title: str | None = None


class VacancyDocumentsPatchIn(BaseModel):
    """Partial update of editable vacancy document keys (merge, not replace)."""

    profile: str | dict | list | None = None
    vacancy_text: str | None = None
    questions: str | dict | list | None = None
    keywords: str | None = None
    notes: str | None = None


class VacancyDocumentGenerateIn(BaseModel):
    key: str
    corrections: str = ""
    apply: bool = True


class VacancyDocumentGenerateOut(BaseModel):
    vacancy_id: int
    key: str
    mode: str
    value: str
    applied: bool
    documents: dict = Field(default_factory=dict)


class VacancyDocumentsFromBriefIn(BaseModel):
    title: str | None = None
    tasks: str = ""
    must_have: str = ""
    conditions: str = ""
    interview_questions: str = ""
    apply: bool = True


class VacancyDocumentsFromBriefOut(BaseModel):
    vacancy_id: int
    applied: bool
    documents: dict = Field(default_factory=dict)


class CandidateListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: int
    name: str
    hr_stage: str
    client_status: str
    created_at: str | None = None
    phone: str | None = None
    city: str | None = None
    vacancy_title: str | None = None
    client_name: str | None = None
    last_contact_at: str | None = None
    attention_reason: str | None = None
    photo_url: str | None = None
    gender: str | None = None
    liked: bool = False
    talent_reserve: bool = False
    talent_reserve_at: str | None = None
    ai_score: int | float | None = None


class CandidateDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: int
    vacancy_title: str | None = None
    client_id: int | None = None
    client_name: str | None = None
    name: str
    hr_stage: str
    client_status: str
    created_at: str | None
    status_updated_at: str | None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    metro: str | None = None
    age: str | None = None
    salary_expected: str | None = None
    resume_link: str | None = None
    hh_resume_link: str | None = None
    portfolio_link: str | None = None
    video_link: str | None = None
    task_link: str | None = None
    hr_comment: str | None = None
    transcript: str | None = None
    interview_digest: dict | None = None
    interview_eval_notes: str | None = None
    questionnaire_recruiter_notes: str | None = None
    client_comment: str | None = None
    ai_score: float | int | None = None
    ai_score_source: str | None = None
    ai_comment: str | None = None
    ai_comment_sections: dict | None = None
    interview_questionnaire: list | None = None
    control_word_status: str | None = None
    control_word_match: str | None = None
    control_word_note: str | None = None
    vacancy_control_word_enabled: bool = False
    vacancy_control_word: str | None = None
    office_interview_date: str | None = None
    office_interview_time: str | None = None
    photo_url: str | None = None
    gender: str | None = None
    hh_resume_id: str | None = None
    liked: bool = False
    liked_at: str | None = None
    talent_reserve: bool = False
    talent_reserve_at: str | None = None
    talent_reserve_note: str | None = None
    talent_reserve_by: str | None = None
    payload: dict = Field(default_factory=dict)


class CandidatePatchIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    age: str | None = None
    city: str | None = None
    metro: str | None = None
    salary_expected: str | None = None
    resume_link: str | None = None
    hh_resume_link: str | None = None
    anonymized_resume_link: str | None = None
    resume_preview_included: bool | None = None
    resume_preview_visible: bool | None = None
    portfolio_link: str | None = None
    video_link: str | None = None
    task_link: str | None = None
    hr_comment: str | None = None
    transcript: str | None = None
    interview_eval_notes: str | None = None
    questionnaire_recruiter_notes: str | None = None
    office_interview_date: str | None = None
    office_interview_time: str | None = None
    remote_interview: bool | None = None
    meeting_link: str | None = None
    liked: bool | None = None
    talent_reserve: bool | None = None
    talent_reserve_note: str | None = None


class CandidateStageIn(BaseModel):
    hr_stage: str
    note: str = ""
    office_interview_date: str | None = None
    office_interview_time: str | None = None
    keep_calendar_event: bool = True
    warranty_start_date: str | None = None
    warranty_months: int | None = None


class CandidateOfferDraftOut(BaseModel):
    greeting: str = ""
    name_patronymic: str = ""
    full_name: str = ""
    company: str = ""
    position: str = ""
    office_address: str = ""
    work_schedule: str = ""
    start_date: str = ""
    probation_months: str = ""
    salary_probation_base: str = ""
    salary_probation_bonus: str = ""
    salary_probation_line: str = ""
    salary_after_base: str = ""
    salary_after_bonus: str = ""
    salary_after_line: str = ""
    duties: str = ""
    manager_name: str = ""
    logo_data_url: str | None = None
    company_client_id: int | None = None


class CandidateOfferDraftIn(BaseModel):
    greeting: str | None = None
    name_patronymic: str | None = None
    full_name: str | None = None
    company: str | None = None
    position: str | None = None
    office_address: str | None = None
    work_schedule: str | None = None
    start_date: str | None = None
    probation_months: str | None = None
    salary_probation_base: str | None = None
    salary_probation_bonus: str | None = None
    salary_probation_line: str | None = None
    salary_after_base: str | None = None
    salary_after_bonus: str | None = None
    salary_after_line: str | None = None
    duties: str | None = None
    manager_name: str | None = None


class CompanyOfferLogoIn(BaseModel):
    logo_data_url: str | None = None
    office_address: str | None = None
    offer_manager_name: str | None = None
    default_work_schedule: str | None = None


class OfferTemplateInfoOut(BaseModel):
    source: str
    filename: str | None = None
    has_custom: bool = False
    can_upload: bool = True
    path: str | None = None


class CandidateCreateIn(BaseModel):
    name: str = ""
    phone: str | None = None
    city: str | None = None
    resume_link: str | None = None
    hh_resume_link: str | None = None
    hr_comment: str | None = None


class StageOptionOut(BaseModel):
    id: str
    label: str


class StageCount(BaseModel):
    stage: str
    count: int


class ClientCount(BaseModel):
    client_id: int | None
    client_name: str
    vacancies_active: int = 0
    vacancies_archive: int = 0
    candidates: int = 0


class FunnelStatsOut(BaseModel):
    vacancies_active: int
    vacancies_archive: int
    candidates_total: int
    by_hr_stage: list[StageCount]
    by_client_status: list[StageCount]
    by_client: list[ClientCount]
    hires: int = 0
    in_client_zone: int = 0
    sent_to_client: int = 0
    vacancy_id: int | None = None
    vacancy_title: str | None = None


class HhEfficiencyStatsOut(BaseModel):
    viewed: int = 0
    ai_score_gt2: int = 0
    ai_low: int = 0
    recruiter_reject: int = 0
    shortlist: int = 0
    in_funnel: int = 0
    jobs_completed: int = 0


class ActivityBucket(BaseModel):
    bucket: str
    candidates_added: int = 0
    stage_changes: int = 0
    jobs: int = 0


class ActivityStatsOut(BaseModel):
    period: str
    period_from: str
    period_to: str
    candidates_added: int = 0
    stage_changes: int = 0
    jobs: int = 0
    series: list[ActivityBucket] = Field(default_factory=list)


class DashboardKpi(BaseModel):
    key: str
    label: str
    value: float | int
    unit: str | None = None


class DashboardAttentionItem(BaseModel):
    id: str
    name: str
    vacancy_id: int
    vacancy_title: str | None = None
    reason: str | None = None
    photo_url: str | None = None
    gender: str | None = None


class DashboardVacancyRow(BaseModel):
    vacancy_id: int
    title: str
    active: bool
    days_open: int | None = None
    candidates: int = 0
    hires: int = 0


class DashboardWarrantyClaim(BaseModel):
    candidate_id: str
    candidate_name: str
    vacancy_id: int
    vacancy_title: str
    days_worked: int | None = None
    reason: str | None = None
    hire_at: str | None = None
    left_at: str | None = None


class DashboardWarrantyRisks(BaseModel):
    claims_count: int = 0
    claims: list[DashboardWarrantyClaim] = Field(default_factory=list)
    warranty_searches: int = 0
    multi_hire_vacancies: int = 0
    replacements_total: int = 0


class DashboardClosedVacancyItem(BaseModel):
    vacancy_id: int
    title: str
    closed_at: str | None = None


class DashboardClosedReasonRow(BaseModel):
    reason: str
    label: str
    count: int = 0
    vacancies: list[DashboardClosedVacancyItem] = Field(default_factory=list)


class DashboardClosedBreakdown(BaseModel):
    total: int = 0
    rows: list[DashboardClosedReasonRow] = Field(default_factory=list)


class DashboardStatsOut(BaseModel):
    mode: str
    period: str
    period_from: str | None = None
    period_to: str | None = None
    kpis: list[DashboardKpi] = Field(default_factory=list)
    activity_series: list[ActivityBucket] = Field(default_factory=list)
    funnel_flow: list[StageCount] = Field(default_factory=list)
    attention: list[DashboardAttentionItem] = Field(default_factory=list)
    vacancies_table: list[DashboardVacancyRow] = Field(default_factory=list)
    hh: HhEfficiencyStatsOut | None = None
    warranty_risks: DashboardWarrantyRisks | None = None
    closed_breakdown: DashboardClosedBreakdown | None = None


class StatsAiBriefIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    client_id: int | None = None
    vacancy_id: int | None = None
    period: str = "day"
    date_from: str | None = Field(default=None, alias="from")
    date_to: str | None = Field(default=None, alias="to")
    active_vacancies_only: bool = True

    model_config = ConfigDict(populate_by_name=True)


class StatsAiBriefKpi(BaseModel):
    label: str
    value: str
    tone: str = "neutral"


class StatsAiBriefItem(BaseModel):
    text: str
    tone: str = "neutral"


class StatsAiBriefSection(BaseModel):
    title: str
    body: str | None = None
    items: list[StatsAiBriefItem] = Field(default_factory=list)


class StatsAiBriefOut(BaseModel):
    title: str
    summary: str = ""
    kpis: list[StatsAiBriefKpi] = Field(default_factory=list)
    sections: list[StatsAiBriefSection] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class DocumentGenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_filename: str
    title: str
    mode: str
    created_at_legacy: str | None
    imported_at: datetime
    preview: str | None = None
    vacancy_id: int | None = None


class DocumentGenerationDetail(DocumentGenerationOut):
    documents_snapshot: dict = Field(default_factory=dict)


class ImportStatsOut(BaseModel):
    last_import_at: datetime | None = None
    source_dir: str | None = None
    stats: dict = Field(default_factory=dict)
    counts: dict = Field(default_factory=dict)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: str
    status: str
    progress_pct: int | None
    progress_label: str | None
    client_id: int | None
    vacancy_id: int | None
    result_ref: str | None = None
    error: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None


class JobCreateIn(BaseModel):
    job_type: str = Field(
        description="demo_progress | import_legacy | transcribe_media | hh_cold_search"
    )
    client_id: int | None = None
    vacancy_id: int | None = None
    payload: dict = Field(default_factory=dict)


class JobCreateOut(BaseModel):
    id: UUID
    status: str
    job_type: str
    reused: bool = False
    progress_label: str | None = None


class JobsListOut(BaseModel):
    active_count: int
    items: list[JobOut]


class JobHistoryItemOut(BaseModel):
    id: str
    job_type: str
    status: str
    progress_pct: int | None = None
    progress_label: str | None = None
    vacancy_id: int | None = None
    created_at: str | None = None
    keywords: str = ""
    keywords_short: str = ""
    found: int | None = None
    evaluated: int | None = None
    error: str | None = None


class JobHistoryListOut(BaseModel):
    items: list[JobHistoryItemOut]


class HhShortlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: int
    hh_resume_id: str
    title: str
    url: str | None = None
    area: str | None = None
    ai_score: int | None = None
    snapshot: dict = Field(default_factory=dict)
    note: str | None = None
    created_at: datetime


class HhShortlistCreateIn(BaseModel):
    hh_resume_id: str
    title: str = ""
    url: str | None = None
    area: str | None = None
    ai_score: int | None = None
    snapshot: dict = Field(default_factory=dict)
    note: str | None = None


class HhShortlistToCandidateOut(BaseModel):
    candidate: CandidateDetail
    created: bool
    already_exists: bool = False


class HhSearchCriteriaIn(BaseModel):
    criteria: dict = Field(default_factory=dict)
    rebuild_portrait: bool = False


class HhPresetIn(BaseModel):
    preset: dict = Field(default_factory=dict)
    rebuild_portrait: bool = False
    approve: bool = False


class HhSeenItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vacancy_id: int
    hh_resume_id: str
    reason: str
    title: str = ""
    url: str | None = None
    ai_score: int | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class HhSeenRejectIn(BaseModel):
    hh_resume_id: str
    title: str = ""
    url: str | None = None
    ai_score: int | None = None
    note: str | None = None


class MessagingChannelOut(BaseModel):
    id: UUID
    provider: str
    external_id: str
    client_id: int | None = None
    name: str
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class MessagingChannelDeleteOut(BaseModel):
    ok: bool = True


class MessagingChannelsSyncOut(BaseModel):
    created: int = 0
    updated: int = 0
    skipped_no_chat: int = 0


class MessagingPostOut(BaseModel):
    id: UUID
    channel_id: UUID
    candidate_id: UUID
    vacancy_id: int
    kind: str
    external_message_id: str
    created_at: datetime
    payload: dict = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class CandidateSendToChatIn(BaseModel):
    move_to_client_review: bool = True


class CandidateSendToChatOut(BaseModel):
    ok: bool = True
    message: str
    post_id: str = ""
    external_message_id: str = ""
    channel_id: str = ""
    chat_id: str = ""
    stage_changed: bool = False
    hr_stage: str
    candidate: CandidateDetail | None = None
    results: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

class YandexDiskConfigOut(BaseModel):
    vacancy_id: int
    root_url: str = ""
    ingest_new_resumes: bool = True
    subfolders: dict[str, str] = Field(default_factory=dict)
    last_sync_at: str | None = None
    seen_count: int = 0


class YandexDiskConfigPatchIn(BaseModel):
    root_url: str | None = None
    ingest_new_resumes: bool | None = None
    subfolders: dict[str, str] | None = None
    reset_seen: bool = False


class YandexDiskSyncOut(BaseModel):
    vacancy_id: int
    created: int = 0
    updated: int = 0
    skipped: int = 0
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    changed: bool = False
    last_sync_at: str | None = None
    evaluate_candidate_ids: list[str] = Field(default_factory=list)
    evaluate_job_ids: list[str] = Field(default_factory=list)


class CandidateEvaluateOut(BaseModel):
    ok: bool = True
    ai_score: int | None = None
    extract_error: str | None = None
    profile_present: bool = False
    questionnaire_generated: bool = False
    questionnaire_count: int = 0
    candidate: CandidateDetail


class EvaluateResumeIn(BaseModel):
    skip_questionnaire: bool = False


class BulkLinksIn(BaseModel):
    links: list[str] = Field(default_factory=list)
    text: str | None = None  # newline-separated alternative to links[]
    evaluate: bool = False
    for_resume_preview: bool = False


class ResumePreviewIncludeIn(BaseModel):
    included: bool | None = None
    visible: bool | None = None
    pdf_url: str | None = None
    hr_comment: str | None = None


class BulkLinksOut(BaseModel):
    created: int = 0
    candidate_ids: list[str] = Field(default_factory=list)
    candidate_id: str | None = None
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    evaluate_candidate_ids: list[str] = Field(default_factory=list)
    evaluate_job_ids: list[str] = Field(default_factory=list)


class QuestionnaireItemOut(BaseModel):
    вопрос: str = ""
    уточняющие_вопросы: list[str] = Field(default_factory=list)
    уточнения_по_резюме: list[str] = Field(default_factory=list)
    проверяет_требование: str = ""
    категория: str = ""
    пример_ответа: str = ""
    в_резюме: str = ""
    ответ: str = ""
    ответ_кандидата: str = ""
    оценка_ии: str = ""
    пояснение_ии: str = ""
    оценка_hr: str = ""
    оценка: str = ""
    _qid: str = ""

    model_config = ConfigDict(extra="allow")


class QuestionnairePutIn(BaseModel):
    items: list[dict] = Field(default_factory=list)


class QuestionnaireOut(BaseModel):
    candidate_id: str
    items: list[dict] = Field(default_factory=list)
    count: int = 0


class QuestionnaireRegenerateIn(BaseModel):
    notes: str = ""


class WebhookAckOut(BaseModel):
    ok: bool = True
    handled: bool = False
    provider: str
    events: list[dict] = Field(default_factory=list)
    note: str = ""


# --- M9: typed request bodies (was bare dict) ---


class VacancySettingsPatchIn(BaseModel):
    is_test: bool | None = None
    show_portfolio_field: bool | None = None
    control_word_enabled: bool | None = None
    control_word: str | None = None
    chat_id: str | None = None
    avatar_key: str | None = None


class WarrantyApplyIn(BaseModel):
    candidate_id: UUID
    start_date: str
    months: int | None = None


class AppSettingsPatchIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_warranty_months: int | None = None
    ai_provider: dict | None = None
    ai_model: str | None = None
    provider_links: list | None = None
    candidate_comms: dict | None = None
    yandex_disk_root: str | None = None
    yandex_disk_inbox: str | None = None
    yandex_disk_client_id: str | None = None
    candidate_intake: dict | None = None
    functions: dict | None = None
    client_notify: dict | None = None
    bitrix: dict | None = None


class OauthTokenIn(BaseModel):
    token: str | None = None
    access_token: str | None = None


class InboxProcessIn(BaseModel):
    limit: int | None = 20


class InboxBindIn(BaseModel):
    vacancy_id: int


class InboxSettingsPatchIn(BaseModel):
    auto: bool | None = None
    confidence: float | None = None
    evaluate_on_route: bool | None = None


class StageSchemaPatchIn(BaseModel):
    """Whole stage-schema document; allow arbitrary keys."""

    model_config = ConfigDict(extra="allow")


class GoogleOAuthCompleteIn(BaseModel):
    code: str = ""


class ZoomOAuthCompleteIn(BaseModel):
    code: str = ""


class ZoomMeetingScheduleIn(BaseModel):
    start_date: str = ""
    start_time: str = ""
    duration_minutes: int = 60


class HhSearchPlanReviseIn(BaseModel):
    note: str = ""


class HhManualEvaluateIn(BaseModel):
    text: str | None = None
    refs: str | None = None
    criteria: dict | None = None


class HhSoftenSuggestionsIn(BaseModel):
    criteria: dict | None = None
    search_results: list | None = None
    good_resumes: list | None = None


class HhSoftenApplyIn(BaseModel):
    criteria: dict | None = None
    suggestions: list = Field(default_factory=list)
    selected_ids: list = Field(default_factory=list)
    persist: bool = True


class CandidateCopyIn(BaseModel):
    target_vacancy_id: int


class MessagingTestMessageIn(BaseModel):
    chat_id: str
    text: str | None = None


class ExtraMaterialIn(BaseModel):
    title: str | None = None
    url: str = ""


class HistoryApplyIn(BaseModel):
    vacancy_id: int | None = None
    keys: list[str] | None = None


class TemplateCreateVacancyIn(BaseModel):
    title: str | None = None
    client_id: int | None = None
    chat_id: str | None = None
    is_test: bool = False


class AuthLoginIn(BaseModel):
    email: str
    password: str


class AuthMeOut(BaseModel):
    id: str
    email: str
    full_name: str = ""
    org_id: str
    org_name: str = ""
    roles: list[str] = Field(default_factory=list)
    auth_disabled: bool = False
    bitrix_responsible_id: str = ""
    telegram_available: bool = True
    is_demo: bool = False


class AuthOkOut(BaseModel):
    ok: bool = True


class UsefulLinkItem(BaseModel):
    id: str
    label: str
    url: str


class UsefulLinksOut(BaseModel):
    items: list[UsefulLinkItem] = Field(default_factory=list)
    auth_disabled: bool = False


class UsefulLinksPut(BaseModel):
    items: list[UsefulLinkItem] = Field(default_factory=list)


class NotifyPrefsOut(BaseModel):
    google_calendar_enabled: bool = True
    telegram_enabled: bool = False
    telegram_chat_id: str = ""
    telegram_period: str = "digest_admin"
    telegram_text: str = ""
    auth_disabled: bool = False
    telegram_bound: bool = False


class NotifyPrefsPut(BaseModel):
    google_calendar_enabled: bool | None = None
    telegram_enabled: bool | None = None
    telegram_chat_id: str | None = None
    telegram_period: str | None = None
    telegram_text: str | None = None

