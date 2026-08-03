"""Import legacy JSON snapshot into PostgreSQL (read-only on data/)."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.db.init_db import main as init_db
from app.db.session import SessionLocal

VACANCY_CORE = {
    "id",
    "client_id",
    "title",
    "active",
    "chat_id",
    "documents",
    "created_at",
    "closed_at",
    "candidates",
}
CANDIDATE_CORE = {
    "id",
    "vacancy_id",
    "name",
    "hr_stage",
    "client_status",
    "created_at",
    "status_updated_at",
}


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _as_str_chat_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _parse_candidate_id(raw: Any) -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-candidate:{raw}")


def _history_datetime_from_name(filename: str) -> str | None:
    m = re.match(r"^(\d{8}_\d{6})_", filename)
    return m.group(1) if m else None


def _norm_title(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def clear_imported_tables(db: Session) -> None:
    """Wipe domain tables for a clean replace import (keeps schema)."""
    # Child tables first (FK order).
    for table in (
        models.MessagingAction,
        models.MessagingPost,
        models.HhSeenResume,
        models.HhShortlistItem,
        models.Job,
        models.DocumentGeneration,
        models.Candidate,
        models.VacancyTemplate,
        models.MessagingChannel,
        models.Vacancy,
        models.Client,
        models.ImportRun,
    ):
        db.execute(delete(table))
    db.commit()


def ensure_organization(db: Session) -> models.Organization:
    settings = get_settings()
    org = db.scalar(
        select(models.Organization).where(models.Organization.slug == settings.default_org_slug)
    )
    if org:
        return org
    org = models.Organization(name=settings.default_org_name, slug=settings.default_org_slug)
    db.add(org)
    db.flush()
    return org


def import_clients(db: Session, data_dir: Path, org: models.Organization) -> int:
    raw = _load_json(data_dir / "departments.json", {"departments": []})
    departments = raw.get("departments", raw if isinstance(raw, list) else [])
    count = 0
    for dept in departments:
        client = models.Client(
            id=int(dept["id"]),
            organization_id=org.id,
            name=str(dept.get("name") or f"Client {dept['id']}"),
            slug=str(dept.get("slug") or f"client-{dept['id']}"),
            client_zone_token=dept.get("client_zone_token"),
            payload={k: v for k, v in dept.items() if k not in {"id", "name", "slug", "client_zone_token"}},
        )
        db.merge(client)
        count += 1
    db.flush()
    return count


def import_channels(db: Session, data_dir: Path) -> int:
    chats = _load_json(data_dir / "chats_db.json", [])
    if not isinstance(chats, list):
        return 0
    known_clients = set(db.scalars(select(models.Client.id)).all())
    count = 0
    for chat in chats:
        external_id = _as_str_chat_id(chat.get("id"))
        if not external_id:
            continue
        raw_client_id = chat.get("department_id")
        client_id = int(raw_client_id) if raw_client_id is not None else None
        if client_id is not None and client_id not in known_clients:
            client_id = None
        channel = models.MessagingChannel(
            provider="telegram",
            external_id=external_id,
            client_id=client_id,
            name=str(chat.get("name") or ""),
            metadata_json={
                "department_name": chat.get("department_name"),
                "department_id": chat.get("department_id"),
            },
        )
        db.add(channel)
        count += 1
    db.flush()
    return count


def _ensure_channel(
    db: Session,
    *,
    external_id: str,
    client_id: int | None,
    cache: dict[str, models.MessagingChannel],
) -> models.MessagingChannel:
    if external_id in cache:
        return cache[external_id]
    row = db.scalar(
        select(models.MessagingChannel).where(
            models.MessagingChannel.provider == "telegram",
            models.MessagingChannel.external_id == external_id,
        )
    )
    if not row:
        row = models.MessagingChannel(
            provider="telegram",
            external_id=external_id,
            client_id=client_id,
            name=f"chat {external_id}",
            metadata_json={"source": "telegram_posts_import"},
        )
        db.add(row)
        db.flush()
    cache[external_id] = row
    return row


def import_vacancies_and_candidates(db: Session, data_dir: Path) -> tuple[int, int]:
    raw = _load_json(data_dir / "vacancies_db.json", {"vacancies": []})
    vacancies = raw.get("vacancies", [])
    known_clients = set(db.scalars(select(models.Client.id)).all())
    v_count = 0
    c_count = 0
    for item in vacancies:
        vacancy_id = int(item["id"])
        documents = item.get("documents") if isinstance(item.get("documents"), dict) else {}
        payload = {k: v for k, v in item.items() if k not in VACANCY_CORE}
        raw_client_id = item.get("client_id")
        client_id = int(raw_client_id) if raw_client_id is not None else None
        if client_id is not None and client_id not in known_clients:
            payload["legacy_client_id_unmapped"] = client_id
            client_id = None
        vacancy = models.Vacancy(
            id=vacancy_id,
            client_id=client_id,
            title=str(item.get("title") or f"Vacancy {vacancy_id}"),
            active=bool(item.get("active", True)),
            chat_id=_as_str_chat_id(item.get("chat_id")),
            documents=documents,
            created_at=item.get("created_at"),
            closed_at=item.get("closed_at"),
            payload=payload,
            version=1,
        )
        db.merge(vacancy)
        v_count += 1

        for cand in item.get("candidates") or []:
            cid = _parse_candidate_id(cand.get("id"))
            payload_c = {k: v for k, v in cand.items() if k not in CANDIDATE_CORE}
            candidate = models.Candidate(
                id=cid,
                vacancy_id=vacancy_id,
                name=str(cand.get("name") or ""),
                hr_stage=str(cand.get("hr_stage") or "resume_screening"),
                client_status=str(cand.get("client_status") or "wait"),
                created_at=cand.get("created_at"),
                status_updated_at=cand.get("status_updated_at"),
                payload=payload_c,
            )
            db.merge(candidate)
            c_count += 1
    db.flush()
    return v_count, c_count


def migrate_telegram_posts(db: Session) -> int:
    """Create MessagingPost rows from candidates.payload.telegram_posts."""
    channel_cache: dict[str, models.MessagingChannel] = {}
    for ch in db.scalars(select(models.MessagingChannel)).all():
        channel_cache[str(ch.external_id)] = ch

    vacancies = {v.id: v for v in db.scalars(select(models.Vacancy)).all()}
    count = 0
    seen: set[tuple[str, str]] = set()  # (channel_ext, message_id)

    for cand in db.scalars(select(models.Candidate)).all():
        payload = dict(cand.payload or {})
        posts = payload.get("telegram_posts") or []
        if not isinstance(posts, list):
            continue
        vacancy = vacancies.get(cand.vacancy_id)
        tg_callback_id = str(payload.get("tg_callback_id") or "").strip()
        if not tg_callback_id:
            tg_callback_id = str(cand.id).replace("-", "")[:8]
            payload["tg_callback_id"] = tg_callback_id
            cand.payload = payload

        for post in posts:
            if not isinstance(post, dict):
                continue
            mid = post.get("message_id")
            if mid is None:
                continue
            chat_id = _as_str_chat_id(post.get("chat_id")) or (
                vacancy.chat_id if vacancy else None
            )
            if not chat_id:
                continue
            key = (chat_id, str(mid))
            if key in seen:
                continue
            seen.add(key)

            channel = _ensure_channel(
                db,
                external_id=chat_id,
                client_id=vacancy.client_id if vacancy else None,
                cache=channel_cache,
            )
            kind = str(post.get("kind") or "primary").strip() or "primary"
            if kind not in ("primary", "task", "extra"):
                kind = "primary"
            row = models.MessagingPost(
                channel_id=channel.id,
                candidate_id=cand.id,
                vacancy_id=cand.vacancy_id,
                kind=kind,
                external_message_id=str(mid),
                text_snapshot=None,
                payload={
                    "provider": "telegram",
                    "chat_id": chat_id,
                    "tg_callback_id": tg_callback_id,
                    "sent_at": post.get("sent_at"),
                    "imported_from": "telegram_posts",
                    "legacy_vacancy_id": post.get("vacancy_id"),
                },
            )
            db.add(row)
            count += 1
    db.flush()
    return count


def import_history(db: Session, data_dir: Path) -> int:
    history_dir = data_dir / "history"
    if not history_dir.is_dir():
        return 0
    index = _load_json(history_dir / "index.json", [])
    index_by_file = {
        rec.get("filename"): rec for rec in index if isinstance(rec, dict) and rec.get("filename")
    }

    vacancies = list(db.scalars(select(models.Vacancy)).all())
    by_title: dict[str, list[models.Vacancy]] = {}
    for v in vacancies:
        by_title.setdefault(_norm_title(v.title), []).append(v)

    count = 0
    for path in sorted(history_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        snapshot = _load_json(path, {})
        meta = index_by_file.get(path.name, {})
        title = str(
            meta.get("vacancy_title")
            or meta.get("title")
            or (snapshot.get("должность") if isinstance(snapshot, dict) else "")
            or path.stem
        )
        matched = by_title.get(_norm_title(title)) or []
        vacancy_id = matched[0].id if len(matched) == 1 else None
        client_id = matched[0].client_id if len(matched) == 1 else None
        # Prefer explicit ids from index if present and valid
        if meta.get("vacancy_id") is not None:
            try:
                vid = int(meta["vacancy_id"])
                if vid in {v.id for v in vacancies}:
                    vacancy_id = vid
                    vac = next(v for v in vacancies if v.id == vid)
                    client_id = vac.client_id
            except (TypeError, ValueError):
                pass

        gen = models.DocumentGeneration(
            source_filename=path.name,
            title=title,
            mode="legacy_history",
            documents_snapshot=snapshot if isinstance(snapshot, dict) else {"raw": snapshot},
            created_at_legacy=meta.get("datetime") or _history_datetime_from_name(path.name),
            vacancy_id=vacancy_id,
            client_id=client_id,
        )
        db.add(gen)
        count += 1
    db.flush()
    return count


def import_templates(db: Session, data_dir: Path) -> int:
    raw = _load_json(data_dir / "vacancy_templates.json", {})
    if isinstance(raw, list):
        items = {str(i): t for i, t in enumerate(raw)}
    elif isinstance(raw, dict):
        if "templates" in raw and isinstance(raw["templates"], list):
            items = {str(i): t for i, t in enumerate(raw["templates"])}
        else:
            items = raw
    else:
        return 0

    known_clients = set(db.scalars(select(models.Client.id)).all())
    count = 0
    for key, tmpl in items.items():
        if not isinstance(tmpl, dict):
            continue
        title = str(tmpl.get("title") or tmpl.get("name") or key)
        documents = tmpl.get("documents") if isinstance(tmpl.get("documents"), dict) else {}
        if not documents:
            for doc_key in ("profile", "vacancy_text", "questions", "keywords", "notes"):
                if doc_key in tmpl:
                    documents[doc_key] = tmpl[doc_key]
        legacy_key = str(tmpl.get("id") or key)[:255]
        raw_client_id = tmpl.get("client_id")
        client_id = int(raw_client_id) if raw_client_id is not None else None
        if client_id is not None and client_id not in known_clients:
            client_id = None
        row = models.VacancyTemplate(
            legacy_key=legacy_key,
            title=title,
            client_id=client_id,
            chat_id=_as_str_chat_id(tmpl.get("chat_id")),
            documents=documents,
            payload={
                k: v
                for k, v in tmpl.items()
                if k
                not in {
                    "id",
                    "title",
                    "name",
                    "documents",
                    "client_id",
                    "chat_id",
                    *documents.keys(),
                }
            },
        )
        db.add(row)
        count += 1
    db.flush()
    return count


def run_import(data_dir: Path, replace: bool = False) -> dict[str, Any]:
    init_db()
    db = SessionLocal()
    try:
        if replace:
            clear_imported_tables(db)
        org = ensure_organization(db)
        stats: dict[str, Any] = {
            "clients": import_clients(db, data_dir, org),
            "messaging_channels": import_channels(db, data_dir),
            "vacancies": 0,
            "candidates": 0,
            "messaging_posts": 0,
            "document_generations": 0,
            "vacancy_templates": 0,
        }
        stats["vacancies"], stats["candidates"] = import_vacancies_and_candidates(db, data_dir)
        stats["messaging_posts"] = migrate_telegram_posts(db)
        stats["document_generations"] = import_history(db, data_dir)
        stats["vacancy_templates"] = import_templates(db, data_dir)
        db.add(models.ImportRun(source_dir=str(data_dir.resolve()), stats=stats))
        db.commit()
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify_import_counts(db: Session | None = None) -> dict[str, int]:
    """Current PG counts for cutover reconciliation."""
    from sqlalchemy import func

    own = db is None
    if own:
        db = SessionLocal()
    assert db is not None

    def _count(model: type) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    try:
        return {
            "clients": _count(models.Client),
            "messaging_channels": _count(models.MessagingChannel),
            "vacancies": _count(models.Vacancy),
            "candidates": _count(models.Candidate),
            "messaging_posts": _count(models.MessagingPost),
            "document_generations": _count(models.DocumentGeneration),
            "vacancy_templates": _count(models.VacancyTemplate),
            "hh_shortlist_items": _count(models.HhShortlistItem),
            "hh_seen_resumes": _count(models.HhSeenResume),
        }
    finally:
        if own:
            db.close()


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Import legacy JSON → PostgreSQL (v2)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(settings.legacy_data_dir),
        help="Path to legacy data/ (read-only)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Clear imported tables before load (safe for re-import)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Print current PG table counts and exit (no import)",
    )
    args = parser.parse_args()
    if args.verify_only:
        counts = verify_import_counts()
        print("PG counts:")
        for key, value in counts.items():
            print(f"  {key}: {value}")
        return

    data_dir = args.data_dir.resolve()
    if not data_dir.is_dir():
        raise SystemExit(f"Data dir not found: {data_dir}")
    stats = run_import(data_dir, replace=args.replace)
    print("Import OK:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("Verify:")
    for key, value in verify_import_counts().items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
