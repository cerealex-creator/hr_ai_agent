"""Вкладка «Вакансии» — vacancy-centric shell."""

import streamlit as st

import telegram_client

from vacancy_prep import (
    collect_vacancy_documents_for_template,
    render_existing_documents_zone,
    render_new_vacancy_form,
    render_templates_library,
    try_push_vacancy_to_templates,
)
from candidate_funnel import (
    render_candidates_zone,
    run_yandex_disk_sync,
)
from yandex_disk_ingest import migrate_vacancy_yandex_disk
from vacancy_display import find_vacancy_by_id, format_vacancy_search_period
from warranty import (
    format_vacancy_work_line,
    format_warranty_countdown,
    is_warranty_search_vacancy,
    migrate_vacancy_warranty,
)
from vacancy_close import (
    CLOSE_REASON_CLIENT,
    CLOSE_REASON_SUCCESS,
    can_close_vacancy_normally,
    close_reason_label,
    vacancy_has_successful_hire,
)


def _archive_prompt_key(vacancy_id):
    return f"archive_tpl_prompt_{vacancy_id}"


def _delete_prompt_key(vacancy_id):
    return f"delete_vac_prompt_{vacancy_id}"


def _load_fresh_vacancy(vacancy, deps):
    return next(
        (v for v in deps["load_vacancies"]() if v["id"] == vacancy["id"]),
        vacancy,
    )


def _archive_close_reason_key(vacancy_id):
    return f"archive_close_reason_{vacancy_id}"


def _archive_vacancy_record(vacancy, deps, *, close_reason=None):
    vacancy["active"] = False
    from datetime import datetime

    vacancy["closed_at"] = datetime.now().isoformat()
    if close_reason:
        vacancy["close_reason"] = close_reason
    elif vacancy_has_successful_hire(vacancy):
        vacancy["close_reason"] = CLOSE_REASON_SUCCESS
    all_v = deps["load_vacancies"]()
    for v in all_v:
        if v["id"] == vacancy["id"]:
            v.update(vacancy)
    deps["save_vacancies"](all_v)
    if st.session_state.get("opened_vacancy_id") == vacancy["id"]:
        st.session_state.opened_vacancy_id = None
    st.session_state.pop(_archive_prompt_key(vacancy["id"]), None)
    st.session_state.pop(_archive_close_reason_key(vacancy["id"]), None)


def _start_archive_flow(vacancy, deps, *, close_reason):
    fresh = _load_fresh_vacancy(vacancy, deps)
    docs = collect_vacancy_documents_for_template(fresh)
    from vacancy_template_store import get_template_sync_status

    sync_status, _ = get_template_sync_status(fresh, docs)
    if sync_status in ("missing", "differs"):
        st.session_state[_archive_prompt_key(vacancy["id"])] = sync_status
        st.session_state[_archive_close_reason_key(vacancy["id"])] = close_reason
        st.rerun()
    else:
        _archive_vacancy_record(fresh, deps, close_reason=close_reason)
        label = close_reason_label(close_reason) or "Вакансия закрыта"
        st.success(f"{label}.")
        st.rerun()


def _render_archive_template_prompt(vacancy, deps, status):
    vac_id = vacancy["id"]
    close_reason = st.session_state.get(_archive_close_reason_key(vac_id), CLOSE_REASON_SUCCESS)
    if status == "missing":
        st.warning("Данная вакансия отсутствует в шаблонах. Добавить её в шаблоны?")
    else:
        st.warning("Данная вакансия отличается от шаблонной. Сохранить изменения в шаблон?")

    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Да", key=f"archive_tpl_yes_{vac_id}", type="primary", use_container_width=True):
            fresh = _load_fresh_vacancy(vacancy, deps)
            ok, msg, missing, _ = try_push_vacancy_to_templates(fresh)
            if ok:
                _archive_vacancy_record(fresh, deps, close_reason=close_reason)
                done = close_reason_label(close_reason) or "Вакансия закрыта"
                if missing:
                    st.warning(f"{done}. {msg}")
                else:
                    st.success(f"{done}. {msg}")
                st.rerun()
            else:
                st.error(msg)
    with col_no:
        if st.button("Нет, только в архив", key=f"archive_tpl_no_{vac_id}", use_container_width=True):
            fresh = _load_fresh_vacancy(vacancy, deps)
            _archive_vacancy_record(fresh, deps, close_reason=close_reason)
            st.success(close_reason_label(close_reason) or "Вакансия закрыта.")
            st.rerun()


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
                migrate_vacancy_warranty(vacancy)
                is_open = st.session_state.opened_vacancy_id == vacancy["id"]
                label = f"{vacancy['title']}\nКандидаты: {cand_count}"
                period = format_vacancy_search_period(vacancy)
                if period and period != "период не указан":
                    label += f"\n{period}"
                if is_warranty_search_vacancy(vacancy):
                    label += "\n🛡️ Гарантийный поиск"
                countdown = format_warranty_countdown(vacancy)
                if countdown:
                    label += f"\n{countdown}"
                btn_type = "primary" if is_open else "secondary"
                if st.button(label, key=f"vac_pick_{vacancy['id']}", type=btn_type, use_container_width=True):
                    if is_open:
                        st.session_state.opened_vacancy_id = None
                    else:
                        st.session_state.opened_vacancy_id = vacancy["id"]
                    st.rerun()


