"""Auth routes: login / refresh / logout / me (D1)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    REFRESH_COOKIE,
    ROLE_PLATFORM_OWNER,
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
from app.schemas import (
    AuthLoginIn,
    AuthMeOut,
    AuthOkOut,
    NotifyPrefsOut,
    NotifyPrefsPut,
    UsefulLinkItem,
    UsefulLinksOut,
    UsefulLinksPut,
)
from app.services.useful_links import get_user_useful_links, set_user_useful_links
from app.services.notify_prefs import get_user_notify_prefs, set_user_notify_prefs
from app.services.users import normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _me_out(user: AuthUser) -> AuthMeOut:
    is_owner = ROLE_PLATFORM_OWNER in (user.roles or ())
    return AuthMeOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        org_id=str(user.org_id),
        org_name=user.org_name or "",
        roles=list(user.roles),
        auth_disabled=user.auth_disabled,
        bitrix_responsible_id=user.bitrix_responsible_id or "",
        # Recruiters: Telegram UI is a stub on this deploy
        telegram_available=bool(user.auth_disabled or is_owner),
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


@router.get("/useful-links", response_model=UsefulLinksOut)
def get_useful_links(
    user: AuthUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> UsefulLinksOut:
    if user.auth_disabled:
        return UsefulLinksOut(items=[], auth_disabled=True)
    items = get_user_useful_links(db, user.id)
    return UsefulLinksOut(
        items=[UsefulLinkItem(**x) for x in items],
        auth_disabled=False,
    )


@router.put("/useful-links", response_model=UsefulLinksOut)
def put_useful_links(
    body: UsefulLinksPut,
    user: AuthUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> UsefulLinksOut:
    if user.auth_disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="При AUTH_DISABLED свои ссылки хранятся в браузере",
        )
    try:
        items = set_user_useful_links(db, user.id, [x.model_dump() for x in body.items])
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return UsefulLinksOut(
        items=[UsefulLinkItem(**x) for x in items],
        auth_disabled=False,
    )


def _notify_out(prefs: dict, *, auth_disabled: bool = False) -> NotifyPrefsOut:
    chat = str(prefs.get("telegram_chat_id") or "").strip()
    return NotifyPrefsOut(
        google_calendar_enabled=bool(prefs.get("google_calendar_enabled", False)),
        telegram_enabled=bool(prefs.get("telegram_enabled", False)),
        telegram_chat_id=chat,
        telegram_period=str(prefs.get("telegram_period") or "digest_admin"),
        telegram_text=str(prefs.get("telegram_text") or ""),
        auth_disabled=auth_disabled,
        telegram_bound=bool(chat),
    )


@router.get("/notify-prefs", response_model=NotifyPrefsOut)
def get_notify_prefs(
    user: AuthUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> NotifyPrefsOut:
    if user.auth_disabled:
        from app.services.notify_prefs import DEFAULT_NOTIFY_PREFS

        return _notify_out(DEFAULT_NOTIFY_PREFS, auth_disabled=True)
    prefs = get_user_notify_prefs(db, user.id)
    return _notify_out(prefs)


@router.put("/notify-prefs", response_model=NotifyPrefsOut)
def put_notify_prefs(
    body: NotifyPrefsPut,
    user: AuthUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> NotifyPrefsOut:
    if user.auth_disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="При AUTH_DISABLED настройки уведомлений хранятся в браузере",
        )
    patch = body.model_dump(exclude_unset=True)
    is_owner = ROLE_PLATFORM_OWNER in (user.roles or ()) or user.auth_disabled
    if not is_owner:
        # Recruiters cannot enable Telegram notify on this deploy
        for key in ("telegram_enabled", "telegram_chat_id", "telegram_period", "telegram_text"):
            patch.pop(key, None)
    try:
        prefs = set_user_notify_prefs(db, user.id, patch)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
    db.commit()
    return _notify_out(prefs)
