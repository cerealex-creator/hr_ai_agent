"""Общие компоненты отображения оценки кандидата ИИ."""

import streamlit as st

from resume_ai import AI_COMMENT_SECTION_ORDER


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


def _render_section_value(val):
    if val is None or val == "":
        return
    if isinstance(val, list):
        for item in val:
            if str(item).strip():
                st.markdown(f"- {item}")
    else:
        st.markdown(str(val))


def render_structured_ai_comment(cand, *, expanded=False):
    """Свёрнутый по умолчанию разбор ИИ в структуре профиля."""
    sections = cand.get("ai_comment_sections")
    legacy = (cand.get("ai_comment") or "").strip()
    has_sections = isinstance(sections, dict) and any(
        v is not None and v != "" for v in sections.values()
    )
    if not has_sections and not legacy:
        return

    with st.expander("Анализ ИИ (структура)", expanded=expanded):
        if has_sections:
            used = set()
            for key, title in AI_COMMENT_SECTION_ORDER:
                if key not in sections:
                    continue
                used.add(key)
                val = sections.get(key)
                if val is None or val == "":
                    continue
                st.markdown(f"**{title}**")
                _render_section_value(val)
                st.markdown("")
            for key, val in sections.items():
                if key in used or val is None or val == "":
                    continue
                st.markdown(f"**{key}**")
                _render_section_value(val)
                st.markdown("")
        else:
            st.markdown(legacy)


def control_word_badge_html(cand):
    status = (cand.get("control_word_status") or "").strip()
    if not status:
        return ""
    styles = {
        "exact": ("#14532d", "#dcfce7", "Контрольное слово"),
        "fuzzy": ("#854d0e", "#fef9c3", "Контрольное слово ≈"),
        "missing": ("#991b1b", "#fee2e2", "Нет контр. слова"),
        "no_cover_letter": ("#991b1b", "#fee2e2", "Нет письма"),
    }
    if status not in styles:
        return ""
    color, bg, label = styles[status]
    note = (cand.get("control_word_note") or "").replace('"', "&quot;")
    return (
        f'<span title="{note}" style="background:{bg};color:{color};'
        f'padding:0.15rem 0.5rem;border-radius:999px;font-size:0.78rem;'
        f'font-weight:600;margin-left:0.35rem;">{label}</span>'
    )


def render_ai_evaluation_block(cand):
    """Read-only блок оценки ИИ. Не рендерится, если оценки нет."""
    if not has_ai_evaluation(cand):
        return

    with st.expander("🤖 Оценка ИИ", expanded=False):
        st.markdown(render_ai_score_badge(cand["ai_score"]), unsafe_allow_html=True)

        sections = cand.get("ai_comment_sections")
        has_sections = isinstance(sections, dict) and any(
            v is not None and v != "" for v in sections.values()
        )
        if has_sections or (cand.get("ai_comment") or "").strip():
            st.markdown("**Анализ (ИИ):**")
            if has_sections:
                used = set()
                for key, title in AI_COMMENT_SECTION_ORDER:
                    if key not in sections:
                        continue
                    used.add(key)
                    val = sections.get(key)
                    if val is None or val == "":
                        continue
                    st.markdown(f"**{title}**")
                    _render_section_value(val)
                for key, val in sections.items():
                    if key in used or val is None or val == "":
                        continue
                    st.markdown(f"**{key}**")
                    _render_section_value(val)
            else:
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
