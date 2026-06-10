"""Сводная статистика для мастер-зоны руководителя."""

from datetime import datetime, timedelta

import streamlit as st

from models import (
    HR_STAGES,
    HR_STAGE_ORDER,
    CLIENT_STATUS_LABELS,
    CLIENT_REVIEW_STATUSES,
    is_visible_in_client_zone,
)
from client_zone import get_status_meta, STATUS_ORDER


def _reached_stage(candidate, target_stage):
    if candidate.get("hr_stage") == target_stage:
        return True
    if target_stage not in HR_STAGE_ORDER:
        return False
    target_idx = HR_STAGE_ORDER.index(target_stage)
    current = candidate.get("hr_stage", "resume_screening")
    if current in HR_STAGE_ORDER and HR_STAGE_ORDER.index(current) >= target_idx:
        return True
    for h in candidate.get("hr_stage_history", []):
        if h.get("stage") == target_stage:
            return True
    return False


def collect_all_candidates(vacancies):
    candidates = []
    for vacancy in vacancies:
        for cand in vacancy.get("candidates", []):
            candidates.append(cand)
    return candidates


def aggregate_client_status(candidates):
    counts = {}
    for cand in candidates:
        key = cand.get("client_status", "wait")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _parse_dt(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(str(iso_str).replace("Z", ""))
    except (ValueError, TypeError):
        return None


def _client_zone_candidates(candidates):
    return [c for c in candidates if is_visible_in_client_zone(c)]


def _has_interview_scheduled(cand):
    if not (cand.get("office_interview_date") or "").strip():
        return False
    return bool(cand.get("remote_interview") or cand.get("office_interview"))


def _interview_datetime(cand):
    date_str = (cand.get("office_interview_date") or "").strip()
    if not date_str:
        return None
    time_str = (cand.get("office_interview_time") or "").strip() or "12:00"
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return _parse_dt(date_str)


def _status_unchanged_for(cand, delta):
    updated = _parse_dt(cand.get("status_updated_at"))
    if not updated:
        return False
    return datetime.now() - updated >= delta


def _interview_passed_for(cand, delta):
    interview_at = _interview_datetime(cand)
    if not interview_at:
        return False
    return datetime.now() - interview_at >= delta


def _compute_visible_metrics(visible):
    """Метрики по кандидатам, видимым в клиентской зоне."""
    day = timedelta(days=1)
    three_days = timedelta(days=3)
    wait_status = lambda c: c.get("client_status", "wait") == "wait"

    return {
        "under_review": sum(
            1 for c in visible if c.get("client_status", "wait") in CLIENT_REVIEW_STATUSES
        ),
        "waiting_client_action": sum(1 for c in visible if wait_status(c)),
        "wait_over_24h": sum(
            1 for c in visible if wait_status(c) and _status_unchanged_for(c, day)
        ),
        "pending_interview_decision": sum(
            1 for c in visible if _has_interview_scheduled(c)
        ),
        "pending_interview_over_24h": sum(
            1 for c in visible if _has_interview_scheduled(c) and _interview_passed_for(c, day)
        ),
        "pending_over_3_days": sum(
            1
            for c in visible
            if (wait_status(c) and _status_unchanged_for(c, three_days))
            or (_has_interview_scheduled(c) and _interview_passed_for(c, three_days))
        ),
        "offer": sum(1 for c in visible if c.get("client_status") == "offer"),
        "started": sum(1 for c in visible if c.get("client_status") == "started"),
    }


VACANCY_METRIC_LABELS = (
    ("under_review", "на рассмотрении"),
    ("waiting_client_action", "ждут оценки / действий заказчика"),
    ("wait_over_24h", "ждут оценки заказчика > суток"),
    ("pending_interview_decision", "ждут решения по итогам собеседования"),
    ("pending_interview_over_24h", "ждут решения по собеседованию > суток"),
    ("pending_over_3_days", "ждут решений > 3 дней"),
    ("offer", "Сделан оффер"),
    ("started", "Выход на работу"),
)


def _format_vacancy_metrics_line(metrics):
    parts = [
        f"{label} {metrics[key]}"
        for key, label in VACANCY_METRIC_LABELS
        if metrics.get(key, 0) > 0
    ]
    return ", ".join(parts) if parts else "Нет кандидатов в работе"


def compute_master_metrics(vacancies):
    """Ключевые цифры для блока «Статистика по организации»."""
    visible = _client_zone_candidates(collect_all_candidates(vacancies))
    metrics = _compute_visible_metrics(visible)
    metrics["active_vacancies"] = len(vacancies)
    return metrics


def render_master_dashboard(vacancies, dept_names):
    """Сводная статистика по всем активным вакансиям (без тестового подразделения)."""
    st.subheader("📊 Статистика по организации")
    all_candidates = collect_all_candidates(vacancies)
    total_vac = len(vacancies)

    if total_vac == 0:
        st.info("Нет активных вакансий в работе.")
        return

    metrics = compute_master_metrics(vacancies)
    row1 = st.columns(4)
    row1[0].metric("Активных вакансий", metrics["active_vacancies"])
    row1[1].metric("На рассмотрении", metrics["under_review"])
    row1[2].metric("Ждут оценки / действий заказчика", metrics["waiting_client_action"])
    row1[3].metric("Ждут оценки заказчика > суток", metrics["wait_over_24h"])

    row2 = st.columns(3)
    row2[0].metric("Ждут решения по итогам собеседования", metrics["pending_interview_decision"])
    row2[1].metric("Ждут решения по собеседованию > суток", metrics["pending_interview_over_24h"])
    row2[2].metric("Ждут решений > 3 дней", metrics["pending_over_3_days"])

    total_cand = len(all_candidates)
    if total_cand:
        st.markdown("**Конверсия (все вакансии)**")
        conv_pairs = [
            ("resume_screening", "interview_done"),
            ("interview_done", "client_review"),
            ("client_review", "offer"),
        ]
        for from_s, to_s in conv_pairs:
            reached_to = sum(1 for c in all_candidates if _reached_stage(c, to_s))
            pct = reached_to / total_cand * 100
            st.write(f"- {HR_STAGES[from_s]} → {HR_STAGES[to_s]}: {reached_to}/{total_cand} ({pct:.0f}%)")

    client_zone_candidates = _client_zone_candidates(all_candidates)
    client_counts = aggregate_client_status(client_zone_candidates)
    if client_counts:
        st.markdown("**Статусы заказчика (все кандидаты)**")
        parts = [
            f"{get_status_meta(k)['icon']} {get_status_meta(k)['label']}: {v}"
            for k, v in sorted(client_counts.items(), key=lambda x: STATUS_ORDER.get(x[0], 99))
        ]
        st.caption(" · ".join(parts))
        for key, cnt in sorted(client_counts.items(), key=lambda x: STATUS_ORDER.get(x[0], 99)):
            st.write(f"- {CLIENT_STATUS_LABELS.get(key, key)}: {cnt}")

    st.markdown("**По подразделениям**")
    by_dept = {}
    for vacancy in vacancies:
        dept = dept_names.get(vacancy.get("client_id"), "—")
        by_dept.setdefault(dept, {"vacancies": 0, "candidates": 0, "offers": 0})
        by_dept[dept]["vacancies"] += 1
        cands = vacancy.get("candidates", [])
        by_dept[dept]["candidates"] += len(cands)
        by_dept[dept]["offers"] += sum(1 for c in cands if c.get("hr_stage") == "offer")

    for dept in sorted(by_dept):
        info = by_dept[dept]
        st.write(
            f"- **{dept}**: вакансий {info['vacancies']}, "
            f"кандидатов {info['candidates']}, офферов {info['offers']}"
        )

    st.markdown("**По вакансиям**")
    for vacancy in sorted(
        vacancies,
        key=lambda v: (dept_names.get(v.get("client_id"), ""), v.get("title", "")),
    ):
        dept = dept_names.get(vacancy.get("client_id"), "—")
        visible = _client_zone_candidates(vacancy.get("candidates", []))
        m = _compute_visible_metrics(visible)
        summary = (vacancy.get("vacancy_summary") or "").strip()
        line = f"- **{dept} — {vacancy['title']}**: {_format_vacancy_metrics_line(m)}"
        if summary:
            line += f" · _{summary[:120]}{'…' if len(summary) > 120 else ''}_"
        st.write(line)
