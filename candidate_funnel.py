"""Подзона «Кандидаты» — воронка и автоматизация."""

import json
import uuid
from datetime import datetime

import streamlit as st

from models import (
    HR_STAGES,
    HR_STAGE_ORDER_UI,
    CLIENT_ZONE_ENTRY_STAGE,
    OFFER_STAGE,
    INTERNSHIP_STAGE,
    STARTED_WORK_STAGE,
    set_hr_stage,
    CLIENT_STATUS_LABELS,
    sync_hr_stage_from_client_status,
    get_stage_tone,
    format_stage_option,
    format_stage_title_label,
    stage_for_selectbox,
    sort_candidates_for_list,
    migrate_candidate,
    is_rejection_stage,
    is_visible_in_client_zone,
)
from resume_ai import (
    extract_data_from_resume,
    evaluate_resume_with_ai,
    fetch_resume_text_from_url,
    build_candidate_questionnaire_from_template,
    enrich_questionnaire_with_resume_hints,
    enrich_questionnaire_with_personal_followups,
    copy_vacancy_questionnaire_template,
    questionnaire_to_prompt_text,
)
from eval_ui import (
    control_word_badge_html,
    render_ai_score_badge,
    render_ai_evaluation_block,
    render_structured_ai_comment,
)
from telegram_notify import (
    validate_primary_fields,
)
import telegram_client as telegram_client_module
from questionnaire_grid import (
    invalidate_interview_questionnaire_cache,
    render_interview_questionnaire_grid,
)
from interview_schedule import (
    build_time_options,
    validate_interview_schedule,
    reset_reminders_if_schedule_changed,
    format_interview_display,
    sync_interview_calendar,
    INTERVIEW_STAGE,
)
from vacancy_store import vacancy_control_word, vacancy_show_portfolio_field
from warranty import (
    WARRANTY_MONTH_CHOICES,
    WARRANTY_MONTH_LABELS,
    WARRANTY_TRIGGER_STAGES,
    apply_warranty_to_vacancy,
    format_warranty_countdown,
    migrate_vacancy_warranty,
    warranty_date_field_label,
)
from app_settings import get_default_warranty_months
from resume_ai import yandex_link_for_display


def new_candidate_template(vacancy_id):
    return {
        "id": str(uuid.uuid4()),
        "vacancy_id": vacancy_id,
        "name": "",
        "resume_link": "",
        "hh_resume_link": "",
        "portfolio_link": "",
        "video_link": "",
        "task_link": "",
        "extra_materials": [],
        "transcript": "",
        "hr_comment": "",
        "interview_eval_notes": "",
        "client_status": "wait",
        "client_comment": "",
        "office_interview_date": "",
        "office_interview_time": "",
        "client_final_verdict": "",
        "ai_score": None,
        "ai_comment": "",
        "ai_comment_sections": {},
        "ai_strengths": [],
        "ai_weaknesses": [],
        "control_word_status": "",
        "control_word_match": "",
        "control_word_note": "",
        "created_at": datetime.now().isoformat(),
        "viewed": False,
        "status_updated_at": datetime.now().isoformat(),
        "remote_interview": False,
        "office_interview": False,
        "ignore_flags": None,
        "profile_checked": False,
        "ai_profile_requirements_met": {},
        "ai_flags_applied": [],
        "phone": "",
        "age": "",
        "city": "",
        "metro": "",
        "salary_expected": "",
        "age_location": "",
        "resume_text": "",
        "hr_stage": "resume_screening",
        "hr_stage_history": [],
        "ai_score_source": None,
        "interview_focus_questions": [],
        "interview_questionnaire": [],
        "cold_screening": False,
        "interview_schedule_key": "",
        "interview_reminder_30_sent": False,
        "interview_reminder_10_sent": False,
        "interview_reminder_60_sent": False,
        "feedback_reminder_last_sent_at": "",
        "think_long_reminder_sent": False,
        "calendar_event_id": "",
    }


def _would_delete_calendar_on_stage_change(cand, target_stage, current_stage):
    """True, если при фиксации этапа будет удалено событие из Google Calendar."""
    if target_stage == INTERVIEW_STAGE:
        return False
    if current_stage == INTERVIEW_STAGE:
        return True
    return bool(cand.get("calendar_event_id"))


def _apply_calendar_sync(cand, vacancy, previous_stage=None, keep_calendar_event=False):
    ok, msg = sync_interview_calendar(
        cand, vacancy["title"], previous_stage, keep_calendar_event=keep_calendar_event
    )
    return ok, msg


def populate_from_resume(cand, resume_text, client, config, vacancy=None):
    control = vacancy_control_word(vacancy) if vacancy is not None else None
    data = extract_data_from_resume(
        resume_text, client, config, control_word=control
    )
    cand["name"] = data.get("name", cand.get("name", ""))
    cand["phone"] = data.get("phone", "")
    cand["age"] = data.get("age", "")
    cand["city"] = data.get("city", "")
    cand["metro"] = data.get("metro", "")
    cand["age_location"] = data.get("age_location", "")
    cand["salary_expected"] = data.get("salary_expected", "")
    cand["resume_text"] = resume_text
    if control:
        cand["control_word_status"] = data.get("control_word_status", "")
        cand["control_word_match"] = data.get("control_word_match", "")
        cand["control_word_note"] = data.get("control_word_note", "")
    else:
        cand["control_word_status"] = ""
        cand["control_word_match"] = ""
        cand["control_word_note"] = ""


def _load_candidate_resume_text(cand, deps):
    """Текст резюме из карточки или по ссылке. Возвращает (text, error)."""
    resume_text = (cand.get("resume_text") or "").strip()
    if resume_text:
        return resume_text, ""
    if not (cand.get("resume_link") or "").strip():
        return "", ""
    with st.spinner("Загрузка резюме по ссылке…"):
        resume_text, err = fetch_resume_text_from_url(
            cand["resume_link"],
            deps["extract_text_from_pdf_url"],
            deps.get("transcribe_video_from_link"),
        )
    if resume_text:
        cand["resume_text"] = resume_text
    return resume_text, err


_LINK_WIDGET_FIELDS = ("resume_link", "video_link", "task_link", "hh_resume_link")
_LINK_OPEN_WIDGET_FIELDS = ("resume_open", "video_open", "task_open")


def _link_widget_rev_key(vacancy_id):
    return f"yd_widget_rev_{vacancy_id}"


def bump_vacancy_link_widget_revision(vacancy_id):
    key = _link_widget_rev_key(vacancy_id)
    st.session_state[key] = int(st.session_state.get(key, 0) or 0) + 1


def _reload_vacancy_from_disk(vacancy, deps):
    fresh = next((v for v in deps["load_vacancies"]() if v["id"] == vacancy["id"]), None)
    if not fresh:
        return vacancy
    vacancy["candidates"] = fresh.get("candidates", vacancy.get("candidates", []))
    if isinstance(fresh.get("yandex_disk"), dict):
        vacancy["yandex_disk"] = fresh["yandex_disk"]
    return vacancy


def _sync_candidate_link_widgets(vacancy, cand):
    """Подставляет в поля карточки ссылки из базы (после синхронизации с Диском)."""
    for field in _LINK_WIDGET_FIELDS:
        db_val = (cand.get(field) or "").strip()
        if not db_val:
            continue
        key = _card_key(vacancy, cand, field)
        widget_val = str(st.session_state.get(key, "") or "").strip()
        if widget_val != db_val:
            st.session_state[key] = db_val


def refresh_vacancy_link_widgets(vacancy):
    for cand in vacancy.get("candidates", []):
        _sync_candidate_link_widgets(vacancy, cand)


