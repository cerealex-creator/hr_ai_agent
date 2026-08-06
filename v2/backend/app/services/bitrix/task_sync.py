"""Sync Bitrix task DESCRIPTION + comment when candidate status / meeting changes."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.app_settings import get_bitrix
from app.services.bitrix.client import BitrixError, add_task_comment, get_task, update_task
from app.services.bitrix.tokens import STATUS_ICONS, STATUS_LABELS

logger = logging.getLogger(__name__)

STATUS_BLOCK_START = "---HRA_STATUS---"
STATUS_BLOCK_END = "---/HRA_STATUS---"
MEETING_BLOCK_START = "---HRA_MEETING---"
MEETING_BLOCK_END = "---/HRA_MEETING---"


def _tz() -> ZoneInfo:
    return ZoneInfo("Europe/Moscow")


def _now_stamp() -> str:
    return datetime.now(_tz()).strftime("%d.%m.%Y, %H:%M")


def _bb_esc(text: str) -> str:
    return (text or "").replace("[", "(").replace("]", ")")


def upsert_description_block(description: str, start: str, end: str, body: str) -> str:
    block = f"{start}\n{body.strip()}\n{end}"
    pattern = re.escape(start) + r".*?" + re.escape(end)
    if re.search(pattern, description or "", flags=re.DOTALL):
        return re.sub(pattern, block, description, count=1, flags=re.DOTALL)
    base = (description or "").strip()
    if not base:
        return block
    return f"{block}\n\n{base}"


def _meeting_format_label(payload: dict[str, Any]) -> str:
    remote = bool(payload.get("remote_interview"))
    office = bool(payload.get("office_interview"))
    if remote and office:
        return "онлайн / офис"
    if remote:
        return "онлайн"
    if office:
        return "в офисе"
    return ""


def build_decision_status_block(
    candidate: models.Candidate,
    *,
    status_key: str,
    client_comment: str | None = None,
) -> tuple[str, str]:
    """Returns (bbcode_block_body, plain_comment_for_feed)."""
    icon = STATUS_ICONS.get(status_key) or ""
    label = STATUS_LABELS.get(status_key) or status_key
    title = f"{icon} {label}".strip()
    lines = [f"[b]Текущий статус:[/b] {title}"]
    plain_parts = [f"Текущий статус: {label}"]

    p = candidate.payload or {}
    if status_key == "ready":
        date_s = str(p.get("office_interview_date") or "").strip()
        time_s = str(p.get("office_interview_time") or "").strip()
        if date_s and time_s:
            try:
                display_date = datetime.strptime(date_s, "%Y-%m-%d").strftime("%d.%m.%Y")
            except ValueError:
                display_date = date_s
            fmt = _meeting_format_label(p)
            when = f"{display_date}, {time_s}"
            if fmt:
                when = f"{when} ({fmt})"
            lines.append(f"[b]Дата встречи:[/b] {when}")
            plain_parts.append(f"Дата встречи: {when}")

    comment = (client_comment or "").strip()
    if not comment and status_key in ("think", "reject"):
        comment = str(p.get("client_comment") or "").strip().split("\n")[-1].strip()

    if comment:
        lines.append(f"[i]Комментарий заказчика:[/i] {_bb_esc(comment)}")
        plain_parts.append(f"Комментарий: {comment}")

    lines.append(f"[i]Обновлено: {_now_stamp()}[/i]")
    plain_parts.append(f"({_now_stamp()})")
    return "\n".join(lines), " · ".join(plain_parts)


def build_meeting_status_block(*, confirmed: bool) -> tuple[str, str]:
    if confirmed:
        body = f"[b]Статус:[/b] Встреча подтверждена HR\n[i]Обновлено: {_now_stamp()}[/i]"
        comment = f"Встреча подтверждена HR ({_now_stamp()})"
    else:
        body = f"[b]Статус:[/b] Ожидает подтверждения HR\n[i]Обновлено: {_now_stamp()}[/i]"
        comment = "Ожидает подтверждения HR"
    return body, comment


def initial_decision_status_block() -> str:
    body = "[b]Текущий статус:[/b] ⏳ Ждёт оценки"
    return f"{STATUS_BLOCK_START}\n{body}\n{STATUS_BLOCK_END}"


def initial_meeting_status_block() -> str:
    body = "[b]Статус:[/b] Ожидает подтверждения HR"
    return f"{MEETING_BLOCK_START}\n{body}\n{MEETING_BLOCK_END}"


def find_decision_task_post(db: Session, candidate_id) -> models.MessagingPost | None:
    posts = list(
        db.scalars(
            select(models.MessagingPost)
            .where(
                models.MessagingPost.candidate_id == candidate_id,
                models.MessagingPost.kind.in_(("primary", "think_followup")),
            )
            .order_by(models.MessagingPost.created_at.desc())
            .limit(20)
        ).all()
    )
    for p in posts:
        if str((p.payload or {}).get("provider") or "") == "bitrix":
            return p
    return posts[0] if posts else None


def find_meeting_task_post(db: Session, candidate: models.Candidate) -> models.MessagingPost | None:
    tid = str((candidate.payload or {}).get("bitrix_meeting_task_id") or "").strip()
    if tid:
        post = db.scalar(
            select(models.MessagingPost).where(models.MessagingPost.external_message_id == tid)
        )
        if post:
            return post
    return db.scalars(
        select(models.MessagingPost)
        .where(
            models.MessagingPost.candidate_id == candidate.id,
            models.MessagingPost.kind == "meeting",
        )
        .order_by(models.MessagingPost.created_at.desc())
        .limit(1)
    ).first()


def _task_description(task: dict[str, Any], fallback: str = "") -> str:
    desc = task.get("description") or task.get("DESCRIPTION") or fallback
    return str(desc or "")


def _push_task_update(
    task_id: str,
    description: str,
    comment: str,
    *,
    post: models.MessagingPost | None = None,
) -> bool:
    try:
        update_task(
            task_id,
            {
                "DESCRIPTION": description,
                "DESCRIPTION_IN_BBCODE": "Y",
            },
        )
        add_task_comment(task_id, comment)
        if post is not None:
            post.text_snapshot = description
        return True
    except BitrixError as exc:
        logger.warning("bitrix task sync failed for #%s: %s", task_id, exc.message)
        return False


def sync_decision_task_for_candidate(
    db: Session,
    candidate: models.Candidate,
    *,
    status_key: str,
    client_comment: str | None = None,
) -> bool:
    if not get_bitrix().get("enabled"):
        return False
    if status_key not in ("ready", "think", "reject", "offer"):
        return False

    post = find_decision_task_post(db, candidate.id)
    if not post:
        return False
    task_id = str(post.external_message_id or (post.payload or {}).get("task_id") or "").strip()
    if not task_id:
        return False

    try:
        task = get_task(task_id)
    except BitrixError:
        task = {}

    current = _task_description(task, post.text_snapshot or "")
    body, comment = build_decision_status_block(
        candidate, status_key=status_key, client_comment=client_comment
    )
    updated = upsert_description_block(current, STATUS_BLOCK_START, STATUS_BLOCK_END, body)
    ok = _push_task_update(task_id, updated, comment, post=post)
    if ok:
        db.add(post)
    return ok


def sync_meeting_task_hr_status(
    db: Session,
    candidate: models.Candidate,
    *,
    confirmed: bool,
) -> bool:
    if not get_bitrix().get("enabled"):
        return False

    post = find_meeting_task_post(db, candidate)
    if not post:
        return False
    task_id = str(post.external_message_id or (post.payload or {}).get("task_id") or "").strip()
    if not task_id:
        return False

    try:
        task = get_task(task_id)
    except BitrixError:
        task = {}

    current = _task_description(task, post.text_snapshot or "")
    body, comment = build_meeting_status_block(confirmed=confirmed)
    updated = upsert_description_block(current, MEETING_BLOCK_START, MEETING_BLOCK_END, body)
    ok = _push_task_update(task_id, updated, comment, post=post)
    if ok:
        db.add(post)
    return ok
