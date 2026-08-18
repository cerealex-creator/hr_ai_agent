"""Public interview digest page API (token URL, no JWT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.services.interview_digest import digest_for_client

router = APIRouter(prefix="/interview-digest", tags=["interview-digest"])


@router.get("/{token}")
def interview_digest_public(token: str, db: Session = Depends(get_db)) -> dict:
    raw = (token or "").strip()
    if not raw or len(raw) < 12:
        raise HTTPException(status_code=404, detail="Ссылка недействительна")
    # JSONB: payload->>'interview_digest_token'
    candidate = db.scalars(
        select(models.Candidate).where(
            models.Candidate.payload.op("->>")("interview_digest_token") == raw
        )
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Ссылка недействительна или устарела")
    digest = digest_for_client(candidate.payload)
    if not digest or (not digest.get("summary") and not digest.get("qa")):
        raise HTTPException(status_code=404, detail="Конспект ещё не готов")
    vacancy = db.get(models.Vacancy, candidate.vacancy_id)
    return {
        "candidate_name": candidate.name,
        "vacancy_title": vacancy.title if vacancy else None,
        "digest": digest,
    }
