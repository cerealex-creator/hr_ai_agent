"""Consulting diagnosis module (волна 0). Separate from management_system."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConsultingProject(Base):
    __tablename__ = "consulting_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    plan_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    showcase_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    units: Mapped[list["ConsultingUnit"]] = relationship(back_populates="project")
    people: Mapped[list["ConsultingPerson"]] = relationship(back_populates="project")
    members: Mapped[list["ConsultingMember"]] = relationship(back_populates="project")
    milestones: Mapped[list["ConsultingMilestone"]] = relationship(back_populates="project")
    plan_items: Mapped[list["ConsultingPlanItem"]] = relationship(back_populates="project")
    folders: Mapped[list["ConsultingFolder"]] = relationship(back_populates="project")
    sources: Mapped[list["ConsultingSource"]] = relationship(back_populates="project")
    registry_rows: Mapped[list["ConsultingRegistryRow"]] = relationship(back_populates="project")
    meetings: Mapped[list["ConsultingMeeting"]] = relationship(back_populates="project")
    contradictions: Mapped[list["ConsultingContradiction"]] = relationship(back_populates="project")
    comments: Mapped[list["ConsultingComment"]] = relationship(back_populates="project")
    megamaid_nodes: Mapped[list["ConsultingMegamaidNode"]] = relationship(back_populates="project")
    etalon_nodes: Mapped[list["ConsultingEtalonNode"]] = relationship(back_populates="project")
    process_cards: Mapped[list["ConsultingProcessCard"]] = relationship(back_populates="project")
    surveys: Mapped[list["ConsultingSurvey"]] = relationship(back_populates="project")


class ConsultingMember(Base):
    __tablename__ = "consulting_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_consulting_member"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="members")


class ConsultingUnit(Base):
    __tablename__ = "consulting_units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # uk | directorate | be
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped["ConsultingProject"] = relationship(back_populates="units")


class ConsultingPerson(Base):
    __tablename__ = "consulting_people"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_units.id"), nullable=True
    )
    interview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    survey: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="executor")

    project: Mapped["ConsultingProject"] = relationship(back_populates="people")


class ConsultingMilestone(Base):
    __tablename__ = "consulting_milestones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped["ConsultingProject"] = relationship(back_populates="milestones")


class ConsultingPlanItem(Base):
    __tablename__ = "consulting_plan_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="todo")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    milestone_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    project: Mapped["ConsultingProject"] = relationship(back_populates="plan_items")


class ConsultingFolder(Base):
    __tablename__ = "consulting_folders"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_consulting_folder_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped["ConsultingProject"] = relationship(back_populates="folders")


class ConsultingSource(Base):
    __tablename__ = "consulting_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_folders.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # file | url
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mark: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extract_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    space: Mapped[str] = mapped_column(String(16), nullable=False, default="evidence")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="sources")


class ConsultingRegistryRow(Base):
    __tablename__ = "consulting_registry_rows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_sources.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    unit_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    action: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    target_system: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["ConsultingProject"] = relationship(back_populates="registry_rows")


class ConsultingMeeting(Base):
    __tablename__ = "consulting_meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    held_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="directors")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    digest: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_folders.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="meetings")


class ConsultingContradiction(Base):
    __tablename__ = "consulting_contradictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    left_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    right_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    registry_row_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_registry_rows.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="contradictions")


class ConsultingComment(Base):
    __tablename__ = "consulting_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    author_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="project")
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="comments")


class ConsultingMegamaidNode(Base):
    """Библиотека Мегамейд — не эталон проекта."""

    __tablename__ = "consulting_megamaid_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="process")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    be_tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="megamaid_nodes")


class ConsultingEtalonNode(Base):
    """Целевой эталон проекта (как должно быть)."""

    __tablename__ = "consulting_etalon_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="process")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")  # draft|locked|na
    source_megamaid_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_megamaid_nodes.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="etalon_nodes")


class ConsultingProcessCard(Base):
    """Карточка процесса «как есть»: бумаги + как делают."""

    __tablename__ = "consulting_process_cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    papers_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    practice_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    formality: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    folder_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="process_cards")


class ConsultingSurvey(Base):
    __tablename__ = "consulting_surveys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="Опрос диагностики")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")  # draft|published|closed
    public_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    fill_white_spots: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["ConsultingProject"] = relationship(back_populates="surveys")
    questions: Mapped[list["ConsultingSurveyQuestion"]] = relationship(back_populates="survey")
    responses: Mapped[list["ConsultingSurveyResponse"]] = relationship(back_populates="survey")


class ConsultingSurveyQuestion(Base):
    __tablename__ = "consulting_survey_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_surveys.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    section: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="single")  # single|yesno|text|long
    options: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="link")  # link|meeting
    preamble: Mapped[str] = mapped_column(Text, nullable=False, default="")
    preamble_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")  # none|draft|approved
    coverage_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    survey: Mapped["ConsultingSurvey"] = relationship(back_populates="questions")


class ConsultingSurveyResponse(Base):
    __tablename__ = "consulting_survey_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_surveys.id"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consulting_people.id"), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="self")  # self|interviewer
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    survey: Mapped["ConsultingSurvey"] = relationship(back_populates="responses")
