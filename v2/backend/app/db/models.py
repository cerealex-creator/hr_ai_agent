import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Per-org integrations (e.g. zoom OAuth tokens). Shared app Client ID/Secret stay in .env.
    integrations: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    clients: Mapped[list["Client"]] = relationship(back_populates="organization")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # legacy department id
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    client_zone_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Company tree: root company (parent_id NULL) or department under a company.
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("clients.id"), nullable=True, index=True
    )
    # Meaningful on root company: "company" (one chat) | "departments" (chats per dept).
    chat_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="company")
    # "company" | "department" | "test"
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="company", index=True)

    organization: Mapped["Organization"] = relationship(back_populates="clients")
    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="client")
    parent: Mapped["Client | None"] = relationship(
        remote_side="Client.id", back_populates="children"
    )
    children: Mapped[list["Client"]] = relationship(back_populates="parent")


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # legacy vacancy id
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    documents: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    client: Mapped["Client | None"] = relationship(back_populates="vacancies")
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="vacancy")


class Person(Base):
    """Identity hub — one real person may have many Candidate cards across vacancies."""

    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    match_phone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    match_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    match_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    merged_into_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    candidates: Mapped[list["Candidate"]] = relationship(back_populates="person")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    hr_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="resume_screening", index=True)
    client_status: Mapped[str] = mapped_column(String(32), nullable=False, default="wait", index=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status_updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    match_phone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    match_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    match_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")

    vacancy: Mapped["Vacancy"] = relationship(back_populates="candidates")
    person: Mapped["Person | None"] = relationship(back_populates="candidates")


class DocumentGeneration(Base):
    __tablename__ = "document_generations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("vacancies.id"), nullable=True)
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy_history")
    documents_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at_legacy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessagingChannel(Base):
    __tablename__ = "messaging_channels"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_messaging_provider_external"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram")
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    posts: Mapped[list["MessagingPost"]] = relationship(back_populates="channel")


class MessagingPost(Base):
    """Outbound message tied to a candidate card (e.g. Telegram message_id)."""

    __tablename__ = "messaging_posts"
    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "external_message_id",
            name="uq_messaging_post_channel_message",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_channels.id"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False, index=True
    )
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancies.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="primary")
    external_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    channel: Mapped["MessagingChannel"] = relationship(back_populates="posts")
    actions: Mapped[list["MessagingAction"]] = relationship(back_populates="post")


class MessagingAction(Base):
    """Pending / completed client action bound to a messaging post (slice 2: webhook)."""

    __tablename__ = "messaging_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_posts.id"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    external_callback_data: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    post: Mapped["MessagingPost"] = relationship(back_populates="actions")


class VacancyTemplate(Base):
    __tablename__ = "vacancy_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legacy_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    documents: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id"), nullable=True)
    vacancy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("vacancies.id"), nullable=True)
    result_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_dir: Mapped[str] = mapped_column(Text, nullable=False)
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HhShortlistItem(Base):
    """Liked HH resumes for a vacancy (cold search shortlist, not funnel candidates)."""

    __tablename__ = "hh_shortlist_items"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "hh_resume_id", name="uq_hh_shortlist_vacancy_resume"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancies.id"), nullable=False, index=True)
    hh_resume_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HhSeenResume(Base):
    """Resumes already reviewed for a vacancy — skip on next HH cold search."""

    __tablename__ = "hh_seen_resumes"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "hh_resume_id", name="uq_hh_seen_vacancy_resume"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancies.id"), nullable=False, index=True)
    hh_resume_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, default="ai_low")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InboxItem(Base):
    """Yandex Disk _inbox routing queue (L3)."""

    __tablename__ = "inbox_items"
    __table_args__ = (UniqueConstraint("disk_path", name="uq_inbox_disk_path"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disk_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", index=True)
    # new | routed | unsorted | error
    vacancy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("vacancies.id"), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    extracted: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiErrorLog(Base):
    """Sanitized AI failure samples for prompt tuning (no PII / no full resume)."""

    __tablename__ = "ai_error_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="json_parse")
    error_message: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    raw_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessedMessagingUpdate(Base):
    """Idempotency keys for inbound messaging (Telegram callback_query.id, etc.)."""

    __tablename__ = "processed_messaging_updates"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_processed_messaging_provider_ext"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram")
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="callback_query")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """HR / owner account (D1 Auth). No self-registration — seed/CLI only."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Per-user launcher buttons: [{id, label, url}, ...] — presets live in the UI only.
    useful_links: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    # Personal notify: google_calendar_enabled, telegram_enabled/chat_id/period/text
    notify_prefs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Personal candidate intake channels (optional ones off by default)
    candidate_intake: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Fixed Bitrix assignee for this user (pilot); empty → use org/global default
    bitrix_responsible_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list["OrganizationMember"]] = relationship(back_populates="user")


class OrganizationMember(Base):
    """User membership in an organization (D1). client_ids scoping → D2."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # platform_owner | hr_recruiter | (hiring_manager in D2)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="hr_recruiter")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="memberships")
    organization: Mapped["Organization"] = relationship()


class RefreshToken(Base):
    """Revocable refresh tokens (hashed)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrganizationTag(Base):
    """Per-org tag dictionary with usage counters."""

    __tablename__ = "organization_tags"
    __table_args__ = (
        UniqueConstraint("organization_id", "tag", name="pk_org_tags"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(128), primary_key=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CandidateSegment(Base):
    """Saved filter / segment for candidate lists."""

    __tablename__ = "candidate_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filter: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="candidates")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
