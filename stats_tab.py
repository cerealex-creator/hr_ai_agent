"""Вкладка «Статистика» — продуктивность за период, гарантия, деталь по вакансии."""

from datetime import date

import streamlit as st

from period_productivity import (
    METRIC_LABELS,
    build_comparison_row,
    collect_period_context_extras,
    compute_baseline_monthly_averages,
    compute_period_metrics,
    detect_earliest_activity_date,
    format_period_label,
    period_bounds,
    previous_period_bounds,
    vacancy_overlaps_period,
    activity_in_period,
    parse_activity_datetime,
)
from productivity_ai import analyze_productivity_with_ai, build_productivity_analysis_payload
from vacancy_stats_filter import filter_vacancies_for_stats
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


def _load_dept_names():
    try:
        from hri_full_v1 import load_departments

        return {d["id"]: d["name"] for d in load_departments()}
    except Exception:
        return {}


def _delta_badge(delta):
    if delta is None:
        return "—"
    if delta > 0:
        return f"↑ {delta}"
    if delta < 0:
        return f"↓ {abs(delta)}"
    return "→ 0"


def _render_period_selectors():
    today = date.today()
    period_type = st.radio(
        "Период",
        options=["month", "quarter", "half_year"],
        format_func=lambda x: {"month": "Месяц", "quarter": "Квартал", "half_year": "Полугодие"}[x],
        horizontal=True,
        key="stats_period_type",
    )
    year = st.selectbox(
        "Год",
        options=list(range(today.year, today.year - 4, -1)),
        key="stats_period_year",
    )
    if period_type == "month":
        from vacancy_display import MONTHS_RU

        month_options = list(range(1, 13))
        default_month = today.month if year == today.year else 12
        index = st.selectbox(
            "Месяц",
            options=month_options,
            index=month_options.index(default_month),
            format_func=lambda m: MONTHS_RU[m],
            key="stats_period_index",
        )
    elif period_type == "quarter":
        default_q = (today.month - 1) // 3 + 1 if year == today.year else 4
        index = st.selectbox(
            "Квартал",
            options=[1, 2, 3, 4],
            index=default_q - 1,
            format_func=lambda q: f"{q}-й квартал",
            key="stats_period_index",
        )
    else:
        default_half = 1 if today.month <= 6 else 2
        if year != today.year:
            default_half = 2
        index = st.selectbox(
            "Полугодие",
            options=[1, 2],
            index=default_half - 1,
            format_func=lambda h: "1-е полугодие (янв–июн)" if h == 1 else "2-е полугодие (июл–дек)",
            key="stats_period_index",
        )
    return period_type, year, index


def _dept_breakdown_for_period(vacancies, period_start, period_end, dept_names, *, today=None):
    rows = []
    for vacancy in vacancies:
        if not vacancy_overlaps_period(vacancy, period_start, period_end, today=today):
            continue
        dept = dept_names.get(vacancy.get("client_id"), "—")
        added = 0
        for cand in vacancy.get("candidates", []):
            if activity_in_period(parse_activity_datetime(cand.get("created_at")), period_start, period_end):
                added += 1
        rows.append({
            "подразделение": dept,
            "вакансия": vacancy.get("title", "—"),
            "добавлено_кандидатов": added,
            "период_поиска": format_vacancy_search_period(vacancy),
        })
    return rows


