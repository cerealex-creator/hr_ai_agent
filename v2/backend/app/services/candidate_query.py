"""Filtered candidate lists for stats drill-down (PostgreSQL)."""

from __future__ import annotations

from typing import Any

from app.services.candidate_fields import normalize_gender

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.stats_service import (
    CLIENT_ZONE_STAGES,
    _candidates_for_vacancies,
    _filter_vacancies,
    _reached_client_review,
)
from app.services.vacancy_outcome import HIRE_STAGES

CANDIDATE_PRESETS = frozenset({"sent_to_client", "in_client_zone", "hires", "attention"})


def attention_reason(c: models.Candidate) -> str | None:
    """Why this candidate needs HR attention (inbox). None = skip."""
    stage = c.hr_stage or ""
    if stage in ("rejected",) or stage in HIRE_STAGES:
        return None
    p = c.payload or {}
    meeting_date = str(p.get("office_interview_date") or "").strip()
    meeting_time = str(p.get("office_interview_time") or "").strip()
    meeting_set = bool(meeting_date and meeting_time)
    hr_confirmed = bool(p.get("meeting_hr_confirmed"))
    video = str(p.get("video_link") or "").strip()
    transcript = str(p.get("transcript") or "").strip()
    ai_score = p.get("ai_score")
    interview_ai = p.get("interview_ai_score")

    if meeting_set and not hr_confirmed and stage in ("interview_scheduled", "client_meeting"):
        return "Подтвердить встречу HR"
    if stage in ("interview_scheduled", "interview_done"):
        if video and not transcript and interview_ai is None:
            return "Обработать запись собеседования"
        if not video and stage == "interview_scheduled":
            return "Добавить ссылку на запись"
    if stage in ("resume_screening", "primary_contact") and ai_score is None:
        return "Оценить резюме ИИ"
    if stage in ("client_review", "client_pause"):
        st = c.client_status or "wait"
        if st == "wait":
            return "Ждёт решения заказчика"
        if st == "think":
            return "Заказчик думает"
    if stage in ("resume_screening", "primary_contact") and not str(p.get("phone") or "").strip():
        return "Нет телефона"
    return None


def list_candidates_filtered(
    db: Session,
    *,
    client_id: int | None = None,
    vacancy_id: int | None = None,
    active_vacancies_only: bool = False,
    hr_stage: str | None = None,
    client_status: str | None = None,
    preset: str | None = None,
    organization_id=None,
) -> tuple[list[models.Candidate], list[models.Vacancy], str]:
    """
    Returns (candidates, scope_vacancies, label_hint).
    Semantics of presets match stats_service.build_funnel_stats.
    """
    vacancies = _filter_vacancies(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_only=active_vacancies_only,
        organization_id=organization_id,
    )
    vac_ids = [v.id for v in vacancies]
    candidates = _candidates_for_vacancies(db, vac_ids)

    label = "Все кандидаты"
    if preset and preset not in CANDIDATE_PRESETS:
        raise ValueError(f"preset: {', '.join(sorted(CANDIDATE_PRESETS))}")

    if hr_stage:
        candidates = [c for c in candidates if c.hr_stage == hr_stage]
        label = f"Этап: {hr_stage}"
    elif client_status:
        # Same universe as stats «Оценка заказчика»
        candidates = [
            c
            for c in candidates
            if _reached_client_review(c) and (c.client_status or "wait") == client_status
        ]
        label = f"Оценка заказчика: {client_status}"
    elif preset == "sent_to_client":
        candidates = [c for c in candidates if _reached_client_review(c)]
        label = "Отправлены заказчику"
    elif preset == "in_client_zone":
        candidates = [c for c in candidates if c.hr_stage in CLIENT_ZONE_STAGES]
        label = "Сейчас в зоне заказчика+"
    elif preset == "hires":
        candidates = [c for c in candidates if c.hr_stage in HIRE_STAGES]
        label = "Выходы / стажировки"
    elif preset == "attention":
        kept: list[models.Candidate] = []
        for c in candidates:
            reason = attention_reason(c)
            if not reason:
                continue
            # ephemeral, not persisted
            setattr(c, "_attention_reason", reason)
            kept.append(c)
        candidates = kept
        label = "Требуют внимания"

    candidates.sort(
        key=lambda c: (
            c.created_at or "",
            (c.name or "").lower(),
        ),
        reverse=True,
    )
    return candidates, vacancies, label


def vacancy_meta_maps(
    db: Session, vacancies: list[models.Vacancy]
) -> tuple[dict[int, str], dict[int, str | None]]:
    clients = {cl.id: cl.name for cl in db.scalars(select(models.Client)).all()}
    titles = {v.id: v.title for v in vacancies}
    client_names: dict[int, str | None] = {
        v.id: (clients.get(v.client_id) if v.client_id is not None else None) for v in vacancies
    }
    return titles, client_names


def serialize_list_item(
    c: models.Candidate,
    *,
    vacancy_title: str | None = None,
    client_name: str | None = None,
    last_contact_at: str | None = None,
) -> dict[str, Any]:
    p = c.payload or {}
    contact = last_contact_at
    if not contact:
        contact = _infer_last_contact(c)
    return {
        "id": c.id,
        "vacancy_id": c.vacancy_id,
        "name": c.name,
        "hr_stage": c.hr_stage,
        "client_status": c.client_status,
        "created_at": c.created_at,
        "phone": p.get("phone"),
        "city": p.get("city"),
        "vacancy_title": vacancy_title,
        "client_name": client_name,
        "last_contact_at": contact,
        "attention_reason": getattr(c, "_attention_reason", None),
        "photo_url": (p.get("photo_url") or "").strip() or None,
        "gender": normalize_gender(p.get("gender") or p.get("sex")),
    }


def _infer_last_contact(c: models.Candidate) -> str | None:
    """Best-effort last contact: status_updated_at, stage history, created_at."""
    candidates: list[str] = []
    if c.status_updated_at:
        candidates.append(str(c.status_updated_at))
    hist = (c.payload or {}).get("hr_stage_history") or []
    if isinstance(hist, list):
        for item in hist:
            if isinstance(item, dict) and item.get("at"):
                candidates.append(str(item["at"]))
    if c.created_at:
        candidates.append(str(c.created_at))
    if not candidates:
        return None
    return max(candidates)


def last_contact_map(db: Session, candidate_ids: list) -> dict:
    """Max MessagingPost.created_at per candidate (ISO)."""
    if not candidate_ids:
        return {}
    from sqlalchemy import func as sa_func

    rows = db.execute(
        select(
            models.MessagingPost.candidate_id,
            sa_func.max(models.MessagingPost.created_at),
        )
        .where(models.MessagingPost.candidate_id.in_(candidate_ids))
        .group_by(models.MessagingPost.candidate_id)
    ).all()
    out = {}
    for cid, ts in rows:
        if ts is None:
            continue
        out[cid] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    return out
