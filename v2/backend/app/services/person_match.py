"""Person identity hub: normalize keys, find/create person, dedup check.

Single choke-point for all person_id assignment (see IMPLEMENTATION_PLAN_YAKOR §4).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import models

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_DIGITS_RE = re.compile(r"\D")
_SPACES_RE = re.compile(r"\s+")


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = _DIGITS_RE.sub("", raw)
    if not digits or len(digits) < 7:
        return None
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    val = raw.strip().lower()
    return val if "@" in val else None


def normalize_name(raw: str | None) -> str | None:
    if not raw:
        return None
    val = raw.strip().lower().replace("ё", "е")
    val = _SPACES_RE.sub(" ", val)
    return val if len(val) >= 2 else None


# ---------------------------------------------------------------------------
# Dedup check (without creating anything)
# ---------------------------------------------------------------------------


@dataclass
class DupHit:
    candidate_id: uuid.UUID
    person_id: uuid.UUID
    name: str
    vacancy_id: int
    vacancy_title: str
    match_kind: str  # "phone" | "email" | "name"


def check_duplicates(
    db: Session,
    *,
    org_id: uuid.UUID,
    phone: str | None = None,
    email: str | None = None,
    name: str | None = None,
    exclude_candidate_id: uuid.UUID | None = None,
) -> dict[str, list[DupHit]]:
    """Return {"hard": [...], "soft": [...]} duplicate hits within the org."""
    m_phone = normalize_phone(phone)
    m_email = normalize_email(email)
    m_name = normalize_name(name)

    hard: list[DupHit] = []
    soft: list[DupHit] = []

    if not (m_phone or m_email or m_name):
        return {"hard": hard, "soft": soft}

    hard_conditions = []
    if m_phone:
        hard_conditions.append(models.Candidate.match_phone == m_phone)
    if m_email:
        hard_conditions.append(models.Candidate.match_email == m_email)

    soft_condition = models.Candidate.match_name == m_name if m_name else None

    all_conditions = list(hard_conditions)
    if soft_condition is not None:
        all_conditions.append(soft_condition)
    if not all_conditions:
        return {"hard": hard, "soft": soft}

    q = (
        select(models.Candidate, models.Vacancy.title)
        .join(models.Vacancy, models.Candidate.vacancy_id == models.Vacancy.id)
        .where(
            models.Candidate.organization_id == org_id,
            or_(*all_conditions),
        )
    )
    if exclude_candidate_id:
        q = q.where(models.Candidate.id != exclude_candidate_id)

    rows = db.execute(q).all()

    hard_phone_set = set()
    hard_email_set = set()
    for cand, vac_title in rows:
        hit = DupHit(
            candidate_id=cand.id,
            person_id=cand.person_id or uuid.UUID(int=0),
            name=cand.name,
            vacancy_id=cand.vacancy_id,
            vacancy_title=vac_title or "",
            match_kind="",
        )
        if m_phone and cand.match_phone == m_phone:
            hit.match_kind = "phone"
            hard.append(hit)
            hard_phone_set.add(cand.id)
        elif m_email and cand.match_email == m_email:
            hit.match_kind = "email"
            hard.append(hit)
            hard_email_set.add(cand.id)

    already_hard = hard_phone_set | hard_email_set
    if m_name and soft_condition is not None:
        for cand, vac_title in rows:
            if cand.id in already_hard:
                continue
            if cand.match_name == m_name:
                soft.append(DupHit(
                    candidate_id=cand.id,
                    person_id=cand.person_id or uuid.UUID(int=0),
                    name=cand.name,
                    vacancy_id=cand.vacancy_id,
                    vacancy_title=vac_title or "",
                    match_kind="name",
                ))

    return {"hard": hard, "soft": soft}


# ---------------------------------------------------------------------------
# Person find-or-create + candidate sync
# ---------------------------------------------------------------------------


def _find_person(
    db: Session,
    org_id: uuid.UUID,
    m_phone: str | None,
    m_email: str | None,
) -> models.Person | None:
    """Find existing person by hard keys (phone or email) within org."""
    conditions = []
    if m_phone:
        conditions.append(models.Person.match_phone == m_phone)
    if m_email:
        conditions.append(models.Person.match_email == m_email)
    if not conditions:
        return None

    return db.execute(
        select(models.Person).where(
            models.Person.organization_id == org_id,
            models.Person.merged_into_person_id.is_(None),
            or_(*conditions),
        )
    ).scalar_one_or_none()


def refresh_person_keys(
    db: Session,
    *,
    candidate: models.Candidate,
    name: str,
    phone: str,
    email: str,
    org_id: uuid.UUID,
    mode: Literal["create", "patch", "copy", "import"] = "create",
    source_person_id: uuid.UUID | None = None,
) -> models.Person:
    """Single choke-point: normalize → find/create person → sync candidate cache."""
    m_phone = normalize_phone(phone)
    m_email = normalize_email(email)
    m_name = normalize_name(name)

    person: models.Person | None = None

    if mode == "copy" and source_person_id:
        person = db.get(models.Person, source_person_id)

    if person is None:
        person = _find_person(db, org_id, m_phone, m_email)

    if person is None:
        person = models.Person(
            id=uuid.uuid4(),
            organization_id=org_id,
            match_phone=m_phone,
            match_email=m_email,
            match_name=m_name,
        )
        db.add(person)
        db.flush()
    else:
        if m_phone and not person.match_phone:
            person.match_phone = m_phone
        if m_email and not person.match_email:
            person.match_email = m_email
        if m_name and not person.match_name:
            person.match_name = m_name

    candidate.person_id = person.id
    candidate.organization_id = org_id
    candidate.match_phone = m_phone
    candidate.match_email = m_email
    candidate.match_name = m_name

    return person


def get_related_candidates(
    db: Session,
    candidate: models.Candidate,
) -> list[dict[str, Any]]:
    """Return sibling candidates for the same person (different vacancies)."""
    if not candidate.person_id:
        return []

    rows = db.execute(
        select(models.Candidate, models.Vacancy.title)
        .join(models.Vacancy, models.Candidate.vacancy_id == models.Vacancy.id)
        .where(
            models.Candidate.person_id == candidate.person_id,
            models.Candidate.id != candidate.id,
        )
    ).all()

    return [
        {
            "candidate_id": str(c.id),
            "vacancy_id": c.vacancy_id,
            "vacancy_title": vt or "",
            "hr_stage": c.hr_stage,
        }
        for c, vt in rows
    ]
