"""persons table + candidates person_id org_id match columns

Revision ID: ac47a81a7a38
Revises: g7h8i9j0k1l2
Create Date: 2026-08-19 12:15:40.854577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision: str = 'ac47a81a7a38'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(insp, table: str, index_name: str) -> bool:
    return any(ix["name"] == index_name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)
    tables = set(insp.get_table_names())
    cand_cols = {c["name"] for c in insp.get_columns("candidates")} if "candidates" in tables else set()

    # --- persons table ---
    if "persons" not in tables:
        op.create_table(
            "persons",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("match_phone", sa.String(length=16), nullable=True),
            sa.Column("match_email", sa.String(length=320), nullable=True),
            sa.Column("match_name", sa.String(length=512), nullable=True),
            sa.Column("do_not_contact", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("merged_into_person_id", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["merged_into_person_id"], ["persons.id"]),
        )
        # refresh inspector after create
        insp = sa_inspect(bind)

    for ix_name, cols, where in [
        ("ix_persons_org_phone", ["organization_id", "match_phone"], "match_phone IS NOT NULL"),
        ("ix_persons_org_email", ["organization_id", "match_email"], "match_email IS NOT NULL"),
        ("ix_persons_org_name", ["organization_id", "match_name"], "match_name IS NOT NULL"),
    ]:
        if not _has_index(insp, "persons", ix_name):
            op.create_index(ix_name, "persons", cols, unique=False, postgresql_where=sa.text(where))

    # --- candidates columns ---
    for col_name, col_type in [
        ("person_id", sa.UUID()),
        ("organization_id", sa.UUID()),
        ("match_phone", sa.String(length=16)),
        ("match_email", sa.String(length=320)),
        ("match_name", sa.String(length=512)),
    ]:
        if col_name not in cand_cols:
            op.add_column("candidates", sa.Column(col_name, col_type, nullable=True))

    for ix_name, cols, where in [
        ("ix_candidates_person_id", ["person_id"], None),
        ("ix_candidates_organization_id", ["organization_id"], None),
        ("ix_candidates_org_phone", ["organization_id", "match_phone"], "match_phone IS NOT NULL"),
        ("ix_candidates_org_email", ["organization_id", "match_email"], "match_email IS NOT NULL"),
    ]:
        if not _has_index(insp, "candidates", ix_name):
            kw = {}
            if where:
                kw["postgresql_where"] = sa.text(where)
            op.create_index(ix_name, "candidates", cols, unique=False, **kw)

    existing_fks = {fk["name"] for fk in insp.get_foreign_keys("candidates") if fk.get("name")}
    if "fk_candidates_person_id" not in existing_fks:
        op.create_foreign_key("fk_candidates_person_id", "candidates", "persons", ["person_id"], ["id"])
    if "fk_candidates_organization_id" not in existing_fks:
        op.create_foreign_key("fk_candidates_organization_id", "candidates", "organizations", ["organization_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_candidates_organization_id", "candidates", type_="foreignkey")
    op.drop_constraint("fk_candidates_person_id", "candidates", type_="foreignkey")
    op.drop_index("ix_candidates_org_email", table_name="candidates")
    op.drop_index("ix_candidates_org_phone", table_name="candidates")
    op.drop_index(op.f("ix_candidates_organization_id"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_person_id"), table_name="candidates")
    op.drop_column("candidates", "match_name")
    op.drop_column("candidates", "match_email")
    op.drop_column("candidates", "match_phone")
    op.drop_column("candidates", "organization_id")
    op.drop_column("candidates", "person_id")

    op.drop_index("ix_persons_org_name", table_name="persons")
    op.drop_index("ix_persons_org_email", table_name="persons")
    op.drop_index("ix_persons_org_phone", table_name="persons")
    op.drop_table("persons")
