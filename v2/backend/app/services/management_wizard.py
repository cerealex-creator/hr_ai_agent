"""СУП — онбординг-мастер (U2b: команда → паспорт → блоки BSC)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import management_models as m
from app.services.management_business_profile import (
    get_business_profile,
    get_or_create_business_profile,
    mark_profile_complete,
    save_business_profile,
    validate_business_profile,
)
from app.services.management_goal_blocks import (
    BLOCK_CODES,
    all_blocks_done,
    approve_block_goals,
    generate_block_goals,
    goal_blocks_state,
    submit_block_answer,
)
from app.services.management_interview import INTERVIEW_QUESTIONS, append_answer, start_interview
from app.services.management_gap import build_gap_report
from app.services.management_packs import list_industry_packs
from app.services.management_system import (
    approve_all_draft_goals,
    get_draft_revision,
    get_or_create_system,
    import_positions_from_text,
    list_current_positions,
    list_goals,
    list_inherited_goals,
)
from app.services.management_validators import validate_l0_l1


def _migrate_legacy_wizard_step(session: m.MgmtWizardSession) -> None:
    """Сессии старого U2 (интервью на шаге 2) → шаг 4."""
    payload = dict(session.payload or {})
    old_step2 = payload.get("step2") or {}
    if old_step2.get("completed") and not payload.get("goal_blocks", {}).get("completed"):
        if session.step >= 3:
            session.step = 4
            payload.setdefault("goal_blocks", {"completed": True, "legacy_skip": True})
            session.payload = payload


def get_or_create_wizard_session(
    db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID | None
) -> m.MgmtWizardSession:
    system = get_or_create_system(db, organization_id, user_id)
    rev = get_draft_revision(db, system)
    session = None
    if rev:
        session = db.scalar(
            select(m.MgmtWizardSession)
            .where(
                m.MgmtWizardSession.organization_id == organization_id,
                m.MgmtWizardSession.status == "in_progress",
                m.MgmtWizardSession.revision_id == rev.id,
            )
            .order_by(m.MgmtWizardSession.updated_at.desc())
            .limit(1)
        )
    if not session:
        # fallback: любая in_progress без revision или чужая — создаём новую под активную систему
        session = m.MgmtWizardSession(
            organization_id=organization_id,
            revision_id=rev.id if rev else None,
            step=1,
            status="in_progress",
        )
        db.add(session)
    elif rev and not session.revision_id:
        session.revision_id = rev.id
    _migrate_legacy_wizard_step(session)
    db.flush()
    return session


def wizard_state(db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
    system = get_or_create_system(db, organization_id, user_id)
    rev = get_draft_revision(db, system)
    session = get_or_create_wizard_session(db, organization_id=organization_id, user_id=user_id)
    if not rev:
        raise RuntimeError("Draft revision missing")

    profile = get_or_create_business_profile(db, rev.id)
    payload = dict(session.payload or {})
    skipped_blocks = list(payload.get("skipped_blocks") or [])
    blocks = goal_blocks_state(
        db,
        rev.id,
        organization_id=organization_id,
        skipped_blocks=skipped_blocks,
    )
    goals = list_goals(db, rev.id)
    inherited = list_inherited_goals(db, system)
    warnings = validate_l0_l1(db, rev.id)
    profile_errors = validate_business_profile(profile) if session.step >= 2 else []
    gap_report = build_gap_report(db, rev.id) if session.step >= 5 else None

    return {
        "session": session,
        "system": system,
        "revision_id": rev.id,
        "step": session.step,
        "positions": list_current_positions(db, rev.id),
        "business_profile": profile,
        "goal_blocks": blocks,
        "skipped_blocks": skipped_blocks,
        "industry_packs": list_industry_packs(),
        "industry_pack_id": system.industry_pack_id,
        "inherited_goals": inherited,
        "gap_report": gap_report,
        "questions": INTERVIEW_QUESTIONS,
        "answers": [],
        "goals": goals,
        "warnings": warnings + profile_errors,
    }


def complete_wizard_step1(
    db: Session,
    session: m.MgmtWizardSession,
    *,
    skipped: bool = False,
    import_text: str | None = None,
) -> m.MgmtWizardSession:
    if not session.revision_id:
        raise ValueError("revision_id missing on wizard session")
    if import_text and import_text.strip():
        import_positions_from_text(db, session.revision_id, import_text.strip())
    payload = dict(session.payload or {})
    payload["step1"] = {"skipped": skipped, "completed": True}
    session.payload = payload
    session.step = 2
    get_or_create_business_profile(db, session.revision_id)
    db.flush()
    return session


def save_wizard_business_profile(db: Session, revision_id: uuid.UUID, **fields) -> m.MgmtBusinessProfile:
    return save_business_profile(db, revision_id, **fields)


def complete_wizard_step2_profile(db: Session, session: m.MgmtWizardSession) -> m.MgmtWizardSession:
    if not session.revision_id:
        raise ValueError("revision_id missing")
    profile = get_business_profile(db, session.revision_id)
    errors = validate_business_profile(profile)
    if errors:
        raise ValueError(errors[0].split(":", 1)[-1].strip() or errors[0])
    mark_profile_complete(profile)
    payload = dict(session.payload or {})
    payload["business_profile"] = {"completed": True}
    session.payload = payload
    session.step = 3
    db.flush()
    return session


def skip_goal_block(db: Session, session: m.MgmtWizardSession, block_code: str) -> m.MgmtWizardSession:
    if block_code not in BLOCK_CODES:
        raise ValueError(f"Unknown block: {block_code}")
    payload = dict(session.payload or {})
    skipped = list(payload.get("skipped_blocks") or [])
    if block_code not in skipped:
        skipped.append(block_code)
    payload["skipped_blocks"] = skipped
    session.payload = payload
    db.flush()
    return session


def complete_wizard_step3_blocks(db: Session, session: m.MgmtWizardSession) -> m.MgmtWizardSession:
    if not session.revision_id:
        raise ValueError("revision_id missing")
    payload = dict(session.payload or {})
    skipped = list(payload.get("skipped_blocks") or [])
    if not all_blocks_done(db, session.revision_id, skipped):
        raise ValueError("Утвердите цели во всех блоках или пропустите блок")
    payload["goal_blocks"] = {"completed": True}
    session.payload = payload
    session.step = 4
    db.flush()
    return session


def complete_wizard_step4_pack(db: Session, session: m.MgmtWizardSession) -> m.MgmtWizardSession:
    if not session.revision_id:
        raise ValueError("revision_id missing")
    system = db.scalar(
        select(m.MgmtSystem)
        .join(m.MgmtRevision, m.MgmtRevision.system_id == m.MgmtSystem.id)
        .where(m.MgmtRevision.id == session.revision_id)
    )
    if not system or not system.industry_pack_id:
        raise ValueError("Выберите и примените отраслевой пакет")
    payload = dict(session.payload or {})
    payload["industry_pack"] = {"completed": True, "pack_id": system.industry_pack_id}
    session.payload = payload
    session.step = 5
    db.flush()
    return session


def complete_wizard_step5_summary(db: Session, session: m.MgmtWizardSession) -> m.MgmtWizardSession:
    if not session.revision_id:
        raise ValueError("revision_id missing")
    payload = dict(session.payload or {})
    payload["summary"] = {"completed": True}
    session.payload = payload
    session.status = "completed"
    db.flush()
    return session


# --- Legacy aliases (старые URL шага 2 → блоки) ---


def submit_interview_answer(
    db: Session,
    *,
    organization_id: uuid.UUID,
    revision_id: uuid.UUID,
    wizard_session_id: uuid.UUID,
    question_key: str,
    answer_text: str,
) -> m.MgmtOwnerInterviewAnswer:
    if "." in question_key:
        block_code = question_key.split(".", 1)[0]
        return submit_block_answer(
            db,
            organization_id=organization_id,
            revision_id=revision_id,
            wizard_session_id=wizard_session_id,
            block_code=block_code,
            question_key=question_key,
            answer_text=answer_text,
        )
    interview = start_interview(
        db,
        organization_id=organization_id,
        revision_id=revision_id,
        wizard_session_id=wizard_session_id,
    )
    return append_answer(db, interview, question_key=question_key, answer_text=answer_text)


def generate_from_interview(
    db: Session,
    settings: Settings,
    *,
    organization_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> dict:
    return generate_block_goals(
        db, settings, organization_id=organization_id, revision_id=revision_id, block_code="finance"
    )


def approve_wizard_step2_goals(db: Session, revision_id: uuid.UUID) -> dict:
    goals = list_goals(db, revision_id)
    if not goals:
        return {"ok": False, "error": "NO_GOALS", "message": "Нет целей для утверждения"}
    n = approve_all_draft_goals(db, revision_id)
    return {"ok": True, "approved_count": n}


def complete_wizard_step2(db: Session, session: m.MgmtWizardSession) -> m.MgmtWizardSession:
    return complete_wizard_step3_blocks(db, session)
