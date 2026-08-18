"""Public resume-mockup zone (token URL, no JWT)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import resume_preview as rp

router = APIRouter(prefix="/resume-preview", tags=["resume-preview"])


class ResumePreviewDecideIn(BaseModel):
    action: str = Field(description="consider | reject")
    comment: str | None = None


@router.get("/{token}")
def resume_preview_home(token: str, db: Session = Depends(get_db)) -> dict:
    return rp.list_preview_pack(db, token)


@router.post("/{token}/candidates/{candidate_id}/decide")
def resume_preview_decide(
    token: str,
    candidate_id: str,
    body: ResumePreviewDecideIn,
    db: Session = Depends(get_db),
) -> dict:
    return rp.apply_preview_decision(
        db,
        token,
        candidate_id,
        action=body.action,
        comment=body.comment,
    )
