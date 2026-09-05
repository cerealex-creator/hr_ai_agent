"""consulting wave 2

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())

    if "consulting_megamaid_nodes" not in tables:
        op.create_table(
            "consulting_megamaid_nodes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("code", sa.String(64), nullable=False, server_default=""),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False, server_default="process"),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("be_tags", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_megamaid_nodes_project_id", "consulting_megamaid_nodes", ["project_id"])

    if "consulting_etalon_nodes" not in tables:
        op.create_table(
            "consulting_etalon_nodes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("code", sa.String(64), nullable=False, server_default=""),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False, server_default="process"),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column(
                "source_megamaid_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("consulting_megamaid_nodes.id"),
                nullable=True,
            ),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_etalon_nodes_project_id", "consulting_etalon_nodes", ["project_id"])

    if "consulting_process_cards" not in tables:
        op.create_table(
            "consulting_process_cards",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("code", sa.String(64), nullable=False, server_default=""),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("papers_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("practice_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("formality", sa.String(32), nullable=False, server_default="unknown"),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("folder_code", sa.String(32), nullable=True),
            sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_process_cards_project_id", "consulting_process_cards", ["project_id"])

    if "consulting_surveys" not in tables:
        op.create_table(
            "consulting_surveys",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("title", sa.String(512), nullable=False, server_default="Опрос диагностики"),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("public_token", sa.String(64), nullable=True),
            sa.Column("fill_white_spots", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_surveys_project_id", "consulting_surveys", ["project_id"])
        op.create_index("ix_consulting_surveys_public_token", "consulting_surveys", ["public_token"], unique=True)

    if "consulting_survey_questions" not in tables:
        op.create_table(
            "consulting_survey_questions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("survey_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_surveys.id"), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("section", sa.String(128), nullable=False, server_default=""),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False, server_default="single"),
            sa.Column("options", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("channel", sa.String(16), nullable=False, server_default="link"),
            sa.Column("preamble", sa.Text(), nullable=False, server_default=""),
            sa.Column("preamble_status", sa.String(16), nullable=False, server_default="none"),
            sa.Column("coverage_code", sa.String(64), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_consulting_survey_questions_survey_id", "consulting_survey_questions", ["survey_id"])

    if "consulting_survey_responses" not in tables:
        op.create_table(
            "consulting_survey_responses",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("survey_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_surveys.id"), nullable=False),
            sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_people.id"), nullable=True),
            sa.Column("full_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("mode", sa.String(16), nullable=False, server_default="self"),
            sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_survey_responses_survey_id", "consulting_survey_responses", ["survey_id"])


def downgrade() -> None:
    for name in (
        "consulting_survey_responses",
        "consulting_survey_questions",
        "consulting_surveys",
        "consulting_process_cards",
        "consulting_etalon_nodes",
        "consulting_megamaid_nodes",
    ):
        op.drop_table(name)
