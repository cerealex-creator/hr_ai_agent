"""Тесты U5: маппинг gap → transition steps, покрытие."""
from app.services.management_transition import GAP_TO_ACTION


def test_gap_to_action_covers_core_codes():
    for code in (
        "COVERAGE_NONE",
        "COVERAGE_PARTIAL",
        "OVERLOAD",
        "STEP_NO_ROLE",
        "NO_ASSIGNMENTS",
        "PACK_SUGGESTED_GOALS",
        "GOAL_NUMERIC_GAP",
    ):
        assert code in GAP_TO_ACTION
        action, rec, horizon = GAP_TO_ACTION[code]
        assert action
        assert rec
        assert horizon in ("short", "medium", "long")


def test_hire_mapping_for_uncovered_role():
    action, rec, horizon = GAP_TO_ACTION["COVERAGE_NONE"]
    assert action == "hire"
    assert "нанять" in rec.lower() or "слот" in rec.lower()
    assert horizon == "short"
