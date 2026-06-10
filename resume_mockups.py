"""Раздел «Макеты HH» — оценка резюме без контактов по профилю вакансии."""

import json
import re
import uuid
from datetime import datetime

import streamlit as st

from resume_ai import (
    evaluate_resume_with_ai,
    fetch_resume_text_from_url,
    parse_ai_json_response,
)
from eval_ui import render_ai_score_badge, has_ai_evaluation


MOCKUP_RANKING_SYSTEM = """Ты — опытный HR-директор. По результатам холодной оценки резюме составь рейтинг кандидатов
относительно друг друга и профиля должности.

Правила:
- Учитывай rating (0–4), комментарии, сильные и слабые стороны.
- Ранжируй от лучшего к худшему; при равном rating сравни глубину опыта и риски.
- rank=1 — самый сильный кандидат для этой вакансии.
- relative_comment — 1–2 предложения, почему именно это место в рейтинге.

Верни ТОЛЬКО JSON:
{
  "ranking_comment": "общий вывод по пулу кандидатов 3–5 предложений",
  "items": [
    {"mockup_id": "uuid", "rank": 1, "relative_comment": "..."}
  ]
}"""


def new_mockup_template(source=""):
    return {
        "id": str(uuid.uuid4()),
        "label": "",
        "resume_link": source if source.startswith("http") else "",
        "resume_text": "",
        "hr_comment": "",
        "ai_score": None,
        "ai_comment": "",
        "ai_strengths": [],
        "ai_weaknesses": [],
        "ai_score_source": None,
        "profile_checked": False,
        "rank": None,
        "rank_comment": "",
        "status": "pending",
        "error": "",
        "created_at": datetime.now().isoformat(),
        "evaluated_at": "",
    }


def _mockups_key(vacancy_id):
    return f"resume_mockups_{vacancy_id}"


def get_vacancy_mockups(vacancy):
    return list(vacancy.get("resume_mockups") or [])


def _guess_mockup_label(resume_text, fallback=""):
    text = (resume_text or "").strip()
    if not text:
        return fallback or "Макет резюме"
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 8 and not line.lower().startswith("http"):
            return line[:80]
    snippet = re.sub(r"\s+", " ", text)[:80].strip()
    return snippet or fallback or "Макет резюме"


def _persist_mockups(vacancy, mockups, deps):
    vacancy["resume_mockups"] = mockups
    vacancies = deps["load_vacancies"]()
    for v in vacancies:
        if v["id"] == vacancy["id"]:
            v["resume_mockups"] = mockups
    deps["save_vacancies"](vacancies)


def load_mockups_from_sources(links_text, pasted_text, pdfs, deps):
    """Загружает тексты макетов из ссылок, вставки и PDF без извлечения контактов."""
    items = []

    for line in (links_text or "").splitlines():
        url = line.strip()
        if not url:
            continue
        text, err = fetch_resume_text_from_url(url, deps["extract_text_from_pdf_url"])
        mockup = new_mockup_template(url)
        mockup["resume_link"] = url
        if err or not text:
            mockup["status"] = "error"
            mockup["error"] = err or "Пустой текст резюме"
        else:
            mockup["resume_text"] = text
            mockup["label"] = _guess_mockup_label(text, url[:60])
        items.append(mockup)

    pasted_blocks = [b.strip() for b in re.split(r"\n-{3,}\n|\n\n(?=[А-ЯA-Z])", pasted_text or "") if b.strip()]
    if len(pasted_blocks) <= 1 and (pasted_text or "").strip() and not links_text:
        pasted_blocks = [(pasted_text or "").strip()]

    for idx, block in enumerate(pasted_blocks, start=1):
        if len(block) < 80:
            continue
        mockup = new_mockup_template()
        mockup["resume_text"] = block
        mockup["label"] = _guess_mockup_label(block, f"Макет {idx}")
        items.append(mockup)

    for pdf in pdfs or []:
        text = deps["extract_text"](pdf)
        if len((text or "").strip()) < 80:
            continue
        mockup = new_mockup_template(f"file://{pdf.name}")
        mockup["resume_link"] = f"file://{pdf.name}"
        mockup["resume_text"] = text
        mockup["label"] = _guess_mockup_label(text, pdf.name)
        items.append(mockup)

    return items


