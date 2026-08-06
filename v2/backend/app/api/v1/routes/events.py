"""SSE job events stream (D4)."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, require_auth
from app.db.session import SessionLocal
from app.services import jobs as job_svc

logger = logging.getLogger("hr_api.events")

router = APIRouter(tags=["events"])

POLL_SEC = 1.5
HEARTBEAT_SEC = 15.0
# Include recently finished jobs so clients can toast complete/fail.
RECENT_TERMINAL_SEC = 120
SNAPSHOT_LIMIT = 40


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def job_event_payload(job: Any) -> dict[str, Any]:
    err = (job.error or "").strip()
    return {
        "id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "progress_label": job.progress_label,
        "error": err[:300] if err else None,
        "vacancy_id": job.vacancy_id,
        "updated_at": _iso(job.updated_at),
    }


def _signature(payload: dict[str, Any]) -> str:
    return "|".join(
        [
            str(payload.get("status") or ""),
            str(payload.get("progress_pct") if payload.get("progress_pct") is not None else ""),
            str(payload.get("progress_label") or ""),
            str(payload.get("error") or ""),
            str(payload.get("updated_at") or ""),
        ]
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _fetch_org_jobs(organization_id: UUID) -> tuple[int, list[dict[str, Any]]]:
    db: Session = SessionLocal()
    try:
        rows = job_svc.list_jobs(
            db,
            limit=SNAPSHOT_LIMIT,
            organization_id=organization_id,
        )
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=RECENT_TERMINAL_SEC)
        items: list[dict[str, Any]] = []
        for job in rows:
            if job.status in ("queued", "running"):
                items.append(job_event_payload(job))
                continue
            updated = job.updated_at
            if updated is not None:
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if updated >= cutoff:
                    items.append(job_event_payload(job))
        active = job_svc.count_active(db, organization_id=organization_id)
        return active, items
    finally:
        db.close()


@router.get("/events/stream")
async def events_stream(
    request: Request,
    user: AuthUser = Depends(require_auth),
) -> StreamingResponse:
    """Server-Sent Events: org-scoped job updates (DB poll ~1.5s)."""
    org_id = user.org_id

    async def generate():
        last_sigs: dict[str, str] = {}
        sent_snapshot = False
        last_hb = 0.0
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    active_count, items = await asyncio.to_thread(_fetch_org_jobs, org_id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("SSE jobs poll failed: %s", exc)
                    yield _sse("error", {"message": "poll_failed"})
                    await asyncio.sleep(POLL_SEC)
                    continue

                if not sent_snapshot:
                    yield _sse(
                        "jobs.snapshot",
                        {"active_count": active_count, "items": items},
                    )
                    for item in items:
                        last_sigs[str(item["id"])] = _signature(item)
                    sent_snapshot = True
                else:
                    current_ids = {str(item["id"]) for item in items}
                    for item in items:
                        jid = str(item["id"])
                        sig = _signature(item)
                        if last_sigs.get(jid) != sig:
                            last_sigs[jid] = sig
                            yield _sse(
                                "job.updated",
                                {"active_count": active_count, "job": item},
                            )
                    # Drop signatures for jobs that left the watch window
                    for stale in list(last_sigs.keys()):
                        if stale not in current_ids:
                            del last_sigs[stale]
                    # Always push active_count heartbeat-ish via ping payload
                    pass

                loop = asyncio.get_event_loop()
                now = loop.time()
                if now - last_hb >= HEARTBEAT_SEC:
                    yield _sse("ping", {"t": datetime.now(timezone.utc).isoformat(), "active_count": active_count})
                    last_hb = now

                await asyncio.sleep(POLL_SEC)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
