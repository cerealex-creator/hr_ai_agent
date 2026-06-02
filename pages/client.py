import streamlit as st
import json
import os

# 1. Сначала конфигурация страницы
st.set_page_config(page_title="Клиентская зона", page_icon="👥")

# 2. Получаем название отдела из URL
dept_name = st.query_params.get("dept", "")
if not dept_name:
    st.error("Не указано подразделение")
    st.stop()

st.title(f"👥 {dept_name} — кандидаты")

# Загружаем подразделения, чтобы найти client_id
try:
    with open('data/departments.json', 'r', encoding='utf-8') as f:
        depts_data = json.load(f)
        departments = depts_data.get("departments", [])
        dept = next((d for d in departments if d["name"] == dept_name), None)
        if not dept:
            st.error(f"Подразделение '{dept_name}' не найдено")
            st.stop()
        client_id = dept["id"]
except FileNotFoundError:
    st.error("Данные не найдены")
    st.stop()

# Загружаем вакансии
try:
    with open('data/vacancies_db.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    st.error("Данные не найдены")
    st.stop()

# Находим вакансии для этого отдела
vacancy_ids = []
for vacancy in data.get("vacancies", []):
    if vacancy.get("client_id") == client_id:
        vacancy_ids.append(vacancy["id"])

# Собираем кандидатов
candidates = []
for vacancy in data.get("vacancies", []):
    if vacancy["id"] in vacancy_ids:
        for candidate in vacancy.get("candidates", []):
            candidates.append({
                "ФИО": candidate.get("name", ""),
                "Резюме": candidate.get("resume_link", ""),
                "Видео": candidate.get("video_link", ""),
                "Статус": candidate.get("client_status", "wait"),
                "Комментарий клиента": candidate.get("client_comment", ""),
                "Дата собеседования": candidate.get("office_interview_date", "")
            })

if candidates:
    st.dataframe(candidates, use_container_width=True)
else:
    st.info(f"Нет кандидатов для отдела {dept_name}")