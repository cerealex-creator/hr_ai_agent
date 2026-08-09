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
    parser.add_argument("--org-id", default="", help="UUID of existing organization (optional)")
    parser.add_argument(
        "--bitrix-responsible-id",
        default="",
        help="Fixed Bitrix user id for this account (pilot)",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        org_id = None
        if str(args.org_id or "").strip():
            import uuid as _uuid

            org_id = _uuid.UUID(str(args.org_id).strip())
        user = create_user(
            db,
            email=args.email,
            password=args.password,
            role=args.role,
            full_name=args.full_name,
            organization_id=org_id,
            bitrix_responsible_id=args.bitrix_responsible_id or None,
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
