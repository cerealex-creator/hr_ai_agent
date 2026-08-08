"""users.candidate_intake JSONB (personal intake channel toggles)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "candidate_intake" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "candidate_intake",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "candidate_intake" in cols:
        op.drop_column("users", "candidate_intake")
