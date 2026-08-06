"""One-shot: fill missing JSONB keys on candidates/vacancies (audit M11).

Usage (from v2/backend, with .venv and DB up):

  python -m app.scripts.normalize_jsonb --dry-run
  python -m app.scripts.normalize_jsonb

Does not overwrite existing values — only adds missing keys (deep merge).
Run before Alembic baseline (M1) so old rows match current writers.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.db.session import SessionLocal
from app.services.jsonb_defaults import (
    deep_fill_missing,
    default_candidate_payload,
    default_vacancy_documents,
    default_vacancy_payload,
)


def normalize_candidates(db: Session, *, dry_run: bool) -> int:
    defaults = default_candidate_payload()
    changed = 0
    rows = list(db.scalars(select(models.Candidate)).all())
    for cand in rows:
        filled, did = deep_fill_missing(cand.payload or {}, defaults)
        if not did:
            continue
        changed += 1
        if dry_run:
            continue
        cand.payload = filled
        flag_modified(cand, "payload")
    return changed


def normalize_vacancies(db: Session, *, dry_run: bool) -> tuple[int, int]:
    doc_defaults = default_vacancy_documents()
    payload_defaults = default_vacancy_payload()
    docs_changed = 0
    payload_changed = 0
    rows = list(db.scalars(select(models.Vacancy)).all())
    for vac in rows:
        docs_filled, docs_did = deep_fill_missing(vac.documents or {}, doc_defaults)
        if docs_did:
            docs_changed += 1
            if not dry_run:
                vac.documents = docs_filled
                flag_modified(vac, "documents")
        payload_filled, payload_did = deep_fill_missing(vac.payload or {}, payload_defaults)
        if payload_did:
            payload_changed += 1
            if not dry_run:
                vac.payload = payload_filled
                flag_modified(vac, "payload")
    return docs_changed, payload_changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize JSONB defaults on candidates/vacancies")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows that would change without writing",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        c_n = normalize_candidates(db, dry_run=args.dry_run)
        d_n, p_n = normalize_vacancies(db, dry_run=args.dry_run)
        if not args.dry_run:
            db.commit()
        mode = "dry-run" if args.dry_run else "applied"
        print(
            f"OK ({mode}): candidates.payload={c_n}, "
            f"vacancies.documents={d_n}, vacancies.payload={p_n}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
