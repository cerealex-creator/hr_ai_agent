"""Общие UI-хелперы: выпадающие списки без значения по умолчанию."""

import streamlit as st

EMPTY_SELECT_LABEL = "— Выберите —"


def selectbox_no_default(label, options, key, help_text=None):
    """Возвращает выбранное значение или None, если пользователь не выбрал."""
    choices = [EMPTY_SELECT_LABEL] + list(options)
    selected = st.selectbox(label, choices, index=0, key=key, help=help_text)
    if selected == EMPTY_SELECT_LABEL:
        return None
    return selected


def require_selection(value, message="Сделайте выбор в списке выше."):
    if value is None:
        st.warning(message)
        return False
    return True
