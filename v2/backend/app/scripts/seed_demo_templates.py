"""Seed vacancy templates into Demo Sandbox (and optionally owner org).

Usage (inside API container or local backend):
  python -m app.scripts.seed_demo_templates --from-json /path/to/vacancy_templates_seed.json
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from app.db import models
from app.db.session import SessionLocal
from app.services.clients_write import ensure_org_root_company


def _load(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        items = raw.get("templates") or raw.get("items") or []
        return [x for x in items if isinstance(x, dict)]
    return []


def seed(
    db,
    items: list[dict],
    *,
    demo_only: bool = True,
) -> dict:
    demo_org = db.scalar(select(models.Organization).where(models.Organization.slug == "demo-sandbox"))
    if not demo_org:
        raise RuntimeError("Organization demo-sandbox not found")
    demo_company = ensure_org_root_company(db, demo_org.id, default_name="Demo Sandbox")

    owner_org = db.scalar(select(models.Organization).where(models.Organization.slug == "default"))
    owner_company = None
    if owner_org and not demo_only:
        owner_company = ensure_org_root_company(db, owner_org.id, default_name="YourBox")

    created_demo = 0
    created_owner = 0
    skipped = 0

    for item in items:
        title = str(item.get("title") or "").strip()
        base_key = str(item.get("legacy_key") or title or uuid.uuid4())
        docs = item.get("documents") if isinstance(item.get("documents"), dict) else {}
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        chat_id = item.get("chat_id")

        demo_key = f"demo:{base_key}"
        existing_demo = db.scalar(
            select(models.VacancyTemplate).where(models.VacancyTemplate.legacy_key == demo_key)
        )
        if existing_demo:
            existing_demo.title = title or existing_demo.title
            existing_demo.client_id = demo_company.id
            existing_demo.documents = docs
            existing_demo.payload = dict(payload)
            existing_demo.chat_id = str(chat_id) if chat_id else None
            skipped += 1
        else:
            db.add(
                models.VacancyTemplate(
                    id=uuid.uuid4(),
                    legacy_key=demo_key,
                    title=title or "Шаблон",
                    client_id=demo_company.id,
                    chat_id=str(chat_id) if chat_id else None,
                    documents=docs,
                    payload=dict(payload),
                )
            )
            created_demo += 1

        if owner_company is not None:
            owner_key = f"owner:{base_key}"
            existing_owner = db.scalar(
                select(models.VacancyTemplate).where(models.VacancyTemplate.legacy_key == owner_key)
            )
            # Prefer original legacy_key for owner if free
            by_orig = db.scalar(
                select(models.VacancyTemplate).where(models.VacancyTemplate.legacy_key == base_key)
            )
            if by_orig:
                by_orig.client_id = by_orig.client_id or owner_company.id
                by_orig.documents = docs
                by_orig.payload = dict(payload)
                by_orig.title = title or by_orig.title
            elif existing_owner:
                existing_owner.client_id = owner_company.id
                existing_owner.documents = docs
                existing_owner.payload = dict(payload)
                existing_owner.title = title or existing_owner.title
            else:
                db.add(
                    models.VacancyTemplate(
                        id=uuid.uuid4(),
                        legacy_key=base_key,
                        title=title or "Шаблон",
                        client_id=owner_company.id,
                        chat_id=str(chat_id) if chat_id else None,
                        documents=docs,
                        payload=dict(payload),
                    )
                )
                created_owner += 1

    db.commit()
    return {
        "demo_company_id": demo_company.id,
        "created_demo": created_demo,
        "created_owner": created_owner,
        "updated_or_skipped": skipped,
        "total_input": len(items),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed templates into Demo Sandbox")
    parser.add_argument("--from-json", type=Path, required=True)
    parser.add_argument(
        "--also-owner",
        action="store_true",
        help="Also seed/update templates for default (owner) org",
    )
    args = parser.parse_args(argv)
    items = _load(args.from_json)
    if not items:
        print("No templates in JSON", file=sys.stderr)
        return 1
    db = SessionLocal()
    try:
        stats = seed(db, items, demo_only=not args.also_owner)
        print(json.dumps(stats, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
