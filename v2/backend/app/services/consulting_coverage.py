"""Каркас покрытия (скилл в коде) и годный след. Не факты о компании."""

from __future__ import annotations

from typing import Any

# Чек-лист «как обычно устроена компания». Не эталон проекта и не Мегамейд.
COMPANY_FRAME: list[tuple[str, str, tuple[str, ...]]] = [
    ("goals", "Цели и стратегия", ("01",)),
    ("org", "Оргструктура и ответственность", ("02",)),
    ("roles", "Роли и мотивация", ("03",)),
    ("plans", "Планы и отчётность", ("04",)),
    ("rhythms", "Управленческие ритмы", ("05",)),
    ("proc_order", "Получение заказа", ("06.01.01",)),
    ("proc_project", "Реализация проекта", ("06.01.02",)),
    ("proc_supply", "Закупки и снабжение", ("06.01.03",)),
    ("proc_money", "Управление деньгами", ("06.01.04",)),
    ("proc_hire", "Найм и адаптация", ("06.01.05",)),
    ("proc_contract", "Договорная работа", ("06.01.06",)),
    ("uk_fin", "Финансы УК", ("06.02.01",)),
    ("uk_hr", "HR УК", ("06.02.02",)),
    ("uk_legal", "Юридический блок", ("06.02.03",)),
    ("uk_comm", "Коммерция", ("06.02.04",)),
    ("uk_it", "IT", ("06.02.05",)),
    ("be", "Процессы бизнес-единиц", ("06.03",)),
    ("change", "Оргизменения", ("07",)),
    ("control", "Контроль внедрения", ("08",)),
]

CONFIRMED = frozenset({"confirmed", "sent", "approved"})


def folder_matches(folder_code: str | None, prefixes: tuple[str, ...]) -> bool:
    code = (folder_code or "").strip()
    if not code:
        return False
    for prefix in prefixes:
        if code == prefix or code.startswith(prefix + "."):
            return True
    return False


def source_is_good_trace(*, mark: str, quoted_text: str, extracted_text: str, extract_status: str) -> bool:
    """Рабочий документ или цитата. Список файлов папки и «мелькнуло в поиске» — нет."""
    if mark != "working":
        return False
    if (quoted_text or "").strip():
        return True
    if extract_status == "ok" and (extracted_text or "").strip():
        return True
    return False


def meeting_is_good_trace(*, transcript: str, digest: str) -> bool:
    return bool((transcript or "").strip() or (digest or "").strip())


def confidence_from_traces(traces: list[dict[str, Any]], *, blocking: bool = False) -> str:
    """Уверенность считает программа по полям, не ИИ."""
    if blocking:
        return "low"
    from app.services.consulting import traces_are_independent

    useful = [t for t in traces if t]
    if len(useful) < 2:
        return "low" if useful else "none"
    for i, a in enumerate(useful):
        for b in useful[i + 1 :]:
            if traces_are_independent(a, b):
                return "high"
    return "low"


def cell_closed(
    *,
    prefixes: tuple[str, ...],
    sources: list[dict[str, Any]],
    meetings: list[dict[str, Any]],
    registry: list[dict[str, Any]],
) -> bool:
    for src in sources:
        if not folder_matches(src.get("folder_code"), prefixes):
            continue
        if source_is_good_trace(
            mark=str(src.get("mark") or ""),
            quoted_text=str(src.get("quoted_text") or ""),
            extracted_text=str(src.get("extracted_text") or ""),
            extract_status=str(src.get("extract_status") or ""),
        ):
            return True
    for meet in meetings:
        if not folder_matches(meet.get("folder_code"), prefixes):
            continue
        if meeting_is_good_trace(transcript=str(meet.get("transcript") or ""), digest=str(meet.get("digest") or "")):
            return True
    for row in registry:
        if row.get("status") not in CONFIRMED:
            continue
        if folder_matches(row.get("folder_code"), prefixes):
            return True
    return False
