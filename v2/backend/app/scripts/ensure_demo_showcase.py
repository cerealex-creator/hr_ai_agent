"""Seed local demo org (idempotent).

  python -m app.scripts.ensure_demo_showcase
"""
from __future__ import annotations

from app.db.session import SessionLocal
from app.services.demo_showcase import ensure_demo_showcase


def main() -> int:
    db = SessionLocal()
    try:
        org, user, created = ensure_demo_showcase(db)
        print(
            f"demo org={org.slug} user={user.email} "
            f"{'seeded' if created else 'already present'}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
