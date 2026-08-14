"""Aggregated stats for v2 dashboard (PostgreSQL only)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.candidate_fields import normalize_gender, payload_get
from app.services.vacancy_outcome import HIRE_STAGES, close_reason_from_payload, soft_vacancy_outcome

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
    client_ids: list[int] | None = None,
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
    elif client_ids:
        q = q.where(models.Vacancy.client_id.in_(client_ids))
    elif client_id is not None:
        q = q.where(models.Vacancy.client_id == client_id)
    vacancies = list(db.scalars(q).all())
    if active_only:
        vacancies = [v for v in vacancies if v.active]
    return vacancies


def resolve_stats_client_ids(db: Session, client_id: int | None) -> list[int] | None:
    """Expand company → company + departments; otherwise single id."""
    if client_id is None:
        return None
    from app.services import clients_write as cw

    client = db.get(models.Client, int(client_id))
    if not client:
        return [int(client_id)]
    if client.kind == cw.KIND_COMPANY and client.chat_mode == cw.CHAT_MODE_DEPARTMENTS:
        depts = cw.list_departments(db, client.id)
        return [client.id] + [d.id for d in depts]
    return [client.id]


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


def _parse_meeting_date(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text[:10], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return _parse_dt(raw)


def _count_meetings_today(candidates: list[models.Candidate], *, now: datetime) -> int:
    today = now.date()
    count = 0
    for c in candidates:
        payload = c.payload or {}
        meeting = _parse_meeting_date(payload_get(payload, "office_interview_date"))
        if meeting and meeting.date() == today:
            count += 1
    return count


def _count_waiting_client(candidates: list[models.Candidate]) -> int:
    return sum(
        1
        for c in candidates
        if c.hr_stage in ("client_review", "client_pause")
        and (c.client_status or "wait") == "wait"
    )


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


DASHBOARD_MODES = frozenset({"operational", "executive"})

CLOSE_OUTCOME_LABELS: dict[str, str] = {
    "success": "Успешно закрыта",
    "client_cancelled": "Закрыта заказчиком",
    "no_result": "Без результата",
}
CLOSE_OUTCOME_ORDER = ("success", "client_cancelled", "no_result")
# day=текущие сутки (с 00:00); week=текущая календарная неделя (пн→сейчас); month=скользящие 30д;
# mtd/ytd=с начала месяца/года; m1..m12=N календарных месяцев назад; all=всё время
DASHBOARD_PERIODS = frozenset(
    {"day", "week", "month", "all", "mtd", "ytd", "m1", "m2", "m3", "m6", "m12", "custom"}
)
EXECUTIVE_PERIODS = DASHBOARD_PERIODS  # alias for route validation
OPERATIONAL_PERIODS = DASHBOARD_PERIODS
MONTHS_BACK_PERIODS = frozenset({"m1", "m2", "m3", "m6", "m12"})
REJECT_STAGES = frozenset(
    {"rejected_hr", "rejected_client", "rejected_candidate", "rejected_vacancy_closed", "rejected", "archived"}
)


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def _add_calendar_months(dt: datetime, months: int) -> datetime:
    """Shift by calendar months (negative = back). Clamps day to month length."""
    import calendar

    m0 = dt.month - 1 + months
    y = dt.year + m0 // 12
    m = m0 % 12 + 1
    d = min(dt.day, calendar.monthrange(y, m)[1])
    return dt.replace(year=y, month=m, day=d)


def _period_window(
    period: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[datetime | None, datetime]:
    """Return (start, end). start=None means all time."""
    now = datetime.now(timezone.utc)
    if date_from or date_to or period == "custom":
        end = _parse_dt(date_to) if date_to else now
        if end is None:
            end = now
        end = _end_of_day(end) if date_to else now
        start = _parse_dt(date_from) if date_from else None
        if start is not None:
            start = _start_of_day(start)
        return start, end
    if period == "all":
        return None, now
    if period == "day":
        return _start_of_day(now), now
    if period == "week":
        # Monday 00:00 UTC of current week → now
        start = _start_of_day(now - timedelta(days=now.weekday()))
        return start, now
    if period == "mtd":
        return _start_of_day(now.replace(day=1)), now
    if period == "ytd":
        return _start_of_day(now.replace(month=1, day=1)), now
    if period in MONTHS_BACK_PERIODS:
        n = int(period[1:])
        return _add_calendar_months(now, -n), now
    # month / day / quarter… rolling presets
    delta = PERIOD_PRESETS.get(period) or PERIOD_PRESETS["month"]
    return now - delta, now


def _chart_grain(period: str) -> str:
    """Bucket grain for activity charts."""
    if period in ("day", "week", "mtd", "month", "m1", "m2", "m3", "custom"):
        return "week"  # daily labels
    return "half_year"  # monthly labels


def _in_window(dt: datetime | None, start: datetime | None, end: datetime) -> bool:
    if dt is None:
        return False
    if start is not None and dt < start:
        return False
    return dt <= end


def _history_entries(candidate: models.Candidate) -> list[dict[str, Any]]:
    raw = (candidate.payload or {}).get("hr_stage_history") or []
    if not isinstance(raw, list):
        return []
    return [e for e in raw if isinstance(e, dict)]


def _first_hire_at(candidate: models.Candidate) -> datetime | None:
    for entry in _history_entries(candidate):
        if entry.get("stage") in HIRE_STAGES:
            at = _parse_dt(entry.get("at"))
            if at:
                return at
    if candidate.hr_stage in HIRE_STAGES:
        return _parse_dt(candidate.status_updated_at) or _parse_dt(candidate.created_at)
    return None


def _reject_events_after_hire(
    candidate: models.Candidate, hire_at: datetime
) -> list[tuple[datetime, str, str]]:
    """(at, stage, note) for reject transitions after hire."""
    out: list[tuple[datetime, str, str]] = []
    for entry in _history_entries(candidate):
        stage = str(entry.get("stage") or "")
        if stage not in REJECT_STAGES:
            continue
        at = _parse_dt(entry.get("at"))
        if not at or at < hire_at:
            continue
        note = str(entry.get("note") or "").strip()
        out.append((at, stage, note))
    if candidate.hr_stage in REJECT_STAGES:
        at = _parse_dt(candidate.status_updated_at)
        if at and at >= hire_at and not any(x[0] == at for x in out):
            out.append((at, candidate.hr_stage, ""))
    out.sort(key=lambda x: x[0])
    return out


def _vacancy_warranty_months(vacancy: models.Vacancy) -> int:
    payload = vacancy.payload or {}
    w = payload.get("warranty")
    if isinstance(w, dict) and w.get("months") is not None:
        try:
            return max(1, int(w["months"]))
        except (TypeError, ValueError):
            pass
    raw = payload.get("warranty_months")
    if raw is not None:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    from app.services.app_settings import get_default_warranty_months

    return get_default_warranty_months()


def _days_between(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 86400))


def _vacancy_days_open(vacancy: models.Vacancy, *, now: datetime) -> int | None:
    created = _parse_dt(vacancy.created_at)
    if not created:
        return None
    end = _parse_dt(vacancy.closed_at) if not vacancy.active else now
    if not end:
        end = now
    return _days_between(created, end)


def build_dashboard_stats(
    db: Session,
    *,
    mode: str,
    period: str = "day",
    client_id: int | None = None,
    vacancy_id: int | None = None,
    active_vacancies_only: bool = False,
    organization_id: Any | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    if mode not in DASHBOARD_MODES:
        raise ValueError(f"mode: {', '.join(sorted(DASHBOARD_MODES))}")

    allowed = OPERATIONAL_PERIODS if mode == "operational" else EXECUTIVE_PERIODS
    if date_from or date_to:
        period = "custom"
    elif period not in allowed:
        period = "day"

    now = datetime.now(timezone.utc)
    start, end = _period_window(period, date_from=date_from, date_to=date_to)
    activity_start = start if start is not None else (now - PERIOD_PRESETS["year"])

    scope_client_ids = resolve_stats_client_ids(db, client_id)

    vacancies = _filter_vacancies(
        db,
        client_id=None,
        client_ids=scope_client_ids,
        vacancy_id=vacancy_id,
        active_only=False,
        organization_id=organization_id,
    )
    scope = [v for v in vacancies if (v.active if active_vacancies_only else True)]
    if vacancy_id is not None:
        scope = [v for v in vacancies if v.id == vacancy_id]
        if active_vacancies_only:
            scope = [v for v in scope if v.active]
    vac_by_id = {v.id: v for v in scope}
    vac_ids = list(vac_by_id.keys())
    candidates = _candidates_for_vacancies(db, vac_ids)

    period_from = start.isoformat() if start else None
    period_to = end.isoformat()

    if mode == "operational":
        return _build_operational(
            db,
            vacancies=scope,
            candidates=candidates,
            vac_by_id=vac_by_id,
            client_id=client_id,
            vacancy_id=vacancy_id,
            active_vacancies_only=active_vacancies_only,
            organization_id=organization_id,
            now=now,
            period=period,
            activity_start=activity_start,
            period_from=period_from,
            period_to=period_to,
        )

    return _build_executive(
        db,
        vacancies=scope,
        candidates=candidates,
        vac_by_id=vac_by_id,
        period=period,
        start=start,
        end=end,
        now=now,
        period_from=period_from,
        period_to=period_to,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
        organization_id=organization_id,
    )


def _build_operational(
    db: Session,
    *,
    vacancies: list[models.Vacancy],
    candidates: list[models.Candidate],
    vac_by_id: dict[int, models.Vacancy],
    client_id: int | None,
    vacancy_id: int | None,
    active_vacancies_only: bool,
    organization_id: Any | None,
    now: datetime,
    period: str,
    activity_start: datetime,
    period_from: str | None,
    period_to: str,
) -> dict[str, Any]:
    active_vacs = sum(1 for v in vacancies if v.active)
    in_work = sum(
        1
        for c in candidates
        if c.hr_stage not in REJECT_STAGES and c.hr_stage not in HIRE_STAGES
    )
    new_in_period = sum(
        1
        for c in candidates
        if (created := _parse_dt(c.created_at)) and created >= activity_start
    )

    grain = _chart_grain(period)
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"candidates": 0, "stage_changes": 0, "jobs": 0}
    )
    vac_id_set = set(vac_by_id)
    for c in candidates:
        created = _parse_dt(c.created_at)
        if created and created >= activity_start:
            buckets[_bucket_key(created, grain)]["candidates"] += 1
        for entry in _history_entries(c):
            at = _parse_dt(entry.get("at"))
            if at and at >= activity_start:
                buckets[_bucket_key(at, grain)]["stage_changes"] += 1

    jobs = list(db.scalars(select(models.Job).where(models.Job.created_at >= activity_start)).all())
    for j in jobs:
        if vac_id_set and j.vacancy_id not in vac_id_set and j.vacancy_id is not None:
            continue
        if vacancy_id is not None and j.vacancy_id != vacancy_id:
            continue
        created = j.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        buckets[_bucket_key(created, grain)]["jobs"] += 1

    series = [
        {
            "bucket": key,
            "candidates_added": vals["candidates"],
            "stage_changes": vals["stage_changes"],
            "jobs": vals["jobs"],
        }
        for key, vals in sorted(buckets.items())
    ]

    from app.services.candidate_query import list_candidates_filtered, vacancy_meta_maps

    attention_cands, att_vacs, _ = list_candidates_filtered(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
        preset="attention",
        organization_id=organization_id,
    )
    titles, _client_names = vacancy_meta_maps(db, att_vacs)
    attention = [
        {
            "id": str(c.id),
            "name": c.name or "Без имени",
            "vacancy_id": c.vacancy_id,
            "vacancy_title": titles.get(c.vacancy_id),
            "reason": getattr(c, "_attention_reason", None),
            "photo_url": ((c.payload or {}).get("photo_url") or "").strip() or None,
            "gender": normalize_gender((c.payload or {}).get("gender") or (c.payload or {}).get("sex")),
        }
        for c in attention_cands[:30]
    ]

    meetings_today = _count_meetings_today(candidates, now=now)
    waiting_client = _count_waiting_client(candidates)

    hh = build_hh_stats(
        db,
        client_id=client_id,
        vacancy_id=vacancy_id,
        active_vacancies_only=active_vacancies_only,
        organization_id=organization_id,
    )

    return {
        "mode": "operational",
        "period": period,
        "period_from": period_from,
        "period_to": period_to,
        "kpis": [
            {"key": "vacancies_active", "label": "Активные вакансии", "value": active_vacs},
            {"key": "candidates_in_work", "label": "Кандидаты в работе", "value": in_work},
            {"key": "new_period", "label": "Новые за период", "value": new_in_period},
            {"key": "attention", "label": "Требуют внимания", "value": len(attention_cands)},
            {"key": "meetings_today", "label": "Встречи сегодня", "value": meetings_today},
            {"key": "waiting_client", "label": "Ждут заказчика", "value": waiting_client},
        ],
        "activity_series": series,
        "funnel_flow": [],
        "attention": attention,
        "vacancies_table": [],
        "hh": hh,
        "warranty_risks": None,
    }


def _vacancy_close_outcome(
    vacancy: models.Vacancy,
    candidates: list[models.Candidate],
) -> str:
    close_reason = close_reason_from_payload(vacancy.payload)
    has_hire = any(
        str(c.hr_stage or "") in HIRE_STAGES for c in candidates if c.vacancy_id == vacancy.id
    )
    outcome = soft_vacancy_outcome(
        active=bool(vacancy.active),
        close_reason=close_reason,
        has_hire=has_hire,
    )
    return outcome or "no_result"


def _build_closed_breakdown(
    closed_vacancies: list[models.Vacancy],
    candidates: list[models.Candidate],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for v in closed_vacancies:
        outcome = _vacancy_close_outcome(v, candidates)
        closed_at = _parse_dt(v.closed_at)
        grouped[outcome].append(
            {
                "vacancy_id": v.id,
                "title": v.title,
                "closed_at": closed_at.isoformat() if closed_at else None,
            }
        )
    rows: list[dict[str, Any]] = []
    for reason in CLOSE_OUTCOME_ORDER:
        items = grouped.get(reason, [])
        if not items:
            continue
        items.sort(key=lambda x: x.get("closed_at") or "", reverse=True)
        rows.append(
            {
                "reason": reason,
                "label": CLOSE_OUTCOME_LABELS.get(reason, reason),
                "count": len(items),
                "vacancies": items,
            }
        )
    return {"total": len(closed_vacancies), "rows": rows}


def _build_executive(
    db: Session,
    *,
    vacancies: list[models.Vacancy],
    candidates: list[models.Candidate],
    vac_by_id: dict[int, models.Vacancy],
    period: str,
    start: datetime | None,
    end: datetime,
    now: datetime,
    period_from: str | None,
    period_to: str,
    client_id: int | None,
    vacancy_id: int | None,
    active_vacancies_only: bool,
    organization_id: Any | None,
) -> dict[str, Any]:
    closed_in_period = [
        v
        for v in vacancies
        if not v.active and _in_window(_parse_dt(v.closed_at), start, end)
    ]
    closed_count = len(closed_in_period)
    closed_breakdown = _build_closed_breakdown(closed_in_period, candidates)

    hire_durations: list[int] = []
    for v in closed_in_period:
        created = _parse_dt(v.created_at)
        closed = _parse_dt(v.closed_at)
        if created and closed and closed >= created:
            hire_durations.append(_days_between(created, closed))
    avg_days = round(sum(hire_durations) / len(hire_durations), 1) if hire_durations else 0

    hires_in_period = 0
    for c in candidates:
        hire_at = _first_hire_at(c)
        if hire_at and _in_window(hire_at, start, end):
            hires_in_period += 1

    total_cands = len(candidates)
    conversion = round((hires_in_period / total_cands) * 100, 1) if total_cands else 0.0

    flow_counts: dict[str, int] = defaultdict(int)
    for c in candidates:
        for entry in _history_entries(c):
            at = _parse_dt(entry.get("at"))
            stage = str(entry.get("stage") or "")
            if stage and _in_window(at, start, end):
                flow_counts[stage] += 1
    funnel_flow = [
        {"stage": k, "count": v} for k, v in sorted(flow_counts.items(), key=lambda x: -x[1])
    ]

    vac_cand_counts: dict[int, int] = defaultdict(int)
    vac_hire_counts: dict[int, int] = defaultdict(int)
    for c in candidates:
        vac_cand_counts[c.vacancy_id] += 1
        if _first_hire_at(c):
            vac_hire_counts[c.vacancy_id] += 1

    vacancies_table = [
        {
            "vacancy_id": v.id,
            "title": v.title,
            "active": v.active,
            "days_open": _vacancy_days_open(v, now=now),
            "candidates": vac_cand_counts.get(v.id, 0),
            "hires": vac_hire_counts.get(v.id, 0),
        }
        for v in sorted(vacancies, key=lambda x: (not x.active, x.title.lower()))
    ]

    # Warranty claims: hire → reject within warranty months; filter by leave date in period
    claims: list[dict[str, Any]] = []
    for c in candidates:
        hire_at = _first_hire_at(c)
        if not hire_at:
            continue
        vac = vac_by_id.get(c.vacancy_id)
        if not vac:
            continue
        months = _vacancy_warranty_months(vac)
        warranty_end = hire_at + timedelta(days=months * 30)
        rejects = _reject_events_after_hire(c, hire_at)
        if not rejects:
            continue
        left_at, stage, note = rejects[0]
        if left_at > warranty_end:
            continue
        if not _in_window(left_at, start, end):
            continue
        claims.append(
            {
                "candidate_id": str(c.id),
                "candidate_name": c.name or "Без имени",
                "vacancy_id": vac.id,
                "vacancy_title": vac.title,
                "days_worked": _days_between(hire_at, left_at),
                "reason": note or stage,
                "hire_at": hire_at.isoformat(),
                "left_at": left_at.isoformat(),
            }
        )
    claims.sort(key=lambda r: r.get("left_at") or "", reverse=True)

    # Replacements: warranty searches created in period + vacancies with 2+ hires ever
    warranty_searches = 0
    for v in vacancies:
        payload = v.payload or {}
        if payload.get("search_mode") != "warranty":
            continue
        created = _parse_dt(v.created_at)
        if _in_window(created, start, end):
            warranty_searches += 1

    multi_hire = sum(1 for vid, n in vac_hire_counts.items() if n >= 2)
    replacements_total = warranty_searches + multi_hire

    return {
        "mode": "executive",
        "period": period,
        "period_from": period_from,
        "period_to": period_to,
        "kpis": [
            {"key": "vacancies_closed", "label": "Закрыто вакансий", "value": closed_count},
            {"key": "hired", "label": "Нанято", "value": hires_in_period},
            {
                "key": "avg_hire_days",
                "label": "Ср. срок закрытия вакансии",
                "value": avg_days,
                "unit": "дн.",
            },
            {
                "key": "conversion",
                "label": "Конверсия в найм",
                "value": conversion,
                "unit": "%",
            },
            {
                "key": "warranty_claims",
                "label": "Возвраты по гарантии",
                "value": len(claims),
            },
            {
                "key": "replacements",
                "label": "Повторные / гарантийные поиски",
                "value": replacements_total,
            },
        ],
        "activity_series": [],
        "funnel_flow": funnel_flow,
        "attention": [],
        "vacancies_table": vacancies_table,
        "hh": None,
        "warranty_risks": {
            "claims_count": len(claims),
            "claims": claims[:50],
            "warranty_searches": warranty_searches,
            "multi_hire_vacancies": multi_hire,
            "replacements_total": replacements_total,
        },
        "closed_breakdown": closed_breakdown,
    }