def evaluate_mockup(mockup, vacancy, deps, hr_comment=""):
    """Оценивает один макет тем же промптом, что и оценка резюме кандидата."""
    resume_text = (mockup.get("resume_text") or "").strip()
    if not resume_text and mockup.get("resume_link"):
        resume_text, err = fetch_resume_text_from_url(
            mockup["resume_link"], deps["extract_text_from_pdf_url"]
        )
        if err:
            mockup["status"] = "error"
            mockup["error"] = err
            return mockup
        mockup["resume_text"] = resume_text

    if not resume_text:
        mockup["status"] = "error"
        mockup["error"] = "Нет текста резюме"
        return mockup

    profile = deps["get_vacancy_profile_text"](vacancy)
    comment = (hr_comment or mockup.get("hr_comment") or "").strip()
    ev = evaluate_resume_with_ai(
        resume_text,
        profile,
        vacancy["title"],
        deps["client"],
        deps["config"],
        hr_comment=comment,
    )
    mockup.update(ev)
    mockup["status"] = "evaluated"
    mockup["error"] = ""
    mockup["evaluated_at"] = datetime.now().isoformat()
    if not mockup.get("label"):
        mockup["label"] = _guess_mockup_label(resume_text)
    return mockup


def batch_evaluate_mockups(mockups, vacancy, deps, hr_comment="", progress_callback=None):
    """Поочерёдная массовая оценка макетов."""
    updated = []
    pending = [m for m in mockups if m.get("status") != "evaluated" or m.get("ai_score") is None]
    total = len(pending)
    for idx, mockup in enumerate(pending, start=1):
        if progress_callback:
            progress_callback(idx, total, mockup.get("label") or f"Макет {idx}")
        try:
            evaluate_mockup(mockup, vacancy, deps, hr_comment=hr_comment)
        except Exception as e:
            mockup["status"] = "error"
            mockup["error"] = str(e)
        updated.append(mockup)

    by_id = {m["id"]: m for m in mockups}
    for m in updated:
        by_id[m["id"]] = m
    return list(by_id.values())


def build_ai_ranking(mockups, vacancy, deps):
    """Просит ИИ составить рейтинг по результатам оценки."""
    evaluated = [
        m for m in mockups
        if m.get("ai_score") is not None and m.get("status") == "evaluated"
    ]
    if len(evaluated) < 2:
        raise ValueError("Для рейтинга нужно минимум 2 оцененных макета")

    profile = deps["get_vacancy_profile_text"](vacancy)
    payload = []
    for m in evaluated:
        payload.append({
            "mockup_id": m["id"],
            "label": m.get("label", ""),
            "rating": m.get("ai_score"),
            "comment": m.get("ai_comment", ""),
            "strengths": m.get("ai_strengths", []),
            "weaknesses": m.get("ai_weaknesses", []),
        })

    response = deps["client"].chat.completions.create(
        model=deps["config"]["model"]["name"],
        messages=[
            {"role": "system", "content": MOCKUP_RANKING_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Должность: {vacancy['title']}\n\n"
                    f"ПРОФИЛЬ:\n{(profile or 'Профиль не задан')[:8000]}\n\n"
                    f"РЕЗУЛЬТАТЫ ОЦЕНКИ:\n{json.dumps(payload, ensure_ascii=False, indent=2)[:12000]}"
                ),
            },
        ],
        temperature=0.2,
        max_tokens=deps["config"]["model"]["max_tokens"],
    )
    result = parse_ai_json_response(response.choices[0].message.content)
    rank_map = {}
    for item in result.get("items", []):
        mid = item.get("mockup_id")
        if mid:
            rank_map[mid] = item

    for m in mockups:
        info = rank_map.get(m["id"])
        if info:
            m["rank"] = info.get("rank")
            m["rank_comment"] = info.get("relative_comment", "")

    return mockups, result.get("ranking_comment", "")


