"""Apply client status from Bitrix decision link."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.app_settings import get_bitrix
from app.services.bitrix.tokens import OUR_STATUSES, STATUS_LABELS, parse_decide_token
from app.services.messaging.client_apply import apply_client_update
from app.services.messaging.keyboards import STATUSES_REQUIRE_COMMENT, interview_format_flags
from app.services.bitrix.hr_notify import notify_hr_meeting_pending
from app.services.bitrix.meeting_task import create_meeting_bitrix_task
from app.services.bitrix.think_followup import register_think_decision_task
from app.services.bitrix.task_sync import sync_decision_task_for_candidate, sync_meeting_task_hr_status
from app.services.messaging.attendance import set_meeting_hr_confirmed


class DecideError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _parse_meeting_fields(
    meeting_date: str | None,
    meeting_time: str | None,
    meeting_format: str | None,
) -> tuple[str, str, bool, bool]:
    date_s = (meeting_date or "").strip()
    time_s = (meeting_time or "").strip()
    if not date_s or not time_s:
        raise DecideError("Укажите дату и время встречи", 400)
    try:
        datetime.strptime(date_s, "%Y-%m-%d")
    except ValueError as exc:
        raise DecideError("Некорректная дата встречи", 400) from exc
    try:
        datetime.strptime(time_s, "%H:%M")
    except ValueError as exc:
        raise DecideError("Некорректное время встречи", 400) from exc
    fmt = (meeting_format or "o").strip() or "o"
    if fmt not in ("o", "r", "b"):
        fmt = "o"
    remote, office = interview_format_flags(fmt)
    return date_s, time_s, remote, office


def _find_bitrix_post(db: Session, candidate_id) -> models.MessagingPost | None:
    posts = list(
        db.scalars(
            select(models.MessagingPost)
            .where(models.MessagingPost.candidate_id == candidate_id)
            .order_by(models.MessagingPost.created_at.desc())
        ).all()
    )
    for p in posts:
        if p.kind not in ("primary", "think_followup"):
            continue
        if str((p.payload or {}).get("provider") or "") == "bitrix":
            return p
        ch = db.get(models.MessagingChannel, p.channel_id)
        if ch and ch.provider == "bitrix":
            return p
    for p in posts:
        if p.kind in ("primary", "think_followup"):
            return p
    return None


def apply_decide_token(
    db: Session,
    token: str,
    *,
    comment: str | None = None,
    meeting_date: str | None = None,
    meeting_time: str | None = None,
    meeting_format: str | None = None,
) -> dict[str, Any]:
    cfg = get_bitrix()
    if not cfg.get("enabled"):
        raise DecideError("Bitrix отключён в настройках", 403)

    try:
        claims = parse_decide_token(token)
    except ValueError as exc:
        raise DecideError(str(exc) or "Недействительная ссылка", 400) from exc

    status_key = claims["status_key"]
    if status_key not in OUR_STATUSES:
        raise DecideError("Неизвестный статус", 400)

    try:
        cid = UUID(claims["candidate_id"])
    except ValueError as exc:
        raise DecideError("Некорректный кандидат", 400) from exc

    candidate = db.get(models.Candidate, cid)
    if not candidate:
        raise DecideError("Кандидат не найден", 404)

    needs_comment = status_key in STATUSES_REQUIRE_COMMENT
    clean_comment = (comment or "").strip()
    if needs_comment and not clean_comment:
        return {
            "ok": False,
            "needs_comment": True,
            "status_key": status_key,
            "status_label": STATUS_LABELS.get(status_key) or status_key,
            "candidate_id": str(candidate.id),
            "candidate_name": candidate.name,
            "token": token,
        }

    meeting_date_s: str | None = None
    meeting_time_s: str | None = None
    remote_interview: bool | None = None
    office_interview: bool | None = None

    if status_key == "ready":
        has_meeting = bool((meeting_date or "").strip() and (meeting_time or "").strip())
        if not has_meeting:
            return {
                "ok": False,
                "needs_meeting": True,
                "status_key": status_key,
                "status_label": STATUS_LABELS.get(status_key) or status_key,
                "candidate_id": str(candidate.id),
                "candidate_name": candidate.name,
                "token": token,
            }
        meeting_date_s, meeting_time_s, remote_interview, office_interview = _parse_meeting_fields(
            meeting_date,
            meeting_time,
            meeting_format,
        )

    apply_client_update(
        candidate,
        status_key=status_key,
        comment=clean_comment or None,
        append_comment=bool(clean_comment),
        office_interview_date=meeting_date_s,
        office_interview_time=meeting_time_s,
        remote_interview=remote_interview,
        office_interview=office_interview,
        actor="bitrix",
        actor_note="decide_link",
    )

    post = _find_bitrix_post(db, candidate.id)
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
        action_payload: dict[str, Any] = {"via": "decide_link", "comment": clean_comment or None}
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
                external_callback_data=f"bitrix:decide:{status_key}",
                payload=action_payload,
                completed_at=datetime.now(timezone.utc),
            )
        )

    try:
        sync_decision_task_for_candidate(
            db,
            candidate,
            status_key=status_key,
            client_comment=clean_comment or None,
        )
        if status_key == "ready" and meeting_date_s and meeting_time_s:
            sync_meeting_task_hr_status(db, candidate, confirmed=False)
    except Exception:  # noqa: BLE001
        pass

    db.commit()
    db.refresh(candidate)
    return {
        "ok": True,
        "needs_comment": False,
        "needs_meeting": False,
        "status_key": status_key,
        "status_label": STATUS_LABELS.get(status_key) or status_key,
        "candidate_id": str(candidate.id),
        "candidate_name": candidate.name,
        "client_status": candidate.client_status,
        "hr_stage": candidate.hr_stage,
        "meeting_date": meeting_date_s,
        "meeting_time": meeting_time_s,
    }
