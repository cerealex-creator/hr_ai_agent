"""СУП — генерация L0/L1 через chat_json + task= (U2)."""
from __future__ import annotations

import json
import time
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import management_models as m
from app.services.ai_json import chat_json
from app.services.management_system import (
    create_goal,
    create_link,
    create_task,
    list_current_positions,
)
from app.services.management_validators import clamp_ai_block_goals_payload, clamp_ai_goals_payload

L0_L1_SYSTEM = """Ты — методолог системы управления для SME (малый и средний бизнес).
По ответам собственника сформируй цели (L0) и задачи (L1).

Правила:
- Не более 5 целей (goals), не более 5 задач (tasks) на каждую цель.
- Каждая цель должна иметь cited_answer_ids — id ответов интервью, на которых основана цель.
- dimension_codes — из: finance, customers, processes, people (можно несколько).
- primary_dimension_code — одно основное из dimension_codes.
- baseline_value, target_value, metric_unit — только если собственник назвал цифры; иначе null и metric_source null.
- metric_source: "owner" если цифра от собственника, иначе null.
- weight — приоритет цели (сумма не обязана 100).

Верни ТОЛЬКО JSON:
{
  "goals": [
    {
      "title": "...",
      "weight": 25,
      "dimension_codes": ["finance"],
      "primary_dimension_code": "finance",
      "baseline_value": null,
      "target_value": null,
      "metric_unit": null,
      "metric_source": null,
      "cited_answer_ids": ["uuid"],
      "tasks": [
        {"title": "...", "metric_target": null, "metric_unit": null, "deadline": null}
      ]
    }
  ]
}"""


def _build_user_prompt(
    *,
    answers: list[m.MgmtOwnerInterviewAnswer],
    positions: list[m.MgmtCurrentPosition],
) -> str:
    parts = ["## Ответы собственника (immutable)"]
    for a in answers:
        parts.append(f"- [{a.id}] ({a.question_key}): {a.answer_text}")
    if positions:
        parts.append("\n## Текущая команда (as-is)")
        for p in positions:
            parts.append(f"- {p.title} × {p.headcount}")
    return "\n".join(parts)


def generate_l0_l1_from_interview(
    settings: Settings,
    db: Session | None,
    *,
    answers: list[m.MgmtOwnerInterviewAnswer],
    positions: list[m.MgmtCurrentPosition],
    max_retries: int = 3,
) -> tuple[dict[str, Any] | None, list[str], str | None]:
    """Live LLM с повторами. Возвращает (payload, warnings, error_message)."""
    user = _build_user_prompt(answers=answers, positions=positions)
    last_err: str | None = None
    for attempt in range(max_retries):
        try:
            raw = chat_json(
                settings,
                system=L0_L1_SYSTEM,
                user=user,
                temperature=0.35,
                max_tokens=4500,
                db=db,
                task="mgmt_l0_l1_from_interview",
            )
            if not isinstance(raw, dict) or not raw.get("goals"):
                last_err = "AI_SCHEMA_INVALID: empty goals"
                time.sleep(0.4 * (attempt + 1))
                continue
            goals, warnings = clamp_ai_goals_payload(raw)
            if not goals:
                last_err = "AI_SCHEMA_INVALID: no valid goals after clamp"
                time.sleep(0.4 * (attempt + 1))
                continue
            return {"goals": goals}, warnings, None
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            last_err = str(exc)
            time.sleep(0.6 * (attempt + 1))
    return None, [], last_err


def apply_l0_l1_payload(
    db: Session,
    revision_id: uuid.UUID,
    payload: dict[str, Any],
) -> tuple[list[m.MgmtGoal], list[m.MgmtTask]]:
    from app.services.management_system import clear_draft_l0_l1

    clear_draft_l0_l1(db, revision_id)
    created_goals: list[m.MgmtGoal] = []
    created_tasks: list[m.MgmtTask] = []

    for item in payload.get("goals") or []:
        if not isinstance(item, dict):
            continue
        cited = [str(x) for x in (item.get("cited_answer_ids") or []) if x]
        baseline = item.get("baseline_value")
        target = item.get("target_value")
        goal = create_goal(
            db,
            revision_id,
            title=str(item.get("title") or ""),
            weight=Decimal(str(item["weight"])) if item.get("weight") is not None else None,
            metric_unit=str(item["metric_unit"]).strip() if item.get("metric_unit") else None,
            baseline_value=Decimal(str(baseline)) if baseline is not None else None,
            target_value=Decimal(str(target)) if target is not None else None,
            metric_source=str(item["metric_source"]) if item.get("metric_source") else None,
            dimension_codes=[str(c) for c in (item.get("dimension_codes") or [])],
            primary_dimension_code=str(item["primary_dimension_code"])
            if item.get("primary_dimension_code")
            else None,
            cited_answer_ids=cited,
        )
        created_goals.append(goal)
        for t in item.get("tasks") or []:
            if not isinstance(t, dict):
                continue
            mt = t.get("metric_target")
            task = create_task(
                db,
                revision_id,
                title=str(t.get("title") or ""),
                metric_target=Decimal(str(mt)) if mt is not None else None,
                metric_unit=str(t["metric_unit"]).strip() if t.get("metric_unit") else None,
            )
            created_tasks.append(task)
            create_link(
                db,
                revision_id,
                source_type="goal",
                source_id=goal.id,
                target_type="task",
                target_id=task.id,
                link_kind="decomposes",
            )
    return created_goals, created_tasks