def _sort_for_display(mockups):
    def key(m):
        rank = m.get("rank")
        score = m.get("ai_score")
        rank_key = rank if rank is not None else 999
        score_key = -score if score is not None else 999
        return (rank_key, score_key, m.get("label", ""))

    return sorted(mockups, key=key)


def render_mockup_card(mockup, vacancy, deps, idx):
    label = mockup.get("label") or f"Макет {idx + 1}"
    status = mockup.get("status", "pending")
    header = label
    if has_ai_evaluation(mockup):
        header += f" · {mockup['ai_score']}/4"
    if mockup.get("rank"):
        header = f"#{mockup['rank']} · {header}"

    with st.expander(header, expanded=False):
        if mockup.get("resume_link"):
            st.caption(f"Источник: {mockup['resume_link']}")
        if status == "error":
            st.error(mockup.get("error") or "Ошибка загрузки/оценки")
        if mockup.get("rank_comment"):
            st.info(f"**Место в рейтинге:** {mockup['rank_comment']}")
        if has_ai_evaluation(mockup):
            st.markdown(render_ai_score_badge(mockup["ai_score"]), unsafe_allow_html=True)
            if mockup.get("ai_comment"):
                st.markdown("**Анализ (ИИ):**")
                st.write(mockup["ai_comment"])
            if mockup.get("ai_strengths"):
                st.markdown("**Сильные стороны**")
                for item in mockup["ai_strengths"]:
                    st.markdown(f"- {item}")
            if mockup.get("ai_weaknesses"):
                st.markdown("**Слабые стороны**")
                for item in mockup["ai_weaknesses"]:
                    st.markdown(f"- {item}")
        elif status == "pending":
            st.caption("Ожидает оценки ИИ")

        preview = (mockup.get("resume_text") or "")[:600]
        if preview:
            with st.expander("Фрагмент резюме", expanded=False):
                st.text(preview + ("…" if len(mockup.get("resume_text", "")) > 600 else ""))

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 Оценить", key=f"mock_eval_{vacancy['id']}_{mockup['id']}"):
                return "evaluate", mockup["id"]
        with col2:
            if st.button("🗑️ Удалить", key=f"mock_del_{vacancy['id']}_{mockup['id']}"):
                return "delete", mockup["id"]
    return None, None


