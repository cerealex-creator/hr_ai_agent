"""СУП — код-валидаторы L0/L1/L2 (invariant catalog v0)."""
from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_system import list_goals, list_links, list_tasks

MAX_GOALS = 5
MAX_TASKS_PER_GOAL = 5


def count_tasks_by_goal(db: Session, revision_id: uuid.UUID) -> dict[uuid.UUID, int]:
    links = list_links(db, revision_id)
    task_ids = {t.id for t in list_tasks(db, revision_id)}
    counts: dict[uuid.UUID, int] = defaultdict(int)
    for link in links:
        if link.link_kind != "decomposes":
            continue
        if link.source_type == "goal" and link.target_type == "task" and link.target_id in task_ids:
            counts[link.source_id] += 1
    return counts


def validate_l0_l1(db: Session, revision_id: uuid.UUID) -> list[str]:
    warnings: list[str] = []
    goals = list_goals(db, revision_id)
    if len(goals) > MAX_GOALS:
        warnings.append(f"GOAL_COUNT_EXCEEDED: {len(goals)} > {MAX_GOALS}")
    counts = count_tasks_by_goal(db, revision_id)
    for goal in goals:
        n = counts.get(goal.id, 0)
        if n > MAX_TASKS_PER_GOAL:
            warnings.append(
                f"TASK_COUNT_EXCEEDED: цель «{goal.title[:40]}» — {n} > {MAX_TASKS_PER_GOAL}"
            )
    return warnings


def clamp_ai_goals_payload(raw: dict) -> tuple[list[dict], list[str]]:
    """Нормализация ответа LLM + prompt-инварианты."""
    warnings: list[str] = []
    goals_raw = raw.get("goals") if isinstance(raw, dict) else None
    if not isinstance(goals_raw, list):
        return [], ["AI_SCHEMA_INVALID: goals must be a list"]

    goals: list[dict] = []
    for item in goals_raw[:MAX_GOALS]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        tasks_raw = item.get("tasks") if isinstance(item.get("tasks"), list) else []
        tasks: list[dict] = []
        for t in tasks_raw[:MAX_TASKS_PER_GOAL]:
            if not isinstance(t, dict):
                continue
            t_title = str(t.get("title") or "").strip()
            if t_title:
                tasks.append(t)
        if len(tasks_raw) > MAX_TASKS_PER_GOAL:
            warnings.append(f"TASK_COUNT_EXCEEDED: обрезано до {MAX_TASKS_PER_GOAL} для «{title[:30]}»")
        goals.append({**item, "title": title, "tasks": tasks})

    if len(goals_raw) > MAX_GOALS:
        warnings.append(f"GOAL_COUNT_EXCEEDED: обрезано до {MAX_GOALS}")
    return goals, warnings


MAX_BLOCK_GOALS = 3


def clamp_ai_block_goals_payload(raw: dict, *, block_code: str) -> tuple[list[dict], list[str]]:
    """Нормализация ответа LLM для одного BSC-блока (без задач, до 3 целей)."""
    warnings: list[str] = []
    goals_raw = raw.get("goals") if isinstance(raw, dict) else None
    if not isinstance(goals_raw, list):
        return [], ["AI_SCHEMA_INVALID: goals must be a list"]

    goals: list[dict] = []
    for item in goals_raw[:MAX_BLOCK_GOALS]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        goals.append(
            {
                **item,
                "title": title,
                "tasks": [],
                "dimension_codes": [block_code],
                "primary_dimension_code": block_code,
            }
        )

    if len(goals_raw) > MAX_BLOCK_GOALS:
        warnings.append(f"GOAL_COUNT_EXCEEDED: обрезано до {MAX_BLOCK_GOALS} для блока {block_code}")
    return goals, warnings


def validate_l2a_process_map(db: Session, revision_id: uuid.UUID, process_map_id: uuid.UUID) -> list[str]:
    """Ошибки при утверждении L2a: шаг без роли → STEP_NO_ROLE."""
    errors: list[str] = []
    steps = list(
        db.scalars(
            select(m.MgmtProcessStep)
            .where(
                m.MgmtProcessStep.revision_id == revision_id,
                m.MgmtProcessStep.process_map_id == process_map_id,
            )
            .order_by(m.MgmtProcessStep.sort_order)
        ).all()
    )
    for step in steps:
        if not step.role_id:
            errors.append(f"STEP_NO_ROLE: «{step.title[:60]}»")
    return errors


def validate_l2a(db: Session, revision_id: uuid.UUID) -> list[str]:
    errors: list[str] = []
    maps = list(
        db.scalars(select(m.MgmtProcessMap).where(m.MgmtProcessMap.revision_id == revision_id)).all()
    )
    for pm in maps:
        errors.extend(validate_l2a_process_map(db, revision_id, pm.id))
    return errors
