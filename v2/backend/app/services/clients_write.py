"""Company / department tree for Settings (YourBox multi-chat, Pulse single-chat, test)."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.messaging.channels import (
    ChannelError,
    create_channel,
    list_channels,
    normalize_external_id,
    sync_vacancy_chat_ids_from_channels,
    update_channel,
)

CHAT_MODE_COMPANY = "company"
CHAT_MODE_DEPARTMENTS = "departments"
KIND_COMPANY = "company"
KIND_DEPARTMENT = "department"
KIND_TEST = "test"

YOURBOX_DEPT_NAMES = {
    "Маркетинг",
    "Продажи",
    "Бухгалтерия",
    "Склад",
    "Логистика",
    "Руководители",
}


class ClientError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


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


def ensure_client_schema(db: Session) -> None:
    """Add company-tree columns if missing (MVP without Alembic)."""
    stmts = [
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES clients(id)",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS chat_mode VARCHAR(32) NOT NULL DEFAULT 'company'",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS kind VARCHAR(32) NOT NULL DEFAULT 'company'",
    ]
    for sql in stmts:
        db.execute(text(sql))
    db.commit()


def _next_client_id(db: Session) -> int:
    return int(db.scalar(select(func.coalesce(func.max(models.Client.id), 0))) or 0) + 1


def _unique_slug(db: Session, title: str) -> str:
    base_slug = _slugify(title)
    slug = base_slug
    n = 2
    while db.scalar(select(models.Client.id).where(models.Client.slug == slug)):
        slug = f"{base_slug}_{n}"
        n += 1
    return slug


def channel_for_client(db: Session, client_id: int) -> models.MessagingChannel | None:
    return db.scalar(
        select(models.MessagingChannel)
        .where(models.MessagingChannel.client_id == int(client_id))
        .order_by(models.MessagingChannel.name)
        .limit(1)
    )


def migrate_legacy_clients(db: Session) -> dict:
    """
    One-time structure:
    - YourBox company (departments) ← existing dept clients 1–6
    - Pulse stays root company mode
    - Тестировочный → kind=test
    """
    ensure_client_schema(db)
    org = ensure_default_organization(db)
    stats = {"yourbox_created": False, "depts_linked": 0, "pulse": False, "test": False}

    # Mark Pulse
    pulse = db.scalar(select(models.Client).where(models.Client.name.ilike("%пульс%")))
    if pulse:
        pulse.kind = KIND_COMPANY
        pulse.chat_mode = CHAT_MODE_COMPANY
        pulse.parent_id = None
        stats["pulse"] = True

    # Mark test
    test = db.scalar(
        select(models.Client).where(
            (models.Client.name.ilike("%тестир%")) | (models.Client.id == 99)
        )
    )
    if test:
        test.kind = KIND_TEST
        test.chat_mode = CHAT_MODE_COMPANY
        test.parent_id = None
        stats["test"] = True

    # YourBox departments (legacy flat clients)
    dept_rows = [
        c
        for c in db.scalars(select(models.Client)).all()
        if c.name in YOURBOX_DEPT_NAMES and (c.parent_id is None or c.kind != KIND_COMPANY)
    ]
    # Also match by known ids 1-6 if names differ slightly
    for cid in range(1, 7):
        row = db.get(models.Client, cid)
        if row and row not in dept_rows and row.kind != KIND_TEST:
            if pulse and row.id == pulse.id:
                continue
            dept_rows.append(row)
    # unique
    seen: set[int] = set()
    depts: list[models.Client] = []
    for d in dept_rows:
        if d.id in seen:
            continue
        if pulse and d.id == pulse.id:
            continue
        if test and d.id == test.id:
            continue
        seen.add(d.id)
        depts.append(d)

    yourbox = db.scalar(
        select(models.Client).where(
            models.Client.kind == KIND_COMPANY,
            models.Client.name.ilike("yourbox"),
        )
    )
    if not yourbox and depts:
        yourbox = models.Client(
            id=_next_client_id(db),
            organization_id=org.id,
            name="YourBox",
            slug=_unique_slug(db, "YourBox"),
            payload={},
            parent_id=None,
            chat_mode=CHAT_MODE_DEPARTMENTS,
            kind=KIND_COMPANY,
        )
        db.add(yourbox)
        db.flush()
        stats["yourbox_created"] = True

    if yourbox:
        yourbox.kind = KIND_COMPANY
        yourbox.chat_mode = CHAT_MODE_DEPARTMENTS
        yourbox.parent_id = None
        for d in depts:
            d.parent_id = yourbox.id
            d.kind = KIND_DEPARTMENT
            d.chat_mode = CHAT_MODE_COMPANY
            stats["depts_linked"] += 1

    # Any remaining root without kind test/company with children → company
    for c in db.scalars(select(models.Client).where(models.Client.parent_id.is_(None))).all():
        if c.kind == KIND_TEST:
            continue
        kids = db.scalars(select(models.Client).where(models.Client.parent_id == c.id)).all()
        if kids:
            c.kind = KIND_COMPANY
            if c.chat_mode not in (CHAT_MODE_COMPANY, CHAT_MODE_DEPARTMENTS):
                c.chat_mode = CHAT_MODE_DEPARTMENTS
        elif c.kind not in (KIND_COMPANY, KIND_TEST):
            c.kind = KIND_COMPANY
            c.chat_mode = CHAT_MODE_COMPANY

    db.commit()
    return stats


def create_client(
    db: Session,
    name: str,
    *,
    parent_id: int | None = None,
    chat_mode: str = CHAT_MODE_COMPANY,
    kind: str | None = None,
) -> models.Client:
    title = (name or "").strip()
    if not title:
        raise ClientError("Нужно название")
    from app.services.tenancy import current_user

    user = current_user()
    if user is not None:
        org_id = user.org_id
    else:
        org_id = ensure_default_organization(db).id
    parent = None
    if parent_id is not None:
        parent = db.get(models.Client, int(parent_id))
        if not parent or parent.organization_id != org_id:
            raise ClientError("Компания не найдена", 404)
        if parent.kind != KIND_COMPANY:
            raise ClientError("Подразделение можно создать только внутри компании")
        kind = KIND_DEPARTMENT
        chat_mode = CHAT_MODE_COMPANY
    else:
        kind = kind or KIND_COMPANY
        if chat_mode not in (CHAT_MODE_COMPANY, CHAT_MODE_DEPARTMENTS):
            raise ClientError("chat_mode: company | departments")

    existing = db.scalar(
        select(models.Client).where(
            models.Client.organization_id == org_id,
            models.Client.name == title,
            models.Client.parent_id == (int(parent_id) if parent_id is not None else None),
        )
    )
    if existing:
        raise ClientError(f"«{title}» уже есть")

    row = models.Client(
        id=_next_client_id(db),
        organization_id=org_id,
        name=title,
        slug=_unique_slug(db, title),
        payload={},
        parent_id=int(parent_id) if parent_id is not None else None,
        chat_mode=chat_mode,
        kind=kind,
    )
    db.add(row)
    db.flush()
    return row


def create_company(db: Session, name: str, chat_mode: str = CHAT_MODE_COMPANY) -> models.Client:
    row = create_client(db, name, chat_mode=chat_mode, kind=KIND_COMPANY)
    db.commit()
    db.refresh(row)
    return row


def ensure_org_root_company(
    db: Session,
    org_id: uuid.UUID | None = None,
    *,
    default_name: str = "Моя компания",
) -> models.Client:
    """Return an existing root company in the org, or create one (empty sandbox)."""
    from app.services.tenancy import current_user

    oid = org_id
    if oid is None:
        user = current_user()
        if user is None:
            raise ClientError("Нужна авторизация", 401)
        oid = user.org_id

    root = db.scalar(
        select(models.Client)
        .where(
            models.Client.organization_id == oid,
            models.Client.parent_id.is_(None),
            models.Client.kind.in_((KIND_COMPANY, KIND_TEST)),
        )
        .order_by(models.Client.id.asc())
        .limit(1)
    )
    if root:
        return root

    # Any root client in org (legacy / mis-tagged)
    root = db.scalar(
        select(models.Client)
        .where(
            models.Client.organization_id == oid,
            models.Client.parent_id.is_(None),
        )
        .order_by(models.Client.id.asc())
        .limit(1)
    )
    if root:
        if root.kind not in (KIND_COMPANY, KIND_TEST):
            root.kind = KIND_COMPANY
        return root

    row = models.Client(
        id=_next_client_id(db),
        organization_id=oid,
        name=(default_name or "Моя компания").strip() or "Моя компания",
        slug=_unique_slug(db, default_name or "company"),
        payload={},
        parent_id=None,
        chat_mode=CHAT_MODE_COMPANY,
        kind=KIND_COMPANY,
    )
    db.add(row)
    db.flush()
    return row


def patch_client(
    db: Session,
    client: models.Client,
    *,
    name: str | None = None,
    chat_mode: str | None = None,
) -> models.Client:
    if name is not None:
        title = name.strip()
        if not title:
            raise ClientError("Нужно название")
        client.name = title
    if chat_mode is not None:
        if client.kind != KIND_COMPANY:
            raise ClientError("Режим чатов задаётся только для компании")
        if chat_mode not in (CHAT_MODE_COMPANY, CHAT_MODE_DEPARTMENTS):
            raise ClientError("chat_mode: company | departments")
        # Switching to company mode: keep departments but primary chat stays on company
        # Switching to departments: require at least ability to add depts
        client.chat_mode = chat_mode
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client: models.Client) -> None:
    if client.kind == KIND_COMPANY:
        kids = list(db.scalars(select(models.Client).where(models.Client.parent_id == client.id)))
        if kids:
            raise ClientError("Сначала удалите или перенесите подразделения")
    vac_count = db.scalar(
        select(func.count()).select_from(models.Vacancy).where(models.Vacancy.client_id == client.id)
    )
    if vac_count:
        raise ClientError(f"Нельзя удалить: есть вакансии ({vac_count})")
    # Unbind channels
    for ch in db.scalars(
        select(models.MessagingChannel).where(models.MessagingChannel.client_id == client.id)
    ):
        ch.client_id = None
    db.delete(client)
    db.commit()


def list_companies(db: Session, organization_id=None) -> list[models.Client]:
    q = select(models.Client).where(
        models.Client.kind == KIND_COMPANY, models.Client.parent_id.is_(None)
    )
    if organization_id is not None:
        q = q.where(models.Client.organization_id == organization_id)
    return list(db.scalars(q.order_by(models.Client.name)).all())


def list_departments(db: Session, company_id: int) -> list[models.Client]:
    return list(
        db.scalars(
            select(models.Client)
            .where(models.Client.parent_id == int(company_id))
            .order_by(models.Client.name)
        ).all()
    )


def get_test_client(db: Session) -> models.Client | None:
    return db.scalar(
        select(models.Client).where(models.Client.kind == KIND_TEST).order_by(models.Client.id)
    )


def ensure_test_client(db: Session) -> models.Client:
    row = get_test_client(db)
    if row:
        return row
    row = create_client(db, "Тестировочный", kind=KIND_TEST, chat_mode=CHAT_MODE_COMPANY)
    db.commit()
    db.refresh(row)
    return row


def set_test_chat(db: Session, *, name: str, chat_id: str) -> tuple[models.Client, models.MessagingChannel]:
    client = ensure_test_client(db)
    title = (name or "").strip() or "Тестировочный"
    client.name = title
    external = normalize_external_id(chat_id)
    if not external:
        raise ClientError("Некорректный Chat ID")
    existing = channel_for_client(db, client.id)
    if existing:
        ch = update_channel(db, existing, name=title, chat_id=external, client_id=client.id)
    else:
        # Reuse channel with same chat_id if unbound / retarget
        found = db.scalar(
            select(models.MessagingChannel).where(
                models.MessagingChannel.provider == "telegram",
                models.MessagingChannel.external_id == external,
            )
        )
        if found:
            ch = update_channel(db, found, name=title, client_id=client.id)
        else:
            try:
                ch = create_channel(db, name=title, chat_id=external, client_id=client.id)
            except ChannelError as exc:
                raise ClientError(str(exc), getattr(exc, "status_code", 400)) from exc
    db.commit()
    db.refresh(client)
    db.refresh(ch)
    return client, ch


def clear_test_chat(db: Session) -> None:
    client = get_test_client(db)
    if not client:
        return
    for ch in db.scalars(
        select(models.MessagingChannel).where(models.MessagingChannel.client_id == client.id)
    ):
        ch.client_id = None
    sync_vacancy_chat_ids_from_channels(db)
    db.commit()


def selectable_clients_for_vacancies(db: Session, organization_id=None) -> list[models.Client]:
    """Leaves shown in vacancy forms / sidebar (exclude pure company shells in dept mode, exclude test)."""
    q = select(models.Client).order_by(models.Client.name)
    if organization_id is not None:
        q = q.where(models.Client.organization_id == organization_id)
    rows = list(db.scalars(q).all())
    out: list[models.Client] = []
    for c in rows:
        if c.kind == KIND_TEST:
            continue
        if c.kind == KIND_COMPANY and c.chat_mode == CHAT_MODE_DEPARTMENTS:
            # company shell — vacancies attach to departments
            continue
        out.append(c)
    return out


def client_to_dict(db: Session, c: models.Client, *, with_channel: bool = True) -> dict:
    ch = channel_for_client(db, c.id) if with_channel else None
    d = {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "parent_id": c.parent_id,
        "chat_mode": c.chat_mode,
        "kind": c.kind,
        "channel": (
            {
                "id": str(ch.id),
                "name": ch.name,
                "external_id": ch.external_id,
            }
            if ch
            else None
        ),
    }
    d["client_zone_token"] = c.client_zone_token
    d["has_client_zone"] = bool(c.client_zone_token)
    return d


def company_tree(db: Session, organization_id=None) -> list[dict]:
    companies = list_companies(db, organization_id=organization_id)
    result = []
    for co in companies:
        node = client_to_dict(db, co)
        node["departments"] = [client_to_dict(db, d) for d in list_departments(db, co.id)]
        result.append(node)
    return result
