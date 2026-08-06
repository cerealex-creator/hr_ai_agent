"""Inbound Bitrix24 events → apply_client_update."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.app_settings import get_bitrix
from app.services.bitrix.client import BitrixError, get_task
from app.services.messaging.client_apply import apply_client_update

OUR_STATUSES = frozenset({"ready", "think", "reject", "offer"})


def _normalize_event_name(raw: str) -> str:
    return (raw or "").strip().upper().replace(".", "")


def _verify_token(payload: dict[str, Any]) -> bool:
    cfg = get_bitrix()
    expected = str(cfg.get("outgoing_webhook_token") or "").strip()
    if not expected:
        # No token configured — accept (dev); production should set token.
        return True
    auth = payload.get("auth") if isinstance(payload.get("auth"), dict) else {}
    got = str(auth.get("application_token") or payload.get("auth[application_token]") or "").strip()
    return bool(got) and got == expected


def _find_post_by_task_id(db: Session, task_id: str) -> models.MessagingPost | None:
    tid = str(task_id).strip()
    if not tid:
        return None
    post = db.scalar(
        select(models.MessagingPost).where(models.MessagingPost.external_message_id == tid)
    )
    if post:
        return post
    # Fallback: scan recent bitrix posts
    for p in db.scalars(
        select(models.MessagingPost).order_by(models.MessagingPost.created_at.desc()).limit(500)
    ).all():
        if str((p.payload or {}).get("task_id") or "") == tid:
            return p
        if str((p.payload or {}).get("provider") or "") == "bitrix" and str(p.external_message_id) == tid:
            return p
    return None


def _enum_id_to_status(cfg: dict[str, Any], value: Any) -> str | None:
    if value is None or value == "" or value == []:
        return None
    # Bitrix may send list as [id] or single id / string
    raw = value
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    if s in OUR_STATUSES:
        return s
    enum = cfg.get("status_enum") if isinstance(cfg.get("status_enum"), dict) else {}
    for key, eid in enum.items():
        if str(eid or "").strip() and str(eid).strip() == s:
            return key if key in OUR_STATUSES else None
    return None


def _extract_task_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    after = data.get("FIELDS_AFTER") if isinstance(data.get("FIELDS_AFTER"), dict) else {}
    before = data.get("FIELDS_BEFORE") if isinstance(data.get("FIELDS_BEFORE"), dict) else {}
    for block in (after, before, data, payload):
        if not isinstance(block, dict):
            continue
        for key in ("ID", "id", "TASK_ID", "task_id"):
            if block.get(key) is not None and str(block.get(key)).strip():
                return str(block.get(key)).strip()
    return None


def process_bitrix_webhook(db: Session, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Handle outgoing webhook / event payload from Bitrix24.
    Primary event: OnTaskUpdate (ONTASKUPDATE).
    """
    events: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return [{"type": "bitrix.error", "handled": False, "note": "payload not a dict"}]

    cfg = get_bitrix()
    if not cfg.get("enabled"):
        return [{"type": "bitrix.disabled", "handled": False, "note": "bitrix.enabled=false"}]

    if not _verify_token(payload):
        return [{"type": "bitrix.auth", "handled": False, "note": "invalid application_token"}]

    event_name = _normalize_event_name(str(payload.get("event") or ""))
    if event_name and event_name not in ("ONTASKUPDATE", "ONTASKADD"):
        events.append(
            {
                "type": "bitrix.event",
                "handled": False,
                "note": f"ignored event {payload.get('event')}",
            }
        )
        return events

    task_id = _extract_task_id(payload)
    if not task_id:
        return [{"type": "bitrix.task", "handled": False, "note": "no task id in payload"}]

    post = _find_post_by_task_id(db, task_id)
    if not post:
        return [
            {
                "type": "bitrix.task",
                "handled": False,
                "task_id": task_id,
                "note": "unknown task (not created by this app)",
            }
        ]

    candidate = db.get(models.Candidate, post.candidate_id)
    if not candidate:
        return [{"type": "bitrix.task", "handled": False, "note": "candidate missing"}]

    # Task completed → schedule «Подумать» follow-up (works without UF fields).
    try:
        task = get_task(task_id)
    except BitrixError as exc:
        return [
            {
                "type": "bitrix.fetch",
                "handled": False,
                "task_id": task_id,
                "note": exc.message,
            }
        ]

    from app.services.bitrix.think_followup import handle_decision_task_closed, is_task_completed

    if (
        is_task_completed(task)
        and post.kind in ("primary", "think_followup")
        and (candidate.client_status or "").strip() == "think"
    ):
        follow = handle_decision_task_closed(db, candidate, task_id=task_id)
        if follow:
            return [
                {
                    "type": "bitrix.think_followup",
                    "handled": True,
                    "task_id": task_id,
                    "candidate_id": str(candidate.id),
                    "followup_at": follow.get("followup_at"),
                }
            ]

    if is_task_completed(task) and post.kind in ("primary", "think_followup", "meeting"):
        return [
            {
                "type": "bitrix.task",
                "handled": True,
                "task_id": task_id,
                "note": "task completed",
            }
        ]

    uf_status = str(cfg.get("uf_status_field") or "").strip()
    uf_comment = str(cfg.get("uf_comment_field") or "").strip()
    if not uf_status:
        return [
            {
                "type": "bitrix.config",
                "handled": False,
                "note": "UF sync optional; primary path is decide links in task description",
            }
        ]

    # UF fallback path (often unavailable on cloud incoming webhooks).
    status_raw = task.get(uf_status)
    status_key = _enum_id_to_status(cfg, status_raw)
    comment = ""
    if uf_comment:
        raw_c = task.get(uf_comment)
        if isinstance(raw_c, list):
            raw_c = raw_c[0] if raw_c else ""
        comment = str(raw_c or "").strip()

    event: dict[str, Any] = {
        "type": "bitrix.task_update",
        "task_id": task_id,
        "candidate_id": str(candidate.id),
        "status_raw": status_raw,
        "status_key": status_key,
    }

    if not status_key:
        event["handled"] = False
        event["note"] = "status empty or unmapped"
        return [event]

    if candidate.client_status == status_key and (not comment):
        event["handled"] = True
        event["note"] = "no change"
        return [event]

    apply_client_update(
        candidate,
        status_key=status_key,
        comment=comment or None,
        append_comment=bool(comment),
        actor="bitrix",
        actor_note=f"task:{task_id}",
    )
    try:
        from app.services.bitrix.task_sync import sync_decision_task_for_candidate

        sync_decision_task_for_candidate(
            db,
            candidate,
            status_key=status_key,
            client_comment=comment or None,
        )
    except Exception:  # noqa: BLE001
        pass
    db.add(
        models.MessagingAction(
            post_id=post.id,
            action_type=f"status:{status_key}",
            status="completed",
            external_callback_data=f"bitrix:{task_id}:{status_key}",
            payload={"task_id": task_id, "comment": comment or None},
            completed_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    event["handled"] = True
    event["client_status"] = candidate.client_status
    event["hr_stage"] = candidate.hr_stage
    return [event]
