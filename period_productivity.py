"""Продуктивность HR за календарный период (месяц / квартал / полугодие)."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import mean

from models import (
    CLIENT_ZONE_ENTRY_STAGE,
    HR_STAGES,
    HR_STAGE_ORDER,
    INTERNSHIP_STAGE,
    OFFER_STAGE,
    STARTED_WORK_STAGE,
    is_rejection_stage,
    received_hr_stage,
)
from vacancy_close import CLOSE_REASON_CLIENT, CLOSE_REASON_SUCCESS, vacancy_has_successful_hire
from vacancy_display import format_vacancy_search_period, parse_vacancy_date, vacancy_period_bounds

INTERVIEW_SCHEDULED = "interview_scheduled"

METRIC_KEYS = (
    "vacancies_started",
    "selected_candidates",
    "primary_interviews",
    "client_review",
    "client_approved",
    "invited_work",
    "vacancies_closed_success",
    "vacancies_closed_client",
)

METRIC_LABELS = {
    "vacancies_started": "Взято в работу вакансий",
    "selected_candidates": "Отобрано кандидатов",
    "primary_interviews": "Проведено первичных собеседований",
    "client_review": "Внесено на рассмотрение",
    "client_approved": "Одобрено заказчиком",
    "invited_work": "Приглашены на работу / стажировку",
    "vacancies_closed_success": "Закрыто вакансий (успешно)",
    "vacancies_closed_client": "Закрыто заказчиком",
}

INVITE_KIND_LABELS = {
    "offer": "оффер",
    "internship": "стажировка",
    "direct_start": "выход на работу (без оффера/стажировки)",
}

CLOSURE_KIND_LABELS = {
    "before_period": "начата ранее периода",
    "in_period": "начата и закрыта в периоде",
}

_INTERVIEW_SCHED_IDX = HR_STAGE_ORDER.index(INTERVIEW_SCHEDULED)


def _candidate_name(candidate) -> str:
    return (candidate.get("name") or "").strip() or "Без имени"


def _vacancy_detail_label(vacancy) -> str:
    title = vacancy.get("title", "—")
    period_label = format_vacancy_search_period(vacancy, precise=True)
    return f"{title} ({period_label})" if period_label else title


def _started_vacancy_display_label(vacancy) -> str:
    """Для открытых вакансий — только название; для закрытых — с периодом поиска."""
    if vacancy.get("active", True):
        return vacancy.get("title", "—")
    return _vacancy_detail_label(vacancy)


def _candidate_stage_label(candidate) -> str:
    stage = candidate.get("hr_stage", "")
    return HR_STAGES.get(stage, stage or "—")


def _hire_candidates_for_vacancy(vacancy) -> list[dict]:
    hires = []
    for cand in vacancy.get("candidates", []):
        if received_hr_stage(cand, STARTED_WORK_STAGE):
            outcome = "вышел на работу"
        elif received_hr_stage(cand, INTERNSHIP_STAGE):
            outcome = "стажировка"
        else:
            continue
        hires.append({"name": _candidate_name(cand), "outcome": outcome})
    return hires


@dataclass
class PeriodMetrics:
    period_start: date
    period_end: date
    vacancies_started: int = 0
    selected_candidates: int = 0
    primary_interviews: int = 0
    client_review: int = 0
    client_approved: int = 0
    invited_work: int = 0
    vacancies_closed_success: int = 0
    vacancies_closed_success_started_before: int = 0
    vacancies_closed_success_started_in_period: int = 0
    vacancies_closed_client: int = 0
    vacancies_in_work: int = 0
    vacancy_titles_in_work: list[str] = field(default_factory=list)
    vacancies_started_details: list[dict] = field(default_factory=list)
    vacancies_closed_success_details: list[dict] = field(default_factory=list)
    vacancies_closed_not_success_details: list[dict] = field(default_factory=list)
    invited_work_details: list[dict] = field(default_factory=list)

    def as_dict(self):
        return {key: getattr(self, key) for key in METRIC_KEYS}


def _parse_dt(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _stage_index(stage):
    try:
        return HR_STAGE_ORDER.index(stage)
    except ValueError:
        return -1


def _is_forward_from_interview(stage):
    if is_rejection_stage(stage) or stage in ("rejected", "archived"):
        return False
    idx = _stage_index(stage)
    return idx > _INTERVIEW_SCHED_IDX


def _date_in_period(dt: datetime | None, start: date, end: date) -> bool:
    if not dt:
        return False
    day = dt.date() if hasattr(dt, "date") else dt
    return start <= day <= end


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    _, last = monthrange(year, end_month)
    return date(year, start_month, 1), date(year, end_month, last)


def _half_year_bounds(year: int, half: int) -> tuple[date, date]:
    if half == 1:
        return date(year, 1, 1), date(year, 6, 30)
    return date(year, 7, 1), date(year, 12, 31)


def period_bounds(period_type: str, year: int, index: int) -> tuple[date, date]:
    """index: месяц 1–12, квартал 1–4, полугодие 1–2."""
    if period_type == "month":
        return _month_bounds(year, index)
    if period_type == "quarter":
        return _quarter_bounds(year, index)
    if period_type == "half_year":
        return _half_year_bounds(year, index)
    raise ValueError(f"Unknown period_type: {period_type}")


def previous_period_bounds(period_type: str, year: int, index: int) -> tuple[date, date]:
    if period_type == "month":
        if index == 1:
            return _month_bounds(year - 1, 12)
        return _month_bounds(year, index - 1)
    if period_type == "quarter":
        if index == 1:
            return _quarter_bounds(year - 1, 4)
        return _quarter_bounds(year, index - 1)
    if period_type == "half_year":
        if index == 1:
            return _half_year_bounds(year - 1, 2)
        return _half_year_bounds(year, 1)
    raise ValueError(f"Unknown period_type: {period_type}")


def format_period_label(period_type: str, year: int, index: int) -> str:
    from vacancy_display import MONTHS_RU

    if period_type == "month":
        return f"{MONTHS_RU[index]} {year}"
    if period_type == "quarter":
        return f"{index}-й квартал {year}"
    if period_type == "half_year":
        return f"{'1-е' if index == 1 else '2-е'} полугодие {year}"
    return f"{year}"


def iter_calendar_months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        ms, me = _month_bounds(y, m)
        yield max(ms, start), min(me, end)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


def collect_all_entries(vacancies):
    entries = []
    for vacancy in vacancies:
        for candidate in vacancy.get("candidates", []):
            entries.append((candidate, vacancy))
    return entries


def detect_earliest_activity_date(vacancies, *, today=None) -> date | None:
    today = today or date.today()
    earliest = None

    def consider(raw):
        nonlocal earliest
        d = parse_vacancy_date(raw)
        if d and (earliest is None or d < earliest):
            earliest = d

    for vacancy in vacancies:
        consider(vacancy.get("created_at"))
        consider(vacancy.get("closed_at"))
        for cand in vacancy.get("candidates", []):
            consider(cand.get("created_at"))
            for entry in cand.get("hr_stage_history") or []:
                dt = _parse_dt(entry.get("at"))
                if dt:
                    consider(dt.date().isoformat())
            for entry in cand.get("client_status_history") or []:
                dt = _parse_dt(entry.get("at"))
                if dt:
                    consider(dt.date().isoformat())
    return earliest


def _sorted_hr_history(candidate):
    rows = []
    for entry in candidate.get("hr_stage_history") or []:
        stage = entry.get("stage")
        at = _parse_dt(entry.get("at"))
        if stage and at:
            rows.append((stage, at))
    rows.sort(key=lambda x: x[1])
    return rows


def first_primary_interview_at(candidate):
    """Первый переход с «Назначено собеседование» на рабочий этап вперёд."""
    history = _sorted_hr_history(candidate)
    for i in range(len(history) - 1):
        stage, _ = history[i]
        next_stage, next_at = history[i + 1]
        if stage == INTERVIEW_SCHEDULED and _is_forward_from_interview(next_stage):
            return next_at
    return None


def first_client_review_at(candidate):
    for stage, at in _sorted_hr_history(candidate):
        if stage == CLIENT_ZONE_ENTRY_STAGE:
            return at
    return None


def first_client_approved_at(candidate):
    times = []
    for entry in candidate.get("client_status_history") or []:
        if entry.get("status") in ("ready", "offer"):
            at = _parse_dt(entry.get("at"))
            if at:
                times.append(at)
    for entry in candidate.get("hr_stage_history") or []:
        note = entry.get("note") or ""
        if "статус «Встреча»" in note or "статус «Оффер»" in note:
            at = _parse_dt(entry.get("at"))
            if at:
                times.append(at)
    return min(times) if times else None


def first_invite_info(candidate):
    """Первое приглашение: (дата, offer|internship|direct_start)."""
    saw_offer_or_intern = False
    for stage, at in _sorted_hr_history(candidate):
        if stage == OFFER_STAGE:
            return at, "offer"
        if stage == INTERNSHIP_STAGE:
            return at, "internship"
        if stage == STARTED_WORK_STAGE and not saw_offer_or_intern:
            return at, "direct_start"
        if stage in (OFFER_STAGE, INTERNSHIP_STAGE):
            saw_offer_or_intern = True
    return None, None


def first_invite_at(candidate):
    at, _kind = first_invite_info(candidate)
    return at


def _vacancy_closed_success(vacancy) -> bool:
    reason = vacancy.get("close_reason")
    if reason == CLOSE_REASON_SUCCESS:
        return True
    if reason in (None, "") and not vacancy.get("active", True):
        return vacancy_has_successful_hire(vacancy)
    return False


def _vacancy_overlaps_period(vacancy, period_start: date, period_end: date, *, today=None) -> bool:
    vac_start, vac_end = vacancy_period_bounds(vacancy, today=today)
    if not vac_start or not vac_end:
        return False
    return vac_start <= period_end and vac_end >= period_start


def compute_period_metrics(
    vacancies,
    period_start: date,
    period_end: date,
    *,
    today=None,
) -> PeriodMetrics:
    today = today or date.today()
    result = PeriodMetrics(period_start=period_start, period_end=period_end)
    entries = collect_all_entries(vacancies)
    seen_vacancies_in_work = []

    for candidate, _vacancy in entries:
        created = _parse_dt(candidate.get("created_at"))
        if _date_in_period(created, period_start, period_end):
            result.selected_candidates += 1

        interview_at = first_primary_interview_at(candidate)
        if _date_in_period(interview_at, period_start, period_end):
            result.primary_interviews += 1

        review_at = first_client_review_at(candidate)
        if _date_in_period(review_at, period_start, period_end):
            result.client_review += 1

        approved_at = first_client_approved_at(candidate)
        if _date_in_period(approved_at, period_start, period_end):
            result.client_approved += 1

        invite_at, invite_kind = first_invite_info(candidate)
        if _date_in_period(invite_at, period_start, period_end):
            result.invited_work += 1
            result.invited_work_details.append({
                "candidate_name": _candidate_name(candidate),
                "vacancy_label": _vacancy_detail_label(_vacancy),
                "invite_kind": INVITE_KIND_LABELS.get(invite_kind, invite_kind or "—"),
                "event_date": invite_at.date().isoformat() if invite_at else "",
            })

    for vacancy in vacancies:
        created_vac = parse_vacancy_date(vacancy.get("created_at"))
        if created_vac and period_start <= created_vac <= period_end:
            result.vacancies_started += 1
            result.vacancies_started_details.append({
                "vacancy_label": _started_vacancy_display_label(vacancy),
                "created_at": created_vac.isoformat(),
                "is_active": bool(vacancy.get("active", True)),
            })

        closed = _parse_dt(vacancy.get("closed_at"))
        if _date_in_period(closed, period_start, period_end):
            if vacancy.get("close_reason") == CLOSE_REASON_CLIENT:
                result.vacancies_closed_client += 1
            elif _vacancy_closed_success(vacancy):
                result.vacancies_closed_success += 1
                closure_kind = None
                if created_vac and created_vac < period_start:
                    result.vacancies_closed_success_started_before += 1
                    closure_kind = "before_period"
                elif created_vac and period_start <= created_vac <= period_end:
                    result.vacancies_closed_success_started_in_period += 1
                    closure_kind = "in_period"
                hires = _hire_candidates_for_vacancy(vacancy)
                result.vacancies_closed_success_details.append({
                    "vacancy_label": _vacancy_detail_label(vacancy),
                    "closure_kind": CLOSURE_KIND_LABELS.get(closure_kind, "—"),
                    "closed_at": closed.date().isoformat() if closed else "",
                    "candidates": hires,
                })
            else:
                result.vacancies_closed_not_success_details.append({
                    "vacancy_label": _vacancy_detail_label(vacancy),
                    "closed_at": closed.date().isoformat() if closed else "",
                    "close_reason": vacancy.get("close_reason"),
                    "candidates": [
                        {
                            "name": _candidate_name(c),
                            "hr_stage": _candidate_stage_label(c),
                        }
                        for c in vacancy.get("candidates", [])
                    ],
                    "hint": (
                        "Вакансия закрыта в периоде, но ни у кого нет этапа "
                        "«Вышел на работу» или «Выход на стажировку»."
                    ),
                })

        if _vacancy_overlaps_period(vacancy, period_start, period_end, today=today):
            title = vacancy.get("title", "—")
            period_label = format_vacancy_search_period(vacancy, precise=True)
            seen_vacancies_in_work.append(f"{title} ({period_label})" if period_label else title)

    result.vacancy_titles_in_work = sorted(seen_vacancies_in_work)
    result.vacancies_in_work = len(seen_vacancies_in_work)
    return result


def compute_baseline_monthly_averages(
    vacancies,
    before: date,
    *,
    max_months: int = 12,
    today=None,
) -> tuple[int, dict[str, float]]:
    """Средние помесячные показатели за завершённые календарные месяцы до `before`."""
    today = today or date.today()
    earliest = detect_earliest_activity_date(vacancies, today=today)
    if not earliest:
        return 0, {}

    end_month = before.replace(day=1)
    if end_month <= earliest.replace(day=1):
        return 0, {}

    months = list(iter_calendar_months(earliest.replace(day=1), end_month))
    if not months:
        return 0, {}

    months = months[-max_months:]
    snapshots = [compute_period_metrics(vacancies, ms, me, today=today) for ms, me in months]
    if not snapshots:
        return 0, {}

    averages = {}
    for key in METRIC_KEYS:
        averages[key] = mean(getattr(s, key) for s in snapshots)
    return len(months), averages


def build_comparison_row(current: PeriodMetrics, previous: PeriodMetrics, averages: dict[str, float]):
    rows = []
    for key in METRIC_KEYS:
        cur = getattr(current, key)
        prev = getattr(previous, key)
        avg = averages.get(key)
        delta_prev = cur - prev if prev is not None else None
        delta_avg = (cur - avg) if avg is not None else None
        rows.append({
            "key": key,
            "label": METRIC_LABELS[key],
            "current": cur,
            "previous": prev,
            "average": avg,
            "delta_prev": delta_prev,
            "delta_avg": delta_avg,
        })
    return rows


def collect_period_context_extras(vacancies, period_start: date, period_end: date, *, today=None):
    """Доп. факторы для ИИ-анализа за период."""
    today = today or date.today()
    entries = collect_all_entries(vacancies)
    rejections = {"rejected_hr": 0, "rejected_client": 0, "rejected_candidate": 0}
    no_contact = 0
    with_ai_score = []
    days_in_work = []

    from funnel_metrics import had_primary_contact_communication, no_contact_lost_funnel

    for candidate, vacancy in entries:
        created = _parse_dt(candidate.get("created_at"))
        if not _date_in_period(created, period_start, period_end):
            continue
        stage = candidate.get("hr_stage", "")
        if stage in rejections:
            rejections[stage] += 1
        if no_contact_lost_funnel(candidate, vacancy):
            no_contact += 1
        if not had_primary_contact_communication(candidate):
            pass
        score = candidate.get("ai_score")
        if score is not None:
            with_ai_score.append(score)

    for vacancy in vacancies:
        if _vacancy_overlaps_period(vacancy, period_start, period_end, today=today):
            vac_start, vac_end = vacancy_period_bounds(vacancy, today=today)
            if vac_start and vac_end:
                overlap_start = max(vac_start, period_start)
                overlap_end = min(vac_end, period_end)
                days_in_work.append((overlap_end - overlap_start).days + 1)

    return {
        "rejections_in_period_added": rejections,
        "no_contact_among_added": no_contact,
        "ai_scores_added": with_ai_score,
        "avg_ai_score_added": mean(with_ai_score) if with_ai_score else None,
        "avg_vacancy_overlap_days": mean(days_in_work) if days_in_work else None,
    }


def vacancy_overlaps_period(vacancy, period_start: date, period_end: date, *, today=None) -> bool:
    return _vacancy_overlaps_period(vacancy, period_start, period_end, today=today)


def activity_in_period(dt, period_start: date, period_end: date) -> bool:
    return _date_in_period(dt, period_start, period_end)


def parse_activity_datetime(iso_str):
    return _parse_dt(iso_str)
