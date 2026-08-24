"""СУП — интервью собственника (immutable answers)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m

INTERVIEW_QUESTIONS: list[dict[str, str]] = [
    {
        "key": "main_goal_12m",
        "text": "Главная цель бизнеса на ближайшие 12 месяцев — что должно измениться?",
    },
    {
        "key": "critical_metrics",
        "text": "Какие 2–3 показателя для вас критичны (выручка, маржа, клиенты, качество)?",
    },
    {
        "key": "pain_points",
        "text": "Что сейчас больше всего не устраивает в работе команды или процессах?",
    },
    {
        "key": "baseline_numbers",
        "text": "Текущие цифры по ключевому показателю (baseline): что есть сейчас? Можно «не знаю».",
    },
    {
        "key": "target_numbers",
        "text": "К какому результату хотите прийти (target) и к какому сроку?",
    },
    {
        "key": "team_overload",
        "text": "Какие направления или роли сейчас перегружены или, наоборот, не закрыты?",
    },
    {
        "key": "keep_working",
        "text": "Что уже работает хорошо и нельзя ломать при изменениях?",
    },
]

QUESTION_BY_KEY = {q["key"]: q for q in INTERVIEW_QUESTIONS}


def get_active_interview(
    db: Session, *, organization_id: uuid.UUID, revision_id: uuid.UUID
) -> m.MgmtOwnerInterviewSession | None:
    return db.scalar(
        select(m.MgmtOwnerInterviewSession)
        .where(
            m.MgmtOwnerInterviewSession.organization_id == organization_id,
            m.MgmtOwnerInterviewSession.revision_id == revision_id,
            m.MgmtOwnerInterviewSession.status == "in_progress",
        )
        .order_by(m.MgmtOwnerInterviewSession.updated_at.desc())
        .limit(1)
    )


def start_interview(
    db: Session,
    *,
    organization_id: uuid.UUID,
    revision_id: uuid.UUID,
    wizard_session_id: uuid.UUID | None = None,
    pack_hint: str | None = None,
) -> m.MgmtOwnerInterviewSession:
    existing = get_active_interview(db, organization_id=organization_id, revision_id=revision_id)
    if existing:
        if wizard_session_id and not existing.wizard_session_id:
            existing.wizard_session_id = wizard_session_id
        return existing

    session = m.MgmtOwnerInterviewSession(
        organization_id=organization_id,
        revision_id=revision_id,
        wizard_session_id=wizard_session_id,
        pack_hint=pack_hint,
        status="in_progress",
    )
    db.add(session)
    db.flush()
    return session


def list_active_answers(db: Session, session_id: uuid.UUID) -> list[m.MgmtOwnerInterviewAnswer]:
    return list(
        db.scalars(
            select(m.MgmtOwnerInterviewAnswer)
            .where(
                m.MgmtOwnerInterviewAnswer.session_id == session_id,
                m.MgmtOwnerInterviewAnswer.deprecated.is_(False),
            )
            .order_by(m.MgmtOwnerInterviewAnswer.sort_order, m.MgmtOwnerInterviewAnswer.created_at)
        ).all()
    )


def append_answer(
    db: Session,
    session: m.MgmtOwnerInterviewSession,
    *,
    question_key: str,
    answer_text: str,
) -> m.MgmtOwnerInterviewAnswer:
    q = QUESTION_BY_KEY.get(question_key)
    if not q:
        raise ValueError(f"Unknown question_key: {question_key}")
    text = answer_text.strip()
    if not text:
        raise ValueError("answer_text is required")

    for old in list_active_answers(db, session.id):
        if old.question_key == question_key:
            old.deprecated = True

    sort_order = INTERVIEW_QUESTIONS.index(q)
    row = m.MgmtOwnerInterviewAnswer(
        session_id=session.id,
        question_key=question_key,
        question_text=q["text"],
        answer_text=text,
        sort_order=sort_order,
    )
    db.add(row)
    db.flush()
    return row
