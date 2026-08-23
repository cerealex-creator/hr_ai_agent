"""mgmt_systems — СУП U1 schema

Revision ID: h8i9j0k1l2m3
Revises: a5dcc48e3506
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "a5dcc48e3506"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "mgmt_systems" in insp.get_table_names():
        return

    op.create_table(
        "mgmt_systems",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("industry_pack_id", sa.String(length=64), nullable=True),
        sa.Column("published_revision_id", sa.UUID(), nullable=True),
        sa.Column("draft_revision_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )

    op.create_table(
        "mgmt_revisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("system_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_revision_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["parent_revision_id"], ["mgmt_revisions.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["mgmt_systems.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mgmt_revisions_system_id", "mgmt_revisions", ["system_id"])

    op.create_table(
        "mgmt_goals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("weight", sa.Numeric(8, 2), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cited_answer_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mgmt_goals_revision_id", "mgmt_goals", ["revision_id"])

    op.create_table(
        "mgmt_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("metric_target", sa.Numeric(14, 4), nullable=True),
        sa.Column("metric_unit", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mgmt_tasks_revision_id", "mgmt_tasks", ["revision_id"])

    op.create_table(
        "mgmt_process_maps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mgmt_process_maps_revision_id", "mgmt_process_maps", ["revision_id"])

    op.create_table(
        "mgmt_roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("external_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mgmt_roles_revision_id", "mgmt_roles", ["revision_id"])

    op.create_table(
        "mgmt_process_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("process_map_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["process_map_id"], ["mgmt_process_maps.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["mgmt_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mgmt_process_steps_revision_id", "mgmt_process_steps", ["revision_id"])

    op.create_table(
        "mgmt_step_io_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("glossary_term_id", sa.UUID(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["step_id"], ["mgmt_process_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mgmt_org_nodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=True),
        sa.Column("parent_node_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["parent_node_id"], ["mgmt_org_nodes.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["mgmt_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mgmt_entity_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("link_kind", sa.String(length=32), nullable=False),
        sa.Column("meta", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "revision_id", "source_type", "source_id", "target_type", "target_id", "link_kind",
            name="uq_mgmt_entity_links",
        ),
    )
    op.create_index("ix_mgmt_entity_links_revision", "mgmt_entity_links", ["revision_id", "source_type", "source_id"])
    op.create_index("ix_mgmt_entity_links_revision_tgt", "mgmt_entity_links", ["revision_id", "target_type", "target_id"])

    op.create_table(
        "mgmt_current_positions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mgmt_current_position_duties",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["position_id"], ["mgmt_current_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mgmt_role_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("target_role_id", sa.UUID(), nullable=False),
        sa.Column("current_position_id", sa.UUID(), nullable=False),
        sa.Column("coverage", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["current_position_id"], ["mgmt_current_positions.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.ForeignKeyConstraint(["target_role_id"], ["mgmt_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mgmt_node_layouts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("node_type", sa.String(length=32), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("x", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("y", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "node_type", "node_id", name="uq_mgmt_node_layouts"),
    )

    op.create_table(
        "mgmt_wizard_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mgmt_wizard_sessions_org", "mgmt_wizard_sessions", ["organization_id"])


def downgrade() -> None:
    for table in (
        "mgmt_wizard_sessions",
        "mgmt_node_layouts",
        "mgmt_role_assignments",
        "mgmt_current_position_duties",
        "mgmt_current_positions",
        "mgmt_entity_links",
        "mgmt_org_nodes",
        "mgmt_step_io_items",
        "mgmt_process_steps",
        "mgmt_roles",
        "mgmt_process_maps",
        "mgmt_tasks",
        "mgmt_goals",
        "mgmt_revisions",
        "mgmt_systems",
    ):
        op.drop_table(table)
