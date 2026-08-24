"""Тесты U3: пакеты, gap-валидаторы L2, gates helpers."""
from app.services.management_packs import list_industry_packs, load_pack_manifest
from app.services.management_gates import APPROVABLE_TYPES, REJECTABLE_TYPES, PENDING_STATUSES


def test_list_industry_packs():
    packs = list_industry_packs()
    ids = {p["id"] for p in packs}
    assert "sme_basis" in ids
    assert "construction_pilot" in ids


def test_load_sme_manifest():
    m = load_pack_manifest("sme_basis")
    assert m["id"] == "sme_basis"
    assert m["title"]
    assert m.get("defaults", {}).get("overload_roles") == 2


def test_gate_constants():
    assert "goal" in APPROVABLE_TYPES
    assert "process_map" in APPROVABLE_TYPES
    assert "role" in APPROVABLE_TYPES
    assert "goal" in REJECTABLE_TYPES
    assert "process_map" not in REJECTABLE_TYPES
    assert "suggested" in PENDING_STATUSES
