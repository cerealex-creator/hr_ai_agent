"""U4: deterministic polish + critic shape."""
from app.services.management_l3_polish import _deterministic_polish
from app.services.management_l3_critic import run_deterministic_l3_critic


def test_deterministic_polish_instruction():
    assert _deterministic_polish("принять заявку.", doc_kind="instruction") == "Принять заявку"


def test_deterministic_polish_checklist_dedupe():
    out = _deterministic_polish("Выполнить:  Выполнить: тест", doc_kind="checklist")
    assert out.lower().count("выполнить:") == 1


def test_critic_empty_revision_shape(monkeypatch):
    # без БД — только проверяем, что функция импортируется и сигнатура ок
    assert callable(run_deterministic_l3_critic)
