"""goal dimensions + baseline/target on goals (ревью №5)

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_DIMENSIONS = [
    ("finance", "Финансы", "💰", 25),
    ("customers", "Клиенты / рынок", "🎯", 25),
    ("processes", "Процессы / качество", "⚙️", 25),
    ("people", "Команда / развитие", "👥", 25),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "mgmt_goal_dimensions" not in insp.get_table_names():
        op.create_table(
            "mgmt_goal_dimensions",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("pack_id", sa.String(length=64), nullable=True),
            sa.Column("title", sa.String(length=128), nullable=False),
            sa.Column("icon", sa.String(length=32), nullable=True),
            sa.Column("default_weight_hint", sa.Numeric(8, 2), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_mgmt_goal_dimensions_code"),
        )

    cols = {c["name"] for c in insp.get_columns("mgmt_goals")} if "mgmt_goals" in insp.get_table_names() else set()
    for col, col_type in (
        ("metric_unit", sa.String(length=64)),
        ("metric_source", sa.String(length=32)),
    ):
        if col not in cols:
            op.add_column("mgmt_goals", sa.Column(col, col_type, nullable=True))
    for col in ("baseline_value", "target_value"):
        if col not in cols:
            op.add_column("mgmt_goals", sa.Column(col, sa.Numeric(14, 4), nullable=True))
    for col in ("baseline_date", "target_date"):
        if col not in cols:
            op.add_column("mgmt_goals", sa.Column(col, sa.Date(), nullable=True))

    if "mgmt_goal_dimension_links" not in insp.get_table_names():
        op.create_table(
            "mgmt_goal_dimension_links",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("goal_id", sa.UUID(), nullable=False),
            sa.Column("dimension_id", sa.UUID(), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
            sa.ForeignKeyConstraint(["dimension_id"], ["mgmt_goal_dimensions.id"]),
            sa.ForeignKeyConstraint(["goal_id"], ["mgmt_goals.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("goal_id", "dimension_id", name="uq_mgmt_goal_dimension_links"),
        )
        op.create_index("ix_mgmt_goal_dimension_links_goal", "mgmt_goal_dimension_links", ["goal_id"])

    # Seed default BSC dimensions (idempotent by code)
    for i, (code, title, icon, hint) in enumerate(DEFAULT_DIMENSIONS):
        op.execute(
            sa.text(
                """
                INSERT INTO mgmt_goal_dimensions (id, code, pack_id, title, icon, default_weight_hint, sort_order)
                SELECT gen_random_uuid(), :code, 'sme_base', :title, :icon, :hint, :sort_order
                WHERE NOT EXISTS (SELECT 1 FROM mgmt_goal_dimensions WHERE code = :code)
                """
            ).bindparams(code=code, title=title, icon=icon, hint=hint, sort_order=i)
        )


def downgrade() -> None:
    op.drop_table("mgmt_goal_dimension_links")
    for col in ("target_date", "baseline_date", "target_value", "baseline_value", "metric_source", "metric_unit"):
        op.drop_column("mgmt_goals", col)
    op.drop_table("mgmt_goal_dimensions")
