"""consulting wave 0

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())

    if "consulting_projects" not in tables:
        op.create_table(
            "consulting_projects",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("customer_name", sa.String(512), nullable=False, server_default=""),
            sa.Column("started_on", sa.Date(), nullable=True),
            sa.Column("due_on", sa.Date(), nullable=True),
            sa.Column("plan_status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("showcase_token", sa.String(64), nullable=True),
            sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_projects_organization_id", "consulting_projects", ["organization_id"])
        op.create_index("ix_consulting_projects_showcase_token", "consulting_projects", ["showcase_token"], unique=True)

    if "consulting_members" not in tables:
        op.create_table(
            "consulting_members",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("role", sa.String(32), nullable=False, server_default="owner"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "user_id", name="uq_consulting_member"),
        )
        op.create_index("ix_consulting_members_project_id", "consulting_members", ["project_id"])
        op.create_index("ix_consulting_members_user_id", "consulting_members", ["user_id"])

    if "consulting_units" not in tables:
        op.create_table(
            "consulting_units",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_consulting_units_project_id", "consulting_units", ["project_id"])

    if "consulting_people" not in tables:
        op.create_table(
            "consulting_people",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_units.id"), nullable=True),
            sa.Column("interview", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("survey", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("level", sa.String(32), nullable=False, server_default="executor"),
        )
        op.create_index("ix_consulting_people_project_id", "consulting_people", ["project_id"])

    if "consulting_milestones" not in tables:
        op.create_table(
            "consulting_milestones",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("code", sa.String(32), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("due_on", sa.Date(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_consulting_milestones_project_id", "consulting_milestones", ["project_id"])

    if "consulting_plan_items" not in tables:
        op.create_table(
            "consulting_plan_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="todo"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("milestone_code", sa.String(32), nullable=True),
        )
        op.create_index("ix_consulting_plan_items_project_id", "consulting_plan_items", ["project_id"])

    if "consulting_folders" not in tables:
        op.create_table(
            "consulting_folders",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("code", sa.String(32), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
            sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("parent_code", sa.String(32), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("project_id", "code", name="uq_consulting_folder_code"),
        )
        op.create_index("ix_consulting_folders_project_id", "consulting_folders", ["project_id"])

    if "consulting_sources" not in tables:
        op.create_table(
            "consulting_sources",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("folder_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_folders.id"), nullable=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("url", sa.Text(), nullable=True),
            sa.Column("quoted_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("mark", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("file_name", sa.String(512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_sources_project_id", "consulting_sources", ["project_id"])

    if "consulting_registry_rows" not in tables:
        op.create_table(
            "consulting_registry_rows",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_projects.id"), nullable=False),
            sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consulting_sources.id"), nullable=True),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("owner_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("unit_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("action", sa.String(64), nullable=False, server_default=""),
            sa.Column("priority", sa.String(16), nullable=False, server_default=""),
            sa.Column("target_system", sa.String(64), nullable=False, server_default=""),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_consulting_registry_rows_project_id", "consulting_registry_rows", ["project_id"])


def downgrade() -> None:
    for name in (
        "consulting_registry_rows",
        "consulting_sources",
        "consulting_folders",
        "consulting_plan_items",
        "consulting_milestones",
        "consulting_people",
        "consulting_units",
        "consulting_members",
        "consulting_projects",
    ):
        op.drop_table(name)
