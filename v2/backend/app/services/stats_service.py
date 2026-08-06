"""Aggregated stats for v2 dashboard (PostgreSQL only)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.hh_seen import REASON_AI_LOW, REASON_IN_FUNNEL, REASON_RECRUITER
from app.services.vacancy_outcome import HIRE_STAGES

CLIENT_ZONE_STAGES = (
    "client_review",
    "client_pause",
    "client_meeting",
    "offer",
    "internship",
)

CLIENT_STATUS_ORDER = ("wait", "think", "ready", "offer", "started", "reject", "new")

PERIOD_PRESETS = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
    "quarter": timedelta(days=90),
    "half_year": timedelta(days=182),
    "year": timedelta(days=365),
}


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _reached_client_review(candidate: models.Candidate) -> bool:
    if candidate.hr_stage in CLIENT_ZONE_STAGES or candidate.hr_stage in HIRE_STAGES:
        return True
    if candidate.hr_stage == "started_work":
        return True
    history = (candidate.payload or {}).get("hr_stage_history") or []
    return any(isinstance(e, dict) and e.get("stage") == "client_review" for e in history)


def _filter_vacancies(
    db: Session,
    *,
    client_id: int | None,
    vacancy_id: int | None,
    active_only: bool,
    organization_id: Any | None = None,
) -> list[models.Vacancy]:
    q = select(models.Vacancy)
    if organization_id is not None:
        from app.services.tenancy import org_client_ids

        cids = org_client_ids(db, organization_id)
        if not cids:
            return []
        q = q.where(models.Vacancy.client_id.in_(cids))
    if vacancy_id is not None:
        q = q.where(models.Vacancy.id == vacancy_id)
    elif client_id is not None:
        q = q.where(models.Vacancy.client_id == client_id)
    vacancies = list(db.scalars(q).all())
    if active_only:
        vacancies = [v for v in vacancies if v.active]
    return vacancies


def _candidates_for_vacancies(db: Session, vac_ids: list[int]) -> list[models.Candidate]:
    if not vac_ids:
        return []
    return list(
        db.scalars(select(models.Candidate).where(models.Candidate.vacancy_id.in_(vac_ids))).all()
    )


def build_funnel_stats(
    db: Session,
    *,
    client_id: int | None = None,
    vacancy_id: int | None = None,
    active_vacancies_only: bool = False,
    organization_id: Any | None = None,
) -> dict[str, Any]:
    vacancies = _filter_vacancies(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_only=False,
        organization_id=organization_id,
    )
    active_ids = {v.id for v in vacancies if v.active}
    archive_ids = {v.id for v in vacancies if not v.active}
    scope_vacancies = [v for v in vacancies if (v.active if active_vacancies_only else True)]
    if vacancy_id is not None:
        scope_vacancies = [v for v in vacancies if v.id == vacancy_id]
        if active_vacancies_only:
            scope_vacancies = [v for v in scope_vacancies if v.active]
    vac_ids = [v.id for v in scope_vacancies]
    candidates = _candidates_for_vacancies(db, vac_ids)

    stage_counts: dict[str, int] = {}
    for c in candidates:
        stage_counts[c.hr_stage] = stage_counts.get(c.hr_stage, 0) + 1

    sent = [c for c in candidates if _reached_client_review(c)]
    status_counts: dict[str, int] = {}
    for c in sent:
        key = c.client_status or "wait"
        status_counts[key] = status_counts.get(key, 0) + 1

    clients = {cl.id: cl.name for cl in db.scalars(select(models.Client)).all()}
    by_client_map: dict[int | None, dict[str, Any]] = {}
    for v in vacancies if not vacancy_id else scope_vacancies:
        key = v.client_id
        if key not in by_client_map:
            by_client_map[key] = {
                "client_id": key,
                "client_name": clients.get(key, "Без клиента") if key is not None else "Без клиента",
                "vacancies_active": 0,
                "vacancies_archive": 0,
                "candidates": 0,
            }
        if v.active:
            by_client_map[key]["vacancies_active"] += 1
        else:
            by_client_map[key]["vacancies_archive"] += 1

    vac_client = {v.id: v.client_id for v in scope_vacancies}
    for c in candidates:
        key = vac_client.get(c.vacancy_id)
        if key not in by_client_map:
            by_client_map[key] = {
                "client_id": key,
                "client_name": clients.get(key, "Без клиента") if key is not None else "Без клиента",
                "vacancies_active": 0,
                "vacancies_archive": 0,
                "candidates": 0,
            }
        by_client_map[key]["candidates"] += 1

    ordered_status = []
    for status in CLIENT_STATUS_ORDER:
        if status in status_counts:
            ordered_status.append({"stage": status, "count": status_counts[status]})
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        if status not in CLIENT_STATUS_ORDER:
            ordered_status.append({"stage": status, "count": count})

    return {
        "vacancies_active": len(active_ids)
        if vacancy_id is None
        else (1 if scope_vacancies and scope_vacancies[0].active else 0),
        "vacancies_archive": 0
        if active_vacancies_only
        else (
            len(archive_ids)
            if vacancy_id is None
            else (1 if scope_vacancies and not scope_vacancies[0].active else 0)
        ),
        "candidates_total": len(candidates),
        "by_hr_stage": [
            {"stage": k, "count": v} for k, v in sorted(stage_counts.items(), key=lambda x: -x[1])
        ],
        "by_client_status": ordered_status,
        "by_client": sorted(
            by_client_map.values(), key=lambda r: (-r["candidates"], r["client_name"])
        ),
        "hires": sum(1 for c in candidates if c.hr_stage in HIRE_STAGES),
        "in_client_zone": sum(1 for c in candidates if c.hr_stage in CLIENT_ZONE_STAGES),
        "sent_to_client": len(sent),
        "vacancy_id": vacancy_id,
        "vacancy_title": scope_vacancies[0].title if vacancy_id and scope_vacancies else None,
    }


def build_hh_stats(
    db: Session,
    *,
    client_id: int | None = None,
    vacancy_id: int | None = None,
    active_vacancies_only: bool = False,
    organization_id: Any | None = None,
) -> dict[str, Any]:
    vacancies = _filter_vacancies(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_only=active_vacancies_only,
        organization_id=organization_id,
    )
    vac_ids = [v.id for v in vacancies]
    if not vac_ids:
        return {
            "viewed": 0,
            "ai_score_gt2": 0,
            "ai_low": 0,
            "recruiter_reject": 0,
            "shortlist": 0,
            "in_funnel": 0,
            "jobs_completed": 0,
        }

    seen_rows = list(
        db.scalars(select(models.HhSeenResume).where(models.HhSeenResume.vacancy_id.in_(vac_ids))).all()
    )
    short_rows = list(
        db.scalars(
            select(models.HhShortlistItem).where(models.HhShortlistItem.vacancy_id.in_(vac_ids))
        ).all()
    )
    candidates = _candidates_for_vacancies(db, vac_ids)

    scores: dict[tuple[int, str], int | None] = {}
    reasons: dict[tuple[int, str], str] = {}
    for row in seen_rows:
        key = (row.vacancy_id, row.hh_resume_id)
        reasons[key] = row.reason
        if row.ai_score is not None:
            scores[key] = row.ai_score
    for row in short_rows:
        key = (row.vacancy_id, row.hh_resume_id)
        if key not in reasons or reasons[key] not in (REASON_RECRUITER, REASON_IN_FUNNEL):
            reasons[key] = reasons.get(key) or "shortlist"
        if row.ai_score is not None:
            scores[key] = row.ai_score

    in_funnel_ids: set[tuple[int, str]] = set()
    for c in candidates:
        rid = str((c.payload or {}).get("hh_resume_id") or "").strip()
        source = str((c.payload or {}).get("source") or "")
        if rid:
            key = (c.vacancy_id, rid)
            in_funnel_ids.add(key)
            reasons[key] = REASON_IN_FUNNEL
            score = (c.payload or {}).get("ai_score")
            try:
                if score is not None:
                    scores[key] = int(score)
            except (TypeError, ValueError):
                pass
        elif source == "hh_cold_search":
            # candidate without resume id still counts as funnel from HH
            in_funnel_ids.add((c.vacancy_id, f"cand:{c.id}"))

    viewed_keys = set(reasons) | {(r.vacancy_id, r.hh_resume_id) for r in short_rows} | in_funnel_ids
    # drop synthetic cand: keys from viewed uniqueness for "resumes"
    viewed = len({k for k in viewed_keys if not str(k[1]).startswith("cand:")})

    ai_gt2 = sum(1 for k, s in scores.items() if s is not None and s > 2)
    ai_low = sum(1 for k, r in reasons.items() if r == REASON_AI_LOW)
    recruiter_reject = sum(1 for k, r in reasons.items() if r == REASON_RECRUITER)
    shortlist = len(short_rows)
    in_funnel = len(in_funnel_ids)

    jobs = list(
        db.scalars(
            select(models.Job).where(
                models.Job.job_type == "hh_cold_search",
                models.Job.status == "completed",
                models.Job.vacancy_id.in_(vac_ids),
            )
        ).all()
    )

    return {
        "viewed": viewed,
        "ai_score_gt2": ai_gt2,
        "ai_low": ai_low,
        "recruiter_reject": recruiter_reject,
        "shortlist": shortlist,
        "in_funnel": in_funnel,
        "jobs_completed": len(jobs),
    }


def _bucket_key(dt: datetime, period: str) -> str:
    if period == "day":
        return dt.strftime("%Y-%m-%d %H:00")
    if period == "week":
        return dt.strftime("%Y-%m-%d")
    if period in ("month", "quarter"):
        return dt.strftime("%Y-%m-%d")
    if period in ("half_year", "year"):
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")


def build_activity_stats(
    db: Session,
    *,
    client_id: int | None = None,
    vacancy_id: int | None = None,
    active_vacancies_only: bool = False,
    period: str = "month",
    organization_id: Any | None = None,
) -> dict[str, Any]:
    if period not in PERIOD_PRESETS:
        period = "month"
    now = datetime.now(timezone.utc)
    start = now - PERIOD_PRESETS[period]

    vacancies = _filter_vacancies(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_only=active_vacancies_only,
        organization_id=organization_id,
    )
    vac_ids = [v.id for v in vacancies]
    vac_id_set = set(vac_ids)

    candidates_added = 0
    stage_changes = 0
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"candidates": 0, "stage_changes": 0, "jobs": 0})

    if vac_ids:
        for c in _candidates_for_vacancies(db, vac_ids):
            created = _parse_dt(c.created_at)
            if created and created >= start:
                candidates_added += 1
                buckets[_bucket_key(created, period)]["candidates"] += 1
            history = (c.payload or {}).get("hr_stage_history") or []
            for entry in history:
                if not isinstance(entry, dict):
                    continue
                at = _parse_dt(entry.get("at"))
                if at and at >= start:
                    stage_changes += 1
                    buckets[_bucket_key(at, period)]["stage_changes"] += 1

    jobs_q = select(models.Job).where(models.Job.created_at >= start)
    jobs = list(db.scalars(jobs_q).all())
    jobs_count = 0
    for j in jobs:
        if vac_id_set and j.vacancy_id not in vac_id_set and j.vacancy_id is not None:
            continue
        if vac_id_set and j.vacancy_id is None and vacancy_id is not None:
            continue
        if client_id is not None and j.vacancy_id is not None and j.vacancy_id not in vac_id_set:
            continue
        jobs_count += 1
        created = j.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        buckets[_bucket_key(created, period)]["jobs"] += 1

    series = [
        {
            "bucket": key,
            "candidates_added": vals["candidates"],
            "stage_changes": vals["stage_changes"],
            "jobs": vals["jobs"],
        }
        for key, vals in sorted(buckets.items())
    ]

    return {
        "period": period,
        "period_from": start.isoformat(),
        "period_to": now.isoformat(),
        "candidates_added": candidates_added,
        "stage_changes": stage_changes,
        "jobs": jobs_count,
        "series": series,
    }
