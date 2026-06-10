import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corporate_ui import apply_corporate_ui
from resume_mockups import build_mockups_deps, render_mockups_zone
from ui_helpers import selectbox_no_default

st.set_page_config(page_title="Макеты HH", page_icon="📋", layout="wide")
apply_corporate_ui()

st.title("📋 Макеты HH")
st.caption(
    "Оценка резюме без контактов по профилю должности. "
    "Массовая оценка ИИ и рейтинг кандидатов относительно друг друга."
)
st.markdown(
    '<a class="client-zone-btn" href="/" target="_self">← Вернуться в основное приложение</a>',
    unsafe_allow_html=True,
)

deps = build_mockups_deps()
vacancies = deps["load_vacancies"]()
active = [v for v in vacancies if v.get("active", True)]

if not active:
    st.info("Нет активных вакансий. Создайте вакансию в основном приложении.")
    st.stop()

labels = [v["title"] for v in sorted(active, key=lambda x: x.get("title", ""))]
selected_title = selectbox_no_default(
    "Выберите вакансию",
    labels,
    key="mockups_page_vacancy",
)
if not selected_title:
    st.info("Выберите вакансию из списка.")
    st.stop()

vacancy = next(v for v in active if v["title"] == selected_title)
vacancies = deps["load_vacancies"]()
vacancy = next((v for v in vacancies if v["id"] == vacancy["id"]), vacancy)

st.divider()
st.subheader(vacancy["title"])
render_mockups_zone(vacancy, deps)
