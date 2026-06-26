"""Интерактивный список опросника для собеседования."""

import json
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


def _item_signature(items):
    order = [q.get("_qid", "") for q in items if isinstance(q, dict)]
    return json.dumps(order, ensure_ascii=False)


def _needs_question_ids(items):
    for q in items or []:
        if isinstance(q, str):
            return True
        if isinstance(q, dict) and not (q.get("_qid") or "").strip():
            return True
    return False


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
    selected = normalize_hr_rating(selected)
    if selected != current:
        q["оценка_hr"] = selected
        q["оценка"] = selected
        return True
    q["оценка_hr"] = selected
    q["оценка"] = selected
    return False


def render_interview_questionnaire_list(items, key_prefix):
    """Интерактивный список вопросов. Возвращает обновлённый список или None."""
    if not items:
        return None

    if _needs_question_ids(items):
        return _ensure_question_ids(items)

    items = _ensure_question_ids(items)
    rev = st.session_state.get(_rev_key(key_prefix), 0)
    changed = False

    for index, q in enumerate(items):
        qid = q["_qid"]
        head_cols = st.columns([0.4, 0.4, 8])
        with head_cols[0]:
            if index > 0 and st.button("↑", key=f"{key_prefix}_up_{qid}_{rev}", help="Выше"):
                swapped = _swap_by_qid(items, qid, -1)
                if swapped:
                    st.session_state[_rev_key(key_prefix)] = rev + 1
                    return swapped
        with head_cols[1]:
            if index < len(items) - 1 and st.button(
                "↓", key=f"{key_prefix}_down_{qid}_{rev}", help="Ниже"
            ):
                swapped = _swap_by_qid(items, qid, 1)
                if swapped:
                    st.session_state[_rev_key(key_prefix)] = rev + 1
                    return swapped
        with head_cols[2]:
            st.markdown(f"**{index + 1}. {q.get('вопрос', '')}**")

        _render_question_meta(q)

        resume_hint = (q.get("в_резюме") or q.get("resume_hint") or "").strip()
        if resume_hint:
            with st.expander("Уже есть в резюме", expanded=False):
                st.markdown(resume_hint)

        followups = q.get("уточняющие_вопросы", [])
        if followups:
            with st.expander("Уточняющие вопросы", expanded=False):
                for j, followup in enumerate(followups, 1):
                    st.markdown(f"{j}. {followup}")

        if q.get("пример_ответа"):
            st.caption(f"Желательный результат: {q['пример_ответа']}")

        new_answer = st.text_area(
            "Заметка по ответу",
            value=q.get("ответ", q.get("answer", "")),
            height=68,
            key=f"{key_prefix}_answer_{qid}_{rev}",
            label_visibility="collapsed",
            placeholder="Краткая заметка по ответу кандидата (необязательно)",
        )
        if new_answer != q.get("ответ", ""):
            q["ответ"] = new_answer
            changed = True

        if _render_hr_rating_row(key_prefix, q, rev):
            changed = True

        st.divider()

    if changed:
        return items
    return None


def render_interview_questionnaire_grid(cand, key_prefix):
    """
    Опросник в карточке кандидата (только список).
    Возвращает обновлённый список вопросов, если пользователь что-то изменил.
    """
    items = cand.get("interview_questionnaire") or []
    if not items:
        return None

    with st.expander("Вопросы для собеседования", expanded=True):
        st.caption(
            "Меняйте порядок стрелками ↑↓. Оценки ответов учитываются при «Оценить по интервью»."
        )
        return render_interview_questionnaire_list(items, f"{key_prefix}_list")
