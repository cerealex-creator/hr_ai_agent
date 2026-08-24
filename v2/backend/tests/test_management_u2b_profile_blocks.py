"""Тесты валидаторов паспорта бизнеса и BSC-блоков."""
from app.db import management_models as m
from app.services.management_business_profile import validate_business_profile
from app.services.management_validators import clamp_ai_block_goals_payload


def test_validate_business_profile_missing():
    assert validate_business_profile(None)[0].startswith("BUSINESS_PROFILE_MISSING")


def test_validate_business_profile_min_ok():
    profile = m.MgmtBusinessProfile(
        revision_id=__import__("uuid").uuid4(),
        industry_code="it",
        business_model="service",
        scale_band="small",
        horizon_months=12,
    )
    assert validate_business_profile(profile) == []


def test_clamp_ai_block_goals_payload():
    raw = {
        "goals": [
            {"title": "A", "dimension_codes": ["finance"]},
            {"title": "B"},
            {"title": "C"},
            {"title": "D"},
        ]
    }
    goals, warnings = clamp_ai_block_goals_payload(raw, block_code="finance")
    assert len(goals) == 3
    assert goals[0]["primary_dimension_code"] == "finance"
    assert any("GOAL_COUNT_EXCEEDED" in w for w in warnings)
