"""Warranty period after offer / internship / started_work (v2 port of Streamlit warranty.py)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.app_settings import WARRANTY_MONTH_CHOICES, get_default_warranty_months
from app.services.vacancy_write import create_vacancy

DAYS_PER_WARRANTY_MONTH = 30
WARRANTY_TRIGGER_STAGES = frozenset({"offer", "internship", "started_work"})
SEARCH_MODE_NORMAL = "normal"
SEARCH_MODE_WARRANTY = "warranty"


def default_warranty() -> dict[str, Any]:
    return {
        "active": False,
        "start_date": "",
        "months": get_default_warranty_months(),
        "candidate_id": "",
        "start_kind": "",
    }


def vacancy_as_dict(vacancy: models.Vacancy) -> dict[str, Any]:
    payload = dict(vacancy.payload or {})
    return {
        "id": vacancy.id,
        "title": vacancy.title,
        "chat_id": vacancy.chat_id,
        "client_id": vacancy.client_id,
        "active": vacancy.active,
        "created_at": vacancy.created_at,
        "closed_at": vacancy.closed_at,
        "search_mode": payload.get("search_mode") or SEARCH_MODE_NORMAL,
        "warranty_source_vacancy_id": payload.get("warranty_source_vacancy_id"),
        "warranty": payload.get("warranty") if isinstance(payload.get("warranty"), dict) else {},
        "is_test": bool(payload.get("is_test")),
        "show_portfolio_field": bool(payload.get("show_portfolio_field")),
        "documents": vacancy.documents or {},
    }


def migrate_vacancy_warranty_dict(vacancy: dict[str, Any]) -> bool:
    migrated = False
    if vacancy.get("search_mode") not in (SEARCH_MODE_NORMAL, SEARCH_MODE_WARRANTY):
        vacancy["search_mode"] = SEARCH_MODE_NORMAL
        migrated = True
    if "warranty_source_vacancy_id" not in vacancy:
        vacancy["warranty_source_vacancy_id"] = None
        migrated = True
    warranty = vacancy.get("warranty")
    if not isinstance(warranty, dict):
        vacancy["warranty"] = default_warranty()
        return True
    defaults = default_warranty()
    for key, val in defaults.items():
        if key not in warranty:
            warranty[key] = val
            migrated = True
    months = warranty.get("months")
    if months not in WARRANTY_MONTH_CHOICES:
        warranty["months"] = get_default_warranty_months()
        migrated = True
    return migrated


def ensure_vacancy_warranty_payload(vacancy: models.Vacancy) -> bool:
    payload = dict(vacancy.payload or {})
    view = vacancy_as_dict(vacancy)
    changed = migrate_vacancy_warranty_dict(view)
    if not changed:
        return False
    payload["search_mode"] = view["search_mode"]
    payload["warranty_source_vacancy_id"] = view.get("warranty_source_vacancy_id")
    payload["warranty"] = view["warranty"]
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    return True


def warranty_total_days(warranty: dict | None) -> int:
    months = (warranty or {}).get("months") or 3
    if months not in WARRANTY_MONTH_CHOICES:
        months = 3
    return int(months) * DAYS_PER_WARRANTY_MONTH


def parse_warranty_start(warranty: dict | None) -> date | None:
    raw = (warranty or {}).get("start_date") or ""
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def warranty_end_date(warranty: dict | None) -> date | None:
    start = parse_warranty_start(warranty)
    if not start:
        return None
    return start + timedelta(days=warranty_total_days(warranty))


def warranty_days_remaining(warranty: dict | None, *, today: date | None = None) -> int | None:
    if not (warranty or {}).get("active"):
        return None
    end = warranty_end_date(warranty)
    if not end:
        return None
    today = today or date.today()
    return (end - today).days


def is_warranty_active_dict(vacancy: dict, *, today: date | None = None) -> bool:
    migrate_vacancy_warranty_dict(vacancy)
    warranty = vacancy.get("warranty") or {}
    if not warranty.get("active"):
        return False
    remaining = warranty_days_remaining(warranty, today=today)
    return remaining is not None and remaining >= 0


def format_warranty_countdown(vacancy: models.Vacancy | dict, *, today: date | None = None) -> str:
    view = vacancy_as_dict(vacancy) if isinstance(vacancy, models.Vacancy) else dict(vacancy)
    migrate_vacancy_warranty_dict(view)
    warranty = view.get("warranty") or {}
    if not warranty.get("active"):
        return ""
    remaining = warranty_days_remaining(warranty, today=today)
    if remaining is None:
        return ""
    if remaining < 0:
        return "Гарантия истекла"
    if remaining == 0:
        return "На гарантии · последний день"
    return f"На гарантии · осталось {remaining} дн."


def apply_warranty_to_vacancy(
    vacancy: models.Vacancy,
    candidate: models.Candidate,
    start_date: str | date,
    months: int,
    start_kind: str,
) -> None:
    ensure_vacancy_warranty_payload(vacancy)
    if months not in WARRANTY_MONTH_CHOICES:
        months = get_default_warranty_months()
    if isinstance(start_date, date):
        start_str = start_date.strftime("%Y-%m-%d")
    else:
        start_str = str(start_date or "")[:10]
    payload = dict(vacancy.payload or {})
    payload["warranty"] = {
        "active": True,
        "start_date": start_str,
        "months": months,
        "candidate_id": str(candidate.id),
        "start_kind": start_kind,
    }
    vacancy.payload = payload
    flag_modified(vacancy, "payload")


def is_warranty_search_vacancy(vacancy: models.Vacancy) -> bool:
    ensure_vacancy_warranty_payload(vacancy)
    return (vacancy.payload or {}).get("search_mode") == SEARCH_MODE_WARRANTY


def create_warranty_search_vacancy(db: Session, source: models.Vacancy) -> models.Vacancy:
    title = (source.title or "").strip()
    if not title:
        raise ValueError("У исходной вакансии нет названия")
    new_title = f"{title} · гарантийный поиск"
    new_v = create_vacancy(
        db,
        title=new_title,
        client_id=source.client_id,
        chat_id=source.chat_id,
        is_test=bool((source.payload or {}).get("is_test")),
    )
    # Copy documents + warranty markers
    new_v.documents = dict(source.documents or {})
    payload = dict(new_v.payload or {})
    src_payload = dict(source.payload or {})
    payload["search_mode"] = SEARCH_MODE_WARRANTY
    payload["warranty_source_vacancy_id"] = source.id
    payload["show_portfolio_field"] = bool(src_payload.get("show_portfolio_field"))
    payload["control_word_enabled"] = bool(src_payload.get("control_word_enabled"))
    payload["control_word"] = str(src_payload.get("control_word") or "")
    payload["warranty"] = default_warranty()
    yandex = src_payload.get("yandex_disk")
    if isinstance(yandex, dict):
        payload["yandex_disk"] = dict(yandex)
        # Fresh seen_paths for warranty search
        yd = dict(payload["yandex_disk"])
        yd["seen_paths"] = []
        yd["last_sync_at"] = ""
        payload["yandex_disk"] = yd
    new_v.payload = payload
    flag_modified(new_v, "payload")
    flag_modified(new_v, "documents")
    db.add(new_v)
    db.commit()
    db.refresh(new_v)
    return new_v


def collect_warranty_registry(
    db: Session,
    *,
    today: date | None = None,
    organization_id=None,
) -> list[dict[str, Any]]:
    q = select(models.Vacancy)
    if organization_id is not None:
        from app.services.tenancy import org_vacancy_ids

        vac_ids = org_vacancy_ids(db, organization_id)
        if not vac_ids:
            return []
        q = q.where(models.Vacancy.id.in_(vac_ids))
    rows: list[dict[str, Any]] = []
    for vac in db.scalars(q).all():
        view = vacancy_as_dict(vac)
        if not is_warranty_active_dict(view, today=today):
            continue
        warranty = view.get("warranty") or {}
        remaining = warranty_days_remaining(warranty, today=today)
        cand_id = str(warranty.get("candidate_id") or "")
        cand_name = ""
        if cand_id:
            try:
                from uuid import UUID

                cand = db.get(models.Candidate, UUID(cand_id))
                cand_name = cand.name if cand else ""
            except Exception:
                cand_name = ""
        client_name = None
        if vac.client_id is not None:
            client = db.get(models.Client, vac.client_id)
            client_name = client.name if client else None
        rows.append(
            {
                "vacancy_id": vac.id,
                "title": vac.title,
                "active": vac.active,
                "client_id": vac.client_id,
                "client_name": client_name,
                "candidate_id": cand_id or None,
                "candidate_name": cand_name or None,
                "start_date": warranty.get("start_date") or "",
                "months": warranty.get("months") or 3,
                "start_kind": warranty.get("start_kind") or "",
                "days_remaining": remaining,
                "countdown": format_warranty_countdown(vac, today=today),
                "is_warranty_search": is_warranty_search_vacancy(vac),
            }
        )
    rows.sort(key=lambda r: (r.get("days_remaining") is None, r.get("days_remaining") or 0))
    return rows


def maybe_apply_warranty_on_stage(
    db: Session,
    candidate: models.Candidate,
    *,
    start_date: str | None = None,
    months: int | None = None,
) -> str:
    """If stage is a warranty trigger and start_date provided — activate warranty. Returns note."""
    if candidate.hr_stage not in WARRANTY_TRIGGER_STAGES:
        return ""
    vac = db.get(models.Vacancy, candidate.vacancy_id)
    if not vac:
        return ""
    date_str = (start_date or "").strip()
    if not date_str:
        payload = candidate.payload or {}
        date_str = str(payload.get("office_interview_date") or "").strip()
    if not date_str:
        return ""
    apply_warranty_to_vacancy(
        vac,
        candidate,
        date_str,
        months if months is not None else get_default_warranty_months(),
        candidate.hr_stage,
    )
    db.add(vac)
    return format_warranty_countdown(vac)
