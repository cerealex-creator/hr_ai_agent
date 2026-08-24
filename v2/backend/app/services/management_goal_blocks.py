"""СУП — цели по блокам BSC (4 измерения)."""
from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import management_models as m
from app.services.management_ai import apply_l0_block_payload, generate_l0_for_block
from app.services.management_business_profile import get_business_profile, profile_context_for_ai
from app.services.management_interview import (
    append_answer,
    get_active_interview,
    list_active_answers,
    start_interview,
)
from app.services.management_system import (
    approve_goal,
    list_current_positions,
    list_goals,
)
from app.services.management_validators import validate_l0_l1

BlockCode = Literal["finance", "customers", "processes", "people"]
BLOCK_CODES: tuple[BlockCode, ...] = ("finance", "customers", "processes", "people")

GOAL_BLOCKS: list[dict] = [
    {
        "code": "finance",
        "title": "Финансы",
        "subtitle": "Выручка, прибыль, рентабельность",
        "sort_order": 1,
    },
    {
        "code": "customers",
        "title": "Клиенты / рынок",
        "subtitle": "Удержание, NPS, новые клиенты",
        "sort_order": 2,
    },
    {
        "code": "processes",
        "title": "Процессы / качество",
        "subtitle": "Сроки, ошибки, стандарты",
        "sort_order": 3,
    },
    {
        "code": "people",
        "title": "Команда / развитие",
        "subtitle": "Найм, текучесть, обучение",
        "sort_order": 4,
    },
]

BLOCK_QUESTIONS: dict[str, list[dict]] = {
    "finance": [
        {
            "key": "revenue_yearly",
            "text": "Выручка за год, ₽ (можно «не указываю»)",
            "field_type": "number",
            "placeholder": "например, 10 000 000",
            "optional": True,
        },
        {
            "key": "growth_plan",
            "text": "Планируемый рост",
            "field_type": "select",
            "options": ["0%", "10%", "20%", "30%", "50%", "Свой вариант", "Не указываю"],
        },
        {
            "key": "main_focus",
            "text": "Главный фокус",
            "field_type": "select",
            "options": ["Выручка", "Прибыль", "Рентабельность", "Денежный поток"],
        },
    ],
    "customers": [
        {
            "key": "repeat_share",
            "text": "Доля повторных клиентов, % (можно «не указываю»)",
            "field_type": "number",
            "placeholder": "например, 65",
            "optional": True,
        },
        {
            "key": "nps_target",
            "text": "Целевой NPS или CSAT (можно «не указываю»)",
            "field_type": "number",
            "placeholder": "например, +40",
            "optional": True,
        },
        {
            "key": "client_risk",
            "text": "Главный риск по клиентам",
            "field_type": "select",
            "options": ["Отток", "Жалобы на сроки", "Низкая конверсия", "Другое"],
        },
    ],
    "processes": [
        {
            "key": "deal_cycle_days",
            "text": "Средний цикл сделки, дней (можно «не указываю»)",
            "field_type": "number",
            "placeholder": "например, 14",
            "optional": True,
        },
        {
            "key": "rework_share",
            "text": "Доля переделок / ошибок, % (можно «не указываю»)",
            "field_type": "number",
            "placeholder": "например, 8",
            "optional": True,
        },
        {
            "key": "bottleneck",
            "text": "Что тормозит сильнее всего",
            "field_type": "select",
            "options": ["Согласования", "Закупки", "Производство", "Контроль качества"],
        },
    ],
    "people": [
        {
            "key": "team_size",
            "text": "Численность команды (можно «не указываю»)",
            "field_type": "number",
            "placeholder": "например, 24",
            "optional": True,
        },
        {
            "key": "turnover_pct",
            "text": "Текучесть за год, % (можно «не указываю»)",
            "field_type": "number",
            "placeholder": "например, 22",
            "optional": True,
        },
        {
            "key": "critical_role",
            "text": "Критичная роль",
            "field_type": "select",
            "options": ["Продажи", "Производство", "Бэк-офис", "Руководители"],
        },
    ],
}

