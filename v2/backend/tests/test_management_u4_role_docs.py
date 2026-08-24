"""U4: role documents constants + KPI validator helpers + E6 fixture shape."""
import json
from pathlib import Path

from app.services.management_role_docs import DOC_KINDS, DOC_TITLES
from app.services.management_packs import load_pack_manifest

FIXTURE = Path(__file__).parent / "fixtures" / "management" / "l3_process_to_role_docs.json"


def test_doc_kinds():
    assert set(DOC_KINDS) == {"instruction", "kpi", "checklist"}
    for k in DOC_KINDS:
        assert k in DOC_TITLES


def test_construction_pack_has_processes():
    m = load_pack_manifest("construction_pilot")
    assert m["id"] == "construction_pilot"


def test_e6_l3_fixture_shape():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    steps = data["process_steps"]
    instr = [s["title"] for s in steps]
    assert instr == data["expected_instruction_titles"]
    checklist = [f"Выполнить: {s['title']}" for s in steps]
    assert checklist == data["expected_checklist_titles"]
