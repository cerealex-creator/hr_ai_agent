"""Persist HH resumes already reviewed for a vacancy — skip on next cold search."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models

# Auto-ban after AI eval at or below this score
AI_LOW_MAX = 1

REASON_AI_LOW = "ai_low"
REASON_RECRUITER = "recruiter_reject"
REASON_SHORTLIST = "shortlist"
REASON_IN_FUNNEL = "in_funnel"

REASON_LABELS = {
    REASON_AI_LOW: "ИИ оценил низко",
    REASON_RECRUITER: "рекрутер отклонил",
    REASON_SHORTLIST: "уже в shortlist",
    REASON_IN_FUNNEL: "уже в воронке",
}

# Higher wins when upserting
REASON_PRIORITY = {
    REASON_RECRUITER: 4,
    REASON_IN_FUNNEL: 3,
    REASON_SHORTLIST: 2,
    REASON_AI_LOW: 1,
}


def reason_label(reason: str | None) -> str:
    return REASON_LABELS.get(str(reason or ""), str(reason or "уже смотрели"))


def upsert_seen(
    db: Session,
    *,
    vacancy_id: int,
    hh_resume_id: str,
    reason: str,
    title: str = "",
    url: str | None = None,
    ai_score: int | None = None,
    note: str | None = None,
) -> models.HhSeenResume:
    rid = (hh_resume_id or "").strip()
    if not rid:
        raise ValueError("hh_resume_id пуст")
    row = db.execute(
        select(models.HhSeenResume).where(
            models.HhSeenResume.vacancy_id == vacancy_id,
            models.HhSeenResume.hh_resume_id == rid,
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row:
        if REASON_PRIORITY.get(reason, 0) >= REASON_PRIORITY.get(row.reason, 0):
            row.reason = reason
        if title:
            row.title = title
        if url:
            row.url = url
        if ai_score is not None:
            row.ai_score = ai_score
        if note is not None:
            row.note = note
        row.updated_at = now
    else:
        row = models.HhSeenResume(
            vacancy_id=vacancy_id,
            hh_resume_id=rid,
            reason=reason,
            title=title or "",
            url=url,
            ai_score=ai_score,
            note=note,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mark_ai_low_scores(db: Session, vacancy_id: int, results: list[dict[str, Any]]) -> int:
    """Persist resumes with ai_score <= AI_LOW_MAX from a completed search.

    Skips rows with eval errors / parse failures (must not poison the ban list).
    """
    n = 0
    for r in results:
        if r.get("skipped_eval") or r.get("skipped_prefilter") or r.get("skipped_seen"):
            continue
        if r.get("error") or r.get("parse_error"):
            continue
        score = r.get("ai_score")
        try:
            score_i = int(score) if score is not None else None
        except (TypeError, ValueError):
            score_i = None
        if score_i is None or score_i > AI_LOW_MAX:
            continue
        rid = str(r.get("hh_resume_id") or "").strip()
        if not rid:
            continue
        upsert_seen(
            db,
            vacancy_id=vacancy_id,
            hh_resume_id=rid,
            reason=REASON_AI_LOW,
            title=str(r.get("title") or ""),
            url=r.get("url"),
            ai_score=score_i,
        )
        n += 1
    return n


def excluded_map(db: Session, vacancy_id: int) -> dict[str, dict[str, Any]]:
    """hh_resume_id -> {reason, title, ai_score, ...} including shortlist."""
    out: dict[str, dict[str, Any]] = {}
    seen_rows = (
        db.execute(
            select(models.HhSeenResume).where(models.HhSeenResume.vacancy_id == vacancy_id)
        )
        .scalars()
        .all()
    )
    for row in seen_rows:
        out[row.hh_resume_id] = {
            "reason": row.reason,
            "label": reason_label(row.reason),
            "title": row.title,
            "ai_score": row.ai_score,
            "source": "seen",
        }
    short_rows = (
        db.execute(
            select(models.HhShortlistItem).where(models.HhShortlistItem.vacancy_id == vacancy_id)
        )
        .scalars()
        .all()
    )
    for row in short_rows:
        # shortlist takes precedence for display if not recruiter-rejected / in funnel
        prev = out.get(row.hh_resume_id)
        if prev and prev.get("reason") in (REASON_RECRUITER, REASON_IN_FUNNEL):
            continue
        out[row.hh_resume_id] = {
            "reason": REASON_SHORTLIST,
            "label": reason_label(REASON_SHORTLIST),
            "title": row.title,
            "ai_score": row.ai_score,
            "source": "shortlist",
        }
    # Candidates already in funnel (by hh_resume_id in payload)
    cands = (
        db.execute(select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id))
        .scalars()
        .all()
    )
    for cand in cands:
        rid = str((cand.payload or {}).get("hh_resume_id") or "").strip()
        if not rid:
            continue
        prev = out.get(rid)
        if prev and prev.get("reason") == REASON_RECRUITER:
            continue
        out[rid] = {
            "reason": REASON_IN_FUNNEL,
            "label": reason_label(REASON_IN_FUNNEL),
            "title": cand.name or "",
            "ai_score": (cand.payload or {}).get("ai_score"),
            "source": "funnel",
        }
    return out


def delete_seen(db: Session, vacancy_id: int, hh_resume_id: str) -> bool:
    row = db.execute(
        select(models.HhSeenResume).where(
            models.HhSeenResume.vacancy_id == vacancy_id,
            models.HhSeenResume.hh_resume_id == (hh_resume_id or "").strip(),
        )
    ).scalar_one_or_none()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