def _card_key(vacancy, cand, field):
    """Уникальный ключ виджета: вакансия + кандидат (не индекс в списке)."""
    cid = cand.get("id") or "unknown"
    base = f"c_{vacancy['id']}_{cid}_{field}"
    if field in _LINK_WIDGET_FIELDS or field in _LINK_OPEN_WIDGET_FIELDS:
        rev = int(st.session_state.get(_link_widget_rev_key(vacancy["id"]), 0) or 0)
        return f"{base}_r{rev}"
    return base


def _send_primary_candidate_to_chat(vacancy, cand):
    return telegram_client_module.send_primary_candidate_to_chat(vacancy, cand)


def _send_extra_material_to_chat(vacancy, cand, title, url):
    return telegram_client_module.send_extra_material_to_chat(vacancy, cand, title, url)


def _candidates_snapshot_key(vacancy_id):
    return f"_cands_saved_snapshot_{vacancy_id}"


_CAND_FUNNEL_RERUN_KEY = "_cand_funnel_rerun"
_CAND_FUNNEL_FLASH_KEY = "_cand_funnel_flash"


def _request_candidates_rerun():
    st.session_state[_CAND_FUNNEL_RERUN_KEY] = True


def _flush_candidates_rerun():
    if st.session_state.pop(_CAND_FUNNEL_RERUN_KEY, False):
        st.rerun()


def _set_cand_funnel_flash(message, level="success"):
    st.session_state[_CAND_FUNNEL_FLASH_KEY] = (level, message)


def _render_cand_funnel_flash():
    flash = st.session_state.pop(_CAND_FUNNEL_FLASH_KEY, None)
    if not flash:
        return
    level, message = flash
    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)


def _candidates_snapshot(candidates):
    items = []
    for cand in sorted(candidates, key=lambda c: c.get("id") or ""):
        items.append({k: cand.get(k) for k in sorted(cand.keys())})
    return json.dumps(items, sort_keys=True, ensure_ascii=False, default=str)


def _ensure_candidates_snapshot(vacancy_id, candidates):
    key = _candidates_snapshot_key(vacancy_id)
    if key not in st.session_state:
        st.session_state[key] = _candidates_snapshot(candidates)


def _mark_candidates_snapshot(vacancy_id, candidates):
    st.session_state[_candidates_snapshot_key(vacancy_id)] = _candidates_snapshot(
        candidates
    )


def _has_unsaved_candidate_changes(vacancy_id, candidates):
    key = _candidates_snapshot_key(vacancy_id)
    saved = st.session_state.get(key)
    if saved is None:
        return False
    return saved != _candidates_snapshot(candidates)


def _persist_vacancy_candidates(vacancy, deps, *, candidates=None):
    """Сохраняет кандидатов вакансии в БД (с подтягиванием правок из Telegram)."""
    from vacancy_store import merge_vacancy_candidates_from_disk

    vacancies = deps["load_vacancies"]()
    merge_vacancy_candidates_from_disk(vacancy, vacancies)
    deps["save_vacancies"](vacancies)
    snapshot_source = candidates if candidates is not None else vacancy.get("candidates", [])
    _mark_candidates_snapshot(vacancy["id"], snapshot_source)


def _render_candidate_resume_links(cand, k, vacancy, deps):
    """Ссылки на резюме: компактный вид с кнопками или режим редактирования."""
    edit_key = k("edit_resume_links")
    resume_url = (cand.get("resume_link") or "").strip()
    hh_url = (cand.get("hh_resume_link") or "").strip()
    has_links = bool(resume_url or hh_url)

    if edit_key not in st.session_state:
        st.session_state[edit_key] = not has_links

    if st.session_state[edit_key]:
        rcol1, rcol2 = st.columns([3, 1])
        with rcol1:
            cand["resume_link"] = st.text_input(
                "Ссылка на резюме", value=cand.get("resume_link", ""), key=k("resume")
            )
        with rcol2:
            st.write("")
            st.write("")
            resume_open = yandex_link_for_display((cand.get("resume_link") or "").strip())
            st.link_button(
                "Открыть PDF резюме",
                resume_open or "about:blank",
                disabled=not resume_open,
                key=k("resume_open"),
                use_container_width=True,
            )
        hhcol1, hhcol2 = st.columns([3, 1])
        with hhcol1:
            cand["hh_resume_link"] = st.text_input(
                "Ссылка на резюме HH.ru",
                value=cand.get("hh_resume_link", ""),
                key=k("hh_resume"),
            )
        with hhcol2:
            st.write("")
            st.write("")
            hh_open = (cand.get("hh_resume_link") or "").strip()
            st.link_button(
                "Открыть резюме на HH.ru",
                hh_open or "about:blank",
                disabled=not hh_open,
                key=k("hh_resume_open"),
                use_container_width=True,
            )
        if st.button("Готово", key=k("links_done")):
            st.session_state[edit_key] = False
            _persist_vacancy_candidates(vacancy, deps)
            _request_candidates_rerun()
        return

    buttons = []
    if resume_url:
        buttons.append(("resume", "Открыть PDF резюме", yandex_link_for_display(resume_url)))
    if hh_url:
        buttons.append(("hh", "Открыть резюме на HH.ru", hh_url))
    buttons.append(("edit", "Редактировать ссылки", None))

    cols = st.columns(len(buttons))
    for col, (kind, label, url) in zip(cols, buttons):
        with col:
            if kind == "edit":
                if st.button(label, key=k("links_edit"), use_container_width=True):
                    st.session_state[edit_key] = True
                    _request_candidates_rerun()
            else:
                st.link_button(label, url, key=k(f"{kind}_open_compact"), use_container_width=True)


def render_stage_badge(stage):
    label = HR_STAGES.get(stage, stage)
    return (
        f'<span style="background:#e2e8f0;color:#334155;padding:0.15rem 0.5rem;'
        f'border-radius:999px;font-size:0.75rem;font-weight:600;">{label}</span>'
    )


