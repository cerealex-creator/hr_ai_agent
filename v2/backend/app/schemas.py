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


class ClientCreateIn(BaseModel):
    name: str


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


class VacancyCreateIn(BaseModel):
    title: str
    client_id: int | None = None
    chat_id: str | None = None
    is_test: bool = False
    source_vacancy_id: int | None = None


class VacancyCloseIn(BaseModel):
    close_reason: str  # success | client_cancelled


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
    office_interview_date: str | None = None
    office_interview_time: str | None = None
    payload: dict = Field(default_factory=dict)


class CandidatePatchIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    age: str | None = None
    city: str | None = None
    metro: str | None = None
    salary_expected: str | None = None
    resume_link: str | None = None
    hh_resume_link: str | None = None
    portfolio_link: str | None = None
    video_link: str | None = None
    task_link: str | None = None
    hr_comment: str | None = None
    transcript: str | None = None
    interview_eval_notes: str | None = None
    questionnaire_recruiter_notes: str | None = None
    office_interview_date: str | None = None
    office_interview_time: str | None = None


class CandidateStageIn(BaseModel):
    hr_stage: str
    note: str = ""
    office_interview_date: str | None = None
    office_interview_time: str | None = None
    keep_calendar_event: bool = True
    warranty_start_date: str | None = None
    warranty_months: int | None = None


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


class DocumentGenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_filename: str
    title: str
    mode: str
    created_at_legacy: str | None
    imported_at: datetime
    preview: str | None = None


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
    post_id: str
    external_message_id: str
    channel_id: str
    chat_id: str
    stage_changed: bool = False
    hr_stage: str
    candidate: CandidateDetail | None = None


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


class CandidateEvaluateOut(BaseModel):
    ok: bool = True
    ai_score: int | None = None
    extract_error: str | None = None
    profile_present: bool = False
    questionnaire_generated: bool = False
    questionnaire_count: int = 0
    candidate: CandidateDetail


class BulkLinksIn(BaseModel):
    links: list[str] = Field(default_factory=list)
    text: str | None = None  # newline-separated alternative to links[]
    evaluate: bool = False


class BulkLinksOut(BaseModel):
    created: int = 0
    candidate_ids: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


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