QUESTION_BY_BLOCK_KEY: dict[str, dict] = {}
for block_code, questions in BLOCK_QUESTIONS.items():
    for q in questions:
        full_key = f"{block_code}.{q['key']}"
        QUESTION_BY_BLOCK_KEY[full_key] = {**q, "block_code": block_code, "full_key": full_key}


def block_question_key(block_code: str, question_key: str) -> str:
    if "." in question_key:
        return question_key
    return f"{block_code}.{question_key}"


def get_block_question_meta(question_key: str) -> dict | None:
    return QUESTION_BY_BLOCK_KEY.get(question_key)


def goals_for_block(
    db: Session, revision_id: uuid.UUID, block_code: str, *, dim_map: dict | None = None
) -> list[m.MgmtGoal]:
    goals = list_goals(db, revision_id)
    if dim_map is None:
        from app.services.management_system import goal_dimensions_map

        dim_map = goal_dimensions_map(db, [g.id for g in goals])
    result: list[m.MgmtGoal] = []
    for g in goals:
        dims = dim_map.get(g.id, [])
        primary = next((d for d in dims if d.get("is_primary")), None)
        codes = {d["code"] for d in dims}
        if primary and primary["code"] == block_code:
            result.append(g)
        elif not primary and block_code in codes:
            result.append(g)
    return result


def block_status(db: Session, revision_id: uuid.UUID, block_code: str, *, skipped: bool = False) -> str:
    if skipped:
        return "skipped"
    goals = goals_for_block(db, revision_id, block_code)
    if not goals:
        return "empty"
    if all(g.status == "approved" for g in goals):
        return "approved"
    return "draft"


def block_answers(db: Session, interview_id: uuid.UUID, block_code: str) -> list[m.MgmtOwnerInterviewAnswer]:
    prefix = f"{block_code}."
    return [a for a in list_active_answers(db, interview_id) if a.question_key.startswith(prefix)]


def goal_blocks_state(
    db: Session,
    revision_id: uuid.UUID,
    *,
    organization_id: uuid.UUID,
    skipped_blocks: list[str] | None = None,
) -> list[dict]:
    skipped = set(skipped_blocks or [])
    interview = get_active_interview(db, organization_id=organization_id, revision_id=revision_id)
    from app.services.management_system import goal_dimensions_map

    goals = list_goals(db, revision_id)
    dim_map = goal_dimensions_map(db, [g.id for g in goals])
    blocks: list[dict] = []
    for meta in GOAL_BLOCKS:
        code = meta["code"]
        status = block_status(db, revision_id, code, skipped=code in skipped)
        block_goals = goals_for_block(db, revision_id, code, dim_map=dim_map)
        answers = block_answers(db, interview.id, code) if interview else []
        blocks.append(
            {
                **meta,
                "status": status,
                "questions": BLOCK_QUESTIONS.get(code, []),
                "answers": answers,
                "goals": block_goals,
                "goals_count": len(block_goals),
                "approved_count": sum(1 for g in block_goals if g.status == "approved"),
            }
        )
    return blocks


def submit_block_answer(
    db: Session,
    *,
    organization_id: uuid.UUID,
    revision_id: uuid.UUID,
    wizard_session_id: uuid.UUID | None,
    block_code: str,
    question_key: str,
    answer_text: str,
) -> m.MgmtOwnerInterviewAnswer:
    if block_code not in BLOCK_CODES:
        raise ValueError(f"Unknown block: {block_code}")
    full_key = block_question_key(block_code, question_key)
    meta = get_block_question_meta(full_key)
    if not meta:
        raise ValueError(f"Unknown question_key: {question_key}")
    interview = start_interview(
        db,
        organization_id=organization_id,
        revision_id=revision_id,
        wizard_session_id=wizard_session_id,
    )
    return append_block_answer(db, interview, question_key=full_key, answer_text=answer_text, question_text=meta["text"])