def render_candidate_card(vacancy, cand, idx, deps, *, archive_mode=False):
    _sync_candidate_link_widgets(vacancy, cand)
    k = lambda field: _card_key(vacancy, cand, field)
    current_stage = cand.get("hr_stage", "resume_screening")
    stage_tone = get_stage_tone(current_stage)

    title_parts = [cand.get("name", "Без имени")]
    created = (cand.get("created_at") or "")[:10]
    if created:
        title_parts.append(f"Добавлен {created}")
    title_parts.append(format_stage_title_label(current_stage))
    if current_stage == INTERVIEW_STAGE:
        interview_when = format_interview_display(
            cand.get("office_interview_date"),
            cand.get("office_interview_time"),
        )
        if interview_when != "—":
            title_parts.append(interview_when)
    if cand.get("ai_score") is not None:
        title_parts.append(f"{cand['ai_score']}/4")
    cw = (cand.get("control_word_status") or "").strip()
    if cw == "exact":
        title_parts.append("🔑 слово")
    elif cw == "fuzzy":
        title_parts.append("🔑≈ слово")
    elif cw == "missing":
        title_parts.append("без слова")
    elif cw == "no_cover_letter":
        title_parts.append("нет письма")

    if stage_tone:
        cid = cand.get("id", "unknown")
        st.markdown(
            f'<div class="cand-stage-marker cand-stage-{stage_tone}" id="cand-stage-{cid}"></div>',
            unsafe_allow_html=True,
        )

    collapse_key = k("collapse_after_stage")
    expander_rev_key = k("expander_rev")
    stage_info_key = k("stage_info")
    if st.session_state.pop(collapse_key, False):
        st.session_state[expander_rev_key] = st.session_state.get(expander_rev_key, 0) + 1
    expander_rev = st.session_state.get(expander_rev_key, 0)
    if st.session_state.get(stage_info_key):
        st.info(st.session_state.pop(stage_info_key))

    exp_key = k(f"exp_{expander_rev}")
    with st.expander(
        " · ".join(title_parts),
        expanded=False,
        key=exp_key,
    ):
        c1, c2 = st.columns([3, 1])
        with c1:
            cand["name"] = st.text_input("ФИО", value=cand.get("name", ""), key=k("name"))
            cand["phone"] = st.text_input("Телефон", value=cand.get("phone", ""), key=k("phone"))
            col_a, col_b = st.columns(2)
            with col_a:
                cand["age"] = st.text_input("Возраст", value=cand.get("age", ""), key=k("age"))
                cand["city"] = st.text_input("Город", value=cand.get("city", ""), key=k("city"))
            with col_b:
                cand["metro"] = st.text_input("Метро", value=cand.get("metro", ""), key=k("metro"))
                cand["salary_expected"] = st.text_input(
                    "Желаемая з/п", value=cand.get("salary_expected", ""), key=k("salary")
                )
            _render_candidate_resume_links(cand, k, vacancy, deps)
            vcol1, vcol2 = st.columns([3, 1])
            with vcol1:
                cand["video_link"] = st.text_input(
                    "Запись собеседования",
                    value=cand.get("video_link", ""),
                    key=k("video"),
                )
            with vcol2:
                st.write("")
                st.write("")
                video_open = yandex_link_for_display((cand.get("video_link") or "").strip())
                st.link_button(
                    "Открыть запись",
                    video_open or "about:blank",
                    disabled=not video_open,
                    key=k("video_open"),
                    use_container_width=True,
                )
            if vacancy_show_portfolio_field(vacancy):
                cand["portfolio_link"] = st.text_input(
                    "Портфолио",
                    value=cand.get("portfolio_link", ""),
                    key=k("portfolio"),
                    help="Ссылка на портфолио кандидата — попадёт в Telegram при отправке в чат.",
                )
            cand["hr_comment"] = st.text_area(
                "Комментарий HR", value=cand.get("hr_comment", ""), key=k("hr_comment"), height=80
            )
            tcol1, tcol2 = st.columns([3, 1])
            with tcol1:
                cand["task_link"] = st.text_input(
                    "Тестовое задание",
                    value=cand.get("task_link", ""),
                    key=k("task"),
                )
            with tcol2:
                st.write("")
                st.write("")
                task_open = yandex_link_for_display((cand.get("task_link") or "").strip())
                st.link_button(
                    "Открыть задание",
                    task_open or "about:blank",
                    disabled=not task_open,
                    key=k("task_open"),
                    use_container_width=True,
                )

            st.markdown("##### Доп. материал в чат")
            st.caption(
                "Запись онлайн-встречи, повторное задание и т.п. — reply на карточку кандидата "
                "и обновление основной карточки в Telegram."
            )
            mat_form_rev_key = k("extra_mat_form_rev")
            mat_form_rev = int(st.session_state.get(mat_form_rev_key, 0) or 0)
            mat_title = st.text_input(
                "Название материала",
                value="",
                key=k(f"extra_mat_title_r{mat_form_rev}"),
                placeholder="Например: запись собеседования с Викторией",
            )
            mat_url = st.text_input(
                "Ссылка на материал",
                value="",
                key=k(f"extra_mat_url_r{mat_form_rev}"),
                placeholder="https://… или yadisk:…",
            )
            if st.button(
                "📎 Отправить материал в чат",
                key=k("extra_mat_send"),
                use_container_width=True,
            ):
                ok, tg_msg = _send_extra_material_to_chat(
                    vacancy, cand, mat_title, mat_url
                )
                if ok:
                    _persist_vacancy_candidates(vacancy, deps)
                    st.session_state[mat_form_rev_key] = mat_form_rev + 1
                    _set_cand_funnel_flash(tg_msg, "success")
                    _request_candidates_rerun()
                else:
                    st.error(tg_msg)

            materials = cand.get("extra_materials") or []
            if isinstance(materials, list) and materials:
                st.caption("Уже отправлено:")
                for idx, item in enumerate(materials):
                    if not isinstance(item, dict):
                        continue
                    title = (item.get("title") or "Материал").strip()
                    url = yandex_link_for_display((item.get("url") or "").strip())
                    sent = (item.get("sent_at") or "")[:16].replace("T", " ")
                    mcol1, mcol2 = st.columns([3, 1])
                    with mcol1:
                        st.markdown(f"• **{title}**" + (f" · {sent}" if sent else ""))
                    with mcol2:
                        st.link_button(
                            "Открыть",
                            url or "about:blank",
                            disabled=not url,
                            key=k(f"extra_mat_open_{idx}"),
                            use_container_width=True,
                        )

            if st.button("📨 Отправить в общий чат", key=k("tg_primary"), type="primary"):
                missing = validate_primary_fields(cand)
                if missing:
                    st.warning("Заполните поле: " + ", ".join(missing))
                else:
                    ok, tg_msg = _send_primary_candidate_to_chat(vacancy, cand)
                    if ok:
                        set_hr_stage(cand, CLIENT_ZONE_ENTRY_STAGE, "отправка в Telegram")
                        _persist_vacancy_candidates(vacancy, deps)
                        flash_msg = f"{tg_msg} Статус HR: «На оценке у заказчика»."
                        _set_cand_funnel_flash(
                            flash_msg,
                            "success" if "кнопками" in tg_msg else "warning",
                        )
                        st.session_state[collapse_key] = True
                        _request_candidates_rerun()
                    else:
                        st.error(tg_msg)

            client_label = CLIENT_STATUS_LABELS.get(cand.get("client_status", "wait"), "—")
            st.caption(f"Статус заказчика: **{client_label}**")
            if cand.get("client_comment"):
                st.caption(f"Комментарий заказчика: {cand['client_comment']}")

            client_status = cand.get("client_status", "wait")
            if is_visible_in_client_zone(cand) and client_status == "wait":
                if st.button("🔔 Напомнить о кандидате", key=k("tg_remind_eval"), use_container_width=True):
                    ok, tg_msg = telegram_client_module.send_candidate_reminder_to_chat(
                        vacancy, cand, kind="evaluate"
                    )
                    if ok:
                        st.success("Напоминание отправлено в чат!")
                    else:
                        st.error(tg_msg)
            if client_status == "think":
                if st.button(
                    "🔔 Напомнить принять решение",
                    key=k("tg_remind_decide"),
                    use_container_width=True,
                ):
                    ok, tg_msg = telegram_client_module.send_candidate_reminder_to_chat(
                        vacancy, cand, kind="decide"
                    )
                    if ok:
                        st.success("Напоминание отправлено в чат!")
                    else:
                        st.error(tg_msg)

            if cand.get("ai_score") is not None:
                st.markdown(render_ai_score_badge(cand["ai_score"]), unsafe_allow_html=True)
                render_structured_ai_comment(cand, expanded=False)
            badge = control_word_badge_html(cand)
            if badge:
                st.markdown(badge, unsafe_allow_html=True)
                if cand.get("control_word_note"):
                    st.caption(cand["control_word_note"])
            interview_q = cand.get("interview_questionnaire") or []
            legacy_focus = False
            if not interview_q and cand.get("interview_focus_questions"):
                interview_q = [
                    {"вопрос": q, "уточняющие_вопросы": [], "пример_ответа": ""}
                    for q in cand["interview_focus_questions"]
                ]
                legacy_focus = True
            if interview_q:
                if legacy_focus:
                    with st.expander(
                        "Вопросы (от ИИ) для собеседования этого кандидата",
                        expanded=False,
                    ):
                        for i, q in enumerate(interview_q, 1):
                            deps["render_questionnaire_item"](i, q)
                else:
                    if render_interview_questionnaire_grid(cand, k("iq")):
                        _request_candidates_rerun()

            cand["transcript"] = st.text_area(
                "Расшифровка интервью",
                value=cand.get("transcript", ""),
                height=120,
                key=k("transcript"),
            )

        with c2:
            stage_for_select = stage_for_selectbox(current_stage)
            stage_idx = HR_STAGE_ORDER_UI.index(stage_for_select)
            picked_stage = st.selectbox(
                "Текущий статус кандидата",
                HR_STAGE_ORDER_UI,
                index=stage_idx,
                format_func=format_stage_option,
                key=k("stage"),
            )
            stage_note = st.text_input("Примечание к этапу", key=k("stage_note"))

            show_interview_fields = (
                picked_stage == INTERVIEW_STAGE or current_stage == INTERVIEW_STAGE
            )
            if show_interview_fields:
                date_str = cand.get("office_interview_date", "")
                try:
                    date_val = (
                        datetime.strptime(date_str, "%Y-%m-%d").date()
                        if date_str
                        else None
                    )
                except ValueError:
                    date_val = None
                new_date = st.date_input(
                    "Дата первичного собеседования",
                    value=date_val,
                    key=k("int_date"),
                    format="DD.MM.YYYY",
                )
                time_options = build_time_options()
                current_time = cand.get("office_interview_time", "")
                time_idx = (
                    time_options.index(current_time)
                    if current_time in time_options
                    else 0
                )
                new_time = st.selectbox(
                    "Время первичного собеседования",
                    time_options,
                    index=time_idx,
                    format_func=lambda x: x or "— Выберите —",
                    key=k("int_time"),
                )
                cand["office_interview_date"] = (
                    new_date.strftime("%Y-%m-%d") if new_date else ""
                )
                cand["office_interview_time"] = new_time or ""
                missing_sched = validate_interview_schedule(
                    cand["office_interview_date"], cand["office_interview_time"]
                )
                if missing_sched:
                    st.markdown(
                        f'<p style="color:#b91c1c;font-weight:600;">'
                        f"Заполните: {', '.join(missing_sched)}</p>",
                        unsafe_allow_html=True,
                    )
                else:
                    reset_reminders_if_schedule_changed(
                        cand,
                        cand["office_interview_date"],
                        cand["office_interview_time"],
                    )
                    st.caption(
                        f"Собеседование: **{format_interview_display(cand['office_interview_date'], cand['office_interview_time'])}**"
                    )
                    if cand.get("calendar_event_id"):
                        st.caption("📅 Событие в Google Calendar создано")

            if cand.get("hr_stage_history"):
                with st.expander("История этапов"):
                    for h in reversed(cand["hr_stage_history"]):
                        at = (h.get("at") or "")[:16].replace("T", " ")
                        note = h.get("note") or ""
                        st.caption(f"{at} — {HR_STAGES.get(h.get('stage'), h.get('stage', ''))}" + (f" ({note})" if note else ""))

            suggested = sync_hr_stage_from_client_status(cand)
            show_keep_calendar = (
                _would_delete_calendar_on_stage_change(cand, picked_stage, current_stage)
                or (
                    suggested
                    and suggested != cand.get("hr_stage")
                    and _would_delete_calendar_on_stage_change(
                        cand, suggested, cand.get("hr_stage")
                    )
                )
            )
            keep_calendar_event = False
            if show_keep_calendar:
                keep_calendar_event = st.checkbox(
                    "Не удалять событие из Google Calendar",
                    key=k("keep_cal_event"),
                    help="При смене этапа событие в календаре останется без изменений",
                )

            warranty_start_date = None
            warranty_months = get_default_warranty_months()
            show_warranty_fields = (
                picked_stage in WARRANTY_TRIGGER_STAGES
                or current_stage in WARRANTY_TRIGGER_STAGES
            )
            if show_warranty_fields:
                migrate_vacancy_warranty(vacancy)
                w = vacancy.get("warranty") or {}
                w_cand_match = w.get("candidate_id") == cand.get("id")
                w_start_raw = (w.get("start_date") or "")[:10] if w_cand_match else ""
                try:
                    w_start_default = (
                        datetime.strptime(w_start_raw, "%Y-%m-%d").date()
                        if w_start_raw
                        else datetime.now().date()
                    )
                except ValueError:
                    w_start_default = datetime.now().date()
                if w_cand_match and w.get("months") in WARRANTY_MONTH_CHOICES:
                    w_months_default = w.get("months")
                else:
                    w_months_default = get_default_warranty_months()
                label_stage = (
                    picked_stage
                    if picked_stage in WARRANTY_TRIGGER_STAGES
                    else current_stage
                )
                st.markdown("**Гарантия**")
                st.caption(
                    "Дата и срок фиксируются при этапах «Оффер», «Выход на стажировку» "
                    "или «Выход на работу». Месяц = 30 дней."
                )
                if w_cand_match and w_start_raw and label_stage in (
                    INTERNSHIP_STAGE,
                    STARTED_WORK_STAGE,
                ):
                    st.caption(
                        "Дата подставлена из предыдущего этапа — при необходимости "
                        "скорректируйте; от неё считается срок гарантии."
                    )
                warranty_start_date = st.date_input(
                    warranty_date_field_label(label_stage),
                    value=w_start_default,
                    key=k("warranty_start"),
                    format="DD.MM.YYYY",
                )
                warranty_months = st.selectbox(
                    "Срок гарантии",
                    WARRANTY_MONTH_CHOICES,
                    index=WARRANTY_MONTH_CHOICES.index(w_months_default),
                    format_func=lambda m: WARRANTY_MONTH_LABELS.get(m, f"{m} мес"),
                    key=k("warranty_months"),
                )
                active_countdown = format_warranty_countdown(vacancy)
                if active_countdown:
                    st.caption(active_countdown)

            if st.button("Зафиксировать этап", key=k("stage_btn")):
                target_stage = picked_stage
                if target_stage == INTERVIEW_STAGE:
                    missing_sched = validate_interview_schedule(
                        cand.get("office_interview_date"),
                        cand.get("office_interview_time"),
                    )
                    if missing_sched:
                        st.warning("Заполните поле: " + ", ".join(missing_sched))
                        target_stage = None
                if target_stage and target_stage != cand.get("hr_stage"):
                    if target_stage in WARRANTY_TRIGGER_STAGES and not warranty_start_date:
                        st.warning("Укажите дату начала отсчёта гарантии.")
                    else:
                        prev_stage = cand.get("hr_stage")
                        set_hr_stage(cand, target_stage, stage_note)
                        if target_stage in WARRANTY_TRIGGER_STAGES:
                            apply_warranty_to_vacancy(
                                vacancy,
                                cand,
                                warranty_start_date,
                                warranty_months,
                                target_stage,
                            )
                        if target_stage == INTERVIEW_STAGE:
                            reset_reminders_if_schedule_changed(
                                cand,
                                cand.get("office_interview_date"),
                                cand.get("office_interview_time"),
                            )
                        cal_ok, cal_msg = _apply_calendar_sync(
                            cand,
                            vacancy,
                            previous_stage=prev_stage,
                            keep_calendar_event=keep_calendar_event,
                        )
                        _persist_vacancy_candidates(vacancy, deps)
                        if cal_msg:
                            _set_cand_funnel_flash(
                                cal_msg if cal_ok else f"Google Calendar: {cal_msg}",
                                "success" if cal_ok else "warning",
                            )
                        if suggested and target_stage != suggested:
                            st.session_state[stage_info_key] = (
                                f"Рекомендуемый этап по статусу заказчика: {HR_STAGES[suggested]}"
                            )
                        st.session_state[collapse_key] = True
                        _request_candidates_rerun()
                elif target_stage:
                    if current_stage == INTERVIEW_STAGE:
                        reset_reminders_if_schedule_changed(
                            cand,
                            cand.get("office_interview_date"),
                            cand.get("office_interview_time"),
                        )
                        cal_ok, cal_msg = _apply_calendar_sync(
                            cand,
                            vacancy,
                            previous_stage=INTERVIEW_STAGE,
                            keep_calendar_event=keep_calendar_event,
                        )
                        _persist_vacancy_candidates(vacancy, deps)
                        if cal_msg:
                            _set_cand_funnel_flash(
                                cal_msg if cal_ok else f"Google Calendar: {cal_msg}",
                                "success" if cal_ok else "warning",
                            )
                        st.session_state[collapse_key] = True
                        _request_candidates_rerun()
                    else:
                        if (
                            target_stage in WARRANTY_TRIGGER_STAGES
                            and warranty_start_date
                        ):
                            apply_warranty_to_vacancy(
                                vacancy,
                                cand,
                                warranty_start_date,
                                warranty_months,
                                target_stage,
                            )
                            _persist_vacancy_candidates(vacancy, deps)
                            _set_cand_funnel_flash("Параметры гарантии сохранены.")
                            st.session_state[collapse_key] = True
                            _request_candidates_rerun()
                        else:
                            st.caption("Статус без изменений.")

            if suggested and cand.get("hr_stage") != suggested:
                if st.button("↔ Применить этап по статусу заказчика", key=k("sync")):
                    prev_stage = cand.get("hr_stage")
                    set_hr_stage(cand, suggested, "синхронизация с client_status")
                    if suggested == INTERVIEW_STAGE:
                        reset_reminders_if_schedule_changed(
                            cand,
                            cand.get("office_interview_date"),
                            cand.get("office_interview_time"),
                        )
                    cal_ok, cal_msg = _apply_calendar_sync(
                        cand,
                        vacancy,
                        previous_stage=prev_stage,
                        keep_calendar_event=keep_calendar_event,
                    )
                    _persist_vacancy_candidates(vacancy, deps)
                    if cal_msg:
                        _set_cand_funnel_flash(
                            cal_msg if cal_ok else f"Google Calendar: {cal_msg}",
                            "success" if cal_ok else "warning",
                        )
                    st.session_state[collapse_key] = True
                    _request_candidates_rerun()

            if (cand.get("resume_text") or "").strip():
                st.caption("Резюме: текст сохранён в карточке кандидата.")
            elif (cand.get("resume_link") or "").strip():
                st.caption("Резюме: будет загружено по ссылке при оценке.")
            else:
                st.caption("Резюме: нет текста и ссылки — оценка недоступна.")

            if not deps["vacancy_has_profile"](vacancy):
                st.caption("Профиль вакансии не заполнен — оценка будет менее точной.")

            questionnaire_count = len(cand.get("interview_questionnaire") or [])
            if questionnaire_count:
                st.caption(
                    f"Опросник: {questionnaire_count} вопросов из шаблона вакансии "
                    f"+ уточнения по резюме."
                )

            eval_col, questionnaire_col = st.columns(2)

            with eval_col:
                if st.button("🤖 Оценить по резюме", key=k("eval_res")):
                    resume_text, err = _load_candidate_resume_text(cand, deps)
                    if err:
                        st.error(err)
                    elif resume_text:
                        profile = deps["get_vacancy_profile_text"](vacancy)
                        try:
                            with st.spinner("Оценка резюме… (~30 с)"):
                                ev = evaluate_resume_with_ai(
                                    resume_text,
                                    profile,
                                    vacancy["title"],
                                    deps["client"],
                                    deps["config"],
                                    hr_comment=cand.get("hr_comment", ""),
                                )
                            cand.update(ev)
                            _persist_vacancy_candidates(vacancy, deps)
                            score = ev.get("ai_score", "—")
                            _set_cand_funnel_flash(
                                f"Оценка {score}/4 сохранена для «{cand.get('name', 'кандидат')}»."
                            )
                            st.session_state[exp_key] = True
                            _request_candidates_rerun()
                        except Exception as e:
                            st.error(f"Ошибка оценки по резюме: {e}")
                    else:
                        st.warning(
                            "Нет текста резюме. Добавьте PDF/ссылку или загрузите кандидата через автозагрузку."
                        )

            with questionnaire_col:
                if st.button(
                    "📋 Сформировать опросник",
                    key=k("gen_q"),
                    help="Берёт вопросы из шаблона вакансии; ИИ добавит «В резюме» и персональные уточнения.",
                ):
                    resume_text, err = _load_candidate_resume_text(cand, deps)
                    if err:
                        st.error(err)
                    elif resume_text:
                        base_q = deps["parse_questionnaire_input"](
                            vacancy.get("documents", {}).get("questions", "")
                        )
                        if not base_q:
                            st.warning(
                                "Сначала заполните опросник в «Документы по вакансии» — "
                                "он будет одинаковым для всех кандидатов."
                            )
                        else:
                            try:
                                with st.spinner(
                                    "Опросник: шаблон вакансии + уточнения по резюме… (до 2 мин)"
                                ):
                                    invalidate_interview_questionnaire_cache(k("iq"))
                                    cand["interview_questionnaire"] = (
                                        build_candidate_questionnaire_from_template(
                                            resume_text,
                                            base_q,
                                            deps["client"],
                                            deps["config"],
                                            hr_comment=cand.get("hr_comment", ""),
                                            eval_comment=cand.get("ai_comment", ""),
                                            strengths=cand.get("ai_strengths", []),
                                            weaknesses=cand.get("ai_weaknesses", []),
                                        )
                                    )
                                _persist_vacancy_candidates(vacancy, deps)
                                q_count = len(cand.get("interview_questionnaire") or [])
                                _set_cand_funnel_flash(
                                    f"Опросник ({q_count} вопросов из шаблона) сохранён для "
                                    f"«{cand.get('name', 'кандидат')}»."
                                )
                                st.session_state[exp_key] = True
                                _request_candidates_rerun()
                            except Exception as e:
                                st.error(f"Ошибка формирования опросника: {e}")
                    else:
                        st.warning("Нет текста резюме — опросник нельзя сформировать.")

                questionnaire_count = len(cand.get("interview_questionnaire") or [])
                if questionnaire_count and st.button(
                    "🔄 Обновить по резюме",
                    key=k("refresh_resume_hints"),
                    help="Перезаполнить «В резюме» и персональные уточнения по текущему резюме",
                ):
                    resume_text, err = _load_candidate_resume_text(cand, deps)
                    if err:
                        st.error(err)
                    elif resume_text:
                        try:
                            base_q = deps["parse_questionnaire_input"](
                                vacancy.get("documents", {}).get("questions", "")
                            )
                            with st.spinner("Обновление по резюме…"):
                                if base_q:
                                    invalidate_interview_questionnaire_cache(k("iq"))
                                    cand["interview_questionnaire"] = (
                                        copy_vacancy_questionnaire_template(base_q)
                                    )
                                elif not cand.get("interview_questionnaire"):
                                    st.warning(
                                        "Нет шаблона и опросника — сначала сформируйте опросник."
                                    )
                                if cand.get("interview_questionnaire"):
                                    cand["interview_questionnaire"] = (
                                        enrich_questionnaire_with_resume_hints(
                                            resume_text,
                                            cand["interview_questionnaire"],
                                            deps["client"],
                                            deps["config"],
                                        )
                                    )
                                    cand["interview_questionnaire"] = (
                                        enrich_questionnaire_with_personal_followups(
                                            resume_text,
                                            cand["interview_questionnaire"],
                                            deps["client"],
                                            deps["config"],
                                            hr_comment=cand.get("hr_comment", ""),
                                            eval_comment=cand.get("ai_comment", ""),
                                            strengths=cand.get("ai_strengths", []),
                                            weaknesses=cand.get("ai_weaknesses", []),
                                        )
                                    )
                            if cand.get("interview_questionnaire"):
                                _persist_vacancy_candidates(vacancy, deps)
                                _set_cand_funnel_flash(
                                    f"Колонки «В резюме» и уточнения обновлены для "
                                    f"«{cand.get('name', 'кандидат')}»."
                                )
                                st.session_state[exp_key] = True
                                _request_candidates_rerun()
                        except Exception as e:
                            st.error(f"Ошибка обновления: {e}")
                    else:
                        st.warning("Нет текста резюме.")

            has_profile = deps["vacancy_has_profile"](vacancy)

            transcript_len = len((cand.get("transcript") or "").strip())
            video_url = (cand.get("video_link") or "").strip()
            if transcript_len:
                st.caption(f"Расшифровка интервью: {transcript_len} символов — можно оценивать.")
            elif video_url:
                st.caption(
                    "Расшифровка пуста — при нажатии «Оценить по интервью» "
                    "запись будет расшифрована и оценена автоматически (несколько минут)."
                )
            else:
                st.caption(
                    "Нет расшифровки и ссылки на запись. "
                    "Укажите «Запись собеседования» или вставьте текст в «Расшифровка интервью»."
                )

            cand["interview_eval_notes"] = st.text_area(
                "Уточнения для оценки по интервью",
                value=cand.get("interview_eval_notes", ""),
                height=72,
                key=k("interview_eval_notes"),
                placeholder='Например: «Возраст не критичен», «Опыт в Figma важнее Illustrator»',
                help="ИИ учтёт эти уточнения при оценке расшифровки. Общий «Комментарий HR» на оценку по интервью не влияет.",
            )

            if st.button(
                "🤖 Оценить по интервью",
                key=k("eval_int"),
                disabled=not has_profile,
            ):
                transcript_text = (cand.get("transcript") or "").strip()
                if not transcript_text and not video_url:
                    st.warning(
                        "Укажите ссылку в «Запись собеседования» "
                        "или вставьте текст в «Расшифровка интервью»."
                    )
                else:
                    transcribed_now = False
                    try:
                        if not transcript_text and video_url:
                            with st.spinner("Расшифровка записи…"):
                                transcript_text = deps["transcribe_video_from_link"](video_url) or ""
                            if not transcript_text:
                                st.error(
                                    "Не удалось расшифровать запись по ссылке. "
                                    "Проверьте ссылку (Яндекс.Диск) или вставьте текст вручную."
                                )
                            else:
                                cand["transcript"] = transcript_text
                                transcribed_now = True

                        if transcript_text:
                            resume_text = cand.get("resume_text") or ""
                            if not resume_text and cand.get("resume_link"):
                                with st.spinner("Загрузка резюме по ссылке…"):
                                    resume_text = deps["extract_text_from_pdf_url"](
                                        cand.get("resume_link", "")
                                    ) or ""
                                if resume_text:
                                    cand["resume_text"] = resume_text
                            interview_q_text = questionnaire_to_prompt_text(
                                cand.get("interview_questionnaire")
                            ) or deps["get_vacancy_questionnaire_text"](vacancy)
                            with st.spinner("Оценка по интервью… (1–2 мин)"):
                                ev = deps["evaluate_candidate_with_ai_v2"](
                                    resume_text,
                                    transcript_text,
                                    vacancy["title"],
                                    deps["get_vacancy_profile_text"](vacancy),
                                    cand.get("ignore_flags") or deps["default_ignore_flags"](),
                                    interview_q_text,
                                    interview_eval_notes=cand.get("interview_eval_notes", ""),
                                )
                            if not ev.get("ok", True):
                                st.error(
                                    f"Ошибка оценки по интервью: {ev.get('error') or ev.get('comment')}"
                                )
                            elif ev.get("score") is None:
                                st.error("ИИ не вернул оценку. Попробуйте ещё раз.")
                            else:
                                cand["ai_score"] = ev.get("score", 0)
                                cand["ai_score_source"] = "interview"
                                cand["ai_comment"] = ev.get("comment", "")
                                cand["ai_strengths"] = ev.get("strengths", [])
                                cand["ai_weaknesses"] = ev.get("weaknesses", [])
                                cand["ai_profile_requirements_met"] = ev.get(
                                    "profile_requirements_met", {}
                                )
                                cand["ai_flags_applied"] = ev.get("flags_applied", [])
                                cand["profile_checked"] = True
                                _persist_vacancy_candidates(vacancy, deps)
                                met = ev.get("profile_requirements_met") or {}
                                parts = [
                                    f"Оценка по интервью сохранена: {ev.get('score')}/4",
                                    f"hard {met.get('hard_skills', '—')}%",
                                    f"soft {met.get('soft_skills', '—')}%",
                                    f"опыт {met.get('experience', '—')}%",
                                ]
                                if transcribed_now:
                                    parts.append(
                                        f"расшифровка сохранена ({len(transcript_text)} симв.)"
                                    )
                                _set_cand_funnel_flash(". ".join(parts) + ".")
                                st.session_state[exp_key] = True
                                _request_candidates_rerun()
                    except Exception as e:
                        st.error(f"Ошибка оценки по интервью: {e}")

            if st.button("🗑️ Удалить", key=k("del")):
                return "delete"

        if archive_mode:
            with st.expander("📋 Скопировать в активную вакансию", expanded=False):
                from candidate_copy import render_copy_candidate_ui

                render_copy_candidate_ui(cand, vacancy, deps, key_prefix=k("copy"))

        render_ai_evaluation_block(cand)
    return None


