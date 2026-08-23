"""Management system (СУП) — normalized entities per IMPLEMENTATION_PLAN_SISTEMA U1."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

MGMT_STATUSES = ("draft", "approved", "published")
LINK_KINDS = ("decomposes", "implements", "measures", "assigned_to", "references", "covers")
HIERARCHICAL_LINK_KINDS = ("decomposes", "implements", "measures")
ENTITY_TYPES = (
    "goal",
    "task",
    "process_map",
    "process_step",
    "role",
    "org_node",
    "current_position",
)


class MgmtSystem(Base):
    __tablename__ = "mgmt_systems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    industry_pack_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    draft_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    revisions: Mapped[list["MgmtRevision"]] = relationship(
        back_populates="system",
        foreign_keys="MgmtRevision.system_id",
    )


class MgmtRevision(Base):
    __tablename__ = "mgmt_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_systems.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    system: Mapped["MgmtSystem"] = relationship(
        back_populates="revisions",
        foreign_keys=[system_id],
    )


class MgmtGoal(Base):
    __tablename__ = "mgmt_goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    metric_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    baseline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metric_source: Mapped[str | None] = mapped_column(String(32), nullable=True)  # owner | pack_hint
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    cited_answer_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MgmtGoalDimension(Base):
    """BSC-like измерения целей (справочник; seeds из пакета + дефолт SME)."""

    __tablename__ = "mgmt_goal_dimensions"
    __table_args__ = (UniqueConstraint("code", name="uq_mgmt_goal_dimensions_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    pack_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    default_weight_hint: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtGoalDimensionLink(Base):
    __tablename__ = "mgmt_goal_dimension_links"
    __table_args__ = (UniqueConstraint("goal_id", "dimension_id", name="uq_mgmt_goal_dimension_links"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_goals.id"), nullable=False, index=True
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_goal_dimensions.id"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class MgmtTask(Base):
    __tablename__ = "mgmt_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    metric_target: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    metric_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MgmtProcessMap(Base):
    __tablename__ = "mgmt_process_maps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtRole(Base):
    __tablename__ = "mgmt_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    external_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtProcessStep(Base):
    __tablename__ = "mgmt_process_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    process_map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_process_maps.id"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_roles.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtStepIoItem(Base):
    __tablename__ = "mgmt_step_io_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_process_steps.id"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # in | out
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    glossary_term_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtOrgNode(Base):
    __tablename__ = "mgmt_org_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_roles.id"), nullable=True
    )
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_org_nodes.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtEntityLink(Base):
    __tablename__ = "mgmt_entity_links"
    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "link_kind",
            name="uq_mgmt_entity_links",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    link_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class MgmtCurrentPosition(Base):
    __tablename__ = "mgmt_current_positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtCurrentPositionDuty(Base):
    __tablename__ = "mgmt_current_position_duties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_current_positions.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MgmtRoleAssignment(Base):
    __tablename__ = "mgmt_role_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    target_role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_roles.id"), nullable=False
    )
    current_position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_current_positions.id"), nullable=False
    )
    coverage: Mapped[str] = mapped_column(String(16), nullable=False, default="none")  # full|partial|none
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class MgmtNodeLayout(Base):
    __tablename__ = "mgmt_node_layouts"
    __table_args__ = (
        UniqueConstraint("revision_id", "node_type", "node_id", name="uq_mgmt_node_layouts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=False, index=True
    )
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    x: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    y: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)


class MgmtWizardSession(Base):
    __tablename__ = "mgmt_wizard_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mgmt_revisions.id"), nullable=True
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
