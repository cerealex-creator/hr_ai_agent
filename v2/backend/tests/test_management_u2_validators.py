"""U2 validators + AI payload clamp (E6)."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.management_validators import MAX_GOALS, MAX_TASKS_PER_GOAL, clamp_ai_goals_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "management"


def test_clamp_respects_max_goals_and_tasks():
    raw = {
        "goals": [
            {
                "title": f"Goal {i}",
                "tasks": [{"title": f"T{i}-{j}"} for j in range(8)],
            }
            for i in range(7)
        ]
    }
    goals, warnings = clamp_ai_goals_payload(raw)
    assert len(goals) == MAX_GOALS
    assert all(len(g["tasks"]) <= MAX_TASKS_PER_GOAL for g in goals)
    assert any("GOAL_COUNT_EXCEEDED" in w for w in warnings)
    assert any("TASK_COUNT_EXCEEDED" in w for w in warnings)


def test_l0_l1_fixture_schema():
    data = json.loads((FIXTURES / "l0_l1_from_interview.json").read_text(encoding="utf-8"))
    expected = data["expected_goals"]
    goals, warnings = clamp_ai_goals_payload(expected)
    assert len(warnings) == 0
    assert len(goals) == 1
    assert goals[0]["title"]
    assert len(goals[0]["tasks"]) == 2
    cited = goals[0].get("cited_answer_ids") or []
    assert len(cited) >= 1
