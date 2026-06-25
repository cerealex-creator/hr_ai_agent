"""Вкладка «Статистика» — сводки, гарантия, настраиваемые показатели."""

import streamlit as st

from vacancy_stats import render_vacancy_stats
from warranty import (
    WARRANTY_MONTH_LABELS,
    collect_warranty_vacancies,
    create_warranty_search_vacancy,
    format_warranty_countdown,
    is_warranty_search_vacancy,
    migrate_vacancy_warranty,
)
from vacancy_display import (
    build_vacancy_picker_options,
    format_vacancy_search_period,
)
from funnel_metrics import (
    candidate_vacancy_entries,
    candidates_from_vacancies,
    compute_funnel_metrics,
)

# Показатели по таблице учёта
REPORT_METRICS = [
    ("total_selected", "Всего отобрано для рассмотрения, чел"),
    ("primary_contact", "Первый контакт (сообщение)"),
    ("no_contact", "Не общался/пропали со связи"),
    ("interview_done", "Прошли первичное собеседование"),
    ("client_review", "Внесены в список на рассмотрение"),
    ("client_approved", "Одобрены заказчиком"),
    ("test_task", "Выполнили задание/тест"),
    ("internship", "Приглашено на стажировку"),
    ("offer", "Приглашены на работу"),
    ("started_work", "Вышли на работу"),
    ("rejected_hr", "Получили отказ от меня"),
    ("rejected_client", "Получили отказ от заказчика"),
    ("rejected_candidate", "Отказались сами"),
]

DEFAULT_REPORT_KEYS = [
    "total_selected",
    "primary_contact",
    "no_contact",
    "interview_done",
    "client_review",
    "client_approved",
    "test_task",
    "internship",
    "offer",
    "started_work",
    "rejected_hr",
    "rejected_client",
    "rejected_candidate",
]


def _render_configurable_report(entries, report_keys):
    metrics = compute_funnel_metrics(entries)
    st.markdown("**Сводка по этапам (настраиваемая)**")
    for key in report_keys:
        label = next((lbl for k, lbl in REPORT_METRICS if k == key), key)
        st.write(f"- {label}: **{metrics.get(key, 0)}**")


def _render_warranty_registry(all_vacancies, deps, create_vacancy_fn):
    st.subheader("🛡️ На гарантии")
    st.caption(
        "Вакансии, по которым идёт гарантийный срок после оффера или выхода на стажировку. "
        "Месяц = 30 дней."
    )
    warranty_rows = collect_warranty_vacancies(all_vacancies)
    if not warranty_rows:
        st.info("Сейчас нет вакансий с активной гарантией.")
        return

    for vac in warranty_rows:
        migrate_vacancy_warranty(vac)
        w = vac.get("warranty") or {}
        countdown = format_warranty_countdown(vac)
        months = w.get("months", 3)
        start = (w.get("start_date") or "")[:10]
        start_fmt = ""
        if start:
            try:
                from datetime import datetime
                start_fmt = datetime.strptime(start[:10], "%Y-%m-%d").strftime("%d.%m.%y")
            except ValueError:
                start_fmt = start[:10]
        period = format_vacancy_search_period(vac)
        active_label = "в работе" if vac.get("active", True) else "в архиве"
        st.markdown(
            f"**{vac.get('title', '—')}** · {period} · {active_label} · "
            f"{countdown} · с {start_fmt} · срок {WARRANTY_MONTH_LABELS.get(months, months)}"
        )
        if not vac.get("active", True):
            if st.button(
                "Открыть гарантийный поиск",
                key=f"warranty_open_{vac['id']}",
            ):
                ok, result = create_warranty_search_vacancy(vac, create_vacancy_fn)
                if not ok:
                    st.error(result)
                else:
                    all_v = deps["load_vacancies"]()
                    for v in all_v:
                        if v.get("id") == result.get("id"):
                            v.update(result)
                            break
                    deps["save_vacancies"](all_v)
                    st.session_state.opened_vacancy_id = result.get("id")
                    src_period = format_vacancy_search_period(vac)
                    st.success(
                        f"Создана вакансия «{result.get('title')}» (гарантийный поиск). "
                        f"Связана с архивной «{vac.get('title')}» ({src_period})."
                    )
                    st.rerun()


def render_stats_tab(deps, *, create_vacancy_fn):
    st.header("📊 Статистика")
    st.caption("Сводки по воронке, реестр гарантии и детальная статистика по вакансии.")

    all_vacancies = deps["load_vacancies"]()
    for v in all_vacancies:
        migrate_vacancy_warranty(v)

    _render_warranty_registry(all_vacancies, deps, create_vacancy_fn)
    st.divider()

    active = [v for v in all_vacancies if v.get("active", True)]
    archived = [v for v in all_vacancies if not v.get("active", True)]

    st.subheader("Настраиваемая сводка")
    scope = st.radio(
        "Область",
        ["Одна вакансия", "Все активные", "Все (включая архив)"],
        horizontal=True,
        key="stats_scope",
    )
    picked_vacancy = None
    if scope == "Одна вакансия":
        pool = active + archived
        if not pool:
            st.info("Нет вакансий.")
            return
        labels, by_label = build_vacancy_picker_options(
            pool,
            suffix_fn=lambda v: "гарантийный поиск" if is_warranty_search_vacancy(v) else "",
        )
        picked = st.selectbox("Вакансия", labels, key="stats_vac_pick")
        picked_vacancy = by_label[picked]
        entries = candidate_vacancy_entries(picked_vacancy.get("candidates", []), picked_vacancy)
    elif scope == "Все активные":
        entries = candidates_from_vacancies(active)
    else:
        entries = candidates_from_vacancies(all_vacancies)

    metric_labels = {k: lbl for k, lbl in REPORT_METRICS}
    selected_keys = st.multiselect(
        "Показатели в сводке",
        options=[k for k, _ in REPORT_METRICS],
        default=[k for k in DEFAULT_REPORT_KEYS if k in metric_labels],
        format_func=lambda k: metric_labels.get(k, k),
        key="stats_metric_keys",
    )
    if selected_keys:
        _render_configurable_report(entries, selected_keys)
    else:
        st.caption("Выберите хотя бы один показатель.")

    st.divider()
    st.subheader("Детальная статистика по вакансии")
    if scope == "Одна вакансия" and picked_vacancy:
        if render_vacancy_stats(picked_vacancy):
            all_v = deps["load_vacancies"]()
            for v in all_v:
                if v["id"] == picked_vacancy["id"]:
                    v["vacancy_summary"] = picked_vacancy.get("vacancy_summary", "")
            deps["save_vacancies"](all_v)
            st.success("Итог сохранён!")
            st.rerun()
    else:
        st.caption("Выберите «Одна вакансия» выше для воронки HR и поля «Общий итог HR».")
