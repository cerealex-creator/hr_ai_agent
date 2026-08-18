"""Vacancy-scoped resume mockup zone: PDFs without contacts for client screening."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.candidate_fields import normalize_gender
from app.services.candidate_write import apply_hr_stage
from app.services.demo_showcase import client_org_is_demo
from app.services.tenancy import generate_client_zone_token
from app.services.yandex_public import yandex_link_for_display

PREVIEW_ACTIONS = frozenset({"consider", "reject"})
PREVIEW_ACTIONABLE = frozenset({"", "wait"})
MAX_STRENGTHS = 6
MAX_WEAKNESSES = 6


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _https_url(raw: Any) -> str | None:
    display = (yandex_link_for_display(str(raw or "")) or "").strip()
    if display.startswith(("http://", "https://")):
        return display
    return None


def _bullet_list(payload: dict[str, Any], *keys: str, limit: int) -> list[str]:
    raw: list[Any] = []
    for key in keys:
        val = payload.get(key)
        if isinstance(val, list) and val:
            raw = val
            break
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _strengths(payload: dict[str, Any]) -> list[str]:
    return _bullet_list(payload, "ai_strengths", "resume_ai_strengths", limit=MAX_STRENGTHS)


def _weaknesses(payload: dict[str, Any]) -> list[str]:
    return _bullet_list(payload, "ai_weaknesses", "resume_ai_weaknesses", limit=MAX_WEAKNESSES)


def anonymized_pdf_url(payload: dict[str, Any] | None) -> str | None:
    p = payload or {}
    return _https_url(p.get("anonymized_resume_link"))


def is_preview_ready(payload: dict[str, Any] | None) -> bool:
    return bool(anonymized_pdf_url(payload))


def is_resume_preview_included(payload: dict[str, Any] | None) -> bool:
    """Кандидат в пачке макетов — не в основной воронке вакансии."""
    return bool((payload or {}).get("resume_preview_included"))


def is_resume_preview_visible(payload: dict[str, Any] | None) -> bool:
    """Показывать в публичной зоне /m/…. Старые карточки без ключа — видны."""
    p = payload or {}
    if "resume_preview_visible" not in p:
        return True
    return bool(p.get("resume_preview_visible"))


def sql_not_resume_preview():
    """SQL: не показывать макеты в обычных списках и счётчиках."""
    flag = models.Candidate.payload["resume_preview_included"].astext
    return or_(flag.is_(None), flag != "true")


def mark_resume_preview(
    candidate: models.Candidate,
    *,
    pdf_url: str | None = None,
    included: bool = True,
) -> None:
    payload = dict(candidate.payload or {})
    url = (pdf_url or "").strip()
    if url:
        payload["anonymized_resume_link"] = url
        if not str(payload.get("resume_link") or "").strip():
            payload["resume_link"] = url
    payload["resume_preview_included"] = bool(included)
    if included:
        payload["resume_preview_visible"] = True
    status = str(payload.get("resume_preview_status") or "").strip()
    if included and status not in ("consider", "reject"):
        payload["resume_preview_status"] = "wait"
    candidate.payload = payload
    flag_modified(candidate, "payload")


def resume_preview_path(token: str) -> str:
    return f"/m/{token}"


def resume_preview_public_url(token: str, *, settings: Any = None) -> str:
    from app.services.interview_digest import public_app_base

    base = public_app_base(settings)
    if not base:
        return ""
    return f"{base}{resume_preview_path(token)}"


def _vacancy_token(vacancy: models.Vacancy) -> str:
    return str((vacancy.payload or {}).get("resume_preview_token") or "").strip()


def ensure_preview_token(db: Session, vacancy: models.Vacancy) -> str:
    existing = _vacancy_token(vacancy)
    if existing:
        return existing
    token = generate_client_zone_token(db)
    payload = dict(vacancy.payload or {})
    payload["resume_preview_token"] = token
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return token


def resolve_preview_vacancy(db: Session, token: str) -> models.Vacancy:
    raw = (token or "").strip()
    if not raw:
        raise HTTPException(status_code=404, detail="Zone not found")
    row = db.scalar(
        select(models.Vacancy).where(
            models.Vacancy.payload["resume_preview_token"].astext == raw
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Zone not found")
    return row


def _header(db: Session, vacancy: models.Vacancy) -> dict[str, Any]:
    company = ""
    department = None
    demo = False
    if vacancy.client_id is not None:
        client = db.get(models.Client, vacancy.client_id)
        if client:
            demo = client_org_is_demo(db, client)
            if client.parent_id:
                parent = db.get(models.Client, client.parent_id)
                company = (parent.name if parent else "") or client.name
                department = client.name
            else:
                company = client.name
    return {
        "vacancy_id": vacancy.id,
        "vacancy_title": vacancy.title,
        "company_name": company,
        "department_name": department,
        "demo": demo,
    }


def _card(c: models.Candidate, *, demo: bool) -> dict[str, Any]:
    payload = c.payload or {}
    status = str(payload.get("resume_preview_status") or "wait").strip() or "wait"
    resume_url = anonymized_pdf_url(payload)
    actionable = status in PREVIEW_ACTIONABLE and not demo and bool(resume_url)
    return {
        "id": str(c.id),
        "name": c.name or "Кандидат",
        "photo_url": (str(payload.get("photo_url") or "").strip() or None),
        "gender": normalize_gender(payload.get("gender") or payload.get("sex")),
        "resume_url": resume_url,
        "ai_strengths": _strengths(payload),
        "ai_weaknesses": _weaknesses(payload),
        "status": status,
        "actionable": actionable,
        "ready": bool(resume_url),
    }


def _included_candidates(db: Session, vacancy_id: int) -> list[models.Candidate]:
    rows = list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)
        ).all()
    )
    out: list[models.Candidate] = []
    for c in rows:
        payload = c.payload or {}
        if not bool(payload.get("resume_preview_included")):
            continue
        if not is_resume_preview_visible(payload):
            continue
        out.append(c)
    out.sort(key=lambda c: (c.name or "").casefold())
    return out


def list_preview_pack(db: Session, token: str) -> dict[str, Any]:
    vacancy = resolve_preview_vacancy(db, token)
    header = _header(db, vacancy)
    demo = bool(header.get("demo"))
    cards = [_card(c, demo=demo) for c in _included_candidates(db, vacancy.id)]
    cards = [x for x in cards if x.get("ready")]
    waiting = [x for x in cards if x["actionable"]]
    done = [x for x in cards if not x["actionable"]]
    return {
        "vacancy": header,
        "candidates": waiting + done,
        "demo": demo,
    }


def apply_preview_decision(
    db: Session,
    token: str,
    candidate_id: str,
    *,
    action: str,
    comment: str | None = None,
) -> dict[str, Any]:
    key = (action or "").strip()
    if key not in PREVIEW_ACTIONS:
        raise HTTPException(status_code=400, detail="Нужно: consider или reject")
    vacancy = resolve_preview_vacancy(db, token)
    header = _header(db, vacancy)
    if header.get("demo"):
        raise HTTPException(status_code=403, detail="В демо решения недоступны")
    try:
        cid = UUID(str(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate or candidate.vacancy_id != vacancy.id:
        raise HTTPException(status_code=404, detail="Кандидат не найден")
    payload = dict(candidate.payload or {})
    if not bool(payload.get("resume_preview_included")) or not is_resume_preview_visible(payload):
        raise HTTPException(status_code=404, detail="Кандидат не в пачке макетов")
    current = str(payload.get("resume_preview_status") or "wait").strip() or "wait"
    if current not in PREVIEW_ACTIONABLE:
        raise HTTPException(status_code=400, detail="Решение по этому макету уже сохранено")
    if not anonymized_pdf_url(payload):
        raise HTTPException(status_code=400, detail="Нет ссылки на PDF макета")

    payload["resume_preview_status"] = key
    note = (comment or "").strip()
    if note:
        prev = str(payload.get("client_comment") or "").strip()
        stamp = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
        label = "Можно рассмотреть" if key == "consider" else "Отказ"
        line = f"[{stamp} · макет · {label}] {note}"
        payload["client_comment"] = f"{prev}\n{line}".strip() if prev else line
    candidate.payload = payload
    flag_modified(candidate, "payload")

    if key == "reject":
        apply_hr_stage(candidate, "rejected_client", "отказ по макету резюме")
        candidate.client_status = "reject"
        candidate.status_updated_at = _now_iso()

    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    _notify_preview_decision(db, vacancy, candidate, key, note)
    return {"ok": True, "candidate": _card(candidate, demo=False)}


def pack_status(db: Session, vacancy: models.Vacancy) -> dict[str, Any]:
    token = _vacancy_token(vacancy)
    items: list[dict[str, Any]] = []
    ready_n = 0
    for c in db.scalars(
        select(models.Candidate).where(models.Candidate.vacancy_id == vacancy.id)
    ).all():
        payload = c.payload or {}
        included = bool(payload.get("resume_preview_included"))
        visible = is_resume_preview_visible(payload)
        url = anonymized_pdf_url(payload)
        raw = str(payload.get("anonymized_resume_link") or "").strip()
        photo = str(payload.get("photo_url") or "").strip() or None
        item = {
            "id": str(c.id),
            "name": c.name or "Кандидат",
            "included": included,
            "visible": visible,
            "ready": bool(url),
            "has_photo": bool(photo),
            "photo_url": photo,
            "gender": normalize_gender(payload.get("gender") or payload.get("sex")),
            "strengths_count": len(_strengths(payload)),
            "weaknesses_count": len(_weaknesses(payload)),
            "status": str(payload.get("resume_preview_status") or "").strip() or "wait",
            "anonymized_resume_link": raw,
            "resume_url": url,
        }
        if included:
            items.append(item)
            if url and visible:
                ready_n += 1
    items.sort(key=lambda x: (not x["ready"], (x["name"] or "").casefold()))
    public_url = resume_preview_public_url(token) if token else ""
    return {
        "token": token or None,
        "path": resume_preview_path(token) if token else None,
        "public_url": public_url or None,
        "sent_at": str((vacancy.payload or {}).get("resume_preview_sent_at") or "") or None,
        "included_count": len(items),
        "ready_count": ready_n,
        "candidates": items,
    }


def set_included(
    db: Session,
    vacancy: models.Vacancy,
    candidate_id: str,
    *,
    included: bool | None = None,
    visible: bool | None = None,
    pdf_url: str | None = None,
) -> dict[str, Any]:
    try:
        cid = UUID(str(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный id") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate or candidate.vacancy_id != vacancy.id:
        raise HTTPException(status_code=404, detail="Кандидат не найден")
    if included is None and visible is None:
        raise HTTPException(status_code=400, detail="Нужно included или visible")
    if included is True:
        url = (pdf_url or "").strip() or str((candidate.payload or {}).get("anonymized_resume_link") or "").strip()
        if not url:
            url = str((candidate.payload or {}).get("resume_link") or "").strip()
        if not _https_url(url) and not url:
            raise HTTPException(
                status_code=400,
                detail="Нужна публичная ссылка на PDF без контактов (Яндекс.Диск)",
            )
        mark_resume_preview(candidate, pdf_url=url or None, included=True)
    elif included is False:
        mark_resume_preview(candidate, included=False)
        payload = dict(candidate.payload or {})
        payload["resume_preview_included"] = False
        candidate.payload = payload
        flag_modified(candidate, "payload")
    if visible is not None:
        payload = dict(candidate.payload or {})
        payload["resume_preview_visible"] = bool(visible)
        candidate.payload = payload
        flag_modified(candidate, "payload")
    db.add(candidate)
    db.commit()
    return pack_status(db, vacancy)


def _notify_preview_decision(
    db: Session,
    vacancy: models.Vacancy,
    candidate: models.Candidate,
    action: str,
    comment: str,
) -> None:
    chat_id = str(vacancy.chat_id or "").strip()
    if not chat_id:
        return
    from app.services.messaging.telegram_provider import send_html_message

    label = "можно рассмотреть" if action == "consider" else "отказ"
    text = (
        f"Макет резюме: <b>{_esc(candidate.name)}</b> — {label}."
        + (f"\n{_esc(comment)}" if comment else "")
    )
    try:
        send_html_message(chat_id, text)
    except Exception:  # noqa: BLE001
        return


def _esc(text: Any) -> str:
    import html

    return html.escape(str(text or "").strip())


def send_preview_pack(db: Session, vacancy: models.Vacancy) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.services.messaging.gateway import MessagingError
    from app.services.messaging.keyboards import build_url_button_keyboard
    from app.services.messaging.telegram_provider import send_html_message

    settings = get_settings()
    if not settings.messaging_outbound_enabled:
        raise MessagingError("Отправка в мессенджер отключена", 403)
    if not (settings.telegram_bot_token or "").strip():
        raise MessagingError("Не задан TELEGRAM_BOT_TOKEN", 400)
    chat_id = str(vacancy.chat_id or "").strip()
    if not chat_id:
        raise MessagingError("У вакансии не указан Chat ID", 400)

    status = pack_status(db, vacancy)
    if status["ready_count"] < 1:
        raise MessagingError("Нет готовых макетов: нужна ссылка на PDF без контактов", 400)

    token = ensure_preview_token(db, vacancy)
    url = resume_preview_public_url(token, settings=settings)
    if not url:
        raise MessagingError(
            "Нет публичного адреса сайта (задайте PUBLIC_APP_URL, например https://hr-toolbox.ru)",
            400,
        )

    n = int(status["ready_count"])
    noun = "макет" if n == 1 else "макета" if n < 5 else "макетов"
    text = (
        f"Макеты резюме <b>без контактов</b>\n"
        f"Вакансия: {_esc(vacancy.title)}\n"
        f"{n} {noun} на согласование"
    )
    ok, msg, message_id = send_html_message(
        chat_id,
        text,
        reply_markup=build_url_button_keyboard(url, "Посмотреть макеты"),
    )
    if not ok or not message_id:
        raise MessagingError(msg or "Ошибка отправки", 502)

    payload = dict(vacancy.payload or {})
    payload["resume_preview_token"] = token
    payload["resume_preview_sent_at"] = _now_iso()
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.add(vacancy)
    db.commit()
    return {
        "ok": True,
        "message": "Ссылка на макеты отправлена в Telegram",
        "path": resume_preview_path(token),
        "public_url": url,
        "ready_count": n,
    }
