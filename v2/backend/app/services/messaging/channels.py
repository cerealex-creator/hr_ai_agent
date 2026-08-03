"""Resolve / sync messaging channels from vacancy.chat_id and Settings CRUD."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models

PROVIDER_TELEGRAM = "telegram"


class ChannelError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_external_id(chat_id: str | int | None) -> str | None:
    if chat_id is None:
        return None
    text = str(chat_id).strip()
    if not text:
        return None
    try:
        return str(int(text))
    except ValueError:
        return text


def is_system_channel(external_id: str | None) -> bool:
    return str(external_id or "").startswith("__")


def ensure_channel_for_vacancy(db: Session, vacancy: models.Vacancy) -> models.MessagingChannel | None:
    external_id = normalize_external_id(vacancy.chat_id)
    if not external_id:
        return None

    row = db.scalar(
        select(models.MessagingChannel).where(
            models.MessagingChannel.provider == PROVIDER_TELEGRAM,
            models.MessagingChannel.external_id == external_id,
        )
    )
    title = (vacancy.title or "").strip() or f"chat {external_id}"
    if row:
        if vacancy.client_id is not None and row.client_id is None:
            row.client_id = vacancy.client_id
        if not row.name:
            row.name = title
        db.flush()
        return row

    row = models.MessagingChannel(
        provider=PROVIDER_TELEGRAM,
        external_id=external_id,
        client_id=vacancy.client_id,
        name=title,
        metadata_json={"source": "vacancy.chat_id", "vacancy_ids": [vacancy.id]},
    )
    db.add(row)
    db.flush()
    return row


def sync_channels_from_vacancies(db: Session) -> dict[str, int]:
    vacancies = list(db.scalars(select(models.Vacancy)).all())
    created = 0
    updated = 0
    skipped = 0
    for vac in vacancies:
        external_id = normalize_external_id(vac.chat_id)
        if not external_id:
            skipped += 1
            continue
        existing = db.scalar(
            select(models.MessagingChannel).where(
                models.MessagingChannel.provider == PROVIDER_TELEGRAM,
                models.MessagingChannel.external_id == external_id,
            )
        )
        if existing:
            meta = dict(existing.metadata_json or {})
            ids = list(meta.get("vacancy_ids") or [])
            if vac.id not in ids:
                ids.append(vac.id)
                meta["vacancy_ids"] = ids
                existing.metadata_json = meta
                flag_modified(existing, "metadata_json")
            if vac.client_id is not None:
                existing.client_id = vac.client_id
            if not existing.name and vac.title:
                existing.name = vac.title
            updated += 1
        else:
            ensure_channel_for_vacancy(db, vac)
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "skipped_no_chat": skipped}


def sync_vacancy_chat_ids_from_channels(db: Session) -> int:
    """Align vacancy.chat_id to channels by client_id (Settings = source of truth)."""
    by_client: dict[int, str] = {}
    for ch in db.scalars(select(models.MessagingChannel)).all():
        if is_system_channel(ch.external_id) or ch.client_id is None:
            continue
        by_client[int(ch.client_id)] = str(ch.external_id)

    changed = 0
    for vac in db.scalars(select(models.Vacancy)).all():
        if vac.client_id is None:
            continue
        canonical = by_client.get(int(vac.client_id))
        if canonical is None:
            continue
        current = normalize_external_id(vac.chat_id) or ""
        if current != canonical:
            vac.chat_id = canonical
            changed += 1
    return changed


def list_channels(db: Session, *, include_system: bool = False) -> list[models.MessagingChannel]:
    rows = list(
        db.scalars(
            select(models.MessagingChannel).order_by(models.MessagingChannel.name)
        ).all()
    )
    if include_system:
        return rows
    return [r for r in rows if not is_system_channel(r.external_id)]


def create_channel(
    db: Session,
    *,
    name: str,
    chat_id: str,
    client_id: int | None = None,
    sync_vacancies: bool = True,
) -> models.MessagingChannel:
    title = (name or "").strip()
    external_id = normalize_external_id(chat_id)
    if not title:
        raise ChannelError("Нужно название чата")
    if not external_id:
        raise ChannelError("Некорректный Chat ID")
    if is_system_channel(external_id):
        raise ChannelError("Зарезервированный chat_id")

    if client_id is not None and not db.get(models.Client, int(client_id)):
        raise ChannelError("Подразделение не найдено", 404)

    dup_id = db.scalar(
        select(models.MessagingChannel).where(
            models.MessagingChannel.provider == PROVIDER_TELEGRAM,
            models.MessagingChannel.external_id == external_id,
        )
    )
    if dup_id:
        raise ChannelError("Чат с таким Chat ID уже есть")

    dup_name = db.scalar(
        select(models.MessagingChannel).where(
            models.MessagingChannel.provider == PROVIDER_TELEGRAM,
            models.MessagingChannel.name == title,
        )
    )
    if dup_name and not is_system_channel(dup_name.external_id):
        raise ChannelError("Чат с таким именем уже есть")

    row = models.MessagingChannel(
        provider=PROVIDER_TELEGRAM,
        external_id=external_id,
        client_id=int(client_id) if client_id is not None else None,
        name=title,
        metadata_json={"source": "settings"},
    )
    db.add(row)
    db.flush()
    if sync_vacancies:
        sync_vacancy_chat_ids_from_channels(db)
    db.commit()
    db.refresh(row)
    return row


def update_channel(
    db: Session,
    channel: models.MessagingChannel,
    *,
    name: str | None = None,
    chat_id: str | None = None,
    client_id: int | None | object = ...,
    sync_vacancies: bool = True,
) -> models.MessagingChannel:
    if is_system_channel(channel.external_id):
        raise ChannelError("Системный канал нельзя менять")

    if name is not None:
        title = name.strip()
        if not title:
            raise ChannelError("Нужно название чата")
        dup = db.scalar(
            select(models.MessagingChannel).where(
                models.MessagingChannel.provider == PROVIDER_TELEGRAM,
                models.MessagingChannel.name == title,
                models.MessagingChannel.id != channel.id,
            )
        )
        if dup and not is_system_channel(dup.external_id):
            raise ChannelError("Чат с таким именем уже есть")
        channel.name = title

    if chat_id is not None:
        external_id = normalize_external_id(chat_id)
        if not external_id:
            raise ChannelError("Некорректный Chat ID")
        if is_system_channel(external_id):
            raise ChannelError("Зарезервированный chat_id")
        dup = db.scalar(
            select(models.MessagingChannel).where(
                models.MessagingChannel.provider == PROVIDER_TELEGRAM,
                models.MessagingChannel.external_id == external_id,
                models.MessagingChannel.id != channel.id,
            )
        )
        if dup:
            raise ChannelError("Чат с таким Chat ID уже есть")
        channel.external_id = external_id

    if client_id is not ...:
        if client_id is not None and not db.get(models.Client, int(client_id)):
            raise ChannelError("Подразделение не найдено", 404)
        channel.client_id = int(client_id) if client_id is not None else None

    db.flush()
    if sync_vacancies:
        sync_vacancy_chat_ids_from_channels(db)
    db.commit()
    db.refresh(channel)
    return channel


def delete_channel(db: Session, channel: models.MessagingChannel) -> None:
    if is_system_channel(channel.external_id):
        raise ChannelError("Системный канал нельзя удалить")

    posts = list(
        db.scalars(
            select(models.MessagingPost).where(models.MessagingPost.channel_id == channel.id)
        ).all()
    )
    post_ids = [p.id for p in posts]
    if post_ids:
        actions = list(
            db.scalars(
                select(models.MessagingAction).where(
                    models.MessagingAction.post_id.in_(post_ids)
                )
            ).all()
        )
        for action in actions:
            db.delete(action)
        for post in posts:
            db.delete(post)
    db.delete(channel)
    sync_vacancy_chat_ids_from_channels(db)
    db.commit()


def channel_to_out(row: models.MessagingChannel) -> dict:
    return {
        "id": row.id,
        "provider": row.provider,
        "external_id": row.external_id,
        "client_id": row.client_id,
        "name": row.name or row.external_id,
        "metadata": row.metadata_json or {},
    }
