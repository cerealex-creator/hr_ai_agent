"""Public client-zone API (token URL, no JWT)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import client_report as cr
from app.services import client_zone as cz

router = APIRouter(prefix="/client-zone", tags=["client-zone"])


class ClientZoneDecideIn(BaseModel):
    status: str = Field(description="ready | think | reject")
    decision_role: str = Field(
        description="unit_head | director | owner",
    )
    comment: str | None = None
    meeting_date: str | None = None
    meeting_time: str | None = None
    meeting_format: str | None = Field(default="o", description="o|r|b")


@router.get("/{token}")
def client_zone_home(token: str, db: Session = Depends(get_db)) -> dict:
    home = cz.list_zone_candidates(db, token)
    return cr.enrich_zone_home_with_reports(db, token, home)


@router.get("/{token}/reports")
def client_zone_reports(token: str, db: Session = Depends(get_db)) -> dict:
    return cr.list_zone_reports(db, token)


@router.get("/{token}/reports/{vacancy_id}")
def client_zone_report(token: str, vacancy_id: int, db: Session = Depends(get_db)) -> dict:
    return cr.get_zone_report(db, token, vacancy_id)


@router.get("/{token}/reports/{vacancy_id}/cohorts/{cohort}")
def client_zone_report_cohort(
    token: str,
    vacancy_id: int,
    cohort: str,
    db: Session = Depends(get_db),
) -> dict:
    return cr.list_zone_report_cohort(db, token, vacancy_id, cohort)


@router.get("/{token}/reports/{vacancy_id}/candidates/{candidate_id}")
def client_zone_report_candidate(
    token: str,
    vacancy_id: int,
    candidate_id: str,
    db: Session = Depends(get_db),
) -> dict:
    return cr.get_zone_report_candidate(db, token, vacancy_id, candidate_id)


@router.get("/{token}/candidates/{candidate_id}")
def client_zone_candidate(token: str, candidate_id: str, db: Session = Depends(get_db)) -> dict:
    return cz.get_zone_candidate(db, token, candidate_id)


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
        decision_role=body.decision_role,
        comment=body.comment,
        meeting_date=body.meeting_date,
        meeting_time=body.meeting_time,
        meeting_format=body.meeting_format,
    )
