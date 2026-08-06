"""baseline_v2_schema — current SQLAlchemy models as Alembic head.

Revision ID: d22a995b8f9c
Revises:
Create Date: 2026-08-06 14:48:44.653185

History: schema was bootstrapped via create_all. This revision:
- creates any missing tables from Base.metadata (fresh DBs / Wave A tables);
- ensures clients indexes that older DBs may lack.

Existing DBs that already match models: ``alembic upgrade head`` is safe (idempotent).
Fresh DBs: ``alembic upgrade head`` then import / seed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d22a995b8f9c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from app.db.base import Base
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=bind)

    # Indexes that may be absent on DBs created before index=True on Client.
    inspector = sa.inspect(bind)
    if "clients" in inspector.get_table_names():
        existing = {ix["name"] for ix in inspector.get_indexes("clients")}
        if "ix_clients_kind" not in existing:
            op.create_index(op.f("ix_clients_kind"), "clients", ["kind"], unique=False)
        if "ix_clients_parent_id" not in existing:
            op.create_index(op.f("ix_clients_parent_id"), "clients", ["parent_id"], unique=False)


def downgrade() -> None:
    # Baseline — do not drop production tables.
    op.drop_index(op.f("ix_clients_parent_id"), table_name="clients")
    op.drop_index(op.f("ix_clients_kind"), table_name="clients")
