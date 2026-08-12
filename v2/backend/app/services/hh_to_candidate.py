"""Create a funnel candidate from an HH cold-search shortlist item."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.candidate_photo import hh_photo_url_from_data


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _salary_str(snapshot: dict[str, Any]) -> str:
    amount = snapshot.get("salary_amount")
    if amount is None:
        return ""
    cur = (snapshot.get("salary_currency") or "").strip()
    return f"{amount} {cur}".strip()


def _display_name(item: models.HhShortlistItem, snapshot: dict[str, Any]) -> str:
    """Cold search usually has no FIO — use HH title as placeholder name."""
    title = (item.title or snapshot.get("title") or "").strip()
    if title:
        return f"HH · {title}"
    rid = (item.hh_resume_id or "")[:10]
    return f"HH resume {rid}" if rid else "HH кандидат"


def find_candidate_by_hh_resume(
    db: Session, vacancy_id: int, hh_resume_id: str
) -> models.Candidate | None:
    rid = (hh_resume_id or "").strip()
    if not rid:
        return None
    rows = db.scalars(
        select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)
    ).all()
    for c in rows:
        payload = c.payload or {}
        if str(payload.get("hh_resume_id") or "").strip() == rid:
            return c
        link = str(payload.get("hh_resume_link") or payload.get("resume_link") or "")
        if rid and rid in link:
            return c
    return None


def build_payload_from_shortlist(item: models.HhShortlistItem) -> dict[str, Any]:
    snap = item.snapshot if isinstance(item.snapshot, dict) else {}
    photo_url = hh_photo_url_from_data(snap) or ""
    url = (item.url or snap.get("url") or "").strip()
    if not url and item.hh_resume_id:
        url = f"https://hh.ru/resume/{item.hh_resume_id}"

    age = snap.get("age")
    age_str = str(age) if age is not None and str(age).strip() else ""
    city = (item.area or snap.get("area") or "") or ""
    if isinstance(city, dict):
        city = str(city.get("name") or "")

    ai_preview = (snap.get("ai_preview") or "").strip()
    sections = snap.get("ai_comment_sections")
    if not isinstance(sections, dict):
        sections = {}

    score = item.ai_score if item.ai_score is not None else snap.get("ai_score")

    return {
        "hh_resume_id": item.hh_resume_id,
        "hh_resume_link": url,
        "resume_link": url,
        "portfolio_link": "",
        "video_link": "",
        "task_link": "",
        "extra_materials": [],
        "transcript": "",
        "hr_comment": (item.note or "").strip(),
        "interview_eval_notes": "",
        "client_comment": "",
        "photo_url": photo_url,
        "office_interview_date": "",
        "office_interview_time": "",
        "client_final_verdict": "",
        "ai_score": score,
        "ai_comment": ai_preview,
        "ai_comment_sections": sections,
        "ai_strengths": snap.get("ai_strengths") or [],
        "ai_weaknesses": snap.get("ai_weaknesses") or [],
        "ai_score_source": "hh_cold_search",
        "control_word_status": "",
        "control_word_match": "",
        "control_word_note": "",
        "viewed": False,
        "remote_interview": False,
        "office_interview": False,
        "ignore_flags": None,
        "profile_checked": False,
        "ai_profile_requirements_met": {},
        "ai_flags_applied": [],
        "phone": "",
        "age": age_str,
        "city": str(city).strip() if city else "",
        "metro": "",
        "salary_expected": _salary_str(snap),
        "age_location": "",
        "resume_text": "",
        "hr_stage_history": [],
        "interview_focus_questions": [],
        "interview_questionnaire": [],
        "cold_screening": True,
        "contacts_opened": bool(snap.get("contacts_opened")),
        "source": "hh_cold_search",
        "hh_title_fit": snap.get("title_fit"),
        "hh_office_fit": snap.get("office_fit"),
        "hh_commute_ok": snap.get("commute_ok"),
        "interview_schedule_key": "",
        "interview_reminder_30_sent": False,
        "interview_reminder_10_sent": False,
        "interview_reminder_60_sent": False,
        "feedback_reminder_last_sent_at": "",
        "think_long_reminder_sent": False,
        "calendar_event_id": "",
    }


def create_candidate_from_shortlist(
    db: Session,
    *,
    vacancy_id: int,
    item: models.HhShortlistItem,
    remove_from_shortlist: bool = True,
) -> tuple[models.Candidate, bool]:
    """
    Returns (candidate, created_new).
    Idempotent by hh_resume_id within the vacancy.
    """
    if item.vacancy_id != vacancy_id:
        raise ValueError("Shortlist item belongs to another vacancy")

    from app.services.hh_seen import REASON_IN_FUNNEL, upsert_seen

    rid = (item.hh_resume_id or "").strip()
    item_title = item.title or ""
    item_url = item.url
    item_score = item.ai_score

    existing = find_candidate_by_hh_resume(db, vacancy_id, rid)
    if existing:
        if remove_from_shortlist:
            db.delete(item)
            db.commit()
            db.refresh(existing)
        try:
            upsert_seen(
                db,
                vacancy_id=vacancy_id,
                hh_resume_id=rid,
                reason=REASON_IN_FUNNEL,
                title=existing.name or item_title,
                url=item_url,
                ai_score=item_score,
            )
        except ValueError:
            pass
        return existing, False

    snap = item.snapshot if isinstance(item.snapshot, dict) else {}
    now = _now_iso()
    payload = build_payload_from_shortlist(item)
    if not str(payload.get("photo_url") or "").strip() and rid:
        try:
            from app.core.config import get_settings
            from app.services.hh_client import HhClient

            client = HhClient(get_settings())
            resume = client.get_resume(rid)
            if isinstance(resume, dict):
                url = hh_photo_url_from_data(resume)
                if url:
                    payload["photo_url"] = url
        except Exception:  # noqa: BLE001
            pass
    cand = models.Candidate(
        id=uuid.uuid4(),
        vacancy_id=vacancy_id,
        name=_display_name(item, snap),
        hr_stage="resume_screening",
        client_status="wait",
        created_at=now,
        status_updated_at=now,
        payload=payload,
    )
    db.add(cand)
    if remove_from_shortlist:
        db.delete(item)
    db.commit()
    db.refresh(cand)
    try:
        upsert_seen(
            db,
            vacancy_id=vacancy_id,
            hh_resume_id=rid,
            reason=REASON_IN_FUNNEL,
            title=cand.name,
            url=(cand.payload or {}).get("hh_resume_link") or item_url,
            ai_score=item_score,
        )
    except ValueError:
        pass
    return cand, True
