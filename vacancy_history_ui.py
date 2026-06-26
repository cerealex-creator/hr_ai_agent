"""Панель прошлых генераций документов (без отдельной вкладки «История»)."""

from __future__ import annotations

import json

import streamlit as st

from vacancy_prep import (
    apply_package_from_history,
    describe_history_package,
    _vacancy_history_picker_options,
)


def _normalize_title(value: str) -> str:
    return (value or "").strip().casefold()


def filter_history_for_vacancy(index, vacancy, *, include_all: bool = False):
    if include_all or not index:
        return index or []
    title = _normalize_title(vacancy.get("title"))
    if not title:
        return index
    matched = []
    for rec in index:
        vac_title = _normalize_title(rec.get("vacancy_title"))
        job_title = _normalize_title(rec.get("title"))
        if title in (vac_title, job_title) or vac_title == title or job_title == title:
            matched.append(rec)
        elif title in vac_title or title in job_title:
            matched.append(rec)
    return matched if matched else index[:5]


def find_history_for_title(index, title: str, *, limit: int = 5):
    title_n = _normalize_title(title)
    if not title_n or not index:
        return []
    matched = []
    for rec in index:
        vac_title = _normalize_title(rec.get("vacancy_title"))
        job_title = _normalize_title(rec.get("title"))
        if title_n in (vac_title, job_title) or title_n in vac_title or title_n in job_title:
            matched.append(rec)
        if len(matched) >= limit:
            break
    return matched


def render_vacancy_history_panel(
    vacancy,
    deps,
    *,
    get_history_index,
    load_generation_from_history,
    delete_generation_from_history,
    key_prefix: str = "vac_hist",
):
    """Блок «Прошлые генерации» внутри документов вакансии."""
    index = get_history_index()
    if not index:
        st.caption("Прошлых генераций пока нет — они сохраняются автоматически после успешной генерации.")
        return

    show_all_key = f"{key_prefix}_show_all_{vacancy['id']}"
    show_all = st.checkbox(
        "Показать все пакеты (не только по названию вакансии)",
        value=False,
        key=show_all_key,
    )
    filtered = filter_history_for_vacancy(index, vacancy, include_all=show_all)
    st.caption(
        f"Найдено пакетов: **{len(filtered)}**. "
        "Применение **полностью заменяет** документы этой вакансии."
    )

    loaded_rec = st.session_state.get(f"{key_prefix}_loaded_rec")
    gen = st.session_state.get(f"{key_prefix}_generated")
    if gen and loaded_rec:
        parts = describe_history_package(gen)
        st.info(
            f"Загружен пакет от {loaded_rec.get('datetime', '')} "
            f"({', '.join(parts) if parts else 'без распознанных документов'})."
        )
        if st.button("📥 Применить загруженный пакет к этой вакансии", key=f"{key_prefix}_apply_{vacancy['id']}", type="primary"):
            if not parts:
                st.error("Пакет пустой — нечего применять.")
            else:
                with st.spinner("Замена документов…"):
                    saved, written, cleared = apply_package_from_history(vacancy, gen, deps)
                if saved and written:
                    st.session_state.opened_vacancy_id = vacancy["id"]
                    st.success(
                        f"Документы обновлены: {', '.join(written)}."
                        + (f" Очищено: {', '.join(cleared)}." if cleared else "")
                    )
                    st.session_state.pop(f"{key_prefix}_generated", None)
                    st.session_state.pop(f"{key_prefix}_loaded_rec", None)
                    st.rerun()
                elif not written:
                    st.error("В пакете нет документов для применения.")
                else:
                    st.error("Не удалось сохранить документы.")

    for i, rec in enumerate(filtered[:12]):
        parts = []
        data_preview = load_generation_from_history(rec["filename"])
        if data_preview:
            parts = describe_history_package(data_preview)
        label = f"{rec.get('datetime', '')} — {rec.get('title') or rec.get('vacancy_title') or 'Без названия'}"
        if parts:
            label += f" ({', '.join(parts)})"
        with st.expander(label, expanded=False):
            if rec.get("vacancy_title"):
                st.caption(f"Вакансия при генерации: {rec['vacancy_title']}")
            if rec.get("preview"):
                st.text(rec["preview"])
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Загрузить для применения", key=f"{key_prefix}_load_{vacancy['id']}_{i}"):
                    data = load_generation_from_history(rec["filename"])
                    if data:
                        st.session_state[f"{key_prefix}_generated"] = data
                        st.session_state[f"{key_prefix}_loaded_rec"] = rec
                        st.rerun()
                    else:
                        st.error("Не удалось прочитать файл.")
            with col_b:
                if data_preview:
                    st.download_button(
                        "Скачать JSON",
                        data=json.dumps(data_preview, ensure_ascii=False, indent=2),
                        file_name=rec["filename"],
                        mime="application/json",
                        key=f"{key_prefix}_dl_{vacancy['id']}_{i}",
                    )
                if st.button("Удалить пакет", key=f"{key_prefix}_del_{vacancy['id']}_{i}"):
                    if delete_generation_from_history(rec["filename"]):
                        if loaded_rec and loaded_rec.get("filename") == rec["filename"]:
                            st.session_state.pop(f"{key_prefix}_generated", None)
                            st.session_state.pop(f"{key_prefix}_loaded_rec", None)
                        st.rerun()


def render_create_vacancy_history_hint(title: str, deps, *, get_history_index, load_generation_from_history):
    """Подсказка при создании вакансии: есть ли похожие пакеты в истории."""
    title = (title or "").strip()
    if len(title) < 3:
        return
    index = get_history_index()
    matches = find_history_for_title(index, title, limit=3)
    if not matches:
        return
    st.info(
        f"В истории есть **{len(matches)}** сохранённых пакетов для похожей должности «{title}». "
        "После создания вакансии откройте «Документы по вакансии» → «Прошлые генерации»."
    )
    with st.expander("Посмотреть пакеты", expanded=False):
        for rec in matches:
            st.write(
                f"- {rec.get('datetime', '')} — {rec.get('title') or rec.get('vacancy_title', '—')}"
            )
