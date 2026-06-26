"""UI поиска кандидатов."""

import streamlit as st

from candidate_search import format_hit_summary, resume_snippet, search_candidates
from vacancy_display import format_vacancy_search_period


def render_candidate_search_tab(deps):
    st.subheader("🔍 Поиск кандидатов")
    st.caption(
        "Поиск по ФИО, телефону и тексту резюме. "
        "Смотрит активные и архивные вакансии; тестовые — по галочке ниже."
    )

    query = st.text_input(
        "Запрос",
        placeholder="Фамилия, ФИО, телефон или фрагмент из резюме",
        key="candidate_search_query",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        include_archived = st.checkbox(
            "Искать в архивных вакансиях",
            value=True,
            key="candidate_search_include_archived",
        )
    with col_b:
        include_test = st.checkbox(
            "Искать в тестовых вакансиях",
            value=True,
            key="candidate_search_include_test",
            help="Кандидаты на вакансиях с пометкой «Тестовая» (например «Трутень»).",
        )

    if len((query or "").strip()) < 2:
        st.info("Введите минимум 2 символа для поиска.")
        return

    all_vacancies = deps["load_vacancies"]()
    pool = all_vacancies if include_archived else [v for v in all_vacancies if v.get("active", True)]
    hits = search_candidates(pool, query, include_test=include_test)

    if not hits and not include_test:
        test_hits = search_candidates(pool, query, include_test=True)
        if test_hits:
            st.warning(
                f"На **тестовых** вакансиях найдено: {len(test_hits)} "
                f"(например «{test_hits[0].candidate.get('name')}» — «{test_hits[0].vacancy.get('title')}»). "
                "Включите «Искать в тестовых вакансиях»."
            )
            return

    if not hits:
        st.warning("Никого не найдено. Попробуйте фамилию, часть ФИО или слово из резюме.")
        return

    st.markdown(f"**Найдено:** {len(hits)}")
    for i, hit in enumerate(hits):
        period = format_vacancy_search_period(hit.vacancy, precise=True)
        vac_line = hit.vacancy.get("title", "—")
        if period and period != "период не указан":
            vac_line += f" ({period})"
        label = format_hit_summary(hit)
        with st.expander(label, expanded=i == 0 and len(hits) == 1):
            st.write(f"**Вакансия:** {vac_line}")
            if hit.vacancy.get("is_test"):
                st.caption("🧪 Тестовая вакансия — в статистике продуктивности не учитывается.")
            st.write(f"**Этап:** {hit.candidate.get('hr_stage', '—')}")
            st.caption(f"Совпадение: {hit.match_in}")
            phone = (hit.candidate.get("phone") or "").strip()
            if phone:
                st.write(f"**Телефон:** {phone}")
            snippet = resume_snippet(hit.candidate, query)
            if snippet:
                st.markdown("**Фрагмент резюме:**")
                st.text(snippet)
            links = []
            if (hit.candidate.get("resume_link") or "").strip():
                links.append("PDF резюме")
            if (hit.candidate.get("hh_resume_link") or "").strip():
                links.append("HH")
            if links:
                st.caption("Ссылки: " + ", ".join(links))

            from candidate_copy import render_copy_candidate_ui

            st.markdown("**Скопировать в активную вакансию**")
            render_copy_candidate_ui(
                hit.candidate,
                hit.vacancy,
                deps,
                key_prefix=f"srch_{hit.vacancy_id}_{hit.candidate_id}_{i}",
            )
