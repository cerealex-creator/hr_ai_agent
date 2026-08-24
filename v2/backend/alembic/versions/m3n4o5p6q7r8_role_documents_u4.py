"""role documents L3 (СИСТЕМА U4)

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())

    if "mgmt_role_documents" not in tables:
        op.create_table(
            "mgmt_role_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "revision_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("mgmt_revisions.id"),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("mgmt_roles.id"),
                nullable=False,
            ),
            sa.Column("doc_kind", sa.String(32), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "revision_id", "role_id", "doc_kind", name="uq_mgmt_role_documents_rev_role_kind"
            ),
        )
        op.create_index("ix_mgmt_role_documents_revision_id", "mgmt_role_documents", ["revision_id"])
        op.create_index("ix_mgmt_role_documents_role_id", "mgmt_role_documents", ["role_id"])

    if "mgmt_role_document_lines" not in tables:
        op.create_table(
            "mgmt_role_document_lines",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("mgmt_role_documents.id"),
                nullable=False,
            ),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("target_value", sa.Numeric(14, 4), nullable=True),
            sa.Column("metric_unit", sa.String(64), nullable=True),
            sa.Column("source_step_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("is_manual", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        )
        op.create_index(
            "ix_mgmt_role_document_lines_document_id", "mgmt_role_document_lines", ["document_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())
    if "mgmt_role_document_lines" in tables:
        op.drop_index("ix_mgmt_role_document_lines_document_id", table_name="mgmt_role_document_lines")
        op.drop_table("mgmt_role_document_lines")
    if "mgmt_role_documents" in tables:
        op.drop_index("ix_mgmt_role_documents_role_id", table_name="mgmt_role_documents")
        op.drop_index("ix_mgmt_role_documents_revision_id", table_name="mgmt_role_documents")
        op.drop_table("mgmt_role_documents")
