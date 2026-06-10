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
    render_candidates_section,
)

st.set_page_config(page_title="Клиентская зона", page_icon="👥", layout="wide")
apply_corporate_ui()
apply_client_styles()

dept_name = st.query_params.get("dept", "")
if not dept_name:
    st.error("Не указано подразделение")
    st.stop()

st.title(f"👥 {dept_name} — управление кандидатами")

try:
    departments = load_departments()
    dept = next((d for d in departments if d["name"] == dept_name), None)
    if not dept:
        st.error(f"Подразделение '{dept_name}' не найдено")
        st.stop()
    client_id = dept["id"]
except FileNotFoundError:
    st.error("Данные о подразделениях не найдены")
    st.stop()

data = migrate_vacancies_data(load_vacancies())
vacancies = data.get("vacancies", [])

client_vacancies = [v for v in vacancies if v.get("client_id") == client_id and v.get("active", True)]

if not client_vacancies:
    st.info("Нет активных вакансий для вашего отдела.")
    st.stop()

vacancy_titles = [v["title"] for v in client_vacancies]
selected_title = selectbox_no_default("Выберите вакансию", vacancy_titles, key="client_vac_picker")
if not selected_title:
    st.info("Выберите вакансию из списка.")
    st.stop()
selected_vacancy = next(v for v in client_vacancies if v["title"] == selected_title)

st.divider()
st.subheader(f"Кандидаты по вакансии: {selected_title}")

render_candidates_section(data, selected_vacancy, key_prefix="client")
