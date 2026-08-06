"""User create / bootstrap helpers (D1 Auth)."""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ALLOWED_ROLES, ROLE_PLATFORM_OWNER, hash_password
from app.core.config import get_settings
from app.db import models
from app.services.clients_write import ensure_default_organization

logger = logging.getLogger("hr_api.users")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: str = ROLE_PLATFORM_OWNER,
    full_name: str = "",
    organization_id: uuid.UUID | None = None,
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

    user = models.User(
        email=email_n,
        password_hash=hash_password(password),
        full_name=(full_name or "").strip(),
        is_active=True,
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
