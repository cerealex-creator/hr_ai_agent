"""Job status helpers (sync SQLAlchemy)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import models

TERMINAL = frozenset({"completed", "failed", "cancelled"})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_job(db: Session, job_id: uuid.UUID) -> models.Job | None:
    return db.get(models.Job, job_id)


def update_job(
    db: Session,
    job_id: uuid.UUID,
    *,
    status: str | None = None,
    progress_pct: int | None = None,
    progress_label: str | None = None,
    result_ref: str | None = None,
    error: str | None = None,
    payload_patch: dict | None = None,
) -> models.Job | None:
    job = db.get(models.Job, job_id)
    if not job:
        return None
    if status is not None:
        job.status = status
    if progress_pct is not None:
        job.progress_pct = progress_pct
    if progress_label is not None:
        job.progress_label = progress_label
    if result_ref is not None:
        job.result_ref = result_ref
    if error is not None:
        job.error = error
    if payload_patch:
        payload = dict(job.payload or {})
        payload.update(payload_patch)
        job.payload = payload
    job.updated_at = utcnow()
    db.commit()
    db.refresh(job)
    return job


def update_job_isolated(
    job_id: uuid.UUID,
    *,
    status: str | None = None,
    progress_pct: int | None = None,
    progress_label: str | None = None,
    result_ref: str | None = None,
    error: str | None = None,
    payload_patch: dict | None = None,
) -> models.Job | None:
    """Own Session — safe from worker threads / asyncio.to_thread callbacks (audit M5)."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return update_job(
            db,
            job_id,
            status=status,
            progress_pct=progress_pct,
            progress_label=progress_label,
            result_ref=result_ref,
            error=error,
            payload_patch=payload_patch,
        )
    finally:
        db.close()


def is_cancelled(db: Session, job_id: uuid.UUID) -> bool:
    job = db.get(models.Job, job_id)
    return bool(job and job.status == "cancelled")


def is_cancelled_isolated(job_id: uuid.UUID) -> bool:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return is_cancelled(db, job_id)
    finally:
        db.close()