def append_block_answer(
    db: Session,
    session: m.MgmtOwnerInterviewSession,
    *,
    question_key: str,
    answer_text: str,
    question_text: str,
) -> m.MgmtOwnerInterviewAnswer:
    text = answer_text.strip()
    if not text:
        raise ValueError("answer_text is required")

    for old in list_active_answers(db, session.id):
        if old.question_key == question_key:
            old.deprecated = True

    meta = get_block_question_meta(question_key) or {}
    block_code = meta.get("block_code", question_key.split(".")[0])
    q_index = 0
    for i, q in enumerate(BLOCK_QUESTIONS.get(block_code, [])):
        if f"{block_code}.{q['key']}" == question_key:
            q_index = i
            break

    row = m.MgmtOwnerInterviewAnswer(
        session_id=session.id,
        question_key=question_key,
        question_text=question_text,
        answer_text=text,
        sort_order=100 + BLOCK_CODES.index(block_code) * 10 + q_index,  # type: ignore[arg-type]
    )
    db.add(row)
    db.flush()
    return row


def generate_block_goals(
    db: Session,
    settings: Settings,
    *,
    organization_id: uuid.UUID,
    revision_id: uuid.UUID,
    block_code: str,
) -> dict:
    if block_code not in BLOCK_CODES:
        return {"ok": False, "error": "UNKNOWN_BLOCK", "message": "Неизвестный блок", "retryable": False}

    interview = get_active_interview(db, organization_id=organization_id, revision_id=revision_id)
    if not interview:
        return {
            "ok": False,
            "error": "INTERVIEW_MISSING",
            "message": "Сначала ответьте на вопросы блока",
            "retryable": False,
        }

    answers = block_answers(db, interview.id, block_code)
    if len(answers) < 1:
        return {
            "ok": False,
            "error": "BLOCK_INCOMPLETE",
            "message": "Нужен хотя бы один ответ в блоке",
            "retryable": False,
        }

    profile = get_business_profile(db, revision_id)
    positions = list_current_positions(db, revision_id)
    payload, ai_warnings, err = generate_l0_for_block(
        settings,
        db,
        block_code=block_code,
        answers=answers,
        profile=profile,
        positions=positions,
    )
    if err or not payload:
        return {
            "ok": False,
            "error": "AI_UNAVAILABLE",
            "message": err or "Не удалось получить ответ ИИ",
            "retryable": True,
        }

    goals = apply_l0_block_payload(db, revision_id, block_code, payload)
    val_warnings = validate_l0_l1(db, revision_id)
    return {
        "ok": True,
        "goals_count": len(goals),
        "warnings": ai_warnings + val_warnings,
    }


def approve_block_goals(
    db: Session,
    revision_id: uuid.UUID,
    block_code: str,
    *,
    goal_ids: list[uuid.UUID] | None = None,
) -> dict:
    block_goals = goals_for_block(db, revision_id, block_code)
    if not block_goals:
        return {"ok": False, "error": "NO_GOALS", "message": "Нет целей для утверждения в этом блоке"}

    to_approve = block_goals
    if goal_ids:
        id_set = set(goal_ids)
        to_approve = [g for g in block_goals if g.id in id_set and g.status == "draft"]
        if not to_approve:
            return {"ok": False, "error": "NO_SELECTED", "message": "Выберите черновые цели блока"}

    n = 0
    for g in to_approve:
        if g.status == "draft":
            approve_goal(db, g)
            n += 1
    return {"ok": True, "approved_count": n}


def all_blocks_done(db: Session, revision_id: uuid.UUID, skipped_blocks: list[str] | None = None) -> bool:
    skipped = set(skipped_blocks or [])
    for code in BLOCK_CODES:
        if code in skipped:
            continue
        if block_status(db, revision_id, code) != "approved":
            return False
    return True


def build_block_ai_context(
    db: Session,
    revision_id: uuid.UUID,
    block_code: str,
    answers: list[m.MgmtOwnerInterviewAnswer],
) -> str:
    profile = get_business_profile(db, revision_id)
    parts = [profile_context_for_ai(profile), f"\n## Блок BSC: {block_code}"]
    for a in answers:
        parts.append(f"- [{a.id}] ({a.question_key}): {a.answer_text}")
    return "\n".join(parts)
