"""Гарантийный период после оффера, стажировки или выхода на работу."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from models import INTERNSHIP_STAGE, OFFER_STAGE, STARTED_WORK_STAGE

DAYS_PER_WARRANTY_MONTH = 30
WARRANTY_MONTH_CHOICES = list(range(1, 7))
WARRANTY_MONTH_LABELS = {m: f"{m} мес" for m in WARRANTY_MONTH_CHOICES}
WARRANTY_TRIGGER_STAGES = frozenset(
    {OFFER_STAGE, INTERNSHIP_STAGE, STARTED_WORK_STAGE}
)
SEARCH_MODE_NORMAL = "normal"
SEARCH_MODE_WARRANTY = "warranty"


def default_warranty():
    try:
        from app_settings import get_default_warranty_months

        months = get_default_warranty_months()
    except Exception:
        months = 3
    return {
        "active": False,
        "start_date": "",
        "months": months,
        "candidate_id": "",
        "start_kind": "",
    }


def migrate_vacancy_warranty(vacancy):
    """Дополняет поля гарантии у вакансии. Возвращает True если были изменения."""
    migrated = False
    if vacancy.get("search_mode") not in (SEARCH_MODE_NORMAL, SEARCH_MODE_WARRANTY):
        vacancy["search_mode"] = SEARCH_MODE_NORMAL
        migrated = True
    if "warranty_source_vacancy_id" not in vacancy:
        vacancy["warranty_source_vacancy_id"] = None
        migrated = True
    warranty = vacancy.get("warranty")
    if not isinstance(warranty, dict):
        vacancy["warranty"] = default_warranty()
        return True
    defaults = default_warranty()
    for key, val in defaults.items():
        if key not in warranty:
            warranty[key] = val
            migrated = True
    months = warranty.get("months")
    if months not in WARRANTY_MONTH_CHOICES:
        try:
            from app_settings import get_default_warranty_months

            warranty["months"] = get_default_warranty_months()
        except Exception:
            warranty["months"] = 3
        migrated = True
    return migrated


def warranty_total_days(warranty):
    months = warranty.get("months") or 3
    if months not in WARRANTY_MONTH_CHOICES:
        months = 3
    return months * DAYS_PER_WARRANTY_MONTH


def parse_warranty_start(warranty):
    raw = (warranty or {}).get("start_date") or ""
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def warranty_end_date(warranty):
    start = parse_warranty_start(warranty)
    if not start:
        return None
    return start + timedelta(days=warranty_total_days(warranty))


def warranty_days_remaining(warranty, *, today=None):
    if not (warranty or {}).get("active"):
        return None
    end = warranty_end_date(warranty)
    if not end:
        return None
    today = today or date.today()
    return (end - today).days


def is_warranty_active(vacancy, *, today=None):
    migrate_vacancy_warranty(vacancy)
    warranty = vacancy.get("warranty") or {}
    if not warranty.get("active"):
        return False
    remaining = warranty_days_remaining(warranty, today=today)
    return remaining is not None and remaining >= 0


def format_warranty_countdown(vacancy, *, today=None):
    migrate_vacancy_warranty(vacancy)
    warranty = vacancy.get("warranty") or {}
    if not warranty.get("active"):
        return ""
    remaining = warranty_days_remaining(warranty, today=today)
    if remaining is None:
        return ""
    if remaining < 0:
        return "Гарантия истекла"
    if remaining == 0:
        return "На гарантии · последний день"
    return f"На гарантии · осталось {remaining} дн."


def warranty_date_field_label(stage):
    """Подпись поля даты в зависимости от этапа воронки."""
    if stage == OFFER_STAGE:
        return (
            "Дата планируемого выхода на работу "
            "(точка отсчета срока гарантии)"
        )
    if stage == INTERNSHIP_STAGE:
        return "Дата выхода на стажировку (точка отсчета срока гарантии)"
    if stage == STARTED_WORK_STAGE:
        return "Дата выхода на работу (точка отсчета срока гарантии)"
    return "Дата начала отсчёта гарантии"


def apply_warranty_to_vacancy(vacancy, candidate, start_date, months, start_kind):
    """Запускает или обновляет гарантию на вакансии."""
    migrate_vacancy_warranty(vacancy)
    if months not in WARRANTY_MONTH_CHOICES:
        months = 3
    if isinstance(start_date, date):
        start_str = start_date.strftime("%Y-%m-%d")
    else:
        start_str = str(start_date or "")[:10]
    vacancy["warranty"] = {
        "active": True,
        "start_date": start_str,
        "months": months,
        "candidate_id": candidate.get("id", ""),
        "start_kind": start_kind,
    }


def vacancy_days_in_work(vacancy, *, today=None):
    """Сколько дней вакансия в работе (от created_at до сегодня или closed_at)."""
    today = today or date.today()
    raw = vacancy.get("created_at") or ""
    if not raw:
        return None, ""
    try:
        start = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            start = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return None, ""
    end_raw = vacancy.get("closed_at")
    if end_raw:
        try:
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                end = datetime.strptime(end_raw[:10], "%Y-%m-%d").date()
            except ValueError:
                end = today
    else:
        end = today
    days = max(0, (end - start).days)
    return days, start.strftime("%d.%m.%Y")


def format_vacancy_work_line(vacancy, *, html=False):
    cand_count = len(vacancy.get("candidates", []))
    days, since = vacancy_days_in_work(vacancy)
    if days is None:
        if html:
            return f"Кандидатов: <strong>{cand_count}</strong>"
        return f"Кандидатов: **{cand_count}**"
    if html:
        return (
            f"Кандидатов: <strong>{cand_count}</strong> · "
            f"В работе: <strong>{days}</strong> дн. (с {since})"
        )
    return f"Кандидатов: **{cand_count}** · В работе: **{days}** дн. (с {since})"


def is_warranty_search_vacancy(vacancy):
    migrate_vacancy_warranty(vacancy)
    return vacancy.get("search_mode") == SEARCH_MODE_WARRANTY


def create_warranty_search_vacancy(source_vacancy, create_vacancy_fn):
    """Создаёт активную вакансию «Гарантийный поиск», связанную с архивной."""
    title = (source_vacancy.get("title") or "").strip()
    if not title:
        return False, "У исходной вакансии нет названия"
    ok, result = create_vacancy_fn(
        title,
        source_vacancy.get("chat_id"),
        client_id=source_vacancy.get("client_id", 0),
        documents=source_vacancy.get("documents"),
        show_portfolio_field=source_vacancy.get("show_portfolio_field", False),
    )
    if not ok:
        return False, result
    new_v = result
    new_v["search_mode"] = SEARCH_MODE_WARRANTY
    new_v["warranty_source_vacancy_id"] = source_vacancy.get("id")
    return True, new_v


def collect_warranty_vacancies(all_vacancies, *, today=None):
    """Вакансии с активной гарантией (архивные и не только)."""
    rows = []
    for v in all_vacancies:
        migrate_vacancy_warranty(v)
        if is_warranty_active(v, today=today):
            rows.append(v)
    return rows
