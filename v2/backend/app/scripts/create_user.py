"""CLI: create HR user (no self-register).

Usage (from v2/backend):
  .venv/bin/python -m app.scripts.create_user --email hr@example.com --password 'secret123' --role platform_owner
"""
from __future__ import annotations

import argparse
import sys

from app.core.auth import ALLOWED_ROLES, ROLE_PLATFORM_OWNER
from app.db.session import SessionLocal
from app.services.users import create_user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create v2 auth user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default=ROLE_PLATFORM_OWNER, choices=sorted(ALLOWED_ROLES))
    parser.add_argument("--full-name", default="")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        user = create_user(
            db,
            email=args.email,
            password=args.password,
            role=args.role,
            full_name=args.full_name,
        )
        print(f"Created user {user.email} id={user.id} role={args.role}")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
