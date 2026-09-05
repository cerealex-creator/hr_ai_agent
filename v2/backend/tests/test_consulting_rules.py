from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.consulting import apply_row_status, traces_are_independent
from app.services.consulting_folders import FOLDER_TEMPLATE, parent_code


def test_folder_template_covers_00_09():
    codes = {row[1] for row in FOLDER_TEMPLATE}
    assert "00" in codes and "09" in codes
    assert "06.01.03" in codes
    assert parent_code("06.01.03") == "06.01"
    assert parent_code("00") is None
    assert len(FOLDER_TEMPLATE) >= 80


def test_echo_same_meeting_not_independent():
    a = {"source_type": "meeting", "meeting_id": "m1", "unit_id": "u1"}
    b = {"source_type": "meeting", "meeting_id": "m1", "unit_id": "u2"}
    assert traces_are_independent(a, b) is False


def test_survey_and_file_independent():
    a = {"source_type": "survey", "source_id": "s1", "unit_id": "u1"}
    b = {"source_type": "file", "source_id": "s2", "unit_id": "u1"}
    assert traces_are_independent(a, b) is True


def test_same_source_not_independent():
    a = {"source_type": "survey", "source_id": "s1"}
    b = {"source_type": "file", "source_id": "s1"}
    assert traces_are_independent(a, b) is False


def test_disputed_does_not_roll_back_to_recommended():
    row = SimpleNamespace(status="confirmed")
    apply_row_status(row, "sent")
    apply_row_status(row, "disputed")
    assert row.status == "disputed"
    with pytest.raises(HTTPException) as exc:
        apply_row_status(row, "recommended")
    assert exc.value.status_code == 400
    apply_row_status(row, "sent")
    assert row.status == "sent"
