"""Public client-zone API (token URL, no JWT)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import client_zone as cz

router = APIRouter(prefix="/client-zone", tags=["client-zone"])


class ClientZoneDecideIn(BaseModel):
    status: str = Field(description="ready | think | reject")
    comment: str | None = None
    meeting_date: str | None = None
    meeting_time: str | None = None
    meeting_format: str | None = Field(default="o", description="o|r|b")


@router.get("/{token}")
def client_zone_home(token: str, db: Session = Depends(get_db)) -> dict:
    return cz.list_zone_candidates(db, token)


@router.post("/{token}/candidates/{candidate_id}/decide")
def client_zone_decide(
    token: str,
    candidate_id: str,
    body: ClientZoneDecideIn,
    db: Session = Depends(get_db),
) -> dict:
    return cz.apply_zone_decision(
        db,
        token,
        candidate_id,
        status_key=body.status,
        comment=body.comment,
        meeting_date=body.meeting_date,
        meeting_time=body.meeting_time,
        meeting_format=body.meeting_format,
    )
