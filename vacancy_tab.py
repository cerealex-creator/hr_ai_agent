"""Вкладка «Вакансии» — vacancy-centric shell."""

import streamlit as st

import telegram_client

from vacancy_prep import render_existing_documents_zone, render_new_vacancy_form
from candidate_funnel import render_candidates_zone
from vacancy_stats import render_vacancy_stats


def render_vacancy_picker(active):
    """Интерактивный список вакансий кнопками."""
    if "opened_vacancy_id" not in st.session_state:
        st.session_state.opened_vacancy_id = None

    cols_per_row = 3
    for row_start in range(0, len(active), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, vacancy in enumerate(active[row_start:row_start + cols_per_row]):
            with cols[col_idx]:
                cand_count = len(vacancy.get("candidates", []))
                is_open = st.session_state.opened_vacancy_id == vacancy["id"]
                label = f"{vacancy['title']}\nКандидаты: {cand_count}"
                btn_type = "primary" if is_open else "secondary"
                if st.button(label, key=f"vac_pick_{vacancy['id']}", type=btn_type, use_container_width=True):
                    if is_open:
                        st.session_state.opened_vacancy_id = None
                    else:
                        st.session_state.opened_vacancy_id = vacancy["id"]
                    st.rerun()


def render_active_vacancy_workspace(vacancy, deps):
    cand_count = len(vacancy.get("candidates", []))
    st.markdown(
        f'<p class="vacancy-candidates-count">Кандидаты: <strong>{cand_count}</strong></p>',
        unsafe_allow_html=True,
    )

    sub_cands, sub_docs, sub_stats = st.tabs([
        "👥 Кандидаты",
        "📄 Документы по вакансии",
        "📊 Статистика",
    ])

    with sub_cands:
        render_candidates_zone(vacancy, deps)

    with sub_docs:
        render_existing_documents_zone(vacancy, deps)

    with sub_stats:
        if render_vacancy_stats(vacancy):
            all_v = deps["load_vacancies"]()
            for v in all_v:
                if v["id"] == vacancy["id"]:
                    v["vacancy_summary"] = vacancy.get("vacancy_summary", "")
            deps["save_vacancies"](all_v)
            st.success("Итог сохранён!")
            st.rerun()

    with st.expander("🔒 Закрыть вакансию"):
        if st.button("Переместить в архив", key=f"close_{vacancy['id']}"):
            vacancy["active"] = False
            from datetime import datetime
            vacancy["closed_at"] = datetime.now().isoformat()
            all_v = deps["load_vacancies"]()
            for v in all_v:
                if v["id"] == vacancy["id"]:
                    v.update(vacancy)
            deps["save_vacancies"](all_v)
            if st.session_state.get("opened_vacancy_id") == vacancy["id"]:
                st.session_state.opened_vacancy_id = None
            st.success("Вакансия закрыта.")
            st.rerun()


def render_vacancies_in_work(deps):
    vacancies = deps["load_vacancies"]()
    active = [v for v in vacancies if v.get("active", True)]

    if not active:
        st.info("Нет вакансий в работе. Создайте новую во вкладке «Создание новой вакансии».")
        return

    st.markdown("Выберите вакансию, чтобы открыть документы, кандидатов и статистику.")
    render_vacancy_picker(active)

    opened_id = st.session_state.get("opened_vacancy_id")
    if not opened_id:
        st.caption("Вакансия не выбрана — нажмите на кнопку выше.")
        return

    vacancy = next((v for v in active if v["id"] == opened_id), None)
    if not vacancy:
        st.session_state.opened_vacancy_id = None
        st.warning("Вакансия не найдена. Выберите другую.")
        return

    st.divider()
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.subheader(vacancy["title"])
    with head_r:
        st.write("")
        if st.button(
            "📨 Статистика в чат",
            key=f"tg_digest_{vacancy['id']}",
            use_container_width=True,
        ):
            ok, msg = telegram_client.send_vacancy_digest_to_chat(vacancy)
            if ok:
                st.success("Сводка отправлена в Telegram-чат!")
            else:
                st.error(msg)
    render_active_vacancy_workspace(vacancy, deps)


def render_vacancy_tab(deps):
    st.header("🏢 Вакансии")
    st.caption("Вакансии в работе и создание новых — в одном месте.")

    tab_work, tab_create = st.tabs(["📂 Вакансии в работе", "➕ Создание новой вакансии"])

    with tab_work:
        render_vacancies_in_work(deps)

    with tab_create:
        render_new_vacancy_form(deps)
