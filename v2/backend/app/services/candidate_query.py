"""Filtered candidate lists for stats drill-down (PostgreSQL)."""

from __future__ import annotations

from typing import Any

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

CANDIDATE_PRESETS = frozenset({"sent_to_client", "in_client_zone", "hires"})


def list_candidates_filtered(
    db: Session,
    *,
    client_id: int | None = None,
    vacancy_id: int | None = None,
    active_vacancies_only: bool = False,
    hr_stage: str | None = None,
    client_status: str | None = None,
    preset: str | None = None,
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
) -> dict[str, Any]:
    p = c.payload or {}
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
    }
