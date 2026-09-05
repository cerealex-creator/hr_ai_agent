from app.services.consulting_coverage import (
    COMPANY_FRAME,
    cell_closed,
    confidence_from_traces,
    folder_matches,
    source_is_good_trace,
)
from app.services.consulting_extract import extract_public_source


def test_frame_is_skill_not_empty():
    assert len(COMPANY_FRAME) >= 10
    assert any(code == "proc_supply" for code, _, _ in COMPANY_FRAME)


def test_search_word_does_not_close_cell():
    sources = [
        {
            "folder_code": "06.01.03",
            "mark": "pending",
            "quoted_text": "закупки",
            "extracted_text": "закупки в поиске",
            "extract_status": "ok",
        }
    ]
    assert (
        cell_closed(prefixes=("06.01.03",), sources=sources, meetings=[], registry=[])
        is False
    )


def test_working_quote_closes_cell():
    sources = [
        {
            "folder_code": "01.02",
            "mark": "working",
            "quoted_text": "цели группы на год",
            "extracted_text": "",
            "extract_status": "none",
        }
    ]
    assert cell_closed(prefixes=("01",), sources=sources, meetings=[], registry=[]) is True
    assert cell_closed(prefixes=("06.01.03",), sources=sources, meetings=[], registry=[]) is False


def test_folder_listing_is_not_good_trace():
    assert (
        source_is_good_trace(
            mark="working",
            quoted_text="",
            extracted_text="Папка\n- a.docx",
            extract_status="folder",
        )
        is False
    )


def test_confirmed_registry_closes():
    registry = [{"status": "confirmed", "folder_code": "02.01"}]
    assert cell_closed(prefixes=("02",), sources=[], meetings=[], registry=registry) is True


def test_folder_match_prefix():
    assert folder_matches("06.01.03", ("06.01.03",))
    assert folder_matches("06.01.03.01", ("06.01.03",))
    assert not folder_matches("06.01.04", ("06.01.03",))


def test_confidence_needs_independent_traces():
    same = [
        {"source_type": "meeting", "meeting_id": "m1", "unit_id": "u1"},
        {"source_type": "meeting", "meeting_id": "m1", "unit_id": "u2"},
    ]
    assert confidence_from_traces(same) == "low"
    pair = [
        {"source_type": "file", "source_id": "s1", "unit_id": "u1"},
        {"source_type": "meeting", "source_id": "s2", "unit_id": "u1"},
    ]
    assert confidence_from_traces(pair) == "high"
    assert confidence_from_traces(pair, blocking=True) == "low"


def test_yandex_extract_folder_status(monkeypatch):
    monkeypatch.setattr(
        "app.services.consulting_extract.get_yandex_public_meta",
        lambda *a, **k: {"type": "dir", "name": "Реестры"},
    )
    monkeypatch.setattr(
        "app.services.consulting_extract.list_yandex_public_folder",
        lambda *a, **k: [{"name": "план.docx"}],
    )
    text, status = extract_public_source("https://disk.yandex.ru/d/abc")
    assert status == "folder"
    assert "план.docx" in text


def test_yandex_media_not_downloaded(monkeypatch):
    monkeypatch.setattr(
        "app.services.consulting_extract.get_yandex_public_meta",
        lambda *a, **k: {"media_type": "video", "name": "встреча.mp4"},
    )
    text, status = extract_public_source("https://disk.yandex.ru/i/xyz")
    assert status == "media"
    assert text == ""
