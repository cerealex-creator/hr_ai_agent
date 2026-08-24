"""multi systems per org + workspace prefs (СИСТЕМА U2c)

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect, text

revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "mgmt_systems" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("mgmt_systems")}

        # Drop UNIQUE(organization_id) — имя может отличаться
        for uc in insp.get_unique_constraints("mgmt_systems"):
            cols_uc = list(uc.get("column_names") or [])
            if cols_uc == ["organization_id"]:
                op.drop_constraint(uc["name"], "mgmt_systems", type_="unique")
                break

        # Refresh column set after potential DDL
        insp = sa_inspect(bind)
        cols = {c["name"] for c in insp.get_columns("mgmt_systems")}

        if "title" not in cols:
            op.add_column(
                "mgmt_systems",
                sa.Column("title", sa.String(length=256), nullable=False, server_default="Основная система"),
            )
        if "kind" not in cols:
            op.add_column(
                "mgmt_systems",
                sa.Column("kind", sa.String(length=32), nullable=False, server_default="company"),
            )
        if "parent_system_id" not in cols:
            op.add_column("mgmt_systems", sa.Column("parent_system_id", sa.UUID(), nullable=True))
            op.create_foreign_key(
                "fk_mgmt_systems_parent",
                "mgmt_systems",
                "mgmt_systems",
                ["parent_system_id"],
                ["id"],
            )
        if "is_archived" not in cols:
            op.add_column(
                "mgmt_systems",
                sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
            )

        insp = sa_inspect(bind)
        existing_idx = {i["name"] for i in insp.get_indexes("mgmt_systems")}
        if "ix_mgmt_systems_organization_id" not in existing_idx:
            op.create_index("ix_mgmt_systems_organization_id", "mgmt_systems", ["organization_id"])

    insp = sa_inspect(bind)
    if "mgmt_workspace_prefs" not in insp.get_table_names():
        op.create_table(
            "mgmt_workspace_prefs",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("active_system_id", sa.UUID(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["active_system_id"], ["mgmt_systems.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", "user_id", name="uq_mgmt_workspace_prefs_org_user"),
        )
        op.create_index("ix_mgmt_workspace_prefs_org", "mgmt_workspace_prefs", ["organization_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "mgmt_workspace_prefs" in insp.get_table_names():
        op.drop_index("ix_mgmt_workspace_prefs_org", table_name="mgmt_workspace_prefs")
        op.drop_table("mgmt_workspace_prefs")
