"""Find candidate groups that share the same person_id (potential duplicates).

Usage:
    python -m app.scripts.find_duplicate_groups [--org-id UUID]
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal


def find_groups(db: Session, *, org_id=None) -> list[dict]:
    q = (
        select(
            models.Candidate.person_id,
            func.count(models.Candidate.id).label("cnt"),
        )
        .where(models.Candidate.person_id.isnot(None))
        .group_by(models.Candidate.person_id)
        .having(func.count(models.Candidate.id) > 1)
    )
    if org_id:
        q = q.where(models.Candidate.organization_id == org_id)

    rows = db.execute(q).all()
    groups = []
    for person_id, cnt in rows:
        cands = list(
            db.scalars(
                select(models.Candidate).where(models.Candidate.person_id == person_id)
            ).all()
        )
        groups.append({
            "person_id": str(person_id),
            "count": cnt,
            "candidates": [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "vacancy_id": c.vacancy_id,
                    "hr_stage": c.hr_stage,
                    "phone": (c.payload or {}).get("phone", ""),
                }
                for c in cands
            ],
        })

    return groups


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", default=None)
    args = parser.parse_args()

    from uuid import UUID
    org_id = UUID(args.org_id) if args.org_id else None

    db = SessionLocal()
    try:
        groups = find_groups(db, org_id=org_id)
        print(json.dumps(groups, ensure_ascii=False, indent=2))
        print(f"\nTotal groups with shared person: {len(groups)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
