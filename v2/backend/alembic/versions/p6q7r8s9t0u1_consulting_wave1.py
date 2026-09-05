"""consulting wave 1

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())

    if "consulting_sources" in tables:
        cols = {c["name"] for c in insp.get_columns("consulting_sources")}
        if "extracted_text" not in cols:
            op.add_column(
                "consulting_sources",
                sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
            )
        if "extract_status" not in cols:
            op.add_column(
                "consulting_sources",
                sa.Column("extract_status", sa.String(16), nullable=False, server_default="none"),
            )
        if "space" not in cols:
            op.add_column(
                "consulting_sources",
                sa.Column("space", sa.String(16), nullable=False, server_default="evidence"),
            )

    if "consulting_meetings" not in tables:
        op.create_table(
            "consulting_meetings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("held_on", sa.Date(), nullable=True),
            sa.Column("level", sa.String(32), nullable=False, server_default="directors"),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("transcript", sa.Text(), nullable=False, server_default=""),
            sa.Column("digest", sa.Text(), nullable=False, server_default=""),
            sa.Column("url", sa.Text(), nullable=True),
            sa.Column("folder_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_folders.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_meetings_project_id", "consulting_meetings", ["project_id"])

    if "consulting_contradictions" not in tables:
        op.create_table(
            "consulting_contradictions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("left_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("right_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(16), nullable=False, server_default="open"),
            sa.Column(
                "registry_row_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("consulting_registry_rows.id"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_contradictions_project_id", "consulting_contradictions", ["project_id"])

    if "consulting_comments" not in tables:
        op.create_table(
            "consulting_comments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("author_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("target_kind", sa.String(32), nullable=False, server_default="project"),
            sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_comments_project_id", "consulting_comments", ["project_id"])


def downgrade() -> None:
    for name in ("consulting_comments", "consulting_contradictions", "consulting_meetings"):
        op.drop_table(name)
    for col in ("space", "extract_status", "extracted_text"):
        op.drop_column("consulting_sources", col)
