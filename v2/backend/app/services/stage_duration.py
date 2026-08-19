"""Stage duration analytics — compute time candidates spend on each HR stage.

Source: candidate.payload.hr_stage_history [{stage, at, note?}, ...]
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _stage_durations_from_history(
    history: list[dict], current_stage: str
) -> list[dict[str, Any]]:
    """Return per-transition durations: [{stage, entered_at, exited_at, days, data_quality}]."""
    if not history:
        return []

    result: list[dict[str, Any]] = []
    for i, entry in enumerate(history):
        stage = entry.get("stage", "")
        entered = _parse_iso(entry.get("at"))
        if not entered:
            continue

        exited: datetime | None = None
        if i + 1 < len(history):
            exited = _parse_iso(history[i + 1].get("at"))

        if exited:
            days = (exited - entered).total_seconds() / 86400
            quality = "exact"
        elif stage == current_stage:
            days = (datetime.now(timezone.utc) - entered).total_seconds() / 86400
            quality = "partial"
        else:
            continue

        result.append({
            "stage": stage,
            "entered_at": entered.isoformat(),
            "exited_at": exited.isoformat() if exited else None,
            "days": round(days, 1),
            "data_quality": quality,
        })

    return result


def candidate_stage_durations(candidate: models.Candidate) -> list[dict[str, Any]]:
    history = (candidate.payload or {}).get("hr_stage_history") or []
    return _stage_durations_from_history(history, candidate.hr_stage)


def aggregate_stage_timing(
    db: Session,
    *,
    organization_id,
    vacancy_id: int | None = None,
    client_id: int | None = None,
) -> list[dict[str, Any]]:
    """Aggregate stage timing across candidates. Returns per-stage summary."""
    q = select(models.Candidate)
    if vacancy_id:
        q = q.where(models.Candidate.vacancy_id == vacancy_id)
    elif client_id:
        vac_ids = list(
            db.scalars(
                select(models.Vacancy.id).where(models.Vacancy.client_id == client_id)
            ).all()
        )
        if not vac_ids:
            return []
        q = q.where(models.Candidate.vacancy_id.in_(vac_ids))

    candidates = list(db.scalars(q).all())

    from collections import defaultdict
    stage_data: dict[str, list[float]] = defaultdict(list)

    for cand in candidates:
        for dur in candidate_stage_durations(cand):
            stage_data[dur["stage"]].append(dur["days"])

    result = []
    for stage, days_list in stage_data.items():
        days_list.sort()
        count = len(days_list)
        avg = sum(days_list) / count if count else 0
        median = days_list[count // 2] if count else 0
        result.append({
            "stage": stage,
            "count": count,
            "avg_days": round(avg, 1),
            "median_days": round(median, 1),
            "data_quality": "exact" if count >= 3 else "partial",
        })

    return result


# --- V13 stale detection ---

DEFAULT_STAGE_THRESHOLDS = {
    "resume_screening": 3,
    "primary_contact": 5,
    "no_response_3d": 7,
    "interview_scheduled": 7,
    "interview_done": 5,
    "test_task": 10,
    "client_review": 5,
    "client_pause": 14,
    "client_meeting": 7,
    "offer": 7,
}


def stale_candidates(
    db: Session,
    *,
    organization_id,
    vacancy_id: int | None = None,
    thresholds: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Find candidates stuck on a stage beyond its threshold."""
    thresholds = thresholds or DEFAULT_STAGE_THRESHOLDS

    q = select(models.Candidate).join(
        models.Vacancy, models.Candidate.vacancy_id == models.Vacancy.id
    ).where(models.Vacancy.active.is_(True))

    if vacancy_id:
        q = q.where(models.Candidate.vacancy_id == vacancy_id)

    candidates = list(db.scalars(q).all())
    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []

    for cand in candidates:
        stage = cand.hr_stage
        threshold = thresholds.get(stage)
        if not threshold:
            continue

        history = (cand.payload or {}).get("hr_stage_history") or []
        entered: datetime | None = None
        for entry in reversed(history):
            if entry.get("stage") == stage:
                entered = _parse_iso(entry.get("at"))
                break

        if not entered:
            entered = _parse_iso(cand.created_at)

        if not entered:
            continue

        days = (now - entered).total_seconds() / 86400
        if days >= threshold:
            results.append({
                "candidate_id": str(cand.id),
                "name": cand.name,
                "vacancy_id": cand.vacancy_id,
                "stage": stage,
                "days_on_stage": round(days),
                "threshold": threshold,
                "entered_at": entered.isoformat(),
            })

    return results