def render_active_vacancy_workspace(vacancy, deps):
    migrate_vacancy_warranty(vacancy)
    metrics_line = format_vacancy_work_line(vacancy, html=True)
    st.markdown(
        f'<p class="vacancy-candidates-count">{metrics_line}</p>',
        unsafe_allow_html=True,
    )
    if is_warranty_search_vacancy(vacancy):
        src_id = vacancy.get("warranty_source_vacancy_id")
        source = find_vacancy_by_id(deps["load_vacancies"](), src_id)
        if source:
            src_period = format_vacancy_search_period(source)
            st.info(
                f"🛡️ **Гарантийный поиск** — замена по архивной вакансии "
                f"«{source.get('title', '—')}» ({src_period})."
            )
        else:
            st.info("🛡️ **Гарантийный поиск** — замена по архивной вакансии.")
    countdown = format_warranty_countdown(vacancy)
    if countdown:
        st.caption(f"🛡️ {countdown}")

    sub_cands, sub_docs = st.tabs([
        "👥 Кандидаты",
        "📄 Документы по вакансии",
    ])

    with sub_cands:
        render_candidates_zone(vacancy, deps)

    with sub_docs:
        render_existing_documents_zone(vacancy, deps)

    with st.expander("🔒 Закрыть вакансию"):
        prompt_status = st.session_state.get(_archive_prompt_key(vacancy["id"]))
        if prompt_status in ("missing", "differs"):
            _render_archive_template_prompt(vacancy, deps, prompt_status)
        elif can_close_vacancy_normally(vacancy):
            if st.button("Переместить в архив", key=f"close_{vacancy['id']}"):
                _start_archive_flow(vacancy, deps, close_reason=CLOSE_REASON_SUCCESS)
        else:
            st.warning(
                "Нельзя закрыть вакансию в архив: ни у одного кандидата нет статуса "
                "«Вышел на работу» или «Выход на стажировку»."
            )
            st.caption(
                "Если заказчик передумал или решил не продолжать поиск — "
                "используйте вариант ниже."
            )
            if st.button(
                "Вакансия закрыта заказчиком",
                key=f"close_client_{vacancy['id']}",
                type="primary",
            ):
                _start_archive_flow(vacancy, deps, close_reason=CLOSE_REASON_CLIENT)

    with st.expander("🗑️ Удалить вакансию"):
        st.warning(
            "Удаление необратимо: вакансия и все кандидаты будут удалены из базы."
        )
        prompt_key = _delete_prompt_key(vacancy["id"])
        if st.session_state.get(prompt_key):
            c1, c2 = st.columns([1, 3])
            with c1:
                if st.button(
                    "Удалить",
                    key=f"del_vac_yes_{vacancy['id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    from vacancy_store import delete_vacancy_by_id

                    ok, msg = delete_vacancy_by_id(vacancy.get("id"))
                    st.session_state.pop(prompt_key, None)
                    if ok:
                        st.success(msg)
                        if st.session_state.get("opened_vacancy_id") == vacancy["id"]:
                            st.session_state.opened_vacancy_id = None
                        st.rerun()
                    st.error(msg)
            with c2:
                if st.button(
                    "Отмена",
                    key=f"del_vac_no_{vacancy['id']}",
                    use_container_width=True,
                ):
                    st.session_state.pop(prompt_key, None)
                    st.rerun()
        else:
            if st.button(
                "Запросить удаление",
                key=f"del_vac_ask_{vacancy['id']}",
                use_container_width=True,
            ):
                st.session_state[prompt_key] = True
                st.rerun()


def render_archive_vacancy_picker(archived):
    if "opened_archive_vacancy_id" not in st.session_state:
        st.session_state.opened_archive_vacancy_id = None

    cols_per_row = 3
    for row_start in range(0, len(archived), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, vacancy in enumerate(archived[row_start:row_start + cols_per_row]):
            with cols[col_idx]:
                cand_count = len(vacancy.get("candidates", []))
                is_open = st.session_state.opened_archive_vacancy_id == vacancy["id"]
                label = f"{vacancy['title']}\nКандидаты: {cand_count}"
                period = format_vacancy_search_period(vacancy, precise=True)
                if period and period != "период не указан":
                    label += f"\n{period}"
                label += "\n📦 архив"
                btn_type = "primary" if is_open else "secondary"
                if st.button(
                    label,
                    key=f"arch_vac_pick_{vacancy['id']}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    if is_open:
                        st.session_state.opened_archive_vacancy_id = None
                    else:
                        st.session_state.opened_archive_vacancy_id = vacancy["id"]
                    st.rerun()


def render_archive_vacancy_workspace(vacancy, deps):
    migrate_vacancy_warranty(vacancy)
    period = format_vacancy_search_period(vacancy, precise=True)
    st.subheader(f"{vacancy['title']} · архив")
    if period and period != "период не указан":
        st.caption(f"Период поиска: {period}")

    sub_cands, sub_docs = st.tabs([
        "👥 Кандидаты",
        "📄 Документы (только просмотр)",
    ])

    with sub_cands:
        render_candidates_zone(vacancy, deps, archive_mode=True)

    with sub_docs:
        render_existing_documents_zone(vacancy, deps)


def render_archived_vacancies(deps):
    from vacancy_stats_filter import filter_vacancies_for_stats

    all_vacancies = deps["load_vacancies"]()
    archived = [
        v for v in all_vacancies
        if not v.get("active", True) and not v.get("is_test")
    ]
    archived.sort(
        key=lambda v: (v.get("closed_at") or v.get("created_at") or ""),
        reverse=True,
    )

    if not archived:
        st.info("Архив пуст — закрытые вакансии появятся здесь после «Переместить в архив».")
        return

    st.markdown("Выберите архивную вакансию, чтобы посмотреть кандидатов или скопировать карточку в активную.")
    render_archive_vacancy_picker(archived)

    opened_id = st.session_state.get("opened_archive_vacancy_id")
    if not opened_id:
        st.caption("Вакансия не выбрана.")
        return

    vacancy = next((v for v in archived if v["id"] == opened_id), None)
    if not vacancy:
        st.session_state.opened_archive_vacancy_id = None
        st.warning("Вакансия не найдена.")
        return

    st.divider()
    render_archive_vacancy_workspace(vacancy, deps)


def render_vacancies_in_work(deps):
    vacancies = deps["load_vacancies"]()
    active = [v for v in vacancies if v.get("active", True)]

    if not active:
        st.info("Нет вакансий в работе. Создайте новую во вкладке «Создание новой вакансии».")
        return

    st.markdown("Выберите вакансию, чтобы открыть документы и кандидатов.")
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
    head_l, head_sync, head_m, head_r = st.columns([3, 1, 1, 1])
    with head_l:
        title = vacancy["title"]
        period = format_vacancy_search_period(vacancy)
        if is_warranty_search_vacancy(vacancy):
            title += " · 🛡️ Гарантийный поиск"
        if period and period != "период не указан":
            title += f" · {period}"
        st.subheader(title)
    with head_sync:
        st.write("")
        migrate_vacancy_yandex_disk(vacancy)
        yd = vacancy.get("yandex_disk") or {}
        sync_help = "Подтянуть новые файлы из папки на Яндекс.Диске"
        if not (yd.get("root_url") or "").strip():
            sync_help += " (сначала укажите ссылку: Кандидаты → Автозагрузка)"
        if st.button(
            "🔄 Синхронизировать с Яндекс",
            key=f"yd_sync_top_{vacancy['id']}",
            use_container_width=True,
            help=sync_help,
        ):
            with st.spinner("Сканируем папку на Яндекс.Диске…"):
                run_yandex_disk_sync(vacancy, deps)
        if yd.get("last_sync_at"):
            st.caption(f"Синхр.: {yd['last_sync_at'][:16].replace('T', ' ')}")
    with head_m:
        st.write("")
        if st.button(
            "📌 Добавить вакансию в шаблоны",
            key=f"tpl_push_{vacancy['id']}",
            use_container_width=True,
        ):
            fresh = next(
                (v for v in deps["load_vacancies"]() if v["id"] == vacancy["id"]),
                vacancy,
            )
            ok, msg, missing, _ = try_push_vacancy_to_templates(fresh)
            if ok:
                if missing:
                    st.warning(msg)
                else:
                    st.success(msg)
            else:
                st.error(msg)
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

    tab_work, tab_archive, tab_search, tab_templates, tab_create = st.tabs([
        "📂 Вакансии в работе",
        "📦 Архив",
        "🔍 Поиск",
        "📌 Шаблоны",
        "➕ Создание новой вакансии",
    ])

    with tab_work:
        render_vacancies_in_work(deps)

    with tab_archive:
        render_archived_vacancies(deps)

    with tab_search:
        from candidate_search_ui import render_candidate_search_tab

        render_candidate_search_tab(deps)

    with tab_templates:
        render_templates_library(deps)

    with tab_create:
        render_new_vacancy_form(deps)
