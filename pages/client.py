import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corporate_ui import apply_corporate_ui
from ui_helpers import selectbox_no_default
from client_access import ensure_department_tokens, extract_access_token, get_department_by_client_token
from client_zone import (
    apply_client_styles,
    load_vacancies,
    migrate_vacancies_data,
    render_candidates_section,
    render_vacancy_profile_block,
)

st.set_page_config(page_title="Клиентская зона", page_icon="👥", layout="wide")
apply_corporate_ui()
apply_client_styles()

if st.query_params.get("dept"):
    st.error("Ссылка устарела. Запросите актуальную ссылку у HR.")
    st.stop()

access_token = extract_access_token(st.query_params)
dept = get_department_by_client_token(access_token)
if not dept:
    st.error("Ссылка недействительна или устарела.")
    st.caption("Обратитесь к HR за новой ссылкой для вашего отдела.")
    st.stop()

dept_name = dept["name"]
client_id = dept["id"]
vacancy_id_param = (st.query_params.get("vacancy_id") or "").strip()
candidate_id_param = (st.query_params.get("candidate_id") or "").strip()

st.title(f"👥 {dept_name} — управление кандидатами")

ensure_department_tokens()
data = migrate_vacancies_data(load_vacancies())
vacancies = data.get("vacancies", [])

client_vacancies = [v for v in vacancies if v.get("client_id") == client_id and v.get("active", True)]

if not client_vacancies:
    st.info("Нет активных вакансий для вашего отдела.")
    st.stop()

selected_vacancy = None
if vacancy_id_param:
    selected_vacancy = next(
        (v for v in client_vacancies if str(v.get("id")) == vacancy_id_param),
        None,
    )
    if not selected_vacancy:
        st.warning("Вакансия из ссылки не найдена или закрыта. Выберите вакансию ниже.")
        candidate_id_param = ""

if selected_vacancy:
    st.caption(f"Вакансия: **{selected_vacancy['title']}**")
    if len(client_vacancies) > 1:
        other_titles = [v["title"] for v in client_vacancies if v["id"] != selected_vacancy["id"]]
        alt = selectbox_no_default("Другая вакансия", other_titles, key="client_vac_alt")
        if alt:
            selected_vacancy = next(v for v in client_vacancies if v["title"] == alt)
            candidate_id_param = ""
else:
    vacancy_titles = [v["title"] for v in client_vacancies]
    selected_title = selectbox_no_default("Выберите вакансию", vacancy_titles, key="client_vac_picker")
    if not selected_title:
        st.info("Выберите вакансию из списка.")
        st.stop()
    selected_vacancy = next(v for v in client_vacancies if v["title"] == selected_title)

st.divider()
render_vacancy_profile_block(selected_vacancy)
st.subheader(f"Кандидаты: {selected_vacancy['title']}")

render_candidates_section(
    data,
    selected_vacancy,
    key_prefix="client",
    focus_candidate_id=candidate_id_param or None,
)
