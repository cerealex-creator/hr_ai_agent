import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corporate_ui import apply_corporate_ui
from ui_helpers import selectbox_no_default
from client_zone import (
    apply_client_styles,
    load_departments,
    load_vacancies,
    migrate_vacancies_data,
    get_production_vacancies,
    vacancy_picker_label,
    render_candidates_section,
)
from master_stats import render_master_dashboard

st.set_page_config(page_title="Мастер-зона", page_icon="🏢", layout="wide")
apply_corporate_ui()
apply_client_styles()

st.title("🏢 Мастер-зона — сводка по всем вакансиям")
st.caption(
    "Обзор работы по всем подразделениям. "
    "Для детальной работы с кандидатами выберите вакансию ниже."
)

departments = load_departments()
dept_names = {d["id"]: d["name"] for d in departments}
data = migrate_vacancies_data(load_vacancies())
production_vacancies = get_production_vacancies(data.get("vacancies", []), departments)

if not production_vacancies:
    st.info("Нет активных вакансий в работе.")
    st.stop()

st.subheader("Кандидаты по вакансии")

vacancy_labels = [
    vacancy_picker_label(v, dept_names)
    for v in sorted(
        production_vacancies,
        key=lambda x: (dept_names.get(x.get("client_id"), ""), x.get("title", "")),
    )
]
selected_label = selectbox_no_default(
    "Выберите вакансию",
    vacancy_labels,
    key="master_vac_picker",
)
if selected_label:
    selected_vacancy = next(
        v for v in production_vacancies if vacancy_picker_label(v, dept_names) == selected_label
    )
    dept = dept_names.get(selected_vacancy.get("client_id"), "—")
    st.markdown(f"**{dept}** · {selected_vacancy['title']}")
    render_candidates_section(data, selected_vacancy, key_prefix="master")
else:
    st.info("Выберите вакансию из списка, чтобы работать с кандидатами.")

st.divider()
render_master_dashboard(production_vacancies, dept_names)
