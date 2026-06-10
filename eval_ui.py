"""Общие компоненты отображения оценки кандидата ИИ."""

import streamlit as st


def has_ai_evaluation(cand):
    return cand.get("ai_score") is not None


def render_ai_score_badge(score):
    if score is None:
        return ""
    score = int(score)
    if score > 4:
        return (
            f'<span style="background:#f1f5f9;color:#64748b;padding:0.2rem 0.55rem;'
            f'border-radius:999px;font-size:0.85rem;">⚠️ {score}/10 (устарело)</span>'
        )
    styles = {
        4: ("ai-score-4", "👑", "#14532d", "#dcfce7"),
        3: ("ai-score-3", "🟢", "#15803d", "#dcfce7"),
        2: ("ai-score-2", "🟡", "#a16207", "#fef9c3"),
        1: ("ai-score-1", "🟠", "#c2410c", "#ffedd5"),
        0: ("ai-score-0", "🔴", "#b91c1c", "#fee2e2"),
    }
    css_class, icon, color, bg = styles.get(score, ("ai-score-0", "🔴", "#b91c1c", "#fee2e2"))
    return (
        f'<span class="ai-score-badge {css_class}" '
        f'style="background:{bg};color:{color};padding:0.2rem 0.55rem;'
        f'border-radius:999px;font-weight:700;font-size:0.85rem;">'
        f'{icon} {score}/4</span>'
    )


def render_ai_evaluation_block(cand):
    """Read-only блок оценки ИИ. Не рендерится, если оценки нет."""
    if not has_ai_evaluation(cand):
        return

    with st.expander("🤖 Оценка ИИ", expanded=False):
        st.markdown(render_ai_score_badge(cand["ai_score"]), unsafe_allow_html=True)

        if cand.get("ai_comment"):
            st.markdown("**Анализ (ИИ):**")
            st.info(cand["ai_comment"])

        met = cand.get("ai_profile_requirements_met") or {}
        if met:
            c1, c2, c3 = st.columns(3)
            c1.metric("Hard skills", f"{met.get('hard_skills', '—')}%")
            c2.metric("Soft skills", f"{met.get('soft_skills', '—')}%")
            c3.metric("Опыт", f"{met.get('experience', '—')}%")

        flags = cand.get("ai_flags_applied") or []
        if flags:
            st.caption(f"Учтены исключения: {', '.join(flags)}")

        if cand.get("ai_strengths"):
            st.markdown("**Сильные стороны**")
            for item in cand["ai_strengths"]:
                st.markdown(f"- {item}")

        if cand.get("ai_weaknesses"):
            st.markdown("**Слабые стороны**")
            for item in cand["ai_weaknesses"]:
                st.markdown(f"- {item}")
