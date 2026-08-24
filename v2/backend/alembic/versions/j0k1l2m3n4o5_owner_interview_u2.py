"""owner interview sessions + answers (СИСТЕМА U2)

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "mgmt_owner_interview_sessions" not in insp.get_table_names():
        op.create_table(
            "mgmt_owner_interview_sessions",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("revision_id", sa.UUID(), nullable=False),
            sa.Column("wizard_session_id", sa.UUID(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
            sa.Column("pack_hint", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
            sa.ForeignKeyConstraint(["wizard_session_id"], ["mgmt_wizard_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_mgmt_owner_interview_sessions_org",
            "mgmt_owner_interview_sessions",
            ["organization_id"],
        )

    if "mgmt_owner_interview_answers" not in insp.get_table_names():
        op.create_table(
            "mgmt_owner_interview_answers",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("session_id", sa.UUID(), nullable=False),
            sa.Column("question_key", sa.String(length=64), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("answer_text", sa.Text(), nullable=False),
            sa.Column("deprecated", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["mgmt_owner_interview_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_mgmt_owner_interview_answers_session",
            "mgmt_owner_interview_answers",
            ["session_id"],
        )


def downgrade() -> None:
    op.drop_table("mgmt_owner_interview_answers")
    op.drop_table("mgmt_owner_interview_sessions")