def _is_rejected_candidate(cand):
    stage = cand.get("hr_stage", "resume_screening")
    return stage == "rejected" or is_rejection_stage(stage)


def _parse_bulk_link_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _append_bulk_candidate(
    vacancy,
    deps,
    resume_link="",
    hh_resume_link="",
    video_link="",
    resume_text=None,
    transcript="",
):
    """Создаёт кандидата при автозагрузке и заполняет карточку через ИИ при наличии текста."""
    cand = new_candidate_template(vacancy["id"])
    cand["resume_link"] = (resume_link or "").strip()
    cand["hh_resume_link"] = (hh_resume_link or "").strip()
    cand["video_link"] = (video_link or "").strip()
    cand["ignore_flags"] = deps["default_ignore_flags"]()
    text = (resume_text or "").strip()
    if (transcript or "").strip():
        cand["transcript"] = transcript.strip()
    if text:
        populate_from_resume(cand, text, deps["client"], deps["config"], vacancy=vacancy)
    cand["cold_screening"] = True
    cand["hr_stage"] = "resume_screening"
    vacancy["candidates"].append(cand)
    return cand


def _show_yandex_sync_result(result):
    if result.errors:
        for err in result.errors:
            st.error(err)
    if result.messages:
        for msg in result.messages[:20]:
            st.caption(f"• {msg}")
        if len(result.messages) > 20:
            st.caption(f"… и ещё {len(result.messages) - 20}")
    if result.created or result.updated:
        st.success(
            f"Синхронизация: добавлено {result.created}, обновлено {result.updated}."
        )
    elif not result.errors:
        st.info("Новых файлов для привязки не найдено.")


