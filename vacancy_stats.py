"""Подзона «Итоги» — статистика по вакансии."""

import streamlit as st
from datetime import datetime

from models import HR_STAGES, stage_counts, CLIENT_STATUS_LABELS, HR_STAGE_ORDER


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


def render_vacancy_stats(vacancy):
    st.subheader("📊 Статистика")
    candidates = vacancy.get("candidates", [])
    if not candidates:
        st.info("Нет кандидатов для статистики.")
        return

    counts = stage_counts(candidates)
    st.markdown("**Воронка HR (кандидаты по этапам)**")
    cols = st.columns(min(len(HR_STAGES), 5))
    for i, (code, label) in enumerate(HR_STAGES.items()):
        with cols[i % 5]:
            st.metric(label[:18], counts.get(code, 0))

    total = len(candidates)
    conv_pairs = [
        ("resume_screening", "interview_done"),
        ("interview_done", "client_review"),
        ("client_review", "offer"),
    ]
    st.markdown("**Конверсия между этапами**")
    for from_s, to_s in conv_pairs:
        reached_to = sum(1 for c in candidates if _reached_stage(c, to_s))
        pct = (reached_to / total * 100) if total else 0
        st.write(f"- {HR_STAGES[from_s]} → {HR_STAGES[to_s]}: {reached_to}/{total} ({pct:.0f}%)")

    scored = [c for c in candidates if c.get("ai_score") is not None]
    if scored:
        avg = sum(c["ai_score"] for c in scored) / len(scored)
        st.metric("Средняя оценка ИИ", f"{avg:.1f} / 4")

    client_counts = {}
    for c in candidates:
        s = c.get("client_status", "wait")
        client_counts[s] = client_counts.get(s, 0) + 1
    st.markdown("**Статусы заказчика**")
    for key, cnt in client_counts.items():
        st.write(f"- {CLIENT_STATUS_LABELS.get(key, key)}: {cnt}")

    st.markdown("**Итог по вакансии**")
    summary = vacancy.get("vacancy_summary", "")
    new_summary = st.text_area("Общий итог HR", value=summary, height=120, key=f"vac_summary_{vacancy['id']}")
    if st.button("💾 Сохранить итог", key=f"save_summary_{vacancy['id']}"):
        vacancy["vacancy_summary"] = new_summary
        return True
    return False