def create_job_row(
    db: Session,
    *,
    job_type: str,
    client_id: int | None = None,
    vacancy_id: int | None = None,
    payload: dict | None = None,
) -> models.Job:
    job = models.Job(
        job_type=job_type,
        status="queued",
        progress_pct=0,
        progress_label="В очереди",
        client_id=client_id,
        vacancy_id=vacancy_id,
        payload=payload or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_jobs(
    db: Session,
    *,
    limit: int = 50,
    vacancy_id: int | None = None,
    job_type: str | None = None,
    status: str | None = None,
    organization_id=None,
) -> list[models.Job]:
    q = select(models.Job)
    if organization_id is not None:
        from app.services.tenancy import org_client_ids, org_vacancy_ids

        vac_ids = org_vacancy_ids(db, organization_id)
        client_ids = org_client_ids(db, organization_id)
        if not vac_ids and not client_ids:
            return []
        clauses = []
        if vac_ids:
            clauses.append(models.Job.vacancy_id.in_(vac_ids))
        if client_ids:
            clauses.append(
                (models.Job.vacancy_id.is_(None)) & (models.Job.client_id.in_(client_ids))
            )
        if clauses:
            q = q.where(or_(*clauses))
        else:
            return []
    if vacancy_id is not None:
        q = q.where(models.Job.vacancy_id == int(vacancy_id))
    if job_type:
        q = q.where(models.Job.job_type == job_type)
    if status:
        q = q.where(models.Job.status == status)
    return list(db.scalars(q.order_by(models.Job.created_at.desc()).limit(limit)).all())


def job_history_summary(job: models.Job) -> dict:
    """Compact fields for HH search history UI (no full results array)."""
    payload = dict(job.payload or {})
    keywords = str(payload.get("keywords") or "").strip()
    return {
        "id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "progress_label": job.progress_label,
        "vacancy_id": job.vacancy_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "keywords": keywords,
        "keywords_short": " / ".join(
            line.strip() for line in keywords.splitlines() if line.strip()
        )[:120],
        "found": payload.get("found"),
        "evaluated": payload.get("evaluated"),
        "error": job.error,
    }


def delete_job(db: Session, job_id: uuid.UUID) -> bool:
    job = db.get(models.Job, job_id)
    if not job:
        return False
    db.delete(job)
    db.commit()
    return True


def delete_hh_jobs(
    db: Session,
    *,
    vacancy_id: int,
    statuses: list[str] | None = None,
    only_problematic: bool = False,
) -> int:
    """Delete HH search jobs for a vacancy. Returns deleted count."""
    q = select(models.Job).where(
        models.Job.vacancy_id == int(vacancy_id),
        models.Job.job_type == "hh_cold_search",
    )
    if only_problematic:
        q = q.where(models.Job.status.in_(("failed", "cancelled", "queued")))
    elif statuses:
        q = q.where(models.Job.status.in_(tuple(statuses)))
    rows = list(db.scalars(q).all())
    for job in rows:
        db.delete(job)
    db.commit()
    return len(rows)


def count_active(db: Session, organization_id=None) -> int:
    q = select(func.count()).select_from(models.Job).where(
        models.Job.status.in_(("queued", "running"))
    )
    if organization_id is not None:
        from app.services.tenancy import org_client_ids, org_vacancy_ids

        vac_ids = org_vacancy_ids(db, organization_id)
        client_ids = org_client_ids(db, organization_id)
        clauses = []
        if vac_ids:
            clauses.append(models.Job.vacancy_id.in_(vac_ids))
        if client_ids:
            clauses.append(
                (models.Job.vacancy_id.is_(None)) & (models.Job.client_id.in_(client_ids))
            )
        if not clauses:
            return 0
        q = q.where(or_(*clauses))
    return int(db.scalar(q) or 0)


def find_active_job_for_candidate(
    db: Session,
    *,
    job_type: str,
    candidate_id: str,
    limit: int = 40,
) -> models.Job | None:
    """Return newest queued/running job of this type for a candidate (payload.candidate_id)."""
    cid = str(candidate_id or "").strip()
    if not cid:
        return None
    rows = db.scalars(
        select(models.Job)
        .where(
            models.Job.job_type == job_type,
            models.Job.status.in_(("queued", "running")),
        )
        .order_by(models.Job.created_at.desc())
        .limit(limit)
    ).all()
    for job in rows:
        if str((job.payload or {}).get("candidate_id") or "").strip() == cid:
            return job
    return None


async def enqueue_candidate_resume_evals(
    db: Session,
    candidate_ids: list[str],
    *,
    skip_questionnaire: bool = False,
    pool=None,
    raise_on_pool_error: bool = True,
) -> list[str]:
    """Create candidate_evaluate_resume jobs and put them on the ARQ queue."""
    from uuid import UUID

    job_ids: list[str] = []
    if not candidate_ids:
        return job_ids
    if pool is None:
        try:
            from app.workers.redis_pool import get_arq_pool

            pool = await get_arq_pool()
        except Exception:
            if raise_on_pool_error:
                raise
            return job_ids

    for raw_id in candidate_ids:
        try:
            cid = UUID(str(raw_id))
        except ValueError:
            continue
        cand = db.get(models.Candidate, cid)
        if not cand:
            continue
        existing = find_active_job_for_candidate(
            db,
            job_type="candidate_evaluate_resume",
            candidate_id=str(cand.id),
        )
        if existing:
            job_ids.append(str(existing.id))
            continue
        payload: dict[str, str | bool] = {
            "candidate_id": str(cand.id),
            "candidate_name": cand.name,
        }
        if skip_questionnaire:
            payload["skip_questionnaire"] = True
        job = create_job_row(
            db,
            job_type="candidate_evaluate_resume",
            vacancy_id=cand.vacancy_id,
            payload=payload,
        )
        try:
            await pool.enqueue_job(
                "candidate_evaluate_resume", str(job.id), _job_id=str(job.id)
            )
            job_ids.append(str(job.id))
        except Exception as exc:  # noqa: BLE001
            update_job(
                db,
                job.id,
                status="failed",
                progress_label="Не удалось поставить в очередь",
                error=str(exc),
            )
            if raise_on_pool_error:
                raise
    return job_ids


def find_active_job_for_vacancy(
    db: Session,
    *,
    job_type: str,
    vacancy_id: int,
) -> models.Job | None:
    """Return newest queued/running job of this type for a vacancy (audit M8)."""
    return db.scalars(
        select(models.Job)
        .where(
            models.Job.job_type == job_type,
            models.Job.vacancy_id == int(vacancy_id),
            models.Job.status.in_(("queued", "running")),
        )
        .order_by(models.Job.created_at.desc())
        .limit(1)
    ).first()