L0_BLOCK_SYSTEM = """Ты — методолог системы управления для SME.
По паспорту бизнеса и ответам собственника по одному блоку BSC сформируй 2–3 цели (L0) без задач.

Правила:
- Ровно один блок: primary_dimension_code = dimension_code из запроса.
- dimension_codes — только этот код.
- Не более 3 целей.
- cited_answer_ids — id ответов блока.
- baseline_value, target_value, metric_unit — только если собственник назвал цифры или явно хочет KPI;
  иначе null и metric_source null (качественная цель допустима).
- metric_source: "owner" если цифра от собственника, "pack_hint" если типовая подсказка, иначе null.
- Учитывай отрасль и масштаб из паспорта — формулировки должны быть уместны для этого бизнеса.

Верни ТОЛЬКО JSON:
{
  "goals": [
    {
      "title": "...",
      "weight": 25,
      "dimension_codes": ["finance"],
      "primary_dimension_code": "finance",
      "baseline_value": null,
      "target_value": null,
      "metric_unit": null,
      "metric_source": null,
      "cited_answer_ids": ["uuid"]
    }
  ]
}"""


def generate_l0_for_block(
    settings: Settings,
    db: Session | None,
    *,
    block_code: str,
    answers: list[m.MgmtOwnerInterviewAnswer],
    profile: m.MgmtBusinessProfile | None,
    positions: list[m.MgmtCurrentPosition],
    max_retries: int = 3,
) -> tuple[dict[str, Any] | None, list[str], str | None]:
    from app.services.management_business_profile import profile_context_for_ai

    parts = [
        profile_context_for_ai(profile),
        f"\n## Блок BSC: {block_code}",
        "## Ответы собственника по блоку",
    ]
    for a in answers:
        parts.append(f"- [{a.id}] ({a.question_key}): {a.answer_text}")
    if positions:
        parts.append("\n## Текущая команда (as-is)")
        for p in positions:
            parts.append(f"- {p.title} × {p.headcount}")
    parts.append(f"\nСгенерируй 2–3 цели для dimension_code={block_code}.")
    user = "\n".join(parts)

    last_err: str | None = None
    for attempt in range(max_retries):
        try:
            raw = chat_json(
                settings,
                system=L0_BLOCK_SYSTEM,
                user=user,
                temperature=0.35,
                max_tokens=3000,
                db=db,
                task="mgmt_l0_block_from_interview",
            )
            if not isinstance(raw, dict) or not raw.get("goals"):
                last_err = "AI_SCHEMA_INVALID: empty goals"
                time.sleep(0.4 * (attempt + 1))
                continue
            goals, warnings = clamp_ai_block_goals_payload(raw, block_code=block_code)
            if not goals:
                last_err = "AI_SCHEMA_INVALID: no valid goals after clamp"
                time.sleep(0.4 * (attempt + 1))
                continue
            return {"goals": goals}, warnings, None
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(0.6 * (attempt + 1))
    return None, [], last_err


def apply_l0_block_payload(
    db: Session,
    revision_id: uuid.UUID,
    block_code: str,
    payload: dict[str, Any],
) -> list[m.MgmtGoal]:
    from app.services.management_system import clear_draft_goals_for_dimension

    clear_draft_goals_for_dimension(db, revision_id, block_code)
    created_goals: list[m.MgmtGoal] = []

    for item in payload.get("goals") or []:
        if not isinstance(item, dict):
            continue
        cited = [str(x) for x in (item.get("cited_answer_ids") or []) if x]
        baseline = item.get("baseline_value")
        target = item.get("target_value")
        goal = create_goal(
            db,
            revision_id,
            title=str(item.get("title") or ""),
            weight=Decimal(str(item["weight"])) if item.get("weight") is not None else None,
            metric_unit=str(item["metric_unit"]).strip() if item.get("metric_unit") else None,
            baseline_value=Decimal(str(baseline)) if baseline is not None else None,
            target_value=Decimal(str(target)) if target is not None else None,
            metric_source=str(item["metric_source"]) if item.get("metric_source") else None,
            dimension_codes=[block_code],
            primary_dimension_code=block_code,
            cited_answer_ids=cited,
        )
        created_goals.append(goal)
    return created_goals


def parse_fixture_payload(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
