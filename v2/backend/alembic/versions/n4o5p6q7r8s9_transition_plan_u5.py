"""transition plan U5 (СИСТЕМА)

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())

    if "mgmt_gap_items" not in tables:
        op.create_table(
            "mgmt_gap_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "revision_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("mgmt_revisions.id"),
                nullable=False,
            ),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("entity_type", sa.String(32), nullable=True),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("recommendation", sa.String(64), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_mgmt_gap_items_revision_id", "mgmt_gap_items", ["revision_id"])

    if "mgmt_transition_steps" not in tables:
        op.create_table(
            "mgmt_transition_steps",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "revision_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("mgmt_revisions.id"),
                nullable=False,
            ),
            sa.Column(
                "gap_item_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("mgmt_gap_items.id"),
                nullable=True,
            ),
            sa.Column("action_code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("horizon", sa.String(16), nullable=False, server_default="short"),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_mgmt_transition_steps_revision_id", "mgmt_transition_steps", ["revision_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())
    if "mgmt_transition_steps" in tables:
        op.drop_index("ix_mgmt_transition_steps_revision_id", table_name="mgmt_transition_steps")
        op.drop_table("mgmt_transition_steps")
    if "mgmt_gap_items" in tables:
        op.drop_index("ix_mgmt_gap_items_revision_id", table_name="mgmt_gap_items")
        op.drop_table("mgmt_gap_items")
