"""users.bitrix_responsible_id for pilot Bitrix assignee

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g7h8i9j0k1l2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("bitrix_responsible_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "bitrix_responsible_id")