def _previous_period_label(period_type, prev_start):
    if period_type == "month":
        return format_period_label("month", prev_start.year, prev_start.month)
    if period_type == "quarter":
        return format_period_label("quarter", prev_start.year, (prev_start.month - 1) // 3 + 1)
    return format_period_label("half_year", prev_start.year, 1 if prev_start.month <= 6 else 2)


def _format_short_date(iso_str):
    if not iso_str:
        return ""
    try:
        return date.fromisoformat(str(iso_str)[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return str(iso_str)[:10]


def _render_closed_success_details(details, not_success_details=None):
    if not details and not not_success_details:
        st.caption("— нет закрытий за период")
        return
    for item in details:
        st.markdown(f"**{item['vacancy_label']}**")
        st.caption(f"Закрыта {_format_short_date(item.get('closed_at'))} · {item.get('closure_kind', '—')}")
        hires = item.get("candidates") or []
        if hires:
            for hire in hires:
                st.write(f"· {hire['name']} — {hire['outcome']}")
        else:
            st.warning("Кандидат с выходом на работу/стажировку не найден в данных")
    if not_success_details:
        st.caption("**Закрыты в периоде, но не в счётчике «успешно»:**")
        for item in not_success_details:
            st.warning(item.get("hint", "Нет выхода на работу/стажировку в данных."))
            st.markdown(f"**{item['vacancy_label']}**")
            st.caption(f"Закрыта {_format_short_date(item.get('closed_at'))}")
            for cand in item.get("candidates") or []:
                st.write(f"· {cand['name']} — этап «{cand['hr_stage']}»")
            st.caption(
                "Если кандидат уже вышел на работу — зафиксируйте этап "
                "«Вышел на работу» или «Выход на стажировку» в карточке."
            )


def _render_started_details(details):
    if not details:
        st.caption("— нет новых вакансий за период")
        return
    for item in sorted(details, key=lambda x: x.get("created_at", "")):
        created = _format_short_date(item.get("created_at"))
        st.write(f"· **{item['vacancy_label']}**")
        if created:
            st.caption(f"Создана {created}")


def _render_invited_details(details):
    if not details:
        st.caption("— нет приглашений за период")
        return
    for item in sorted(details, key=lambda x: (x.get("vacancy_label", ""), x.get("candidate_name", ""))):
        event = _format_short_date(item.get("event_date"))
        st.write(f"· **{item['candidate_name']}**")
        st.caption(
            f"Вакансия: {item['vacancy_label']} · {item.get('invite_kind', '—')}"
            + (f" · {event}" if event else "")
        )


def _render_highlight_metrics_with_details(current):
    cols = st.columns(3)
    with cols[0]:
        st.metric(METRIC_LABELS["vacancies_closed_success"], current.vacancies_closed_success)
        _render_closed_success_details(
            current.vacancies_closed_success_details,
            current.vacancies_closed_not_success_details,
        )
    with cols[1]:
        st.metric(METRIC_LABELS["vacancies_started"], current.vacancies_started)
        _render_started_details(current.vacancies_started_details)
    with cols[2]:
        st.metric(METRIC_LABELS["invited_work"], current.invited_work)
        _render_invited_details(current.invited_work_details)
    if current.vacancies_closed_success:
        st.caption(
            f"Из закрытых успешно: начатых ранее периода — **{current.vacancies_closed_success_started_before}**, "
            f"начатых и закрытых в этом периоде — **{current.vacancies_closed_success_started_in_period}**"
        )


def _render_productivity_section(all_vacancies, deps):
    st.subheader("Моя продуктивность за период")
    st.caption(
        "Показатели по календарному периоду: что сделано за месяц/квартал/полугодие. "
        "Тестовые вакансии не учитываются. "
        "Даты берутся из истории этапов; у старых записей без истории цифры могут быть занижены."
    )

    earliest = detect_earliest_activity_date(all_vacancies)
    if earliest:
        st.caption(f"Первая активность в данных: {earliest.strftime('%d.%m.%Y')}")

    period_type, year, index = _render_period_selectors()
    p_start, p_end = period_bounds(period_type, year, index)
    prev_start, prev_end = previous_period_bounds(period_type, year, index)

    current = compute_period_metrics(all_vacancies, p_start, p_end)
    previous = compute_period_metrics(all_vacancies, prev_start, prev_end)
    baseline_months, baseline_avg = compute_baseline_monthly_averages(all_vacancies, p_start)
    comparison = build_comparison_row(current, previous, baseline_avg)

    period_label = format_period_label(period_type, year, index)
    prev_label = _previous_period_label(period_type, prev_start)

    st.markdown(f"**{period_label}** ({p_start.strftime('%d.%m.%Y')} — {p_end.strftime('%d.%m.%Y')})")

    _render_highlight_metrics_with_details(current)

    st.markdown("**Сравнение показателей**")
    header = st.columns([2.2, 1, 1, 1, 1])
    header[0].markdown("**Показатель**")
    header[1].markdown(f"**{period_label}**")
    header[2].markdown(f"**{prev_label}**")
    header[3].markdown("**Δ к пред.**")
    if baseline_months:
        header[4].markdown(f"**Ср. {baseline_months} мес.**")
    else:
        header[4].markdown("**Ср.**")

    for row in comparison:
        cols = st.columns([2.2, 1, 1, 1, 1])
        cols[0].write(row["label"])
        cols[1].write(row["current"])
        cols[2].write(row["previous"])
        cols[3].write(_delta_badge(row["delta_prev"]))
        avg_val = row["average"]
        if baseline_months and avg_val is not None:
            cols[4].write(f"{avg_val:.1f}")
        else:
            cols[4].write("—")
        if row["key"] == "vacancies_closed_success" and row["current"]:
            st.caption(
                f"↳ начатых ранее периода: {current.vacancies_closed_success_started_before}; "
                f"начатых в этом периоде: {current.vacancies_closed_success_started_in_period}"
            )

    if baseline_months < 3:
        st.caption(
            f"Среднее посчитано за **{baseline_months}** календарных мес. "
            "Для устойчивого квартального сравнения нужно больше истории."
        )
    else:
        st.caption(f"Среднее — по **{baseline_months}** завершённым календарным месяцам до выбранного периода.")

    st.markdown(
        f"**Вакансий в работе за период:** {current.vacancies_in_work}"
    )
    if current.vacancy_titles_in_work:
        with st.expander("Список вакансий в работе за период", expanded=False):
            for title in current.vacancy_titles_in_work:
                st.write(f"- {title}")

    st.divider()
    st.markdown("**ИИ-анализ и рекомендации**")
    st.caption("Запускается по кнопке — без лишних расходов на токены.")

    dept_names = _load_dept_names()
    context_extras = collect_period_context_extras(all_vacancies, p_start, p_end)
    dept_breakdown = _dept_breakdown_for_period(all_vacancies, p_start, p_end, dept_names)

    if st.button("🤖 Получить ИИ-анализ за период", key="stats_ai_analyze", type="primary"):
        payload = build_productivity_analysis_payload(
            period_type=period_type,
            year=year,
            index=index,
            current_metrics=current,
            previous_metrics=previous,
            baseline_months=baseline_months,
            baseline_averages=baseline_avg,
            comparison_rows=comparison,
            context_extras=context_extras,
            dept_breakdown=dept_breakdown,
            vacancies_in_work_titles=current.vacancy_titles_in_work,
        )
        with st.spinner("ИИ анализирует показатели…"):
            try:
                text = analyze_productivity_with_ai(deps["client"], deps["config"], payload)
                st.session_state["stats_ai_result"] = text
            except Exception as exc:
                st.error(f"Не удалось выполнить анализ: {exc}")

    if st.session_state.get("stats_ai_result"):
        st.markdown(st.session_state["stats_ai_result"])


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
    st.caption("Продуктивность за период, реестр гарантии и детальная статистика по вакансии.")

    all_vacancies_raw = deps["load_vacancies"]()
    for v in all_vacancies_raw:
        migrate_vacancy_warranty(v)

    stats_vacancies = filter_vacancies_for_stats(all_vacancies_raw)

    _render_productivity_section(stats_vacancies, deps)
    st.divider()
    _render_warranty_registry(all_vacancies_raw, deps, create_vacancy_fn)
    st.divider()

    st.subheader("Детальная статистика по вакансии")
    pool = [v for v in all_vacancies_raw if v.get("candidates")]
    if not pool:
        st.info("Нет вакансий с кандидатами.")
        return
    labels, by_label = build_vacancy_picker_options(
        pool,
        suffix_fn=lambda v: "гарантийный поиск" if is_warranty_search_vacancy(v) else "",
    )
    picked = st.selectbox("Вакансия", labels, key="stats_vac_pick")
    picked_vacancy = by_label[picked]
    if render_vacancy_stats(picked_vacancy):
        all_v = deps["load_vacancies"]()
        for v in all_v:
            if v["id"] == picked_vacancy["id"]:
                v["vacancy_summary"] = picked_vacancy.get("vacancy_summary", "")
        deps["save_vacancies"](all_v)
        st.success("Итог сохранён!")
        st.rerun()
