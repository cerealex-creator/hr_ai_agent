"""Verify that all candidates have person_id. Exit 1 if any NULL found.

Usage:
    python -m app.scripts.verify_person_coverage
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.db import models
from app.db.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(models.Candidate.id)))
        missing = db.scalar(
            select(func.count(models.Candidate.id)).where(models.Candidate.person_id.is_(None))
        )
        print(f"Total candidates: {total}")
        print(f"Missing person_id: {missing}")
        if missing:
            print("FAIL — run backfill_persons first")
            raise SystemExit(1)
        print("OK — all candidates have person_id")
    finally:
        db.close()


if __name__ == "__main__":
    main()
