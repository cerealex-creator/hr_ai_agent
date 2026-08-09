"""User create / bootstrap helpers (D1 Auth)."""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.auth import ALLOWED_ROLES, ROLE_HR_RECRUITER, ROLE_PLATFORM_OWNER, hash_password
from app.core.config import get_settings
from app.db import models
from app.services.clients_write import ensure_default_organization

logger = logging.getLogger("hr_api.users")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def ensure_bitrix_responsible_column(db: Session) -> None:
    """Idempotent bootstrap when Alembic lag / lock."""
    db.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bitrix_responsible_id "
            "VARCHAR(64) NULL"
        )
    )
    db.commit()


def create_organization(
    db: Session,
    *,
    name: str,
    slug: str,
) -> models.Organization:
    name_n = (name or "").strip()
    slug_n = (slug or "").strip().lower()
    if not name_n:
        raise ValueError("Organization name required")
    if not slug_n or not _SLUG_RE.match(slug_n):
        raise ValueError("Organization slug must be lowercase latin/digits with hyphens")
    existing = db.scalar(select(models.Organization).where(models.Organization.slug == slug_n))
    if existing:
        return existing
    org = models.Organization(name=name_n, slug=slug_n)
    db.add(org)
    db.flush()
    return org


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: str = ROLE_PLATFORM_OWNER,
    full_name: str = "",
    organization_id: uuid.UUID | None = None,
    bitrix_responsible_id: str | None = None,
) -> models.User:
    email_n = normalize_email(email)
    if not email_n or not _EMAIL_RE.match(email_n):
        raise ValueError("Invalid email")
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters")
    role_n = (role or ROLE_PLATFORM_OWNER).strip()
    if role_n not in ALLOWED_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(ALLOWED_ROLES))}")

    existing = db.scalar(select(models.User).where(models.User.email == email_n))
    if existing:
        raise ValueError(f"User already exists: {email_n}")

    org_id = organization_id
    if org_id is None:
        org_id = ensure_default_organization(db).id

    bx_id = str(bitrix_responsible_id or "").strip() or None

    user = models.User(
        email=email_n,
        password_hash=hash_password(password),
        full_name=(full_name or "").strip(),
        is_active=True,
        bitrix_responsible_id=bx_id,
    )
    db.add(user)
    db.flush()
    db.add(
        models.OrganizationMember(
            organization_id=org_id,
            user_id=user.id,
            role=role_n,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def ensure_demo_sandbox(
    db: Session,
    *,
    org_name: str = "Demo Sandbox",
    org_slug: str = "demo-sandbox",
    email: str = "pilot@demo.ru",
    password: str = "password123",
    full_name: str = "Pilot Recruiter",
    bitrix_responsible_id: str = "32",
) -> tuple[models.Organization, models.User, bool]:
    """Create empty demo org + recruiter if missing. Returns (org, user, created_user)."""
    ensure_bitrix_responsible_column(db)
    org = create_organization(db, name=org_name, slug=org_slug)
    db.commit()
    db.refresh(org)

    email_n = normalize_email(email)
    existing = db.scalar(select(models.User).where(models.User.email == email_n))
    if existing:
        # Keep membership on demo org; refresh fixed Bitrix id if empty
        if not (existing.bitrix_responsible_id or "").strip() and bitrix_responsible_id:
            existing.bitrix_responsible_id = str(bitrix_responsible_id).strip()
            db.commit()
            db.refresh(existing)
        return org, existing, False

    user = create_user(
        db,
        email=email_n,
        password=password,
        role=ROLE_HR_RECRUITER,
        full_name=full_name,
        organization_id=org.id,
        bitrix_responsible_id=bitrix_responsible_id,
    )
    return org, user, True


def ensure_bootstrap_user(db: Session) -> models.User | None:
    """Create owner from AUTH_BOOTSTRAP_* env if set and user missing."""
    settings = get_settings()
    email = normalize_email(settings.auth_bootstrap_email)
    password = settings.auth_bootstrap_password or ""
    if not email or not password:
        return None
    existing = db.scalar(select(models.User).where(models.User.email == email))
    if existing:
        return existing
    role = (settings.auth_bootstrap_role or ROLE_PLATFORM_OWNER).strip()
    try:
        user = create_user(db, email=email, password=password, role=role, full_name="Bootstrap Owner")
        logger.info("Bootstrap user created: %s", email)
        return user
    except ValueError as exc:
        logger.warning("Bootstrap user skipped: %s", exc)
        return None