show_yandex_sync_result = _show_yandex_sync_result


def _flash_yandex_sync_result(result):
    if result.errors:
        _set_cand_funnel_flash(result.errors[0], "warning")
    elif result.created or result.updated:
        _set_cand_funnel_flash(
            f"Синхронизация с Яндекс.Диском: добавлено {result.created}, "
            f"обновлено {result.updated}.",
            "success",
        )
    elif not result.errors:
        _set_cand_funnel_flash("Новых файлов для привязки не найдено.", "info")


def finalize_yandex_sync_ui(vacancy, result):
    """Обновляет карточки после синхронизации без ручного F5."""
    _flash_yandex_sync_result(result)
    bump_vacancy_link_widget_revision(vacancy["id"])
    _mark_candidates_snapshot(vacancy["id"], vacancy.get("candidates", []))
    _request_candidates_rerun()


def run_yandex_disk_sync(vacancy, deps, *, ingest_new_resumes=None):
    """Синхронизирует папку на Диске и сохраняет настройки + seen_paths в базу."""
    from yandex_disk_ingest import (
        YandexSyncResult,
        migrate_vacancy_yandex_disk,
        sync_vacancy_yandex_disk,
    )

    migrate_vacancy_yandex_disk(vacancy)
    yd = vacancy["yandex_disk"]
    if ingest_new_resumes is None:
        ingest_new_resumes = bool(yd.get("ingest_new_resumes", True))
    root_url = (yd.get("root_url") or "").strip()
    if not root_url:
        result = YandexSyncResult()
        result.errors.append(
            "Не указана ссылка на папку. Задайте её в «Кандидаты» → «Автозагрузка»."
        )
        return result
    result = sync_vacancy_yandex_disk(
        vacancy, deps, ingest_new_resumes=ingest_new_resumes
    )
    _persist_vacancy_candidates(vacancy, deps)
    _reload_vacancy_from_disk(vacancy, deps)
    finalize_yandex_sync_ui(vacancy, result)
    return result


