"""Talent pool API routes (YAKOR PR3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.schemas import (
    TalentPoolEntryOut,
    TalentPoolTakeIn,
    CandidateDetail,
)

router = APIRouter()


def _require_talent_pool_flag():
    from app.services.tenancy import require_org_id, current_org_integrations
    org_id = require_org_id()
    integrations = current_org_integrations()
    features = (integrations or {}).get("features") or {}
    if not features.get("talent_pool"):
        raise HTTPException(status_code=403, detail="talent_pool feature is not enabled")
    return org_id


@router.get("/talent-pool", response_model=list[TalentPoolEntryOut])
def list_talent_pool(
    q: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TalentPoolEntryOut]:
    from app.services.talent_pool import list_pool_entries

    org_id = _require_talent_pool_flag()
    entries = list_pool_entries(db, organization_id=org_id, q=q, limit=limit)
    return [TalentPoolEntryOut.model_validate(e) for e in entries]


@router.get("/talent-pool/{entry_id}", response_model=TalentPoolEntryOut)
def get_talent_pool_entry(entry_id: str, db: Session = Depends(get_db)) -> TalentPoolEntryOut:
    from uuid import UUID
    from app.services.talent_pool import get_pool_entry

    _require_talent_pool_flag()
    try:
        eid = UUID(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid entry id") from exc
    entry = get_pool_entry(db, eid)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return TalentPoolEntryOut.model_validate(entry)


@router.post("/talent-pool/{entry_id}/take", response_model=CandidateDetail, status_code=201)
def take_pool_entry(
    entry_id: str,
    body: TalentPoolTakeIn,
    db: Session = Depends(get_db),
) -> CandidateDetail:
    from uuid import UUID
    from app.services.talent_pool import get_pool_entry, take_to_vacancy
    from app.api.v1.common import _candidate_detail

    _require_talent_pool_flag()
    try:
        eid = UUID(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid entry id") from exc
    entry = get_pool_entry(db, eid)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    try:
        cand = take_to_vacancy(db, entry, body.vacancy_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _candidate_detail(db, cand)
