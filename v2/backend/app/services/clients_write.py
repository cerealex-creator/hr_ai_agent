"""Create clients (departments) for Settings UI."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models


def _slugify(name: str) -> str:
    raw = (name or "").strip().lower().replace(" ", "_")
    slug = re.sub(r"[^0-9a-zа-яё_\-]+", "", raw, flags=re.IGNORECASE)
    return slug or "client"


def ensure_default_organization(db: Session) -> models.Organization:
    settings = get_settings()
    org = db.scalar(
        select(models.Organization).where(models.Organization.slug == settings.default_org_slug)
    )
    if org:
        return org
    org = db.scalar(select(models.Organization).limit(1))
    if org:
        return org
    org = models.Organization(name=settings.default_org_name, slug=settings.default_org_slug)
    db.add(org)
    db.flush()
    return org


def create_client(db: Session, name: str) -> models.Client:
    title = (name or "").strip()
    if not title:
        raise ValueError("Нужно название подразделения")
    org = ensure_default_organization(db)
    existing = db.scalar(
        select(models.Client).where(
            models.Client.organization_id == org.id,
            models.Client.name == title,
        )
    )
    if existing:
        raise ValueError(f"Подразделение «{title}» уже есть")
    new_id = int(db.scalar(select(func.coalesce(func.max(models.Client.id), 0))) or 0) + 1
    base_slug = _slugify(title)
    slug = base_slug
    n = 2
    while db.scalar(select(models.Client.id).where(models.Client.slug == slug)):
        slug = f"{base_slug}_{n}"
        n += 1
    row = models.Client(
        id=new_id,
        organization_id=org.id,
        name=title,
        slug=slug,
        payload={},
    )
    db.add(row)
    db.flush()
    return row