def render_bulk_intake(vacancy, deps):
    st.markdown("##### Автозагрузка")
    vid = vacancy["id"]
    from yandex_disk_ingest import (
        migrate_vacancy_yandex_disk,
        reset_yandex_disk_seen,
    )

    migrate_vacancy_yandex_disk(vacancy)
    yd = vacancy["yandex_disk"]

    with st.expander("📁 Папка на Яндекс.Диске (синхронизация с Mac)", expanded=True):
        st.caption(
            "Опубликуйте папку вакансии на Диске (доступ по ссылке). Структура: "
            "«Резюме» — PDF, «Записи» — видео, «Задания» — папки по имени кандидата. "
            "Файлы сопоставляются с кандидатами по имени в названии."
        )
        yd["root_url"] = st.text_input(
            "Ссылка на корень папки вакансии",
            value=yd.get("root_url", ""),
            key=f"yd_root_{vid}",
            placeholder="https://disk.yandex.ru/d/…",
        )
        c1, c2, c3 = st.columns(3)
        subs = yd.setdefault("subfolders", {})
        with c1:
            subs["resume"] = st.text_input(
                "Подпапка резюме",
                value=subs.get("resume", "Резюме"),
                key=f"yd_sub_res_{vid}",
            )
        with c2:
            subs["video"] = st.text_input(
                "Подпапка записей",
                value=subs.get("video", "Записи"),
                key=f"yd_sub_vid_{vid}",
            )
        with c3:
            subs["task"] = st.text_input(
                "Подпапка заданий",
                value=subs.get("task", "Задания"),
                key=f"yd_sub_task_{vid}",
            )
        yd["ingest_new_resumes"] = st.checkbox(
            "Создавать новых кандидатов из новых PDF в «Резюме»",
            value=bool(yd.get("ingest_new_resumes", True)),
            key=f"yd_new_{vid}",
        )
        b1, b2, b3 = st.columns(3)
        with b1:
            do_sync = st.button("🔄 Синхронизировать с Диском", key=f"yd_sync_{vid}")
        with b2:
            do_save_cfg = st.button("💾 Сохранить настройки", key=f"yd_save_{vid}")
        with b3:
            do_reset = st.button(
                "♻️ Сбросить историю",
                key=f"yd_reset_{vid}",
                help="Повторно проверить все файлы в папке",
            )
        if yd.get("last_sync_at"):
            st.caption(f"Последняя синхронизация: {yd['last_sync_at']}")

        if do_save_cfg:
            _persist_vacancy_candidates(vacancy, deps)
            st.success("Настройки папки сохранены.")

        if do_reset:
            reset_yandex_disk_seen(vacancy)
            _persist_vacancy_candidates(vacancy, deps)
            st.success("История синхронизации сброшена.")
            st.rerun()

        if do_sync:
            with st.spinner("Сканируем папку на Яндекс.Диске…"):
                run_yandex_disk_sync(
                    vacancy, deps, ingest_new_resumes=yd.get("ingest_new_resumes", True)
                )

    st.markdown("---")
    st.markdown("##### Загрузка по ссылкам вручную")
    success_key = f"bulk_success_{vid}"
    links_ver_key = f"bulk_links_v_{vid}"
    hh_links_ver_key = f"bulk_hh_links_v_{vid}"
    if links_ver_key not in st.session_state:
        st.session_state[links_ver_key] = 0
    if hh_links_ver_key not in st.session_state:
        st.session_state[hh_links_ver_key] = 0

    if st.session_state.get(success_key):
        st.markdown(
            '<div class="bulk-success-msg">Кандидаты успешно добавлены</div>',
            unsafe_allow_html=True,
        )
        st.session_state[success_key] = False

    links_key = f"bulk_links_{vid}_{st.session_state[links_ver_key]}"
    hh_links_key = f"bulk_hh_links_{vid}_{st.session_state[hh_links_ver_key]}"
    links = st.text_area(
        "Ссылки на PDF или видео на Яндекс.Диске (по строке)",
        height=80,
        key=links_key,
    )
    hh_links = st.text_area(
        "Ссылки на резюме HH.ru (по строке)",
        height=80,
        key=hh_links_key,
        help="Строка 1 объединяется со строкой 1 из PDF, строка 2 — со строкой 2 и т.д.",
    )
    st.caption(
        "Одна строка в каждом поле = один кандидат. PDF или видео с Диска заполняют карточку через ИИ "
        "(видео расшифровывается), ссылка HH.ru — для кнопки «Открыть резюме на HH.ru»."
    )

    if st.button("🤖 Извлечь и добавить", key=f"bulk_btn_{vid}"):
        added = 0
        pdf_lines = _parse_bulk_link_lines(links)
        hh_lines = _parse_bulk_link_lines(hh_links)
        row_count = max(len(pdf_lines), len(hh_lines))

        for i in range(row_count):
            pdf_link = pdf_lines[i] if i < len(pdf_lines) else ""
            hh_link = hh_lines[i] if i < len(hh_lines) else ""
            if not pdf_link and not hh_link:
                continue

            resume_text = ""
            notes = []

            source_link = pdf_link
            video_link = ""
            resume_link = pdf_link
            transcript = ""

            if pdf_link:
                from resume_ai import get_yandex_public_meta, is_yandex_video_or_audio

                yandex_meta = (
                    get_yandex_public_meta(pdf_link)
                    if ("disk.yandex" in pdf_link or "yadi.sk" in pdf_link)
                    else None
                )
                is_video = is_yandex_video_or_audio(yandex_meta)
                spinner_label = (
                    f"Строка {i + 1}: расшифровка видео…"
                    if is_video
                    else f"Строка {i + 1}: загрузка файла…"
                )
                with st.spinner(spinner_label):
                    text, err = fetch_resume_text_from_url(
                        pdf_link,
                        deps["extract_text_from_pdf_url"],
                        deps.get("transcribe_video_from_link"),
                    )
                if text:
                    resume_text = text
                    if is_video:
                        video_link = pdf_link
                        resume_link = ""
                        transcript = text
                elif err:
                    notes.append(err)

            if not resume_text and hh_link:
                text, err = fetch_resume_text_from_url(
                    hh_link,
                    deps["extract_text_from_pdf_url"],
                    deps.get("transcribe_video_from_link"),
                )
                if text:
                    resume_text = text
                elif err:
                    notes.append(f"HH.ru: {err}")

            if source_link and not resume_text:
                st.warning(
                    f"Строка {i + 1}: не удалось получить текст ({source_link})"
                    + (f" — {'; '.join(notes)}" if notes else "")
                )
                if not hh_link:
                    continue

            _append_bulk_candidate(
                vacancy,
                deps,
                resume_link=resume_link,
                hh_resume_link=hh_link,
                video_link=video_link,
                resume_text=resume_text or None,
                transcript=transcript,
            )
            added += 1
            if hh_link and notes:
                st.caption(
                    f"Строка {i + 1}: ссылка HH.ru сохранена в карточке "
                    f"({'; '.join(notes)})"
                )

        if added:
            _persist_vacancy_candidates(vacancy, deps)
            st.session_state[links_ver_key] = st.session_state[links_ver_key] + 1
            st.session_state[hh_links_ver_key] = st.session_state[hh_links_ver_key] + 1
            st.session_state[success_key] = True
            st.rerun()
        else:
            st.warning("Никого не добавлено.")


