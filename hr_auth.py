"""Пароль HR-панели (client/master зоны — отдельно, по секретным ссылкам)."""

import os

import streamlit as st


def hr_password_configured():
    return bool((os.getenv("HR_APP_PASSWORD") or "").strip())


def require_hr_login():
    """
    Блокирует HR-панель без пароля, если задан HR_APP_PASSWORD в .env.
    Client zone и master — не вызывают эту функцию.
    """
    password = (os.getenv("HR_APP_PASSWORD") or "").strip()
    if not password:
        return
    if st.session_state.get("_hr_auth_ok"):
        return

    st.markdown("### 🔐 Вход в HR-панель")
    with st.form("hr_login_form", clear_on_submit=False):
        entered = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти", type="primary")
    if submitted:
        if entered == password:
            st.session_state["_hr_auth_ok"] = True
            st.rerun()
        st.error("Неверный пароль")
    st.stop()
