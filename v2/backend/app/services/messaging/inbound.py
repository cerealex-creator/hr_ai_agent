"""Inbound Telegram updates → domain apply (slice 2)."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.candidate_fields import candidate_public_fields
from app.services.messaging.card_html import build_candidate_card_html
from app.services.messaging.client_apply import (
    apply_client_update,
    candidate_view_dict,
    ensure_tg_callback_id,
)
from app.services.messaging.keyboards import (
    CLIENT_STATUS_META,
    STATUSES_REQUIRE_COMMENT,
    build_change_status_keyboard,
    build_initial_status_keyboard,
    build_interview_date_keyboard,
    build_interview_format_keyboard,
    build_interview_time_keyboard,
    build_locked_keyboard,
    interview_format_flags,
    parse_interview_date_token,
    parse_interview_time_token,
)
from app.services.messaging.channels import (
    ensure_channel_for_vacancy,
    normalize_external_id,
)
from app.services.messaging.telegram_provider import (
    answer_callback_query,
    delete_message,
    edit_html_message,
    edit_message_keyboard,
    send_html_message,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actor_label(user: dict | None) -> str:
    if not user:
        return ""
    username = (user.get("username") or "").strip()
    if username:
        return f"@{username}"
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        return name
    uid = user.get("id")
    return str(uid) if uid is not None else ""


def find_candidate_by_callback_id(db: Session, callback_id: str) -> models.Candidate | None:
    cid = (callback_id or "").strip()
    if not cid:
        return None
    # JSONB path (Postgres)
    try:
        row = db.scalar(
            select(models.Candidate).where(
                models.Candidate.payload["tg_callback_id"].astext == cid
            )
        )
        if row:
            return row
    except Exception:  # noqa: BLE001
        pass
    # Fallback scan (import may lack tg_callback_id; derive from UUID)
    for cand in db.scalars(select(models.Candidate)).all():
        payload = cand.payload or {}
        existing = str(payload.get("tg_callback_id") or "")
        derived = str(cand.id).replace("-", "")[:8]
        if existing == cid or derived == cid:
            ensure_tg_callback_id(cand)
            return cand
    return None


def find_post_for_candidate(
    db: Session, candidate_id, chat_id: str | None = None
) -> models.MessagingPost | None:
    q = (
        select(models.MessagingPost)
        .where(models.MessagingPost.candidate_id == candidate_id)
        .order_by(models.MessagingPost.created_at.desc())
    )
    posts = list(db.scalars(q).all())
    if not posts:
        return None
    if chat_id is None:
        return posts[0]
    for p in posts:
        if str((p.payload or {}).get("chat_id") or "") == str(chat_id):
            return p
        ch = db.get(models.MessagingChannel, p.channel_id)
        if ch and str(ch.external_id) == str(chat_id):
            return p
    return posts[0]


def find_client_chat_post(
    db: Session, candidate: models.Candidate
) -> models.MessagingPost | None:
    """Post in the vacancy client chat (not HR DM / other chats)."""
    vac = db.get(models.Vacancy, candidate.vacancy_id)
    chat_id = (vac.chat_id or "").strip() if vac else ""
    return find_post_for_candidate(db, candidate.id, chat_id or None)


def ensure_post_from_callback(
    db: Session,
    candidate: models.Candidate,
    *,
    chat_id: str | int | None,
    message_id: str | int | None,
) -> models.MessagingPost | None:
    """Anchor MessagingPost to the callback card message (legacy parity)."""
    if chat_id is None or message_id is None:
        return None
    existing = find_post_for_candidate(db, candidate.id, str(chat_id))
    if existing and str(existing.external_message_id) == str(message_id):
        return existing
    if existing:
        # Prefer exact message id match if another row already has it
        by_mid = db.scalar(
            select(models.MessagingPost).where(
                models.MessagingPost.external_message_id == str(message_id)
            )
        )
        if by_mid:
            return by_mid
        existing.external_message_id = str(message_id)
        payload = dict(existing.payload or {})
        payload["chat_id"] = str(normalize_external_id(chat_id) or chat_id)
        existing.payload = payload
        flag_modified(existing, "payload")
        db.flush()
        return existing

    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    if not vacancy:
        return None
    # Prefer vacancy channel; fall back to channel for this chat id
    channel = ensure_channel_for_vacancy(db, vacancy)
    ext = normalize_external_id(chat_id)
    if channel is None and ext:
        channel = db.scalar(
            select(models.MessagingChannel).where(
                models.MessagingChannel.provider == "telegram",
                models.MessagingChannel.external_id == ext,
            )
        )
    if channel is None and ext:
        channel = models.MessagingChannel(
            provider="telegram",
            external_id=ext,
            client_id=vacancy.client_id,
            name=(vacancy.title or "").strip() or f"chat {ext}",
            metadata_json={"source": "callback_anchor", "vacancy_ids": [vacancy.id]},
        )
        db.add(channel)
        db.flush()
    if channel is None:
        return None

    post = models.MessagingPost(
        channel_id=channel.id,
        candidate_id=candidate.id,
        vacancy_id=vacancy.id,
        kind="primary",
        external_message_id=str(message_id),
        text_snapshot="",
        payload={
            "provider": "telegram",
            "chat_id": str(channel.external_id),
            "tg_callback_id": ensure_tg_callback_id(candidate),
            "has_buttons": True,
            "anchored_from_callback": True,
        },
    )
    db.add(post)
    db.flush()
    return post


def _request_comment_prompt(
    db: Session,
    *,
    cq_id: str,
    chat_id: str | int | None,
    message_id: str | int | None,
    post: models.MessagingPost,
    action: models.MessagingAction,
    prompt_html: str,
) -> tuple[bool, str | None]:
    """Send reply-prompt under the card like Streamlit; silent callback ack on success."""
    reply_to = message_id or post.external_message_id
    ok, msg, prompt_mid = send_html_message(
        chat_id,
        prompt_html,
        reply_to_message_id=reply_to,
    )
    if not ok or not prompt_mid:
        answer_callback_query(
            cq_id,
            text=msg or "Не удалось отправить запрос комментария",
            show_alert=True,
        )
        return False, msg
    payload = dict(action.payload or {})
    payload["prompt_message_id"] = str(prompt_mid)
    payload["card_message_id"] = str(reply_to) if reply_to is not None else None
    action.payload = payload
    flag_modified(action, "payload")
    db.commit()
    answer_callback_query(cq_id)
    return True, None


def find_candidate_by_message(
    db: Session, chat_id: str | int, message_id: str | int
) -> tuple[models.Candidate | None, models.MessagingPost | None]:
    mid = str(message_id)
    cid = str(chat_id)
    post = db.scalar(
        select(models.MessagingPost).where(models.MessagingPost.external_message_id == mid)
    )
    if not post:
        return None, None
    ch = db.get(models.MessagingChannel, post.channel_id)
    if ch and str(ch.external_id) != cid:
        # still allow if payload chat matches
        if str((post.payload or {}).get("chat_id") or "") != cid:
            return None, None
    cand = db.get(models.Candidate, post.candidate_id)
    return cand, post


def _cancel_pending_actions(db: Session, post_id, types: set[str] | None = None) -> None:
    q = select(models.MessagingAction).where(
        models.MessagingAction.post_id == post_id,
        models.MessagingAction.status == "pending",
    )
    for action in db.scalars(q).all():
        if types and action.action_type not in types:
            continue
        action.status = "cancelled"
        action.completed_at = _now()


def _create_pending(
    db: Session,
    post: models.MessagingPost,
    action_type: str,
    *,
    callback_data: str | None = None,
    payload: dict | None = None,
) -> models.MessagingAction:
    _cancel_pending_actions(db, post.id, {action_type, "await_comment", "await_status_comment"})
    action = models.MessagingAction(
        post_id=post.id,
        action_type=action_type,
        status="pending",
        external_callback_data=callback_data,
        payload=payload or {},
    )
    db.add(action)
    db.flush()
    return action


def find_pending_for_chat_user(
    db: Session, chat_id: str | int, user_id: str | int | None
) -> models.MessagingAction | None:
    actions = db.scalars(
        select(models.MessagingAction)
        .where(models.MessagingAction.status == "pending")
        .order_by(models.MessagingAction.created_at.desc())
        .limit(50)
    ).all()
    for action in actions:
        p = action.payload or {}
        if str(p.get("chat_id") or "") != str(chat_id):
            continue
        if user_id is not None and str(p.get("user_id") or "") not in ("", str(user_id)):
            continue
        if action.action_type in ("await_comment", "await_status_comment"):
            return action
    return None


def build_card_text(db: Session, candidate: models.Candidate, *, locked: bool) -> str:
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    fields = candidate_public_fields(candidate.payload)
    view = candidate_view_dict(candidate)
    status = candidate.client_status or "wait"
    return build_candidate_card_html(
        name=candidate.name,
        vacancy_title=(vacancy.title if vacancy else "") or "",
        resume_link=fields.get("resume_link"),
        hh_resume_link=fields.get("hh_resume_link"),
        video_link=fields.get("video_link"),
        portfolio_link=fields.get("portfolio_link"),
        task_link=fields.get("task_link"),
        hr_comment=fields.get("hr_comment") or (candidate.payload or {}).get("hr_comment"),
        locked=locked,
        status_key=status if locked else None,
        client_comment=view.get("client_comment"),
        office_interview_date=view.get("office_interview_date"),
        office_interview_time=view.get("office_interview_time"),
        remote_interview=bool(view.get("remote_interview")),
        office_interview=bool(view.get("office_interview")),
        meeting_hr_confirmed=bool((candidate.payload or {}).get("meeting_hr_confirmed")),
    )


def keyboard_for_candidate(candidate: models.Candidate, *, mode: str = "auto") -> dict:
    view = candidate_view_dict(candidate)
    cid = str(view["tg_callback_id"])
    status = candidate.client_status or "wait"
    if mode == "change":
        return build_change_status_keyboard(cid, status)
    if mode == "initial" or status in ("", "wait"):
        return build_initial_status_keyboard(cid, status or "wait")
    return build_locked_keyboard(
        cid,
        status=status,
        date_str=view.get("office_interview_date"),
        time_str=view.get("office_interview_time"),
    )


def refresh_card_message(
    db: Session,
    candidate: models.Candidate,
    post: models.MessagingPost,
    *,
    mode: str = "auto",
    interview_prompt: str | None = None,
) -> tuple[bool, str]:
    ch = db.get(models.MessagingChannel, post.channel_id)
    if not ch:
        return False, "channel missing"
    locked = mode not in ("initial", "change") and (candidate.client_status or "wait") not in (
        "",
        "wait",
    )
    if mode == "change":
        locked = True
    text = build_card_text(db, candidate, locked=locked and mode != "initial")
    if interview_prompt:
        text = f"{text}\n\n{interview_prompt}"
    kb = keyboard_for_candidate(candidate, mode=mode)
    ok, msg = edit_html_message(ch.external_id, post.external_message_id, text, reply_markup=kb)
    if ok:
        post.text_snapshot = text
        flag_modified(post, "payload")
    return ok, msg


def _complete_action(action: models.MessagingAction, result: dict | None = None) -> None:
    action.status = "completed"
    action.completed_at = _now()
    if result:
        payload = dict(action.payload or {})
        payload["result"] = result
        action.payload = payload


def handle_callback_query(db: Session, cq: dict) -> dict[str, Any]:
    data = str(cq.get("data") or "")
    cq_id = str(cq.get("id") or "")
    user = cq.get("from") or {}
    message = cq.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    parts = data.split(":")
    if len(parts) < 2:
        answer_callback_query(cq_id, text="Некорректные данные", show_alert=True)
        return {"handled": False, "error": "bad callback"}

    prefix = parts[0]
    callback_id = parts[1]
    candidate = find_candidate_by_callback_id(db, callback_id)
    if not candidate:
        answer_callback_query(cq_id, text="Кандидат не найден", show_alert=True)
        return {"handled": False, "error": "candidate not found"}

    post = find_post_for_candidate(db, candidate.id, str(chat_id) if chat_id is not None else None)
    if not post and message_id is not None:
        # create synthetic post row if outbound was from elsewhere — try by message id
        found_c, found_p = find_candidate_by_message(db, chat_id, message_id)
        if found_p:
            post = found_p
    if not post and message_id is not None:
        post = ensure_post_from_callback(
            db, candidate, chat_id=chat_id, message_id=message_id
        )

    actor = _actor_label(user)
    event: dict[str, Any] = {
        "type": "telegram.callback_query",
        "prefix": prefix,
        "callback_id": callback_id,
        "candidate_id": str(candidate.id),
    }

    # --- status ---
    if prefix == "cs" and len(parts) >= 3:
        status_key = parts[2]
        if status_key not in ("ready", "think", "reject", "offer"):
            answer_callback_query(cq_id, text="Неизвестный статус", show_alert=True)
            return {**event, "handled": False}

        if status_key in STATUSES_REQUIRE_COMMENT:
            if not post:
                answer_callback_query(cq_id, text="Нет карточки в чате", show_alert=True)
                return {**event, "handled": False}
            meta = CLIENT_STATUS_META.get(status_key) or {}
            label = meta.get("label") or status_key
            action = _create_pending(
                db,
                post,
                "await_status_comment",
                callback_data=data,
                payload={
                    "chat_id": str(chat_id),
                    "user_id": str(user.get("id") or ""),
                    "status_key": status_key,
                    "actor": actor,
                },
            )
            db.flush()
            ok, err = _request_comment_prompt(
                db,
                cq_id=cq_id,
                chat_id=chat_id,
                message_id=message_id,
                post=post,
                action=action,
                prompt_html=(
                    f"💬 Напишите комментарий к статусу «{html.escape(label)}» "
                    f"ответом на это сообщение."
                ),
            )
            if not ok:
                action.status = "cancelled"
                action.completed_at = _now()
                db.commit()
                return {**event, "handled": False, "error": err or "prompt failed"}
            return {**event, "handled": True, "awaiting": "status_comment", "status_key": status_key}

        apply_client_update(candidate, status_key=status_key, actor="telegram", actor_note=actor)
        if post:
            db.add(
                models.MessagingAction(
                    post_id=post.id,
                    action_type=f"status:{status_key}",
                    status="completed",
                    external_callback_data=data,
                    payload={"actor": actor},
                    completed_at=_now(),
                )
            )
        db.commit()
        if post:
            refresh_card_message(db, candidate, post, mode="auto")
            db.commit()
            if status_key == "ready":
                view = candidate_view_dict(candidate)
                if not (view.get("office_interview_date") and view.get("office_interview_time")):
                    cid = ensure_tg_callback_id(candidate)
                    ch = db.get(models.MessagingChannel, post.channel_id)
                    if ch:
                        edit_message_keyboard(
                            ch.external_id,
                            post.external_message_id,
                            build_interview_date_keyboard(cid),
                        )
        answer_callback_query(cq_id, text="Статус сохранён")
        return {**event, "handled": True, "status_key": status_key}

    # --- free comment ---
    if prefix == "cc":
        if not post:
            answer_callback_query(cq_id, text="Нет карточки в чате", show_alert=True)
            return {**event, "handled": False}
        action = _create_pending(
            db,
            post,
            "await_comment",
            callback_data=data,
            payload={
                "chat_id": str(chat_id),
                "user_id": str(user.get("id") or ""),
                "actor": actor,
            },
        )
        db.flush()
        ok, err = _request_comment_prompt(
            db,
            cq_id=cq_id,
            chat_id=chat_id,
            message_id=message_id,
            post=post,
            action=action,
            prompt_html="💬 Напишите комментарий к кандидату следующим сообщением в чат.",
        )
        if not ok:
            action.status = "cancelled"
            action.completed_at = _now()
            db.commit()
            return {**event, "handled": False, "error": err or "prompt failed"}
        return {**event, "handled": True, "awaiting": "comment"}

    # --- change status / cancel ---
    if prefix == "cchg":
        if post:
            refresh_card_message(db, candidate, post, mode="change")
            db.commit()
        answer_callback_query(cq_id)
        return {**event, "handled": True, "mode": "change"}

    if prefix == "ccl":
        if post:
            refresh_card_message(db, candidate, post, mode="auto")
            db.commit()
        answer_callback_query(cq_id)
        return {**event, "handled": True, "mode": "cancel_change"}

    # --- interview wizard ---
    if prefix == "ivi":
        cid = ensure_tg_callback_id(candidate)
        if post:
            ch = db.get(models.MessagingChannel, post.channel_id)
            if ch:
                edit_message_keyboard(
                    ch.external_id,
                    post.external_message_id,
                    build_interview_date_keyboard(cid),
                )
        answer_callback_query(cq_id, text="Выберите дату")
        return {**event, "handled": True, "wizard": "date"}

    if prefix == "ivd" and len(parts) >= 3:
        date_token = parts[2]
        cid = ensure_tg_callback_id(candidate)
        if post:
            ch = db.get(models.MessagingChannel, post.channel_id)
            if ch:
                edit_message_keyboard(
                    ch.external_id,
                    post.external_message_id,
                    build_interview_time_keyboard(cid, date_token),
                )
        answer_callback_query(cq_id, text="Выберите время")
        return {**event, "handled": True, "wizard": "time", "date": date_token}

    if prefix == "ivt" and len(parts) >= 4:
        date_token, time_token = parts[2], parts[3]
        cid = ensure_tg_callback_id(candidate)
        if post:
            ch = db.get(models.MessagingChannel, post.channel_id)
            if ch:
                edit_message_keyboard(
                    ch.external_id,
                    post.external_message_id,
                    build_interview_format_keyboard(cid, date_token, time_token),
                )
        answer_callback_query(cq_id, text="Формат встречи")
        return {**event, "handled": True, "wizard": "format"}

    if prefix == "ivf" and len(parts) >= 5:
        date_token, time_token, fmt = parts[2], parts[3], parts[4]
        try:
            date_str = parse_interview_date_token(date_token)
            time_str = parse_interview_time_token(time_token)
        except ValueError:
            answer_callback_query(cq_id, text="Некорректная дата/время", show_alert=True)
            return {**event, "handled": False}
        remote, office = interview_format_flags(fmt)
        if (candidate.client_status or "wait") in ("", "wait"):
            apply_client_update(
                candidate,
                status_key="ready",
                office_interview_date=date_str,
                office_interview_time=time_str,
                remote_interview=remote,
                office_interview=office,
                actor="telegram",
                actor_note=actor,
            )
        else:
            apply_client_update(
                candidate,
                office_interview_date=date_str,
                office_interview_time=time_str,
                remote_interview=remote,
                office_interview=office,
                actor="telegram",
                actor_note=actor,
            )
        if post:
            db.add(
                models.MessagingAction(
                    post_id=post.id,
                    action_type="meeting_scheduled",
                    status="completed",
                    external_callback_data=data,
                    payload={
                        "date": date_str,
                        "time": time_str,
                        "remote": remote,
                        "office": office,
                        "actor": actor,
                    },
                    completed_at=_now(),
                )
            )
            db.commit()
            refresh_card_message(db, candidate, post, mode="auto")
            db.commit()
        else:
            db.commit()
        # Notify HR to confirm meeting
        try:
            from app.core.config import get_settings
            from app.services.messaging.attendance import (
                build_hr_confirm_message,
                hr_confirm_keyboard,
                set_meeting_hr_confirmed,
            )

            set_meeting_hr_confirmed(candidate, False)
            db.commit()
            hr = (get_settings().telegram_hr_user_id or "").strip()
            if hr:
                cid = ensure_tg_callback_id(candidate)
                vac = db.get(models.Vacancy, candidate.vacancy_id)
                send_html_message(
                    hr,
                    build_hr_confirm_message(candidate, vac.title if vac else ""),
                    reply_markup=hr_confirm_keyboard(cid),
                )
        except Exception:  # noqa: BLE001
            pass
        answer_callback_query(cq_id, text="Встреча сохранена")
        return {**event, "handled": True, "meeting": {"date": date_str, "time": time_str}}

    if prefix == "ivc":
        if post:
            refresh_card_message(db, candidate, post, mode="auto")
            db.commit()
        answer_callback_query(cq_id, text="Отменено")
        return {**event, "handled": True, "wizard": "cancel"}

    if prefix == "ivx":
        apply_client_update(
            candidate,
            office_interview_date="",
            office_interview_time="",
            remote_interview=False,
            office_interview=False,
            actor="telegram",
            actor_note=actor,
        )
        # clear via empty strings already; also meeting_hr
        from app.services.messaging.client_apply import clear_client_meeting

        clear_client_meeting(candidate)
        if post:
            db.add(
                models.MessagingAction(
                    post_id=post.id,
                    action_type="meeting_cancelled",
                    status="completed",
                    external_callback_data=data,
                    payload={"actor": actor},
                    completed_at=_now(),
                )
            )
            db.commit()
            refresh_card_message(db, candidate, post, mode="auto")
            db.commit()
        else:
            db.commit()
        answer_callback_query(cq_id, text="Встреча отменена")
        return {**event, "handled": True, "meeting": "cancelled"}

    # --- attendance / HR confirm (buttons live in HR DM — refresh client chat card) ---
    if prefix in ("iac", "iak", "icl", "mhc"):
        from app.services.messaging.attendance import set_attendance_status, set_meeting_hr_confirmed

        client_post = find_client_chat_post(db, candidate) or post
        if prefix == "mhc":
            set_meeting_hr_confirmed(candidate, True)
            db.commit()
            if client_post:
                refresh_card_message(db, candidate, client_post, mode="auto")
                db.commit()
            answer_callback_query(cq_id, text="Встреча подтверждена HR")
            return {**event, "handled": True, "hr_confirm": True}
        status_map = {
            "iac": "confirmed",
            "iak": "cancelled_candidate",
            "icl": "cancelled_client",
        }
        set_attendance_status(candidate, status_map[prefix])
        db.commit()
        if client_post:
            refresh_card_message(db, candidate, client_post, mode="auto")
            db.commit()
        labels = {
            "iac": "Явка подтверждена",
            "iak": "Отмена кандидатом",
            "icl": "Отмена заказчиком",
        }
        answer_callback_query(cq_id, text=labels[prefix])
        return {**event, "handled": True, "attendance": status_map[prefix]}

    # --- candidate navigator ---
    if prefix in ("cn", "cnp", "cnn"):
        from app.services.messaging.navigator import handle_nav_callback

        return handle_nav_callback(db, cq, event, prefix, callback_id, candidate, post)

    answer_callback_query(cq_id, text="Действие пока не поддерживается", show_alert=True)
    return {**event, "handled": False, "note": f"unsupported prefix {prefix}"}


def _esc_name(name: str) -> str:
    import html

    return html.escape(name or "")


def _telegram_message_link(chat_id: str | int | None, message_id: str | int | None) -> str | None:
    """Deep-link to a message in a private/public supergroup (`t.me/c/...`)."""
    if chat_id is None or message_id is None:
        return None
    mid = str(message_id).strip()
    if not mid.isdigit():
        return None
    raw = str(chat_id).strip()
    if raw.startswith("-100") and raw[4:].isdigit():
        return f"https://t.me/c/{raw[4:]}/{mid}"
    return None


def _comment_saved_notice(
    *,
    name: str,
    comment_text: str,
    status_key: str | None = None,
    card_link: str | None = None,
) -> str:
    import html

    preview = (comment_text or "").strip()
    if len(preview) > 400:
        preview = preview[:400].rstrip() + "…"
    esc_comment = html.escape(preview)
    if status_key:
        meta = CLIENT_STATUS_META.get(status_key) or {}
        label = html.escape(str(meta.get("label") or status_key))
        head = f"✅ Комментарий к статусу «{label}»"
    else:
        head = "✅ Комментарий"
    lines = [
        f"{head} для <b>{_esc_name(name)}</b> сохранён:",
        f"«{esc_comment}»",
    ]
    if card_link:
        lines.append(f'<a href="{html.escape(card_link, quote=True)}">Открыть карточку в чате</a>')
    else:
        lines.append("<i>Ответ на карточку кандидата выше ↑</i>")
    return "\n".join(lines)


def _finalize_comment_in_chat(
    *,
    chat_id: str | int | None,
    user_message_id: str | int | None,
    prompt_message_id: str | int | None,
    post: models.MessagingPost,
    candidate: models.Candidate,
    comment_text: str,
    status_key: str | None = None,
) -> None:
    """Delete prompt + user comment, post confirmation reply to the candidate card."""
    if chat_id is None:
        return
    if prompt_message_id:
        delete_message(chat_id, prompt_message_id)
    if user_message_id is not None:
        delete_message(chat_id, user_message_id)

    card_mid = post.external_message_id
    link = _telegram_message_link(chat_id, card_mid)
    notice = _comment_saved_notice(
        name=candidate.name or "",
        comment_text=comment_text,
        status_key=status_key,
        card_link=link,
    )
    send_html_message(
        chat_id,
        notice,
        reply_to_message_id=card_mid,
    )


def handle_message(db: Session, message: dict) -> dict[str, Any]:
    if message.get("from", {}).get("is_bot"):
        return {"type": "telegram.message", "handled": False, "note": "bot message"}
    text = (message.get("text") or "").strip()
    if not text:
        return {"type": "telegram.message", "handled": False, "note": "empty"}

    # Group / private slash-commands
    if text.startswith("/"):
        from app.services.messaging.commands import handle_group_command

        cmd_event = handle_group_command(db, message)
        if cmd_event is not None:
            return cmd_event

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    user_message_id = message.get("message_id")
    user = message.get("from") or {}
    actor = _actor_label(user)
    reply = message.get("reply_to_message") or {}
    reply_mid = reply.get("message_id")

    action = None
    candidate = None
    post = None

    if reply_mid is not None:
        candidate, post = find_candidate_by_message(db, chat_id, reply_mid)
        if post:
            action = db.scalar(
                select(models.MessagingAction)
                .where(
                    models.MessagingAction.post_id == post.id,
                    models.MessagingAction.status == "pending",
                    models.MessagingAction.action_type.in_(
                        ("await_comment", "await_status_comment")
                    ),
                )
                .order_by(models.MessagingAction.created_at.desc())
            )
        if action is None:
            # Reply to the prompt message (not the card)
            pending = find_pending_for_chat_user(db, chat_id, user.get("id"))
            if pending and str((pending.payload or {}).get("prompt_message_id") or "") == str(
                reply_mid
            ):
                action = pending
                post = db.get(models.MessagingPost, pending.post_id)
                if post:
                    candidate = db.get(models.Candidate, post.candidate_id)

    if action is None:
        action = find_pending_for_chat_user(db, chat_id, user.get("id"))
        if action and candidate is None:
            post = db.get(models.MessagingPost, action.post_id)
            if post:
                candidate = db.get(models.Candidate, post.candidate_id)

    if not action or not candidate or not post:
        return {"type": "telegram.message", "handled": False, "note": "no pending comment"}

    payload = dict(action.payload or {})
    if action.action_type == "await_status_comment":
        status_key = payload.get("status_key")
        apply_client_update(
            candidate,
            status_key=status_key,
            comment=text,
            append_comment=True,
            actor="telegram",
            actor_note=actor or payload.get("actor") or "",
        )
        _complete_action(action, {"status_key": status_key, "comment": text})
        db.commit()
        refresh_card_message(db, candidate, post, mode="auto")
        db.commit()
        _finalize_comment_in_chat(
            chat_id=chat_id,
            user_message_id=user_message_id,
            prompt_message_id=payload.get("prompt_message_id"),
            post=post,
            candidate=candidate,
            comment_text=text,
            status_key=str(status_key) if status_key else None,
        )
        if status_key == "ready":
            view = candidate_view_dict(candidate)
            if not (view.get("office_interview_date") and view.get("office_interview_time")):
                cid = ensure_tg_callback_id(candidate)
                ch = db.get(models.MessagingChannel, post.channel_id)
                if ch:
                    edit_message_keyboard(
                        ch.external_id,
                        post.external_message_id,
                        build_interview_date_keyboard(cid),
                    )
        return {
            "type": "telegram.message",
            "handled": True,
            "status_key": status_key,
            "candidate_id": str(candidate.id),
        }

    # free comment
    apply_client_update(
        candidate,
        comment=text,
        append_comment=True,
        actor="telegram",
        actor_note=actor or payload.get("actor") or "",
    )
    _complete_action(action, {"comment": text})
    db.commit()
    refresh_card_message(db, candidate, post, mode="auto")
    db.commit()
    _finalize_comment_in_chat(
        chat_id=chat_id,
        user_message_id=user_message_id,
        prompt_message_id=payload.get("prompt_message_id"),
        post=post,
        candidate=candidate,
        comment_text=text,
        status_key=None,
    )
    return {
        "type": "telegram.message",
        "handled": True,
        "comment": True,
        "candidate_id": str(candidate.id),
    }


def process_telegram_update(db: Session, payload: dict) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return events
    if payload.get("callback_query"):
        events.append(handle_callback_query(db, payload["callback_query"]))
    elif payload.get("message"):
        events.append(handle_message(db, payload["message"]))
    return events
