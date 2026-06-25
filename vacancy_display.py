"""Подписи вакансий для UI: период поиска вместо id."""

from __future__ import annotations

from datetime import date, datetime

MONTHS_RU = (
    "",
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)


def parse_vacancy_date(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def vacancy_period_bounds(vacancy, *, today=None):
    """Даты начала и конца периода поиска (created_at → closed_at или сегодня)."""
    start = parse_vacancy_date(vacancy.get("created_at"))
    if not start:
        return None, None
    if vacancy.get("closed_at"):
        end = parse_vacancy_date(vacancy.get("closed_at"))
    elif vacancy.get("active", True):
        end = today or date.today()
    else:
        end = start
    if not end:
        end = start
    if end < start:
        start, end = end, start
    return start, end


def format_vacancy_search_period(vacancy, *, precise=False, today=None):
    """
    Период поиска для отображения пользователю.
    precise=True — всегда «24.04.–16.05.26» (для различения одинаковых названий).
    """
    start, end = vacancy_period_bounds(vacancy, today=today)
    if not start:
        return "период не указан"
    if not end:
        end = start

    if precise or start == end:
        if start == end:
            return start.strftime("%d.%m.%y")
        return f"{start.strftime('%d.%m.')}–{end.strftime('%d.%m.%y')}"

    if start.year == end.year and start.month == end.month:
        return f"{MONTHS_RU[start.month]} {start.year % 100:02d}"

    if start.year == end.year:
        return f"{MONTHS_RU[start.month]}–{MONTHS_RU[end.month]} {start.year % 100:02d}"

    return f"{start.strftime('%d.%m.')}–{end.strftime('%d.%m.%y')}"


def format_vacancy_ui_label(vacancy, *, suffix="", precise=False, today=None):
    """«Название · апрель–май 26» — без id."""
    title = (vacancy.get("title") or "—").strip() or "—"
    period = format_vacancy_search_period(vacancy, precise=precise, today=today)
    label = f"{title} · {period}"
    if suffix:
        label = f"{label} · {suffix}"
    return label


def find_vacancy_by_id(all_vacancies, vacancy_id):
    if vacancy_id is None:
        return None
    return next((v for v in all_vacancies if v.get("id") == vacancy_id), None)


def build_vacancy_picker_options(vacancies, *, suffix_fn=None, today=None):
    """
    Подписи для selectbox. При коллизиях — точный диапазон дат.
    suffix_fn(vacancy) -> str | None — доп. пометка («гарантийный поиск» и т.п.).
    """
    title_counts = {}
    for v in vacancies:
        title = (v.get("title") or "").strip()
        title_counts[title] = title_counts.get(title, 0) + 1

    labels = []
    by_label = {}
    for v in vacancies:
        title = (v.get("title") or "").strip()
        need_precise = title_counts.get(title, 0) > 1
        suffix = suffix_fn(v) if suffix_fn else ""
        label = format_vacancy_ui_label(
            v,
            suffix=suffix,
            precise=need_precise,
            today=today,
        )
        if label in by_label:
            label = format_vacancy_ui_label(v, suffix=suffix, precise=True, today=today)
        labels.append(label)
        by_label[label] = v
    return labels, by_label
