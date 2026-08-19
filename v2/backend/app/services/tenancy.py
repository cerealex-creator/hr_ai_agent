"""D2 tenancy: org isolation helpers (no Postgres RLS)."""
from __future__ import annotations

import secrets
import uuid
from contextvars import ContextVar

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthUser
from app.db import models

_request_ctx: ContextVar[Request | None] = ContextVar("tenancy_request", default=None)


def bind_request(request: Request):
    return _request_ctx.set(request)


def reset_request(token) -> None:
    _request_ctx.reset(token)


def set_auth_user(user: AuthUser | None) -> None:
    """Attach user to current request.state (shared across threadpool)."""
    request = _request_ctx.get()
    if request is not None:
        request.state.auth_user = user


def current_user() -> AuthUser | None:
    request = _request_ctx.get()
    if request is None:
        return None
    return getattr(request.state, "auth_user", None)


def is_demo_user() -> bool:
    user = current_user()
    return bool(user and user.is_demo)


def require_current_user() -> AuthUser:
    user = current_user()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_org_id() -> uuid.UUID:
    return require_current_user().org_id


def current_org_integrations() -> dict:
    """Return current org's integrations JSONB (features, tokens, etc.)."""
    from app.db.session import SessionLocal
    org_id = require_org_id()
    db = SessionLocal()
    try:
        org = db.get(models.Organization, org_id)
        return dict(org.integrations or {}) if org else {}
    finally:
        db.close()


def org_client_ids(db: Session, org_id: uuid.UUID) -> set[int]:
    rows = db.scalars(
        select(models.Client.id).where(models.Client.organization_id == org_id)
    ).all()
    return {int(x) for x in rows}


def org_vacancy_ids(db: Session, org_id: uuid.UUID) -> set[int]:
    client_ids = org_client_ids(db, org_id)
    if not client_ids:
        return set()
    rows = db.scalars(
        select(models.Vacancy.id).where(models.Vacancy.client_id.in_(client_ids))
    ).all()
    return {int(x) for x in rows}


def client_in_org(db: Session, client: models.Client | None, org_id: uuid.UUID) -> bool:
    return bool(client and client.organization_id == org_id)


def vacancy_org_id(db: Session, vacancy: models.Vacancy | None) -> uuid.UUID | None:
    if not vacancy or vacancy.client_id is None:
        return None
    client = db.get(models.Client, vacancy.client_id)
    return client.organization_id if client else None


def candidate_org_id(db: Session, candidate: models.Candidate | None) -> uuid.UUID | None:
    if not candidate:
        return None
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    return vacancy_org_id(db, vacancy)


def get_client_or_404(db: Session, client_id: int, org_id: uuid.UUID | None = None) -> models.Client:
    oid = org_id if org_id is not None else require_org_id()
    client = db.get(models.Client, int(client_id))
    if not client_in_org(db, client, oid):
        raise HTTPException(status_code=404, detail="Client not found")
    return client  # type: ignore[return-value]


def get_vacancy_or_404(db: Session, vacancy_id: int, org_id: uuid.UUID | None = None) -> models.Vacancy:
    oid = org_id if org_id is not None else require_org_id()
    vacancy = db.get(models.Vacancy, int(vacancy_id))
    if not vacancy or vacancy_org_id(db, vacancy) != oid:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return vacancy


def get_candidate_or_404(
    db: Session, candidate_id: uuid.UUID | str, org_id: uuid.UUID | None = None
) -> models.Candidate:
    oid = org_id if org_id is not None else require_org_id()
    try:
        cid = candidate_id if isinstance(candidate_id, uuid.UUID) else uuid.UUID(str(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Candidate not found") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate or candidate_org_id(db, candidate) != oid:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


def get_job_or_404(db: Session, job_id: uuid.UUID | str, org_id: uuid.UUID | None = None) -> models.Job:
    oid = org_id if org_id is not None else require_org_id()
    try:
        jid = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    job = db.get(models.Job, jid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job_in_org(db, job, oid):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def job_in_org(db: Session, job: models.Job, org_id: uuid.UUID) -> bool:
    if job.vacancy_id is not None:
        vac = db.get(models.Vacancy, job.vacancy_id)
        return vacancy_org_id(db, vac) == org_id
    if job.client_id is not None:
        client = db.get(models.Client, job.client_id)
        return client_in_org(db, client, org_id)
    return False


def filter_clients_query(q, org_id: uuid.UUID):
    return q.where(models.Client.organization_id == org_id)


def root_company_scope_ids(db: Session, root: models.Client) -> set[int]:
    """Root company + all departments under it."""
    ids = {int(root.id)}
    children = db.scalars(
        select(models.Client.id).where(models.Client.parent_id == root.id)
    ).all()
    ids.update(int(x) for x in children)
    return ids


def generate_client_zone_token(db: Session | None = None) -> str:
    for _ in range(8):
        token = secrets.token_urlsafe(24)
        if db is None:
            return token
        exists = db.scalar(
            select(models.Client.id).where(models.Client.client_zone_token == token)
        )
        if exists is None:
            return token
    return secrets.token_urlsafe(32)


def resolve_client_zone_root(db: Session, token: str) -> models.Client:
    """Resolve company or department that owns this public zone token."""
    raw = (token or "").strip()
    if not raw:
        raise HTTPException(status_code=404, detail="Zone not found")
    owner = db.scalar(select(models.Client).where(models.Client.client_zone_token == raw))
    if not owner:
        raise HTTPException(status_code=404, detail="Zone not found")
    return owner


def zone_owner_scope_ids(owner: models.Client) -> set[int]:
    """One zone = one client: company-level vacancies or a single department."""
    return {int(owner.id)}


def ensure_root_for_zone(db: Session, client: models.Client) -> models.Client:
    """Walk up to the root company (not used for zone tokens)."""
    if client.parent_id is None:
        return client
    parent = db.get(models.Client, client.parent_id)
    if not parent:
        raise HTTPException(status_code=400, detail="Root company not found")
    return parent


def rotate_client_zone_token(db: Session, owner: models.Client) -> str:
    token = generate_client_zone_token(db)
    owner.client_zone_token = token
    db.commit()
    db.refresh(owner)
    return token
