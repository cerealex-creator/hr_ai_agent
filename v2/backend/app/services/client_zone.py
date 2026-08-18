"""Web client zone (D2): token URL access, minimal decide actions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.candidate_fields import normalize_gender
from app.services.messaging.client_apply import apply_client_update
from app.services.messaging.keyboards import interview_format_flags
from app.services.demo_showcase import client_org_is_demo
from app.services.stats_service import CLIENT_ZONE_STAGES
from app.services.tenancy import resolve_client_zone_root, zone_owner_scope_ids
from app.services.yandex_public import yandex_link_for_display

# Approve / think / reject (+ meeting on ready)
ZONE_ACTIONS = frozenset({"ready", "think", "reject"})
ACTIONABLE_STATUSES = frozenset({"wait", "think"})

# Who decided in client zone (stable keys — same list for every zone)
ZONE_DECISION_ROLES: dict[str, str] = {
    "unit_head": "Руководитель подразделения",
    "director": "Директор",
    "owner": "Собственник",
}


def _https_url(raw: Any) -> str | None:
    display = (yandex_link_for_display(str(raw or "")) or "").strip()
    if display.startswith(("http://", "https://")):
        return display
    return None


def client_zone_candidate_path(token: str, candidate_id: str | UUID) -> str:
    return f"/c/{token}/{candidate_id}"


def client_zone_candidate_public_url(
    token: str,
    candidate_id: str | UUID,
    *,
    settings: Any = None,
) -> str:
    from app.services.interview_digest import public_app_base

    base = public_app_base(settings)
    if not base:
        return ""
    return f"{base}{client_zone_candidate_path(token, candidate_id)}"


def ensure_zone_token_for_vacancy(db: Session, vacancy: models.Vacancy) -> str:
    from app.services.tenancy import generate_client_zone_token

    if vacancy.client_id is None:
        return ""
    client = db.get(models.Client, vacancy.client_id)
    if not client:
        return ""
    if not (client.client_zone_token or "").strip():
        client.client_zone_token = generate_client_zone_token(db)
        db.add(client)
        db.commit()
        db.refresh(client)
    return str(client.client_zone_token or "").strip()


def _parse_meeting(
    meeting_date: str | None,
    meeting_time: str | None,
    meeting_format: str | None,
) -> tuple[str, str, bool, bool]:
    date_s = (meeting_date or "").strip()
    time_s = (meeting_time or "").strip()
    if not date_s or not time_s:
        raise HTTPException(status_code=400, detail="Укажите дату и время встречи")
    try:
        datetime.strptime(date_s, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректная дата") from exc
    try:
        datetime.strptime(time_s, "%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректное время") from exc
    fmt = (meeting_format or "o").strip() or "o"
    if fmt not in ("o", "r", "b"):
        fmt = "o"
    remote, office = interview_format_flags(fmt)
    return date_s, time_s, remote, office


def _zone_company_parts(db: Session, owner: models.Client) -> tuple[str, str | None]:
    """Company name + optional department name for the zone owner."""
    if owner.parent_id is None:
        return owner.name, None
    parent = db.get(models.Client, owner.parent_id)
    if parent and parent.name:
        return parent.name, owner.name
    return owner.name, None


def _place_parts(
    client_id: int | None,
    *,
    names: dict[int, str],
    parent_ids: dict[int, int | None],
    fallback_company: str,
    fallback_dept: str | None,
) -> tuple[str, str | None]:
    if client_id is None:
        return fallback_company, fallback_dept
    own = names.get(client_id)
    parent_id = parent_ids.get(client_id)
    if parent_id:
        parent_name = names.get(parent_id) or fallback_company
        return parent_name, own
    return own or fallback_company, None


def _client_maps(db: Session, scope: set[int]) -> tuple[dict[int, str], dict[int, int | None]]:
    rows = list(db.scalars(select(models.Client).where(models.Client.id.in_(scope))).all())
    parent_ids = {int(c.parent_id) for c in rows if c.parent_id is not None}
    if parent_ids:
        rows.extend(db.scalars(select(models.Client).where(models.Client.id.in_(parent_ids))).all())
    names = {int(c.id): c.name for c in rows}
    parents = {int(c.id): (int(c.parent_id) if c.parent_id is not None else None) for c in rows}
    return names, parents


def _zone_header(db: Session, owner: models.Client) -> dict[str, Any]:
    company, dept = _zone_company_parts(db, owner)
    return {
        "id": owner.id,
        "name": company,
        "department_name": dept,
        "demo": client_org_is_demo(db, owner),
    }


def zone_context(db: Session, token: str) -> tuple[models.Client, set[int]]:
    owner = resolve_client_zone_root(db, token)
    return owner, zone_owner_scope_ids(owner)


def _zone_candidate_links(payload: dict[str, Any]) -> dict[str, Any]:
    extra: list[dict[str, str]] = []
    for raw in payload.get("extra_materials") or []:
        if not isinstance(raw, dict):
            continue
        url = _https_url(raw.get("url"))
        if not url:
            continue
        extra.append(
            {
                "title": str(raw.get("title") or "Материал").strip() or "Материал",
                "url": url,
            }
        )
    digest_raw = payload.get("interview_digest")
    digest: dict[str, Any] | None = None
    if isinstance(digest_raw, dict):
        qa: list[dict[str, str]] = []
        for row in digest_raw.get("qa") or []:
            if not isinstance(row, dict):
                continue
            q = str(row.get("q") or row.get("вопрос") or "").strip()
            a = str(row.get("a") or row.get("ответ") or "").strip()
            if q or a:
                qa.append({"q": q, "a": a})
        summary = str(digest_raw.get("summary") or "").strip()
        if summary or qa:
            digest = {"summary": summary, "qa": qa}
    return {
        "resume_url": _https_url(payload.get("resume_link"))
        or _https_url(payload.get("hh_resume_link")),
        "video_url": _https_url(payload.get("video_link")),
        "portfolio_url": _https_url(payload.get("portfolio_link")),
        "task_url": _https_url(payload.get("task_link")),
        "extra_materials": extra,
        "interview_digest": digest,
        "hr_comment": (str(payload.get("hr_comment") or "").strip() or None),
    }


def _zone_list_item(
    c: models.Candidate,
    vac: models.Vacancy,
    *,
    names: dict[int, str],
    parent_ids: dict[int, int | None],
    fallback_company: str,
    fallback_dept: str | None,
) -> dict[str, Any]:
    payload = c.payload or {}
    links = _zone_candidate_links(payload)
    company_name, department_name = _place_parts(
        vac.client_id,
        names=names,
        parent_ids=parent_ids,
        fallback_company=fallback_company,
        fallback_dept=fallback_dept,
    )
    client_name = department_name or company_name
    return {
        "id": str(c.id),
        "name": c.name or "Без имени",
        "vacancy_id": c.vacancy_id,
        "vacancy_title": vac.title,
        "client_id": vac.client_id,
        "client_name": client_name,
        "company_name": company_name,
        "department_name": department_name,
        "hr_stage": c.hr_stage,
        "client_status": c.client_status or "wait",
        "ai_score": payload.get("ai_score"),
        "ai_comment": (str(payload.get("ai_comment") or "")[:800] or None),
        "client_comment": (str(payload.get("client_comment") or "")[:500] or None),
        "office_interview_date": str(payload.get("office_interview_date") or "") or None,
        "office_interview_time": str(payload.get("office_interview_time") or "") or None,
        "actionable": (c.client_status or "wait") in ACTIONABLE_STATUSES,
        "has_resume": bool(links.get("resume_url")),
        "has_video": bool(links.get("video_url")),
        "has_digest": bool(links.get("interview_digest")),
        "photo_url": (str(payload.get("photo_url") or "").strip() or None),
        "gender": normalize_gender(payload.get("gender") or payload.get("sex")),
    }


def list_zone_candidates(db: Session, token: str) -> dict[str, Any]:
    root, scope = zone_context(db, token)
    vacancies = list(
        db.scalars(
            select(models.Vacancy).where(
                models.Vacancy.client_id.in_(scope),
                models.Vacancy.active.is_(True),
            )
        ).all()
    )
    vac_map = {v.id: v for v in vacancies}
    company_name, department_name = _zone_company_parts(db, root)
    header = _zone_header(db, root)
    if not vac_map:
        return {
            "company": header,
            "candidates": [],
            "demo": bool(header.get("demo")),
        }

    names, parent_ids = _client_maps(db, scope)
    rows = list(
        db.scalars(
            select(models.Candidate).where(
                models.Candidate.vacancy_id.in_(list(vac_map.keys())),
                models.Candidate.hr_stage.in_(CLIENT_ZONE_STAGES),
            )
        ).all()
    )
    # Actionable first (wait/think), then recent decided
    actionable: list[dict] = []
    others: list[dict] = []
    for c in rows:
        vac = vac_map.get(c.vacancy_id)
        if not vac:
            continue
        item = _zone_list_item(
            c,
            vac,
            names=names,
            parent_ids=parent_ids,
            fallback_company=company_name,
            fallback_dept=department_name,
        )
        if header.get("demo"):
            item["actionable"] = False
        if item["actionable"]:
            actionable.append(item)
        else:
            others.append(item)
    actionable.sort(key=lambda x: (x["name"] or "").casefold())
    others.sort(key=lambda x: (x["name"] or "").casefold())
    return {
        "company": header,
        "candidates": actionable + others[:30],
        "demo": bool(header.get("demo")),
    }


def get_zone_candidate(db: Session, token: str, candidate_id: str | UUID) -> dict[str, Any]:
    root, scope = zone_context(db, token)
    try:
        cid = candidate_id if isinstance(candidate_id, UUID) else UUID(str(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Candidate not found") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy or vacancy.client_id not in scope or candidate.hr_stage not in CLIENT_ZONE_STAGES:
        raise HTTPException(status_code=404, detail="Candidate not found")
    company_name, department_name = _zone_company_parts(db, root)
    names, parent_ids = _client_maps(db, scope)
    item = _zone_list_item(
        candidate,
        vacancy,
        names=names,
        parent_ids=parent_ids,
        fallback_company=company_name,
        fallback_dept=department_name,
    )
    payload = candidate.payload or {}
    links = _zone_candidate_links(payload)
    item.update(links)
    item["ai_comment"] = str(payload.get("ai_comment") or "").strip() or item.get("ai_comment")
    header = _zone_header(db, root)
    if header.get("demo"):
        item["actionable"] = False
    return {
        "company": header,
        "candidate": item,
        "demo": bool(header.get("demo")),
    }


def _sync_zone_decision_outbound(
    db: Session,
    candidate: models.Candidate,
    *,
    status_key: str,
    clean_comment: str,
    meeting_date_s: str | None = None,
    meeting_time_s: str | None = None,
    remote_interview: bool | None = None,
    office_interview: bool | None = None,
) -> tuple[bool, str]:
    """Push client-zone decision to Bitrix task (same as decide link flow)."""
    from app.services.app_settings import get_bitrix
    from app.services.bitrix.hr_notify import notify_hr_meeting_pending
    from app.services.bitrix.meeting_task import create_meeting_bitrix_task
    from app.services.bitrix.task_sync import (
        find_decision_task_post,
        sync_decision_task_for_candidate,
        sync_meeting_task_hr_status,
    )
    from app.services.bitrix.think_followup import register_think_decision_task
    from app.services.messaging.attendance import set_meeting_hr_confirmed

    if not get_bitrix().get("enabled"):
        return False, "bitrix off"

    post = find_decision_task_post(db, candidate.id)
    if status_key == "ready" and meeting_date_s and meeting_time_s:
        set_meeting_hr_confirmed(candidate, False)
        try:
            create_meeting_bitrix_task(
                db,
                candidate,
                meeting_date=meeting_date_s,
                meeting_time=meeting_time_s,
                remote_interview=bool(remote_interview),
                office_interview=bool(office_interview) if office_interview is not None else True,
            )
        except Exception:  # noqa: BLE001
            pass
        notify_hr_meeting_pending(db, candidate)
    elif status_key == "think" and post:
        tid = str(post.external_message_id or (post.payload or {}).get("task_id") or "")
        if tid:
            register_think_decision_task(db, candidate, task_id=tid)

    if post:
        action_type = "meeting_scheduled" if status_key == "ready" else f"status:{status_key}"
        action_payload: dict[str, Any] = {
            "via": "client_zone",
            "comment": clean_comment or None,
        }
        if status_key == "ready":
            action_payload.update(
                {
                    "date": meeting_date_s,
                    "time": meeting_time_s,
                    "remote": remote_interview,
                    "office": office_interview,
                }
            )
        db.add(
            models.MessagingAction(
                post_id=post.id,
                action_type=action_type,
                status="completed",
                external_callback_data=f"client_zone:{status_key}",
                payload=action_payload,
                completed_at=datetime.now(timezone.utc),
            )
        )

    try:
        ok = sync_decision_task_for_candidate(
            db,
            candidate,
            status_key=status_key,
            client_comment=clean_comment or None,
        )
        if status_key == "ready" and meeting_date_s and meeting_time_s:
            sync_meeting_task_hr_status(db, candidate, confirmed=False)
        db.commit()
        return ok, "bitrix synced" if ok else "bitrix task not found"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc) or "bitrix sync failed"


def resolve_zone_decision_role(role_key: str | None) -> tuple[str, str]:
    key = (role_key or "").strip()
    label = ZONE_DECISION_ROLES.get(key)
    if not label:
        raise HTTPException(
            status_code=400,
            detail="Выберите роль: Руководитель подразделения, Директор или Собственник",
        )
    return key, label


def apply_zone_decision(
    db: Session,
    token: str,
    candidate_id: str | UUID,
    *,
    status_key: str,
    decision_role: str | None = None,
    comment: str | None = None,
    meeting_date: str | None = None,
    meeting_time: str | None = None,
    meeting_format: str | None = None,
) -> dict[str, Any]:
    root, scope = zone_context(db, token)
    if client_org_is_demo(db, root):
        from app.core.demo import DEMO_WRITE_DETAIL

        raise HTTPException(status_code=403, detail=DEMO_WRITE_DETAIL)
    status = (status_key or "").strip()
    if status not in ZONE_ACTIONS:
        raise HTTPException(status_code=400, detail="status: ready | think | reject")
    role_key, role_label = resolve_zone_decision_role(decision_role)

    try:
        cid = candidate_id if isinstance(candidate_id, UUID) else UUID(str(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Candidate not found") from exc

    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy or vacancy.client_id not in scope:
        raise HTTPException(status_code=404, detail="Candidate not found")

    clean_comment = (comment or "").strip()
    if status in ("think", "reject") and not clean_comment:
        raise HTTPException(status_code=400, detail="Нужен комментарий")

    meeting_date_s: str | None = None
    meeting_time_s: str | None = None
    remote_interview: bool | None = None
    office_interview: bool | None = None
    meeting_kwargs: dict[str, Any] = {}
    if status == "ready":
        date_s, time_s, remote, office = _parse_meeting(meeting_date, meeting_time, meeting_format)
        meeting_date_s, meeting_time_s = date_s, time_s
        remote_interview, office_interview = remote, office
        meeting_kwargs = {
            "office_interview_date": date_s,
            "office_interview_time": time_s,
            "remote_interview": remote,
            "office_interview": office,
        }
    elif status in ("think", "reject"):
        meeting_kwargs = {
            "office_interview_date": "",
            "office_interview_time": "",
            "remote_interview": False,
            "office_interview": False,
        }

    apply_client_update(
        candidate,
        status_key=status,
        comment=clean_comment or None,
        append_comment=True,
        actor="client_zone",
        actor_note=role_label,
        **meeting_kwargs,
    )
    payload = dict(candidate.payload or {})
    payload["zone_decision_role"] = role_key
    payload["zone_decision_role_label"] = role_label
    candidate.payload = payload
    flag_modified(candidate, "payload")
    db.commit()
    db.refresh(candidate)

    from app.services.messaging.ops import notify_zone_decision_telegram

    tg_ok, tg_msg = notify_zone_decision_telegram(
        db,
        candidate,
        status_key=status,
        role_label=role_label,
    )
    bx_ok, bx_msg = _sync_zone_decision_outbound(
        db,
        candidate,
        status_key=status,
        clean_comment=clean_comment,
        meeting_date_s=meeting_date_s,
        meeting_time_s=meeting_time_s,
        remote_interview=remote_interview,
        office_interview=office_interview,
    )

    return {
        "ok": True,
        "candidate_id": str(candidate.id),
        "client_status": candidate.client_status,
        "hr_stage": candidate.hr_stage,
        "company_id": root.id,
        "decision_role": role_key,
        "decision_role_label": role_label,
        "telegram_notified": tg_ok,
        "telegram_message": tg_msg,
        "bitrix_synced": bx_ok,
        "bitrix_message": bx_msg,
    }
