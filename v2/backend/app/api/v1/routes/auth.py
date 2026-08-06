"""Auth routes: login / refresh / logout / me (D1)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    REFRESH_COOKIE,
    AuthUser,
    auth_is_disabled,
    auth_user_from_membership,
    clear_auth_cookies,
    create_access_token,
    find_valid_refresh,
    issue_refresh_row,
    load_membership,
    require_auth,
    revoke_refresh_token,
    set_auth_cookies,
    verify_password,
)
from app.core.config import get_settings
from app.db import models
from app.db.session import get_db
from app.schemas import AuthLoginIn, AuthMeOut, AuthOkOut
from app.services.users import normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _me_out(user: AuthUser) -> AuthMeOut:
    return AuthMeOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        org_id=str(user.org_id),
        roles=list(user.roles),
        auth_disabled=user.auth_disabled,
    )


@router.post("/login", response_model=AuthMeOut)
def login(body: AuthLoginIn, response: Response, db: Session = Depends(get_db)) -> AuthMeOut:
    settings = get_settings()
    if auth_is_disabled(settings):
        from app.core.auth import _synthetic_dev_user

        return _me_out(_synthetic_dev_user(db))

    email = normalize_email(body.email)
    user = db.scalar(select(models.User).where(models.User.email == email))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    loaded = load_membership(db, user.id)
    if not loaded:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No organization membership")
    _user, member = loaded
    auth_user = auth_user_from_membership(_user, member)

    access = create_access_token(
        user_id=auth_user.id,
        org_id=auth_user.org_id,
        roles=list(auth_user.roles),
        settings=settings,
    )
    refresh = issue_refresh_row(db, user_id=auth_user.id, settings=settings)
    db.commit()
    set_auth_cookies(response, access_token=access, refresh_token=refresh, settings=settings)
    return _me_out(auth_user)


@router.post("/refresh", response_model=AuthOkOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> AuthOkOut:
    settings = get_settings()
    if auth_is_disabled(settings):
        return AuthOkOut(ok=True)

    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    row = find_valid_refresh(db, raw)
    if not row:
        clear_auth_cookies(response, settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    loaded = load_membership(db, row.user_id)
    if not loaded:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
        clear_auth_cookies(response, settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    user, member = loaded
    auth_user = auth_user_from_membership(user, member)

    # Rotate refresh
    row.revoked_at = datetime.now(timezone.utc)
    access = create_access_token(
        user_id=auth_user.id,
        org_id=auth_user.org_id,
        roles=list(auth_user.roles),
        settings=settings,
    )
    new_refresh = issue_refresh_row(db, user_id=auth_user.id, settings=settings)
    db.commit()
    set_auth_cookies(response, access_token=access, refresh_token=new_refresh, settings=settings)
    return AuthOkOut(ok=True)


@router.post("/logout", response_model=AuthOkOut)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> AuthOkOut:
    settings = get_settings()
    revoke_refresh_token(db, request.cookies.get(REFRESH_COOKIE))
    db.commit()
    clear_auth_cookies(response, settings)
    return AuthOkOut(ok=True)


@router.get("/me", response_model=AuthMeOut)
def me(user: AuthUser = Depends(require_auth)) -> AuthMeOut:
    return _me_out(user)
