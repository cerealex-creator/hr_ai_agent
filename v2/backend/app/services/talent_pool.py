"""Talent pool service: CRUD, import from files, take to vacancy."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.person_match import normalize_email, normalize_name, normalize_phone


def list_pool_entries(
    db: Session,
    *,
    organization_id: uuid.UUID,
    q: str | None = None,
    tags: list[str] | None = None,
    limit: int = 200,
) -> list[models.TalentPoolEntry]:
    query = (
        select(models.TalentPoolEntry)
        .where(models.TalentPoolEntry.organization_id == organization_id)
        .order_by(models.TalentPoolEntry.created_at.desc())
        .limit(limit)
    )
    if q:
        query = query.where(models.TalentPoolEntry.display_name.ilike(f"%{q}%"))
    if tags:
        query = query.where(models.TalentPoolEntry.tags.overlap(tags))
    return list(db.scalars(query).all())


def get_pool_entry(db: Session, entry_id: uuid.UUID) -> models.TalentPoolEntry | None:
    return db.get(models.TalentPoolEntry, entry_id)


def create_pool_entry(
    db: Session,
    *,
    organization_id: uuid.UUID,
    display_name: str,
    phone: str | None = None,
    email: str | None = None,
    source_filename: str | None = None,
    mime_type: str | None = None,
    resume_text: str | None = None,
    payload: dict | None = None,
    tags: list[str] | None = None,
) -> models.TalentPoolEntry:
    m_phone = normalize_phone(phone)
    m_email = normalize_email(email)
    m_name = normalize_name(display_name)

    entry = models.TalentPoolEntry(
        id=uuid.uuid4(),
        organization_id=organization_id,
        display_name=display_name.strip() or "Без имени",
        match_phone=m_phone,
        match_email=m_email,
        match_name=m_name,
        source_filename=source_filename,
        mime_type=mime_type,
        payload=payload or {},
        tags=tags or [],
    )

    if resume_text:
        p = dict(entry.payload)
        p["resume_text"] = resume_text
        entry.payload = p

    db.add(entry)
    db.flush()
    return entry


def take_to_vacancy(
    db: Session,
    entry: models.TalentPoolEntry,
    vacancy_id: int,
) -> models.Candidate:
    """Create a candidate on a vacancy from a talent pool entry."""
    from app.services.candidate_write import create_candidate

    p = entry.payload or {}
    fields: dict[str, Any] = {}
    if entry.match_phone:
        fields["phone"] = entry.match_phone
    if entry.match_email:
        fields["email"] = entry.match_email
    if p.get("city"):
        fields["city"] = p["city"]
    if p.get("resume_link"):
        fields["resume_link"] = p["resume_link"]

    cand = create_candidate(
        db,
        vacancy_id=vacancy_id,
        name=entry.display_name,
        fields=fields,
        org_id=entry.organization_id,
    )

    payload = dict(cand.payload or {})
    payload["source"] = "talent_pool"
    payload["talent_pool_entry_id"] = str(entry.id)
    cand.payload = payload
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(cand, "payload")

    if entry.person_id:
        cand.person_id = entry.person_id

    db.commit()
    db.refresh(cand)
    return cand
