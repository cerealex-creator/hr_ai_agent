"""Сводная статистика для мастер-зоны руководителя."""

import streamlit as st

from models import (
    HR_STAGES,
    HR_STAGE_ORDER,
    CLIENT_STATUS_LABELS,
    stage_counts,
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


def render_master_dashboard(vacancies, dept_names):
    """Сводная статистика по всем активным вакансиям (без тестового подразделения)."""
    st.subheader("📊 Сводка по организации")
    all_candidates = collect_all_candidates(vacancies)
    total_vac = len(vacancies)
    total_cand = len(all_candidates)

    if total_vac == 0:
        st.info("Нет активных вакансий в работе.")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Активных вакансий", total_vac)
    m2.metric("Всего кандидатов", total_cand)
    offers = sum(1 for c in all_candidates if c.get("hr_stage") == "offer")
    m3.metric("Офферы", offers)
    scored = [c for c in all_candidates if c.get("ai_score") is not None]
    avg_ai = sum(c["ai_score"] for c in scored) / len(scored) if scored else None
    m4.metric("Средняя оценка ИИ", f"{avg_ai:.1f} / 4" if avg_ai is not None else "—")

    st.markdown("**Воронка HR (все кандидаты)**")
    hr_counts = stage_counts(all_candidates)
    cols = st.columns(min(len(HR_STAGES), 5))
    for i, (code, label) in enumerate(HR_STAGES.items()):
        with cols[i % 5]:
            st.metric(label[:20], hr_counts.get(code, 0))

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

    client_zone_candidates = [c for c in all_candidates if is_visible_in_client_zone(c)]
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
        cands = vacancy.get("candidates", [])
        offer_n = sum(1 for c in cands if c.get("hr_stage") == "offer")
        visible = [c for c in cands if is_visible_in_client_zone(c)]
        client_ready = sum(1 for c in visible if c.get("client_status") == "ready")
        cand_n = len(visible)
        summary = (vacancy.get("vacancy_summary") or "").strip()
        line = f"- **{dept} — {vacancy['title']}**: кандидатов {cand_n}, рассматриваем {client_ready}, офферов {offer_n}"
        if summary:
            line += f" · _{summary[:120]}{'…' if len(summary) > 120 else ''}_"
        st.write(line)
