"""Интерактивный список опросника для собеседования."""

import uuid

import streamlit as st

from resume_ai import HR_RATING_LABELS, normalize_hr_rating

HR_RATING_OPTIONS = [
    ("", "—"),
    ("good", "Хорошо"),
    ("satisfactory", "Удовлетворительно"),
    ("doubtful", "Сомнительно"),
    ("no", "Нет"),
]


def _ensure_question_ids(items):
    result = []
    for q in items or []:
        if isinstance(q, str):
            q = {"вопрос": q}
        if not isinstance(q, dict):
            continue
        item = dict(q)
        if not (item.get("_qid") or "").strip():
            item["_qid"] = uuid.uuid4().hex[:8]
        rating = normalize_hr_rating(item.get("оценка_hr", item.get("оценка", item.get("rating", ""))))
        item["оценка_hr"] = rating
        item["оценка"] = rating
        result.append(item)
    return result


def _swap_by_qid(items, qid, direction):
    index = next((i for i, q in enumerate(items) if q.get("_qid") == qid), None)
    if index is None:
        return None
    other = index + direction
    if other < 0 or other >= len(items):
        return None
    swapped = list(items)
    swapped[index], swapped[other] = swapped[other], swapped[index]
    return swapped


def _rev_key(key_prefix):
    return f"{key_prefix}_widget_rev"


def _items_cache_key(key_prefix):
    return f"{key_prefix}_items"


def invalidate_interview_questionnaire_cache(card_iq_key):
    """Сброс кэша опросника в session_state (после перегенерации)."""
    list_prefix = f"{card_iq_key}_list"
    st.session_state.pop(_items_cache_key(list_prefix), None)
    st.session_state.pop(_rev_key(list_prefix), None)


def _load_questionnaire_items(cand, key_prefix):
    from resume_ai import looks_like_pipe_questionnaire_dump, normalize_questionnaire_list

    cache_key = _items_cache_key(key_prefix)
    cached = st.session_state.get(cache_key)
    if cached is not None:
        # Drop cached pipe-dump (one giant "question")
        bad_cache = (
            isinstance(cached, list)
            and len(cached) == 1
            and isinstance(cached[0], dict)
            and looks_like_pipe_questionnaire_dump(str(cached[0].get("вопрос") or ""))
        )
        if not bad_cache:
            return _ensure_question_ids(normalize_questionnaire_list(cached))
        st.session_state.pop(cache_key, None)

    items = normalize_questionnaire_list(cand.get("interview_questionnaire") or [])
    if items:
        cand["interview_questionnaire"] = items
    return _ensure_question_ids(items)


def _store_questionnaire_items(cand, key_prefix, items):
    cache_key = _items_cache_key(key_prefix)
    st.session_state[cache_key] = items
    cand["interview_questionnaire"] = items


def _render_question_meta(q):
    meta = []
    if q.get("проверяет_требование"):
        meta.append(f"Проверяет: {q['проверяет_требование']}")
    if q.get("категория"):
        meta.append(f"Категория: {q['категория']}")
    if meta:
        st.caption(" · ".join(meta))


def _render_hr_rating_row(key_prefix, q, rev):
    qid = q["_qid"]
    current = normalize_hr_rating(q.get("оценка_hr", q.get("оценка", "")))
    st.caption("Оценка ответа:")
    cols = st.columns(4)
    selected = current
    clicked = False
    for col, (value, label) in zip(cols, HR_RATING_OPTIONS[1:]):
        with col:
            active = current == value
            if st.button(
                f"{'☑ ' if active else '☐ '}{label}",
                key=f"{key_prefix}_rate_{qid}_{value}_{rev}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                selected = "" if active else value
                clicked = True
                st.session_state[_rev_key(key_prefix)] = rev + 1
    selected = normalize_hr_rating(selected)
    q["оценка_hr"] = selected
    q["оценка"] = selected
    return clicked and selected != current


def render_interview_questionnaire_list(cand, key_prefix):
    """
    Рисует список вопросов, правит cand['interview_questionnaire'] в памяти.
    Возвращает True только если нужен rerun (перестановка / смена оценки).
    """
    items = _load_questionnaire_items(cand, key_prefix)
    if not items:
        _store_questionnaire_items(cand, key_prefix, items)
        return False

    rev = st.session_state.get(_rev_key(key_prefix), 0)
    needs_rerun = False

    for index, q in enumerate(items):
        qid = q["_qid"]
        head_cols = st.columns([0.4, 0.4, 8])
        with head_cols[0]:
            if index > 0 and st.button("↑", key=f"{key_prefix}_up_{qid}_{rev}", help="Выше"):
                swapped = _swap_by_qid(items, qid, -1)
                if swapped:
                    _store_questionnaire_items(cand, key_prefix, swapped)
                    st.session_state[_rev_key(key_prefix)] = rev + 1
                    return True
        with head_cols[1]:
            if index < len(items) - 1 and st.button(
                "↓", key=f"{key_prefix}_down_{qid}_{rev}", help="Ниже"
            ):
                swapped = _swap_by_qid(items, qid, 1)
                if swapped:
                    _store_questionnaire_items(cand, key_prefix, swapped)
                    st.session_state[_rev_key(key_prefix)] = rev + 1
                    return True
        with head_cols[2]:
            st.markdown(f"**{index + 1}. {q.get('вопрос', '')}**")

        _render_question_meta(q)

        resume_hint = (q.get("в_резюме") or q.get("resume_hint") or "").strip()
        if resume_hint:
            with st.expander("Уже есть в резюме", expanded=False):
                st.markdown(resume_hint)

        followups = q.get("уточняющие_вопросы", [])
        if followups:
            with st.expander("Уточняющие вопросы (шаблон)", expanded=False):
                for j, followup in enumerate(followups, 1):
                    st.markdown(f"{j}. {followup}")

        resume_followups = q.get("уточнения_по_резюме") or []
        if resume_followups:
            with st.expander("Уточнения по резюме кандидата", expanded=True):
                for j, followup in enumerate(resume_followups, 1):
                    st.markdown(f"{j}. {followup}")

        if q.get("пример_ответа"):
            st.caption(f"Желательный результат: {q['пример_ответа']}")

        q["ответ"] = st.text_area(
            "Заметка по ответу",
            value=q.get("ответ", q.get("answer", "")),
            height=68,
            key=f"{key_prefix}_answer_{qid}_{rev}",
            label_visibility="collapsed",
            placeholder="Краткая заметка по ответу кандидата (необязательно)",
        )

        if _render_hr_rating_row(key_prefix, q, rev):
            needs_rerun = True

        st.divider()

    _store_questionnaire_items(cand, key_prefix, items)
    return needs_rerun


def render_interview_questionnaire_grid(cand, key_prefix):
    """Опросник в карточке. True = нужен один rerun (оценка / порядок)."""
    items = cand.get("interview_questionnaire") or []
    if not items:
        return False

    with st.expander("Вопросы для собеседования", expanded=True):
        st.caption(
            "Основные вопросы одинаковы для всех кандидатов вакансии (шаблон). "
            "«Уточнения по резюме» — персональные. Оценки учитываются при «Оценить по интервью». "
            "Сохраните правки кнопкой «Сохранить изменения по кандидатам»."
        )
        return render_interview_questionnaire_list(cand, f"{key_prefix}_list")
