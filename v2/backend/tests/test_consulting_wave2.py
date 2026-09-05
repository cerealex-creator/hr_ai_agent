from app.services.consulting_wave2 import (
    MEGAMAID_SEED,
    TRAIL_OPTIONS,
    _build_questions_for_coverage,
)


def test_megamaid_seed_has_supply():
    codes = {c for c, *_ in MEGAMAID_SEED}
    assert "proc_supply" in codes
    assert len(MEGAMAID_SEED) >= 8


def test_full_survey_when_not_only_spots():
    qs = _build_questions_for_coverage(set(), fill_white_spots=False)
    assert len(qs) >= 20
    assert any(q["code"].endswith("_trace") for q in qs)
    assert TRAIL_OPTIONS[0] in qs[0]["options"]


def test_white_spots_survey_filters():
    qs = _build_questions_for_coverage({"proc_supply", "goals"}, fill_white_spots=True)
    codes = {q["coverage_code"] for q in qs}
    assert codes == {"proc_supply", "goals"}
    assert all(q["channel"] == "link" for q in qs)


def test_empty_open_falls_back():
    qs = _build_questions_for_coverage(set(), fill_white_spots=True)
    assert len(qs) >= 6


def test_weak_answer_not_coverage():
    from app.services.consulting_wave2 import _answer_is_substantive

    assert not _answer_is_substantive("Не знаю / не сталкивался")
    assert not _answer_is_substantive("")
    assert _answer_is_substantive("В мессенджере у прораба")
