"""Общая логика клиентских зон (подразделение и мастер-зона)."""

from datetime import datetime, time

import streamlit as st

from eval_ui import has_ai_evaluation, render_ai_score_badge, render_ai_evaluation_block
from models import is_visible_in_client_zone
from resume_ai import yandex_link_for_display

from vacancy_store import (
    STATUS_CONFIG,
    STATUS_LABEL_TO_KEY,
    STATUS_OPTIONS,
    STATUS_ORDER,
    get_status_meta,
    load_departments,
    load_vacancies,
    migrate_candidate,
    migrate_vacancies_data,
    resolve_status_on_save,
    save_vacancies,
)

TEST_DEPARTMENT_IDS = {99}


def is_test_department(dept):
    if not dept:
        return False
    return dept.get("id") in TEST_DEPARTMENT_IDS or dept.get("slug") == "test"


def sort_candidates(candidates):
    def parse_created(cand):
        try:
            return datetime.fromisoformat(cand.get("created_at", ""))
        except ValueError:
            return datetime.min

    return sorted(
        candidates,
        key=lambda c: (
            STATUS_ORDER.get(c.get("client_status", "wait"), 99),
            -parse_created(c).timestamp(),
        ),
    )


def build_time_options():
    options = [""]
    current = time(9, 0)
    end = time(18, 0)
    while current <= end:
        options.append(current.strftime("%H:%M"))
        minutes = current.hour * 60 + current.minute + 30
        current = time(minutes // 60, minutes % 60)
    return options


def apply_client_styles():
    st.markdown(
        """
        <style>
            .candidate-compact-row {
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 0.5rem 0.75rem;
                padding: 0.15rem 0;
            }
            .candidate-name {
                font-size: 1.1rem;
                font-weight: 700;
                color: #0c2340;
            }
            .status-badge {
                display: inline-block;
                padding: 0.2rem 0.55rem;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 600;
                white-space: nowrap;
            }
            .status-badge-wait { background: #f1f5f9; color: #64748b; }
            .status-badge-ready { background: #dcfce7; color: #15803d; }
            .status-badge-reject { background: #fee2e2; color: #b91c1c; }
            .status-badge-think { background: #fef3c7; color: #b45309; }
            .status-badge-offer { background: #dcfce7; color: #15803d; font-weight: 700; }
            .status-badge-started { background: #fef9c3; color: #854d0e; font-weight: 700; }
            .link-btn-compact {
                display: inline-block;
                background: #2563eb;
                color: #ffffff !important;
                padding: 0.25rem 0.6rem;
                border-radius: 6px;
                font-size: 0.78rem;
                font-weight: 500;
                text-decoration: none !important;
                margin-right: 0.25rem;
            }
            .link-btn-compact:hover { background: #1d4ed8; }
            .link-missing {
                color: #94a3b8;
                font-size: 0.78rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_link_button(link, label):
    href = yandex_link_for_display((link or "").strip())
    if href:
        return (
            f'<a class="link-btn-compact" href="{href}" target="_blank">{label}</a>'
        )
    return f'<span class="link-missing">{label} —</span>'


def render_status_badge(status_key):
    meta = get_status_meta(status_key)
    return (
        f'<span class="status-badge {meta["badge_class"]}">'
        f'{meta["icon"]} {meta["label"]}</span>'
    )


def render_compact_summary(cand):
    links = " ".join([
        render_link_button(cand.get("resume_link", ""), "📄 Резюме"),
        render_link_button(cand.get("video_link", ""), "🎥 Запись"),
        render_link_button(cand.get("task_link", ""), "✅ Задание") if cand.get("task_link") else "",
    ])
    ai_badge = render_ai_score_badge(cand["ai_score"]) if has_ai_evaluation(cand) else ""
    return (
        f'<div class="candidate-compact-row">'
        f'<span class="candidate-name">👤 {cand.get("name", "Без имени")}</span>'
        f'{render_status_badge(cand.get("client_status", "wait"))}'
        f'{ai_badge}'
        f'{links}'
        f'</div>'
    )


def format_client_status_date(cand):
    raw = (cand.get("status_updated_at") or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", ""))
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return raw[:10]


def vacancy_picker_label(vacancy, dept_names):
    dept = dept_names.get(vacancy.get("client_id"), "—")
    return f"{dept} — {vacancy['title']}"


def get_production_vacancies(vacancies, departments):
    dept_by_id = {d["id"]: d for d in departments}
    result = []
    for vacancy in vacancies:
        if not vacancy.get("active", True):
            continue
        client_id = vacancy.get("client_id", 0)
        if client_id in TEST_DEPARTMENT_IDS:
            continue
        dept = dept_by_id.get(client_id)
        if is_test_department(dept):
            continue
        result.append(vacancy)
    return result


def render_candidates_section(data, selected_vacancy, key_prefix="client"):
    all_candidates = selected_vacancy.get("candidates", [])
    candidates = sort_candidates(
        [c for c in all_candidates if is_visible_in_client_zone(c)]
    )
    if not candidates:
        if all_candidates:
            st.info(
                "Нет кандидатов на этапе «На оценке у заказчика». "
                "Рекрутер переводит кандидата на этот этап HR — тогда он появится здесь."
            )
        else:
            st.info("Нет кандидатов.")
        return

    time_options = build_time_options()
    vacancy_id = selected_vacancy["id"]

    status_counts = {}
    for c in candidates:
        key = c.get("client_status", "wait")
        status_counts[key] = status_counts.get(key, 0) + 1

    summary_parts = [
        f"{get_status_meta(k)['icon']} {get_status_meta(k)['label']}: {v}"
        for k, v in sorted(status_counts.items(), key=lambda x: STATUS_ORDER.get(x[0], 99))
    ]
    st.caption(" · ".join(summary_parts))

    for idx, cand in enumerate(candidates):
        migrate_candidate(cand)
        status_key = cand.get("client_status", "wait")
        status_date = format_client_status_date(cand)
        expander_label = (
            f"{cand.get('name', 'Без имени')} — "
            f"{get_status_meta(status_key)['icon']} {get_status_meta(status_key)['label']}"
        )
        if status_date:
            expander_label += f" · {status_date}"
        if has_ai_evaluation(cand):
            score = int(cand["ai_score"])
            suffix = f"{score}/10" if score > 4 else f"{score}/4"
            expander_label += f" — 🤖 {suffix}"

        cand_id = cand.get("id", idx)
        collapse_key = f"client_collapse_{key_prefix}_{vacancy_id}_{cand_id}"
        expander_rev_key = f"client_exp_rev_{key_prefix}_{vacancy_id}_{cand_id}"
        if st.session_state.pop(collapse_key, False):
            st.session_state[expander_rev_key] = st.session_state.get(expander_rev_key, 0) + 1
        expander_rev = st.session_state.get(expander_rev_key, 0)

        with st.expander(
            expander_label,
            expanded=False,
            key=f"client_exp_{key_prefix}_{vacancy_id}_{cand_id}_{expander_rev}",
        ):
            st.markdown(render_compact_summary(cand), unsafe_allow_html=True)
            render_ai_evaluation_block(cand)
            st.markdown("---")

            current_label = get_status_meta(status_key)["label"]
            label_index = STATUS_OPTIONS.index(current_label) if current_label in STATUS_OPTIONS else 0
            new_status_label = st.selectbox(
                "Статус",
                options=STATUS_OPTIONS,
                index=label_index,
                key=f"status_{key_prefix}_{vacancy_id}_{idx}",
            )
            show_interview_fields = STATUS_LABEL_TO_KEY[new_status_label] == "ready"

            new_comment = st.text_area(
                "Комментарий клиента",
                value=cand.get("client_comment", ""),
                key=f"comment_{key_prefix}_{vacancy_id}_{idx}",
                height=68,
                placeholder="Ваш комментарий...",
            )

            if show_interview_fields:
                date_str = cand.get("office_interview_date", "")
                try:
                    date_val = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
                except ValueError:
                    date_val = None
                new_date = st.date_input(
                    "Дата собеседования",
                    value=date_val,
                    key=f"date_{key_prefix}_{vacancy_id}_{idx}",
                    format="DD.MM.YYYY",
                )

                current_time = cand.get("office_interview_time", "")
                time_index = time_options.index(current_time) if current_time in time_options else 0
                new_time = st.selectbox(
                    "Время собеседования",
                    options=time_options,
                    index=time_index,
                    key=f"time_{key_prefix}_{vacancy_id}_{idx}",
                )

                col_chk1, col_chk2 = st.columns(2)
                with col_chk1:
                    remote_interview = st.checkbox(
                        "Удалённое собеседование",
                        value=bool(cand.get("remote_interview", False)),
                        key=f"remote_{key_prefix}_{vacancy_id}_{idx}",
                    )
                with col_chk2:
                    office_interview = st.checkbox(
                        "Собеседование в офисе",
                        value=bool(cand.get("office_interview", False)),
                        key=f"office_{key_prefix}_{vacancy_id}_{idx}",
                    )
            else:
                new_date = None
                new_time = cand.get("office_interview_time", "")
                remote_interview = cand.get("remote_interview", False)
                office_interview = cand.get("office_interview", False)

            final_verdict = st.text_area(
                "Итог по кандидату",
                value=cand.get("client_final_verdict", ""),
                key=f"verdict_{key_prefix}_{vacancy_id}_{idx}",
                height=100,
            )

            if st.button("💾 Сохранить изменения", key=f"save_{key_prefix}_{vacancy_id}_{idx}"):
                from client_actions import apply_client_update_from_web_form

                from vacancy_store import merge_vacancy_candidates_from_disk

                fresh = load_vacancies()
                merge_vacancy_candidates_from_disk(selected_vacancy, fresh.get("vacancies", []))
                apply_client_update_from_web_form(
                    cand,
                    new_status_label=new_status_label,
                    new_comment=new_comment,
                    final_verdict=final_verdict,
                    show_interview_fields=show_interview_fields,
                    new_date=new_date,
                    new_time=new_time,
                    remote_interview=remote_interview,
                    office_interview=office_interview,
                    vacancy=selected_vacancy,
                )
                for v in fresh.get("vacancies", []):
                    if v.get("id") == selected_vacancy.get("id"):
                        v["candidates"] = selected_vacancy.get("candidates", [])
                        break
                save_vacancies(fresh)
                st.session_state[collapse_key] = True
                st.success(f"Изменения для {cand.get('name', 'кандидата')} сохранены!")
                st.rerun()

    st.caption("Нажмите на строку кандидата, чтобы развернуть карточку и сохранить изменения.")