def render_mockups_zone(vacancy, deps):
    st.markdown("##### Макеты резюме HH")
    st.caption(
        "Оценка резюме без контактов по профилю вакансии. "
        "Используется тот же промпт, что и «Оценить по резюме» во вкладке «Кандидаты»."
    )

    if not deps["vacancy_has_profile"](vacancy):
        st.warning("Заполните профиль должности в «Документы по вакансии» — без него оценка невозможна.")
        return

    vid = vacancy["id"]
    mockups = get_vacancy_mockups(vacancy)
    ranking_comment_key = f"mockup_ranking_comment_{vid}"

    links_ver = st.session_state.setdefault(f"mock_links_v_{vid}", 0)
    paste_ver = st.session_state.setdefault(f"mock_paste_v_{vid}", 0)
    pdf_ver = st.session_state.setdefault(f"mock_pdf_v_{vid}", 0)

    st.markdown("**Добавить макеты**")
    links = st.text_area(
        "Ссылки на резюме HH / PDF (по одной в строке)",
        height=90,
        key=f"mock_links_{vid}_{links_ver}",
    )
    pasted = st.text_area(
        "Или вставьте текст макетов (несколько резюме — через пустую строку или `---`)",
        height=120,
        key=f"mock_paste_{vid}_{paste_ver}",
    )
    pdfs = st.file_uploader(
        "PDF макеты",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"mock_pdf_{vid}_{pdf_ver}",
    )
    shared_hr_comment = st.text_area(
        "Комментарий HR для оценки (учитывается при массовой оценке)",
        key=f"mock_hr_comment_{vid}",
    )

    if st.button("➕ Загрузить макеты", key=f"mock_load_{vid}"):
        loaded = load_mockups_from_sources(links, pasted, pdfs, deps)
        if not loaded:
            st.warning("Нечего загружать — добавьте ссылки, текст или PDF.")
        else:
            for m in loaded:
                if shared_hr_comment.strip():
                    m["hr_comment"] = shared_hr_comment.strip()
            mockups.extend(loaded)
            _persist_mockups(vacancy, mockups, deps)
            st.session_state[f"mock_links_v_{vid}"] = links_ver + 1
            st.session_state[f"mock_paste_v_{vid}"] = paste_ver + 1
            st.session_state[f"mock_pdf_v_{vid}"] = pdf_ver + 1
            st.success(f"Добавлено макетов: {len(loaded)}")
            st.rerun()

    if not mockups:
        st.info("Макетов пока нет. Загрузите ссылки или текст резюме выше.")
        return

    pending_n = sum(1 for m in mockups if m.get("ai_score") is None and m.get("status") != "error")
    evaluated_n = sum(1 for m in mockups if m.get("ai_score") is not None)
    st.markdown(f"**В очереди:** {len(mockups)} · **Оценено:** {evaluated_n} · **Ждут оценки:** {pending_n}")

    action_cols = st.columns(3)
    with action_cols[0]:
        run_batch = st.button("🤖 Оценить все макеты", key=f"mock_batch_{vid}", disabled=pending_n == 0)
    with action_cols[1]:
        run_rank = st.button(
            "📊 Составить рейтинг ИИ",
            key=f"mock_rank_{vid}",
            disabled=evaluated_n < 2,
        )
    with action_cols[2]:
        clear_all = st.button("🗑️ Очистить все макеты", key=f"mock_clear_{vid}")

    if run_batch:
        progress = st.progress(0.0, text="Подготовка…")
        status = st.empty()

        def on_progress(idx, total, label):
            progress.progress(idx / total, text=f"Оценка {idx}/{total}: {label}")
            status.caption(f"Сейчас: {label}")

        try:
            mockups = batch_evaluate_mockups(
                mockups, vacancy, deps, hr_comment=shared_hr_comment, progress_callback=on_progress
            )
            _persist_mockups(vacancy, mockups, deps)
            progress.progress(1.0, text="Готово")
            st.success(f"Оценено макетов: {pending_n}")
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка массовой оценки: {e}")

    if run_rank:
        try:
            with st.spinner("ИИ составляет рейтинг…"):
                mockups, ranking_comment = build_ai_ranking(mockups, vacancy, deps)
            _persist_mockups(vacancy, mockups, deps)
            st.session_state[ranking_comment_key] = ranking_comment
            st.success("Рейтинг составлен")
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка рейтинга: {e}")

    if clear_all:
        _persist_mockups(vacancy, [], deps)
        st.session_state.pop(ranking_comment_key, None)
        st.rerun()

    ranking_comment = st.session_state.get(ranking_comment_key, "")
    if ranking_comment:
        st.markdown("**Рейтинг ИИ — общий вывод**")
        st.info(ranking_comment)

    st.markdown("**Список макетов**")
    for idx, mockup in enumerate(_sort_for_display(mockups)):
        action, mockup_id = render_mockup_card(mockup, vacancy, deps, idx)
        if action == "delete":
            mockups = [m for m in mockups if m.get("id") != mockup_id]
            _persist_mockups(vacancy, mockups, deps)
            st.rerun()
        elif action == "evaluate":
            target = next((m for m in mockups if m.get("id") == mockup_id), None)
            if target:
                try:
                    with st.spinner("Оценка…"):
                        evaluate_mockup(target, vacancy, deps, hr_comment=shared_hr_comment)
                    _persist_mockups(vacancy, mockups, deps)
                    st.success("Оценка сохранена")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
