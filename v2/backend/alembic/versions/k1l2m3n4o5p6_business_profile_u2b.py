"""business profile per revision (СИСТЕМА U2b)

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if "mgmt_business_profiles" not in insp.get_table_names():
        op.create_table(
            "mgmt_business_profiles",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("revision_id", sa.UUID(), nullable=False),
            sa.Column("industry_code", sa.String(length=64), nullable=True),
            sa.Column("industry_custom", sa.Text(), nullable=True),
            sa.Column("business_model", sa.String(length=64), nullable=True),
            sa.Column("market_type", sa.String(length=32), nullable=True),
            sa.Column("scale_band", sa.String(length=32), nullable=True),
            sa.Column("maturity_stage", sa.String(length=32), nullable=True),
            sa.Column("horizon_months", sa.Integer(), nullable=True),
            sa.Column(
                "priorities",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="[]",
            ),
            sa.Column("constraints_text", sa.Text(), nullable=True),
            sa.Column(
                "sensitive_metrics_opt_out",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "optional_metrics",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["revision_id"], ["mgmt_revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("revision_id", name="uq_mgmt_business_profiles_revision"),
        )
        op.create_index(
            "ix_mgmt_business_profiles_revision",
            "mgmt_business_profiles",
            ["revision_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if "mgmt_business_profiles" in insp.get_table_names():
        op.drop_index("ix_mgmt_business_profiles_revision", table_name="mgmt_business_profiles")
        op.drop_table("mgmt_business_profiles")
