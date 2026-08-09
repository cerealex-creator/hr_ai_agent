"""D1 Auth: password hashing, JWT cookies, FastAPI dependencies."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import models
from app.db.session import get_db

logger = logging.getLogger("hr_api.auth")

ACCESS_COOKIE = "hr_access"
REFRESH_COOKIE = "hr_refresh"

ROLE_PLATFORM_OWNER = "platform_owner"
ROLE_HR_RECRUITER = "hr_recruiter"
ALLOWED_ROLES = frozenset({ROLE_PLATFORM_OWNER, ROLE_HR_RECRUITER})

PUBLIC_API_PATHS = frozenset(
    {
        "/api/v1/health",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    }
)


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: str
    full_name: str
    org_id: uuid.UUID
    roles: tuple[str, ...]
    auth_disabled: bool = False
    bitrix_responsible_id: str = ""
    org_name: str = ""


def auth_is_disabled(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    if not s.auth_disabled:
        return False
    if (s.app_env or "").strip().lower() == "production":
        logger.warning("AUTH_DISABLED ignored when APP_ENV=production")
        return False
    return True


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    roles: list[str],
    settings: Settings | None = None,
) -> str:
    s = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "typ": "access",
        "sub": str(user_id),
        "org_id": str(org_id),
        "roles": list(roles),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=max(1, s.jwt_access_ttl_minutes))).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def create_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def decode_access_token(token: str, settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    if payload.get("typ") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def cookie_kwargs(settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    same = (s.auth_cookie_samesite or "lax").strip().lower()
    if same not in ("lax", "strict", "none"):
        same = "lax"
    kw: dict = {
        "httponly": True,
        "secure": bool(s.auth_cookie_secure) or same == "none",
        "samesite": same,
        "path": "/",
    }
    domain = (s.auth_cookie_domain or "").strip()
    if domain:
        kw["domain"] = domain
    return kw


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    base = cookie_kwargs(s)
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=max(60, s.jwt_access_ttl_minutes * 60),
        **base,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=max(3600, s.jwt_refresh_ttl_days * 86400),
        **base,
    )


def clear_auth_cookies(response: Response, settings: Settings | None = None) -> None:
    base = cookie_kwargs(settings)
    response.delete_cookie(ACCESS_COOKIE, **{k: v for k, v in base.items() if k != "max_age"})
    response.delete_cookie(REFRESH_COOKIE, **{k: v for k, v in base.items() if k != "max_age"})


def issue_refresh_row(
    db: Session,
    *,
    user_id: uuid.UUID,
    settings: Settings | None = None,
) -> str:
    s = settings or get_settings()
    raw = create_refresh_token_value()
    expires = datetime.now(timezone.utc) + timedelta(days=max(1, s.jwt_refresh_ttl_days))
    db.add(
        models.RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(raw),
            expires_at=expires,
        )
    )
    db.flush()
    return raw


def revoke_refresh_token(db: Session, raw: str | None) -> None:
    if not raw:
        return
    row = db.scalar(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == _hash_token(raw))
    )
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)


def find_valid_refresh(db: Session, raw: str) -> models.RefreshToken | None:
    row = db.scalar(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == _hash_token(raw))
    )
    if not row or row.revoked_at is not None:
        return None
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        return None
    return row


def load_membership(
    db: Session, user_id: uuid.UUID
) -> tuple[models.User, models.OrganizationMember] | None:
    user = db.get(models.User, user_id)
    if not user or not user.is_active:
        return None
    member = db.scalar(
        select(models.OrganizationMember)
        .where(models.OrganizationMember.user_id == user_id)
        .order_by(models.OrganizationMember.created_at.asc())
        .limit(1)
    )
    if not member:
        return None
    # Eager org name for /me
    _ = member.organization
    return user, member


def auth_user_from_membership(user: models.User, member: models.OrganizationMember) -> AuthUser:
    org_name = ""
    try:
        org = getattr(member, "organization", None)
        if org is not None:
            org_name = str(org.name or "")
    except Exception:  # noqa: BLE001
        org_name = ""
    return AuthUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        org_id=member.organization_id,
        roles=(member.role,),
        bitrix_responsible_id=str(getattr(user, "bitrix_responsible_id", None) or "").strip(),
        org_name=org_name,
    )


def _synthetic_dev_user(db: Session) -> AuthUser:
    from app.services.clients_write import ensure_default_organization

    org = ensure_default_organization(db)
    return AuthUser(
        id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        email="dev@local",
        full_name="Dev (AUTH_DISABLED)",
        org_id=org.id,
        roles=(ROLE_PLATFORM_OWNER,),
        auth_disabled=True,
    )


def is_public_api_path(path: str) -> bool:
    if path in PUBLIC_API_PATHS:
        return True
    if path.startswith("/api/v1/integrations/") and path.endswith("/webhook"):
        return True
    return False


def require_auth(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    """Require authenticated user (or AUTH_DISABLED synthetic owner). Sets thread-local for tenancy."""
    from app.services.tenancy import set_auth_user

    if auth_is_disabled(settings):
        user = _synthetic_dev_user(db)
        set_auth_user(user)
        return user

    access = request.cookies.get(ACCESS_COOKIE)
    if not access:
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.lower().startswith("bearer "):
            access = auth_header[7:].strip()
    if not access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(access, settings)
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    loaded = load_membership(db, user_id)
    if not loaded:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    user_row, member = loaded
    user = auth_user_from_membership(user_row, member)
    set_auth_user(user)
    return user


def user_is_platform_owner(user: AuthUser) -> bool:
    if user.auth_disabled:
        return True
    return ROLE_PLATFORM_OWNER in (user.roles or ())


def require_platform_owner(user: AuthUser = Depends(require_auth)) -> AuthUser:
    if not user_is_platform_owner(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется роль platform_owner",
        )
    return user