def render_add_candidate(vacancy, deps):
    st.markdown("##### Ручное заполнение")
    with st.form(f"add_cand_{vacancy['id']}"):
        name = st.text_input("ФИО")
        resume_link = st.text_input("Ссылка на резюме")
        hh_resume_link = st.text_input("Ссылка на резюме HH.ru")
        pdf = st.file_uploader("Или PDF резюме", type=["pdf"])
        video_link = st.text_input("Запись собеседования")
        portfolio_link = ""
        if vacancy_show_portfolio_field(vacancy):
            portfolio_link = st.text_input("Портфолио")
        hr_comment = st.text_area("Комментарий")
        auto_extract = st.checkbox("Автоизвлечение данных из резюме", value=True)
        submitted = st.form_submit_button("Добавить")
        if submitted and name.strip():
            cand = new_candidate_template(vacancy["id"])
            cand["name"] = name.strip()
            cand["resume_link"] = resume_link.strip()
            cand["hh_resume_link"] = hh_resume_link.strip()
            cand["video_link"] = video_link.strip()
            cand["portfolio_link"] = portfolio_link.strip()
            cand["hr_comment"] = hr_comment.strip()
            cand["ignore_flags"] = deps["default_ignore_flags"]()
            if auto_extract:
                text = ""
                if pdf:
                    text = deps["extract_text"](pdf)
                elif resume_link.strip():
                    text, _ = fetch_resume_text_from_url(
                        resume_link,
                        deps["extract_text_from_pdf_url"],
                        deps.get("transcribe_video_from_link"),
                    )
                if text:
                    populate_from_resume(cand, text, deps["client"], deps["config"], vacancy=vacancy)
                    if not cand["name"] or cand["name"] == "Нет информации":
                        cand["name"] = name.strip()
            vacancy["candidates"].append(cand)
            vacancies = deps["load_vacancies"]()
            for v in vacancies:
                if v["id"] == vacancy["id"]:
                    v["candidates"] = vacancy["candidates"]
            deps["save_vacancies"](vacancies)
            st.success("Кандидат добавлен! Отправьте в чат кнопкой «Отправить в общий чат» в карточке.")
            st.rerun()


