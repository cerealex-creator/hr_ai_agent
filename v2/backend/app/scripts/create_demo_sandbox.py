"""Create empty Demo Sandbox org + pilot recruiter (does not touch default org).

Usage (from v2/backend):
  python -m app.scripts.create_demo_sandbox
  python -m app.scripts.create_demo_sandbox --email pilot@demo.ru --password 'password123'
"""
from __future__ import annotations

import argparse
import sys

from app.db.session import SessionLocal
from app.services.users import ensure_demo_sandbox


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create Demo Sandbox org + pilot user")
    parser.add_argument("--org-name", default="Demo Sandbox")
    parser.add_argument("--org-slug", default="demo-sandbox")
    parser.add_argument("--email", default="pilot@demo.ru")
    parser.add_argument("--password", default="password123")
    parser.add_argument("--full-name", default="Pilot Recruiter")
    parser.add_argument("--bitrix-responsible-id", default="32")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        org, user, created = ensure_demo_sandbox(
            db,
            org_name=args.org_name,
            org_slug=args.org_slug,
            email=args.email,
            password=args.password,
            full_name=args.full_name,
            bitrix_responsible_id=args.bitrix_responsible_id,
        )
        action = "Created" if created else "Exists"
        print(
            f"{action} user {user.email} id={user.id} "
            f"org={org.name!r} ({org.slug}) org_id={org.id} "
            f"bitrix_responsible_id={user.bitrix_responsible_id!r}"
        )
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
