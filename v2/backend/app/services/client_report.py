"""Client vacancy report: funnel cohorts + Telegram «Отчёт заказчику»."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.candidate_fields import normalize_gender
from app.services.client_zone import (
    _zone_candidate_links,
    _zone_header,
    ensure_zone_token_for_vacancy,
    zone_context,
)

# Cumulative funnel (ever reached) — labels for заказчик
FUNNEL_MAIN: list[tuple[str, str]] = [
    ("selected", "Отобрано из базы и откликов"),
    ("contact", "Вышли на контакт"),
    ("interview", "Первое собеседование"),
    ("to_client", "Направлено на оценку"),
    ("meeting", "Встреча с заказчиком"),
    ("offer", "Получили оффер"),
]

FUNNEL_SIDE: list[tuple[str, str]] = [
    ("no_reply", "Зависли без ответа (более суток)"),
]

FUNNEL_REJECTS: list[tuple[str, str]] = [
    ("rej_client", "отклонены заказчиком"),
    ("rej_hr", "отклонены рекрутером"),
    ("rej_cand", "отказались сами"),
]

ALL_COHORT_KEYS = frozenset(k for k, _ in FUNNEL_MAIN + FUNNEL_SIDE + FUNNEL_REJECTS)

CONTACT_OR_LATER = frozenset(
    {
        "primary_contact",
        "no_response_3d",
        "interview_scheduled",
        "interview_done",
        "test_task",
        "client_review",
        "client_pause",
        "client_meeting",
        "offer",
        "internship",
        "started_work",
        "rejected_client",
        "rejected_candidate",
    }
)
INTERVIEW_OR_LATER = frozenset(
    {
        "interview_scheduled",
        "interview_done",
        "test_task",
        "client_review",
        "client_pause",
        "client_meeting",
        "offer",
        "internship",
        "started_work",
    }
)
CLIENT_OR_LATER = frozenset(
    {
        "client_review",
        "client_pause",
        "client_meeting",
        "offer",
        "internship",
        "started_work",
        "rejected_client",
    }
)
MEETING_OR_LATER = frozenset(
    {"client_meeting", "offer", "internship", "started_work"}
)
OFFER_OR_LATER = frozenset({"offer", "internship", "started_work"})

STAGE_LABELS_RU: dict[str, str] = {
    "resume_screening": "Отсев резюме",
    "primary_contact": "Первичный контакт",
    "no_response_3d": "Нет ответа",
    "interview_scheduled": "Собеседование назначено",
    "interview_done": "Собеседование проведено",
    "test_task": "Тестовое задание",
    "client_review": "На оценке у заказчика",
    "client_pause": "Пауза",
    "client_meeting": "Встреча с заказчиком",
    "offer": "Оффер",
    "internship": "Стажировка",
    "started_work": "Вышел на работу",
    "rejected_hr": "Отказ рекрутера",
    "rejected_client": "Отказ заказчика",
    "rejected_candidate": "Отказ кандидата",
    "rejected_vacancy_closed": "Вакансия закрыта",
    "rejected": "Отказ",
    "archived": "Архив",
}

CLIENT_STATUS_LABELS: dict[str, str] = {
    "wait": "Ожидает",
    "think": "Думает",
    "ready": "Встреча",
    "reject": "Отказ",
    "offer": "Оффер",
    "started": "Вышел",
    "new": "Новый",
}


def _esc(text: Any) -> str:
    return html.escape(str(text or "").strip())


def _stages_ever(c: models.Candidate) -> set[str]:
    out: set[str] = set()
    for entry in (c.payload or {}).get("hr_stage_history") or []:
        if isinstance(entry, dict):
            st = str(entry.get("stage") or "").strip()
            if st:
                out.add(st)
    cur = str(c.hr_stage or "").strip()
    if cur:
        out.add(cur)
    return out


def _last_reject_note(c: models.Candidate) -> str | None:
    hist = list((c.payload or {}).get("hr_stage_history") or [])
    for entry in reversed(hist):
        if not isinstance(entry, dict):
            continue
        note = str(entry.get("note") or "").strip()
        if note:
            return note[:300]
    return None


def cohort_keys_for_candidate(c: models.Candidate) -> set[str]:
    stages = _stages_ever(c)
    keys: set[str] = {"selected"}
    if stages & CONTACT_OR_LATER:
        keys.add("contact")
    if stages & INTERVIEW_OR_LATER:
        keys.add("interview")
    if stages & CLIENT_OR_LATER:
        keys.add("to_client")
    if stages & MEETING_OR_LATER:
        keys.add("meeting")
    if stages & OFFER_OR_LATER:
        keys.add("offer")
    if "no_response_3d" in stages:
        keys.add("no_reply")
    cur = str(c.hr_stage or "").strip()
    if cur == "rejected_client":
        keys.add("rej_client")
    elif cur == "rejected_hr":
        keys.add("rej_hr")
    elif cur == "rejected_candidate":
        keys.add("rej_cand")
    return keys


def compute_funnel_counts(candidates: list[models.Candidate]) -> dict[str, int]:
    counts = {k: 0 for k in ALL_COHORT_KEYS}
    for c in candidates:
        for key in cohort_keys_for_candidate(c):
            counts[key] = counts.get(key, 0) + 1
    return counts


def _period_label(vacancy: models.Vacancy) -> str:
    def fmt(raw: str | None) -> str | None:
        s = (raw or "").strip()
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            months = (
                "января",
                "февраля",
                "марта",
                "апреля",
                "мая",
                "июня",
                "июля",
                "августа",
                "сентября",
                "октября",
                "ноября",
                "декабря",
            )
            return f"{dt.day} {months[dt.month - 1]} {dt.year}"
        except ValueError:
            return s[:10]

    start = fmt(vacancy.created_at)
    end = fmt(vacancy.closed_at) if not vacancy.active else "сейчас"
    if start and end:
        return f"{start} — {end}"
    return start or end or "—"


def client_zone_report_path(token: str, vacancy_id: int) -> str:
    return f"/c/{token}/report/{vacancy_id}"


def client_zone_report_public_url(
    token: str,
    vacancy_id: int,
    *,
    settings: Any = None,
) -> str:
    from app.services.interview_digest import public_app_base

    base = public_app_base(settings)
    if not base:
        return ""
    return f"{base}{client_zone_report_path(token, vacancy_id)}"


def client_zone_hub_public_url(token: str, *, settings: Any = None) -> str:
    from app.services.interview_digest import public_app_base

    base = public_app_base(settings)
    if not base:
        return ""
    return f"{base}/c/{token}"


def _vacancy_in_zone_scope(
    db: Session, token: str, vacancy_id: int
) -> tuple[models.Client, models.Vacancy, set[int]]:
    root, scope = zone_context(db, token)
    vacancy = db.get(models.Vacancy, vacancy_id)
    if not vacancy or vacancy.client_id not in scope:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return root, vacancy, scope


def list_zone_reports(db: Session, token: str) -> dict[str, Any]:
    """Vacancies (active + archive) available as reports for this zone."""
    root, scope = zone_context(db, token)
    header = _zone_header(db, root)
    vacancies = list(
        db.scalars(
            select(models.Vacancy)
            .where(models.Vacancy.client_id.in_(scope))
            .order_by(models.Vacancy.active.desc(), models.Vacancy.id.desc())
        ).all()
    )
    items: list[dict[str, Any]] = []
    for vac in vacancies:
        cands = list(
            db.scalars(
                select(models.Candidate).where(models.Candidate.vacancy_id == vac.id)
            ).all()
        )
        counts = compute_funnel_counts(cands)
        items.append(
            {
                "vacancy_id": vac.id,
                "title": vac.title,
                "active": bool(vac.active),
                "period": _period_label(vac),
                "path": client_zone_report_path(token, vac.id),
                "to_client": counts.get("to_client", 0),
                "offer": counts.get("offer", 0),
                "selected": counts.get("selected", 0),
            }
        )
    return {
        "company": header,
        "reports": items,
        "demo": bool(header.get("demo")),
    }


def get_zone_report(db: Session, token: str, vacancy_id: int) -> dict[str, Any]:
    root, vacancy, _scope = _vacancy_in_zone_scope(db, token, vacancy_id)
    header = _zone_header(db, root)
    cands = list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.vacancy_id == vacancy.id)
        ).all()
    )
    counts = compute_funnel_counts(cands)
    funnel_main = [
        {"key": k, "label": lab, "value": counts.get(k, 0)} for k, lab in FUNNEL_MAIN
    ]
    funnel_side = [
        {"key": k, "label": lab, "value": counts.get(k, 0)} for k, lab in FUNNEL_SIDE
    ]
    funnel_rejects = [
        {"key": k, "label": lab, "value": counts.get(k, 0)} for k, lab in FUNNEL_REJECTS
    ]
    rej_total = sum(counts.get(k, 0) for k, _ in FUNNEL_REJECTS)
    summary = (
        f"Из {counts.get('selected', 0)} отобранных на оценку ушло {counts.get('to_client', 0)}, "
        f"встреч — {counts.get('meeting', 0)}, оффер — {counts.get('offer', 0)}. "
        f"Отказы: {counts.get('rej_client', 0)} заказчиком, "
        f"{counts.get('rej_hr', 0)} рекрутером, "
        f"{counts.get('rej_cand', 0)} отказались сами."
    )
    return {
        "company": header,
        "vacancy": {
            "id": vacancy.id,
            "title": vacancy.title,
            "active": bool(vacancy.active),
            "period": _period_label(vacancy),
        },
        "funnel_main": funnel_main,
        "funnel_side": funnel_side,
        "funnel_rejects": funnel_rejects,
        "reject_total": rej_total,
        "summary": summary,
        "demo": bool(header.get("demo")),
        "path": client_zone_report_path(token, vacancy.id),
    }


def _report_list_item(c: models.Candidate) -> dict[str, Any]:
    payload = c.payload or {}
    links = _zone_candidate_links(payload)
    stage = str(c.hr_stage or "")
    status = str(c.client_status or "wait")
    return {
        "id": str(c.id),
        "name": c.name or "Без имени",
        "hr_stage": stage,
        "stage_label": STAGE_LABELS_RU.get(stage, stage or "—"),
        "client_status": status,
        "status_label": CLIENT_STATUS_LABELS.get(status, status),
        "ai_score": payload.get("ai_score"),
        "hr_comment": (str(payload.get("hr_comment") or "").strip() or None),
        "history_reason": _last_reject_note(c),
        "has_resume": bool(links.get("resume_url")),
        "has_video": bool(links.get("video_url")),
        "has_digest": bool(links.get("interview_digest")),
        "has_portfolio": bool(links.get("portfolio_url")),
        "photo_url": (str(payload.get("photo_url") or "").strip() or None),
        "gender": normalize_gender(payload.get("gender") or payload.get("sex")),
        "phone": (str(payload.get("phone") or "").strip() or None),
    }


def list_zone_report_cohort(
    db: Session, token: str, vacancy_id: int, cohort: str
) -> dict[str, Any]:
    key = (cohort or "").strip()
    if key not in ALL_COHORT_KEYS:
        raise HTTPException(status_code=404, detail="Срез не найден")
    root, vacancy, _scope = _vacancy_in_zone_scope(db, token, vacancy_id)
    header = _zone_header(db, root)
    label = dict(FUNNEL_MAIN + FUNNEL_SIDE + FUNNEL_REJECTS).get(key, key)
    cands = list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.vacancy_id == vacancy.id)
        ).all()
    )
    matched = [c for c in cands if key in cohort_keys_for_candidate(c)]
    matched.sort(key=lambda c: (c.name or "").casefold())
    return {
        "company": header,
        "vacancy": {"id": vacancy.id, "title": vacancy.title},
        "cohort": {"key": key, "label": label, "total": len(matched)},
        "candidates": [_report_list_item(c) for c in matched],
        "demo": bool(header.get("demo")),
    }


def get_zone_report_candidate(
    db: Session, token: str, vacancy_id: int, candidate_id: str | UUID
) -> dict[str, Any]:
    root, vacancy, _scope = _vacancy_in_zone_scope(db, token, vacancy_id)
    try:
        cid = candidate_id if isinstance(candidate_id, UUID) else UUID(str(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Кандидат не найден") from exc
    candidate = db.get(models.Candidate, cid)
    if not candidate or candidate.vacancy_id != vacancy.id:
        raise HTTPException(status_code=404, detail="Кандидат не найден")
    header = _zone_header(db, root)
    item = _report_list_item(candidate)
    payload = candidate.payload or {}
    links = _zone_candidate_links(payload)
    item.update(links)
    strengths = payload.get("ai_strengths") or payload.get("resume_ai_strengths") or []
    weaknesses = payload.get("ai_weaknesses") or payload.get("resume_ai_weaknesses") or []
    item["ai_strengths"] = [str(x).strip() for x in strengths if str(x).strip()][:6]
    item["ai_weaknesses"] = [str(x).strip() for x in weaknesses if str(x).strip()][:6]
    item["ai_comment"] = str(payload.get("ai_comment") or "").strip() or None
    meet_d = str(payload.get("office_interview_date") or "").strip()
    meet_t = str(payload.get("office_interview_time") or "").strip()
    item["meeting"] = f"{meet_d} {meet_t}".strip() or None
    return {
        "company": header,
        "vacancy": {"id": vacancy.id, "title": vacancy.title},
        "candidate": item,
        "demo": bool(header.get("demo")),
        "read_only": True,
    }


def format_client_report_telegram_html(
    vacancy: models.Vacancy,
    counts: dict[str, int],
) -> str:
    lines = [
        "<b>📋 Отчёт по вакансии</b>",
        f"<b>{_esc(vacancy.title)}</b>",
        "",
        "<b>Картина работы</b>",
    ]
    for key, label in FUNNEL_MAIN:
        lines.append(f"• {label}: <b>{counts.get(key, 0)}</b>")
    lines.append("")
    lines.append("<b>Исходы</b>")
    lines.append(f"• Зависли без ответа: <b>{counts.get('no_reply', 0)}</b>")
    lines.append(
        f"• Отказы: <b>{counts.get('rej_client', 0)}</b> заказчиком, "
        f"<b>{counts.get('rej_hr', 0)}</b> рекрутером, "
        f"<b>{counts.get('rej_cand', 0)}</b> отказались сами"
    )
    return "\n".join(lines)


def send_client_report_to_chat(db: Session, vacancy: models.Vacancy) -> dict[str, Any]:
    """Auth HR action: funnel numbers + URL button to report (no bare URLs in text)."""
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

    token = ensure_zone_token_for_vacancy(db, vacancy)
    if not token:
        raise MessagingError("У вакансии нет компании/подразделения для зоны заказчика", 400)

    report_url = client_zone_report_public_url(token, vacancy.id, settings=settings)
    zone_url = client_zone_hub_public_url(token, settings=settings)
    if not report_url:
        raise MessagingError(
            "Нет публичного адреса сайта (задайте PUBLIC_APP_URL, например https://hr-toolbox.ru)",
            400,
        )

    cands = list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.vacancy_id == vacancy.id)
        ).all()
    )
    counts = compute_funnel_counts(cands)
    text = format_client_report_telegram_html(vacancy, counts)
    ok, msg, message_id = send_html_message(
        chat_id,
        text,
        reply_markup=build_url_button_keyboard(
            report_url,
            "Посмотреть отчёт",
            style="primary",
        ),
    )
    if not ok or not message_id:
        raise MessagingError(msg or "Ошибка отправки", 502)

    payload = dict(vacancy.payload or {})
    payload["client_report_sent_at"] = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.add(vacancy)
    db.commit()

    return {
        "ok": True,
        "message": "Отчёт заказчику отправлен в Telegram",
        "path": client_zone_report_path(token, vacancy.id),
        "public_url": report_url,
        "zone_url": zone_url,
        "counts": counts,
    }


def enrich_zone_home_with_reports(db: Session, token: str, home: dict[str, Any]) -> dict[str, Any]:
    """Attach short reports list to existing zone home payload."""
    reports = list_zone_reports(db, token)
    home = dict(home)
    home["reports"] = reports.get("reports") or []
    return home