def render_candidates_zone(vacancy, deps, *, archive_mode=False):
    if not archive_mode and not deps["vacancy_has_profile"](vacancy):
        st.warning("Профиль должности не заполнен — оценка по интервью недоступна. Заполните в «Документы по вакансии».")

    if archive_mode:
        st.info(
            "Архивная вакансия: кандидатов можно просматривать, править и **копировать** "
            "в активную вакансию (этапы и оценка ИИ при копировании обнуляются)."
        )

    _render_cand_funnel_flash()

    if archive_mode:
        _render_candidates_list(vacancy, deps, archive_mode=True)
        _flush_candidates_rerun()
        return

    tab_list, tab_bulk, tab_add = st.tabs(["Список", "Автозагрузка", "Ручное заполнение"])

    with tab_bulk:
        render_bulk_intake(vacancy, deps)
    with tab_add:
        render_add_candidate(vacancy, deps)
    with tab_list:
        _render_candidates_list(vacancy, deps, archive_mode=False)

    _flush_candidates_rerun()


def _render_candidates_list(vacancy, deps, *, archive_mode=False):
    vacancies = deps["load_vacancies"]()
    vacancy = next((v for v in vacancies if v["id"] == vacancy["id"]), vacancy)
    all_candidates = sort_candidates_for_list(vacancy.get("candidates", []))
    if not all_candidates:
        st.info("Нет кандидатов.")
        return

    rejected = [c for c in all_candidates if _is_rejected_candidate(c)]
    active = [c for c in all_candidates if not _is_rejected_candidate(c)]
    rejected_count = len(rejected)
    show_rejected_key = f"show_rejected_{vacancy['id']}"
    show_rejected = st.session_state.get(show_rejected_key, False)
    visible = active + (rejected if show_rejected else [])

    _ensure_candidates_snapshot(vacancy["id"], all_candidates)
    pending_banner = st.empty()
    banner_save_clicked = False

    if not visible:
        st.info("Нет кандидатов в работе.")
        return

    to_delete_id = None
    for idx, cand in enumerate(visible):
        migrate_candidate(cand, deps["default_ignore_flags"])
        action = render_candidate_card(
            vacancy, cand, idx, deps, archive_mode=archive_mode
        )
        if action == "delete":
            to_delete_id = cand.get("id")

    if to_delete_id:
        vacancy["candidates"] = [
            c for c in vacancy.get("candidates", []) if c.get("id") != to_delete_id
        ]
        for v in vacancies:
            if v["id"] == vacancy["id"]:
                v["candidates"] = vacancy["candidates"]
        deps["save_vacancies"](vacancies)
        _mark_candidates_snapshot(vacancy["id"], vacancy.get("candidates", []))
        _request_candidates_rerun()

    if _has_unsaved_candidate_changes(vacancy["id"], all_candidates):
        from corporate_ui import render_pending_changes_banner

        with pending_banner.container():
            banner_save_clicked = render_pending_changes_banner(vacancy["id"])

    save_col, reject_col = st.columns([1, 1])
    with save_col:
        save_clicked = st.button(
            "💾 Сохранить изменения по кандидатам",
            key=f"save_cands_{vacancy['id']}",
        )
    with reject_col:
        if rejected_count:
            reject_label = (
                "Скрыть кандидатов с отказом"
                if show_rejected
                else f"Показать {rejected_count} кандидатов с отказом"
            )
            if st.button(reject_label, key=f"toggle_rejected_{vacancy['id']}"):
                st.session_state[show_rejected_key] = not show_rejected
                st.rerun()

    if save_clicked or banner_save_clicked:
        _persist_vacancy_candidates(vacancy, deps, candidates=all_candidates)
        pending_banner.empty()
        _set_cand_funnel_flash(
            "Изменения по кандидатам сохранены!"
            if banner_save_clicked
            else "Сохранено!"
        )
        _request_candidates_rerun()
