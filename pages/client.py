import streamlit as st
import json
from datetime import datetime, time

st.set_page_config(page_title="Клиентская зона", page_icon="👥", layout="wide")

dept_name = st.query_params.get("dept", "")
if not dept_name:
    st.error("Не указано подразделение")
    st.stop()

st.title(f"👥 {dept_name} — управление кандидатами")

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
    st.error("Данные о подразделениях не найдены")
    st.stop()

def load_vacancies():
    with open('data/vacancies_db.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_vacancies(data):
    with open('data/vacancies_db.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_vacancies()
vacancies = data.get("vacancies", [])

# Фильтруем только активные вакансии для данного отдела
client_vacancies = [v for v in vacancies if v.get("client_id") == client_id and v.get("active", True)]

if not client_vacancies:
    st.info("Нет активных вакансий для вашего отдела.")
    st.stop()

vacancy_titles = [v["title"] for v in client_vacancies]
selected_title = st.selectbox("Выберите вакансию", vacancy_titles)
selected_vacancy = next(v for v in client_vacancies if v["title"] == selected_title)

st.divider()
st.subheader(f"Кандидаты по вакансии: {selected_title}")

candidates = selected_vacancy.get("candidates", [])
if not candidates:
    st.info("Нет кандидатов.")
    st.stop()

def render_button(link, label, empty_text):
    if link and link.strip():
        return f'<a href="{link}" target="_blank"><button style="background-color:#4CAF50; border:none; color:white; padding:6px 16px; text-align:center; text-decoration:none; display:inline-block; font-size:14px; border-radius:4px; margin:2px; cursor:pointer;">{label}</button></a>'
    else:
        return empty_text

status_display = {
    "wait": "ждет оценки",
    "ready": "готовы рассмотреть",
    "reject": "отказ",
    "think": "надо подумать"
}
status_options = list(status_display.values())
status_to_key = {v: k for k, v in status_display.items()}

time_options = [""]
start = time(9, 0)
end = time(18, 0)
current = start
while current <= end:
    time_options.append(current.strftime("%H:%M"))
    minutes = current.hour * 60 + current.minute + 30
    current = time(minutes // 60, minutes % 60)

vacancy_id = selected_vacancy["id"]

for idx, cand in enumerate(candidates):
    with st.container():
        st.markdown("---")
        st.markdown(f"### {idx+1}. {cand.get('name', 'Без имени')}")

        col_buttons = st.columns(3)
        with col_buttons[0]:
            st.markdown(render_button(cand.get("resume_link", ""), "📄 Резюме", "❌ Ссылка отсутствует"), unsafe_allow_html=True)
        with col_buttons[1]:
            st.markdown(render_button(cand.get("video_link", ""), "🎥 Запись собеседования", "❌ Ссылка отсутствует"), unsafe_allow_html=True)
        with col_buttons[2]:
            task_link = cand.get("task_link", "")
            if task_link:
                st.markdown(f"**Задание:** {render_button(task_link, '✅ Сделано', '')}", unsafe_allow_html=True)
            else:
                st.markdown("**Задание:** ⚠️ Нет / Ещё не готово")

        current_status = status_display.get(cand.get("client_status", "wait"), "ждет оценки")
        new_status = st.selectbox("Статус", options=status_options, index=status_options.index(current_status), key=f"status_{vacancy_id}_{idx}")

        new_comment = st.text_area("Комментарий клиента", value=cand.get("client_comment", ""), key=f"comment_{vacancy_id}_{idx}", height=68, placeholder="Ваш комментарий...")

        date_str = cand.get("office_interview_date", "")
        try:
            date_val = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
        except:
            date_val = None
        new_date = st.date_input("Дата собеседования (офис)", value=date_val, key=f"date_{vacancy_id}_{idx}", format="DD.MM.YYYY")

        current_time = cand.get("office_interview_time", "")
        time_index = time_options.index(current_time) if current_time in time_options else 0
        new_time = st.selectbox("Время собеседования", options=time_options, index=time_index, key=f"time_{vacancy_id}_{idx}")

        final_verdict = st.text_area("Итог по кандидату", value=cand.get("client_final_verdict", ""), key=f"verdict_{vacancy_id}_{idx}", height=100)

        if st.button("💾 Сохранить изменения", key=f"save_{vacancy_id}_{idx}"):
            cand["client_status"] = status_to_key[new_status]
            cand["client_comment"] = new_comment
            cand["office_interview_date"] = new_date.strftime("%Y-%m-%d") if new_date else ""
            cand["office_interview_time"] = new_time
            cand["client_final_verdict"] = final_verdict
            save_vacancies(data)
            st.success(f"Изменения для {cand.get('name', 'кандидата')} сохранены!")
            st.rerun()

st.markdown("---")
st.caption("Для каждого кандидата можно изменить статус, комментарий, дату, время и итог, затем нажать «Сохранить изменения».")