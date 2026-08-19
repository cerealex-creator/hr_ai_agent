"""Backfill person_id for existing candidates that lack one.

Usage:
    python -m app.scripts.backfill_persons [--all-orgs] [--org-id UUID] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from app.services.person_match import refresh_person_keys


def backfill(db: Session, *, org_ids: list | None = None, dry_run: bool = False) -> dict:
    q = select(models.Candidate).where(models.Candidate.person_id.is_(None))
    candidates = list(db.scalars(q).all())

    stats = {"total": len(candidates), "linked": 0, "skipped_no_org": 0, "errors": 0}

    for cand in candidates:
        vacancy = db.get(models.Vacancy, cand.vacancy_id)
        if not vacancy or not vacancy.client_id:
            stats["skipped_no_org"] += 1
            continue
        client = db.get(models.Client, vacancy.client_id)
        if not client:
            stats["skipped_no_org"] += 1
            continue
        o_id = client.organization_id
        if org_ids and o_id not in org_ids:
            continue

        p = cand.payload or {}
        try:
            refresh_person_keys(
                db,
                candidate=cand,
                name=cand.name or "",
                phone=str(p.get("phone") or ""),
                email=str(p.get("email") or ""),
                org_id=o_id,
                mode="create",
            )
            stats["linked"] += 1
        except Exception as exc:
            stats["errors"] += 1
            print(f"  ERROR {cand.id}: {exc}")

    if dry_run:
        db.rollback()
        print("DRY RUN — rolled back")
    else:
        db.commit()
        print("Committed")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-orgs", action="store_true")
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from uuid import UUID

    org_ids = None
    if args.org_id:
        org_ids = [UUID(args.org_id)]

    db = SessionLocal()
    try:
        stats = backfill(db, org_ids=org_ids, dry_run=args.dry_run)
        print(f"Done: {stats}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
