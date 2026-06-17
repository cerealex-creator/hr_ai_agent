"""Подзона «Документы» — просмотр/редактирование и создание пакета вакансии."""

import json
import os

import streamlit as st

from ui_helpers import selectbox_no_default

WIZARD_FIELDS = [
    ("job_title", "Название должности"),
    ("tasks", "Основные задачи и зона ответственности"),
    ("hard_skills", "Обязательные hard skills"),
    ("soft_skills", "Желательные навыки и soft skills"),
    ("experience", "Требования к опыту"),
    ("conditions", "Условия: формат, график, зарплата"),
    ("stop_factors", "Стоп-факторы"),
    ("company_context", "О компании и специфике роли"),
]

VACANCY_WIZARD_SYSTEM = """Ты — HR-директор. На основе ответов HR сформируй пакет документов для вакансии.
Верни ТОЛЬКО валидный JSON с запрошенными полями.
Поле «профиль» обязательно: структурированный объект с задачами, требованиями и условиями.
Поле «опросник» обязательно: массив вопросов для собеседования.
Соблюдай правила опросника из QUESTIONNAIRE_GENERATION_RULES."""

VACANCY_CLARIFY_SYSTEM = """Ты — HR-консультант. По черновику анкеты вакансии задай 3–5 уточняющих вопросов HR.
Верни JSON: {"questions": ["вопрос 1", "вопрос 2", ...]}"""


def _vac_key(vacancy_id, suffix):
    return f"prep_{vacancy_id}_{suffix}"


def parse_profile_input(profile_text):
    if isinstance(profile_text, dict):
        return profile_text
    text = str(profile_text or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"raw": text}
    except json.JSONDecodeError:
        return {"raw": text}


def render_profile_display(profile):
    if not profile:
        st.info("Профиль не заполнен.")
        return
    if profile.get("raw"):
        st.markdown(profile["raw"])
        return
    if profile.get("подразделение") or profile.get("непосредственный_руководитель"):
        meta = []
        if profile.get("подразделение"):
            meta.append(f"**Подразделение:** {profile['подразделение']}")
        if profile.get("непосредственный_руководитель"):
            meta.append(f"**Руководитель:** {profile['непосредственный_руководитель']}")
        st.markdown(" · ".join(meta))
    tasks = profile.get("задачи", [])
    if tasks:
        st.markdown("**Задачи**")
        for t in tasks:
            st.markdown(f"- {t}")
    at = profile.get("анкетные_требования", {})
    if at:
        st.markdown("**Анкетные требования**")
        if at.get("возраст"):
            st.markdown(f"- Возраст: {at['возраст']}")
        if at.get("пол"):
            st.markdown(f"- Пол: {at['пол']}")
        stop = at.get("стоп_факторы", [])
        if stop:
            st.markdown("- Стоп-факторы:")
            for s in stop:
                st.markdown(f"  - {s}")
    for section_key, title in (
        ("обязательные_требования", "Обязательные требования"),
        ("желательные_требования", "Желательные требования"),
        ("психологические_черты", "Психологические черты"),
    ):
        items = profile.get(section_key, [])
        if items:
            st.markdown(f"**{title}**")
            for item in items:
                if isinstance(item, dict):
                    label = item.get("навык") or item.get("качество") or ""
                    desc = item.get("описание") or item.get("проявление") or ""
                    st.markdown(f"- **{label}:** {desc}" if label else f"- {desc}")
                else:
                    st.markdown(f"- {item}")
    cond = profile.get("условия_работы", {})
    if cond:
        st.markdown("**Условия работы**")
        for k, label in (("формат", "Формат"), ("режим", "Режим"), ("зарплата", "Зарплата"), ("испытательный_срок", "Испытательный срок")):
            if cond.get(k):
                st.markdown(f"- {label}: {cond[k]}")


def save_documents_from_editor(vacancy, profile, vacancy_text, questions, keywords, deps):
    updater = deps.get("update_vacancy_docs_by_id") or deps["update_vacancy_docs"]
    payload = {
        "profile": profile,
        "vacancy_text": vacancy_text,
        "questions": questions,
        "keywords": keywords,
    }
    if deps.get("update_vacancy_docs_by_id"):
        updater(vacancy["id"], payload)
    else:
        updater(vacancy["title"], payload)


def import_text_from_url(url, deps):
    url = (url or "").strip()
    if not url:
        return ""
    if "disk.yandex" in url or "yadi.sk" in url or url.lower().endswith(".pdf"):
        return deps["extract_text_from_pdf_url"](url) or ""
    try:
        import requests
        r = requests.get(url, timeout=45)
        if r.status_code == 200 and "pdf" in r.headers.get("Content-Type", "").lower():
            from io import BytesIO
            import PyPDF2
            reader = PyPDF2.PdfReader(BytesIO(r.content))
            return "\n".join(p.extract_text() or "" for p in reader.pages).strip()
        return r.text[:50000] if r.status_code == 200 else ""
    except Exception:
        return ""


def get_doc_flags_from_ui(key_prefix):
    st.markdown("**Какие документы создать**")
    c1, c2 = st.columns(2)
    with c1:
        st.checkbox("Профиль должности (обязательно)", value=True, disabled=True, key=f"{key_prefix}_f_prof")
        st.checkbox("Опросник для собеседования (обязательно)", value=True, disabled=True, key=f"{key_prefix}_f_q")
    with c2:
        vac_text = st.checkbox("Текст вакансии", value=False, key=f"{key_prefix}_f_vac")
        keywords = st.checkbox("Ключевые слова", value=False, key=f"{key_prefix}_f_kw")
    return {
        "profile": True,
        "questionnaire": True,
        "vacancy_text": vac_text,
        "keywords": keywords,
    }


def _profile_has_content(profile):
    if profile is None:
        return False
    if isinstance(profile, str):
        return len(profile.strip()) >= 20
    if isinstance(profile, dict):
        if (profile.get("raw") or "").strip():
            return len(profile["raw"].strip()) >= 20
        payload = json.dumps(profile, ensure_ascii=False)
        return len(payload) > 12 and payload not in ("{}", "[]")
    return len(str(profile).strip()) >= 20


def _questionnaire_has_content(questionnaire):
    if isinstance(questionnaire, list):
        return len(questionnaire) > 0
    if isinstance(questionnaire, str):
        return len(questionnaire.strip()) >= 20
    return bool(questionnaire)


def _prepare_generated_for_save(generated):
    """Нормализует ответ ИИ перед сохранением в вакансию."""
    if not isinstance(generated, dict):
        return {}
    prepared = dict(generated)
    profile = prepared.get("профиль")
    if isinstance(profile, str) and profile.strip():
        prepared["профиль"] = {"raw": profile.strip()}
    questionnaire = prepared.get("опросник")
    if isinstance(questionnaire, str) and questionnaire.strip():
        try:
            prepared["опросник"] = json.loads(questionnaire)
        except json.JSONDecodeError:
            prepared["опросник"] = [{"вопрос": questionnaire.strip(), "пример_ответа": ""}]
    return prepared


def _set_doc_gen_flash(message):
    st.session_state["vacancy_doc_gen_flash"] = message


def _render_doc_gen_flash():
    message = st.session_state.pop("vacancy_doc_gen_flash", None)
    if message:
        st.success(message)
        return True
    return False


def _wizard_max_tokens(deps):
    return max(int(deps["config"]["model"].get("max_tokens", 4000)), 12000)


def apply_generated_to_vacancy(vacancy, generated, deps, doc_flags=None, only_fields=None):
    flags = doc_flags or {
        "profile": True,
        "questionnaire": True,
        "vacancy_text": True,
        "keywords": True,
    }
    current = vacancy.get("documents", {})
    updates = dict(current)
    saved_labels = []

    def _should_update(field_key):
        if only_fields is None:
            return flags.get(field_key)
        mapping = {
            "profile": "profile",
            "questionnaire": "questions",
            "vacancy_text": "vacancy_text",
            "keywords": "keywords",
        }
        return field_key in flags and flags[field_key] and mapping.get(field_key) in only_fields

    if _should_update("profile") and _profile_has_content(generated.get("профиль")):
        updates["profile"] = json.dumps(generated.get("профиль", {}), ensure_ascii=False, indent=2)
        saved_labels.append("профиль")
    if _should_update("questionnaire") and _questionnaire_has_content(generated.get("опросник")):
        updates["questions"] = json.dumps(generated.get("опросник", []), ensure_ascii=False, indent=2)
        saved_labels.append("опросник")
    if _should_update("vacancy_text") and (generated.get("текст_вакансии") or "").strip():
        updates["vacancy_text"] = generated.get("текст_вакансии", "")
        saved_labels.append("текст вакансии")
    if _should_update("keywords") and generated.get("ключевые_слова"):
        updates["keywords"] = ", ".join(generated.get("ключевые_слова", []))
        saved_labels.append("ключевые слова")

    if not saved_labels:
        return False, []

    saved = deps["update_vacancy_docs"](vacancy["title"], {
        "profile": updates.get("profile", ""),
        "vacancy_text": updates.get("vacancy_text", ""),
        "questions": updates.get("questions", ""),
        "keywords": updates.get("keywords", ""),
    })
    return saved, saved_labels


def _normalize_generated_doc_keys(doc):
    """Приводит англоязычные ключи ответа модели к формату normalize_docs."""
    if not isinstance(doc, dict):
        return doc
    aliases = {
        "profile": "профиль",
        "questionnaire": "опросник",
        "questions": "опросник",
        "vacancy_text": "текст_вакансии",
        "keywords": "ключевые_слова",
        "job_title": "должность",
        "title": "должность",
    }
    for eng, rus in aliases.items():
        if eng in doc and rus not in doc:
            doc[rus] = doc.pop(eng)
    return doc


def _wizard_field_key(key_prefix, field_id):
    return f"wiz_{key_prefix}_{field_id}"


def _collect_wizard_answers(key_prefix):
    return {
        field_id: (st.session_state.get(_wizard_field_key(key_prefix, field_id), "") or "").strip()
        for field_id, _ in WIZARD_FIELDS
    }


def _collect_clarify_answers(key_prefix, questions):
    return {
        q: (st.session_state.get(f"clar_{key_prefix}_{i}", "") or "").strip()
        for i, q in enumerate(questions)
    }


def _wizard_answers_filled(answers):
    return any(
        (value or "").strip()
        for key, value in answers.items()
        if key != "clarifications"
    )


def generate_package_from_wizard(answers, deps, doc_flags, *, vacancy_title=None):
    rules = deps.get("QUESTIONNAIRE_GENERATION_RULES", "")
    parts = ["профиль должности", "опросник"]
    if doc_flags.get("vacancy_text"):
        parts.append("текст вакансии")
    if doc_flags.get("keywords"):
        parts.append("ключевые слова")
    system = (
        f"{VACANCY_WIZARD_SYSTEM}\n\nСоздай: {', '.join(parts)}.\n\n{rules}"
    )
    payload = dict(answers)
    if vacancy_title and not payload.get("job_title"):
        payload["job_title"] = vacancy_title
    user = "Ответы HR:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    response = deps["client"].chat.completions.create(
        model=deps["config"]["model"]["name"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=deps["config"]["model"]["temperature"],
        max_tokens=_wizard_max_tokens(deps),
    )
    raw = response.choices[0].message.content
    if not (raw or "").strip():
        raise ValueError("ИИ вернул пустой ответ. Попробуйте ещё раз.")
    result = deps["parse_ai_json_response"](raw)
    result = _normalize_generated_doc_keys(result)
    result = deps["normalize_docs"](result)
    return _prepare_generated_for_save(result)


def get_clarify_questions(answers, deps):
    response = deps["client"].chat.completions.create(
        model=deps["config"]["model"]["name"],
        messages=[
            {"role": "system", "content": VACANCY_CLARIFY_SYSTEM},
            {"role": "user", "content": json.dumps(answers, ensure_ascii=False)},
        ],
        temperature=0.4,
        max_tokens=600,
    )
    data = deps["parse_ai_json_response"](response.choices[0].message.content)
    return data.get("questions", [])


def refine_documents_with_ai(current_generated, corrections, deps):
    current_json = json.dumps(current_generated, ensure_ascii=False)
    refine_msg = f"Учти: {corrections}\n\nТекущие документы:\n{current_json}\nВерни полный JSON."
    response = deps["client"].chat.completions.create(
        model=deps["config"]["model"]["name"],
        messages=[
            {"role": "system", "content": "Ты HR-директор. Обнови JSON по запросу."},
            {"role": "user", "content": refine_msg},
        ],
        temperature=deps["config"]["model"]["temperature"],
        max_tokens=deps["config"]["model"]["max_tokens"],
    )
    result = deps["parse_ai_json_response"](response.choices[0].message.content)
    return deps["normalize_docs"](result)


def _docs_fingerprint(docs):
    """Отпечаток сохранённых в БД документов — для синхронизации session_state после импорта."""
    return (
        (docs.get("profile") or "").strip(),
        (docs.get("vacancy_text") or "").strip(),
        (docs.get("questions") or "").strip(),
        (docs.get("keywords") or "").strip(),
    )


def invalidate_doc_session_state(vacancy_id):
    """Сброс кэша редактора документов (после импорта / генерации из другой зоны)."""
    for suffix in ("profile_json", "vac_text", "questions", "keywords", "docs_fp"):
        st.session_state.pop(_vac_key(vacancy_id, suffix), None)


def _init_doc_state(vacancy, docs):
    vid = vacancy["id"]
    prof_key = _vac_key(vid, "profile_json")
    vac_key = _vac_key(vid, "vac_text")
    q_key = _vac_key(vid, "questions")
    kw_key = _vac_key(vid, "keywords")
    fp_key = _vac_key(vid, "docs_fp")

    db_fp = _docs_fingerprint(docs)
    if st.session_state.get(fp_key) != db_fp:
        st.session_state[prof_key] = docs.get("profile", "")
        st.session_state[vac_key] = docs.get("vacancy_text", "")
        st.session_state[q_key] = docs.get("questions", "")
        st.session_state[kw_key] = docs.get("keywords", "")
        st.session_state[fp_key] = db_fp

    return prof_key, vac_key, q_key, kw_key


def _documents_from_history_package(generated):
    """
    Собирает документы вакансии из пакета истории.
    Отсутствующие в пакете поля — пустые строки (полная замена, не слияние).
    Возвращает (docs_dict, written_labels, cleared_labels).
    """
    docs = {
        "profile": "",
        "vacancy_text": "",
        "questions": "",
        "keywords": "",
    }
    written = []
    cleared = []

    if _profile_has_content(generated.get("профиль")):
        docs["profile"] = json.dumps(
            generated.get("профиль", {}), ensure_ascii=False, indent=2
        )
        written.append("профиль")
    else:
        cleared.append("профиль")

    if _questionnaire_has_content(generated.get("опросник")):
        docs["questions"] = json.dumps(
            generated.get("опросник", []), ensure_ascii=False, indent=2
        )
        written.append("опросник")
    else:
        cleared.append("опросник")

    if (generated.get("текст_вакансии") or "").strip():
        docs["vacancy_text"] = generated.get("текст_вакансии", "")
        written.append("текст вакансии")
    else:
        cleared.append("текст вакансии")

    if generated.get("ключевые_слова"):
        docs["keywords"] = ", ".join(generated.get("ключевые_слова", []))
        written.append("ключевые слова")
    else:
        cleared.append("ключевые слова")

    return docs, written, cleared


def apply_package_from_history(vacancy, generated_raw, deps):
    """
    Полностью заменяет документы вакансии пакетом из истории.
    Возвращает (saved: bool, written_labels: list[str], cleared_labels: list[str]).
    """
    gen = dict(generated_raw or {})
    gen = _normalize_generated_doc_keys(gen)
    gen = deps["normalize_docs"](gen)
    gen = _prepare_generated_for_save(gen)
    docs, written, cleared = _documents_from_history_package(gen)
    if not written:
        return False, [], cleared

    saved = deps["update_vacancy_docs_by_id"](
        vacancy["id"], docs, replace_documents=True
    )
    if saved:
        invalidate_doc_session_state(vacancy["id"])
        title = vacancy.get("title", "")
        written_text = ", ".join(written)
        msg = (
            f"✅ Документы вакансии «{title}» заменены пакетом из истории: {written_text}."
        )
        if cleared:
            msg += f" Очищены поля без данных в пакете: {', '.join(cleared)}."
        msg += " Откройте «Вакансии в работе» → «Документы по вакансии»."
        _set_doc_gen_flash(msg)
    return saved, written, cleared


def describe_history_package(generated):
    """Краткое описание содержимого пакета для UI истории."""
    if not isinstance(generated, dict):
        return []
    parts = []
    if _profile_has_content(generated.get("профиль")):
        parts.append("профиль")
    questionnaire = generated.get("опросник")
    if _questionnaire_has_content(questionnaire):
        if isinstance(questionnaire, list):
            parts.append(f"опросник ({len(questionnaire)} вопр.)")
        else:
            parts.append("опросник")
    if (generated.get("текст_вакансии") or "").strip():
        parts.append("текст вакансии")
    keywords = generated.get("ключевые_слова") or []
    if keywords:
        parts.append(f"ключевые слова ({len(keywords)})")
    return parts


def _vacancy_history_picker_options(vacancies):
    """Подписи для выбора вакансии; при одинаковых названиях — id и дата."""
    title_counts = {}
    for v in vacancies:
        title = (v.get("title") or "").strip()
        title_counts[title] = title_counts.get(title, 0) + 1

    labels = []
    by_label = {}
    for v in vacancies:
        title = (v.get("title") or "").strip()
        if title_counts.get(title, 0) > 1:
            created = (v.get("created_at") or "")[:10]
            label = f"{title} · id {v['id']} · {created}"
        else:
            label = title
        labels.append(label)
        by_label[label] = v
    return labels, by_label


def render_history_tab(
    deps,
    *,
    get_history_index,
    load_generation_from_history,
    delete_generation_from_history,
):
    """Вкладка «История генераций»."""
    from ui_helpers import selectbox_no_default

    st.header("📜 История генераций")
    st.caption(
        "Ранее созданные пакеты документов. Загрузите пакет, выберите вакансию "
        "и нажмите «Применить» — **прежние документы вакансии будут полностью заменены** "
        "содержимым пакета."
    )

    _render_doc_gen_flash()

    success_msg = st.session_state.pop("hist_apply_success", None)
    if success_msg:
        st.success(success_msg)

    load_msg = st.session_state.pop("hist_load_message", None)
    if load_msg:
        st.info(load_msg)

    gen = st.session_state.get("generated")
    loaded_rec = st.session_state.get("hist_loaded_rec")
    if gen:
        st.markdown("### 📦 Загруженный пакет")
        if loaded_rec:
            st.markdown(
                f"**{loaded_rec.get('title') or 'Без названия'}** · "
                f"{loaded_rec.get('datetime', '')}"
            )
            if loaded_rec.get("vacancy_title"):
                st.caption(f"Исходная вакансия при генерации: {loaded_rec['vacancy_title']}")

        package_parts = describe_history_package(gen)
        if package_parts:
            st.markdown("**Содержимое:** " + ", ".join(package_parts))
        else:
            st.warning(
                "В пакете не найдено распознанных документов. "
                "Проверьте файл JSON или выберите другой пакет."
            )

        active_v = [v for v in deps["load_vacancies"]() if v.get("active", True)]
        if not active_v:
            st.warning("Нет активных вакансий — создайте вакансию, чтобы применить пакет.")
        else:
            picker_labels, picker_map = _vacancy_history_picker_options(active_v)
            apply_target = selectbox_no_default(
                "Применить пакет к вакансии",
                picker_labels,
                key="hist_apply_vacancy",
                help_text=(
                    "Выберите вакансию, в которую нужно записать документы из пакета. "
                    "Если названия совпадают, смотрите id и дату создания."
                ),
            )
            if st.button("📥 Применить пакет к вакансии", key="hist_apply_btn", type="primary"):
                if not apply_target:
                    st.warning("Выберите вакансию из списка.")
                elif not package_parts:
                    st.error("Нечего применять: пакет пустой или в неверном формате.")
                else:
                    vacancy = picker_map[apply_target]
                    apply_title = vacancy.get("title", apply_target)
                    with st.spinner(
                        f"Замена документов в «{apply_title}» (id {vacancy['id']})…"
                    ):
                        saved, written, cleared = apply_package_from_history(
                            vacancy, gen, deps
                        )
                    if saved and written:
                        st.session_state.opened_vacancy_id = vacancy["id"]
                        success = (
                            f"✅ Документы «{apply_title}» (id {vacancy['id']}) заменены: "
                            f"{', '.join(written)}."
                        )
                        if cleared:
                            success += (
                                f" Очищены (не было в пакете): {', '.join(cleared)}."
                            )
                        success += (
                            " Откройте «Вакансии в работе» → «Документы по вакансии»."
                        )
                        st.session_state.hist_apply_success = success
                        st.rerun()
                    elif not written:
                        st.error(
                            "Пакет не содержит документов для сохранения "
                            "(нужен хотя бы профиль или опросник)."
                        )
                    else:
                        st.error(
                            f"Не удалось сохранить документы для «{apply_title}» "
                            f"(id {vacancy['id']})."
                        )

        st.divider()

    index = get_history_index()
    if not index:
        st.info(
            "История пуста. Сгенерируйте документы во вкладке «Вакансии» → "
            "«Создание новой вакансии», чтобы они появились здесь."
        )
        return

    st.markdown("### Архив пакетов")
    for i, rec in enumerate(index):
        with st.expander(f"📄 {rec['datetime']} – {rec['title'] or 'Без названия'}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Время:** {rec['datetime']}")
                st.markdown(f"**Должность:** {rec['title']}")
                if rec.get("vacancy_title"):
                    st.markdown(f"**Связанная вакансия:** {rec['vacancy_title']}")
                st.markdown("**Превью текста вакансии:**")
                st.text(rec.get("preview") or "(нет текста)")
            with col2:
                if st.button("📂 Загрузить", key=f"load_{i}"):
                    data = load_generation_from_history(rec["filename"])
                    if data:
                        st.session_state.generated = data
                        st.session_state.hist_loaded_rec = {
                            "filename": rec["filename"],
                            "datetime": rec["datetime"],
                            "title": rec.get("title"),
                            "vacancy_title": rec.get("vacancy_title") or "",
                        }
                        parts = describe_history_package(data)
                        parts_text = ", ".join(parts) if parts else "документы не распознаны"
                        st.session_state.hist_load_message = (
                            f"Пакет от {rec['datetime']} загружен ({parts_text}). "
                            "Выберите вакансию выше и нажмите «Применить пакет к вакансии»."
                        )
                        linked = (rec.get("vacancy_title") or "").strip()
                        active_for_link = [
                            v for v in deps["load_vacancies"]() if v.get("active", True)
                        ]
                        picker_labels, picker_map = _vacancy_history_picker_options(
                            active_for_link
                        )
                        if linked:
                            matches = [
                                label
                                for label, vac in picker_map.items()
                                if vac.get("title") == linked
                            ]
                            if len(matches) == 1:
                                st.session_state["hist_apply_vacancy"] = matches[0]
                            elif len(matches) > 1:
                                newest = max(
                                    (picker_map[m] for m in matches),
                                    key=lambda v: v.get("created_at") or "",
                                )
                                for label, vac in picker_map.items():
                                    if vac.get("id") == newest.get("id"):
                                        st.session_state["hist_apply_vacancy"] = label
                                        break
                        st.rerun()
                    else:
                        st.error("Не удалось прочитать файл пакета.")
                data_for_export = load_generation_from_history(rec["filename"])
                if data_for_export:
                    st.download_button(
                        "📥 Скачать JSON",
                        data=json.dumps(data_for_export, ensure_ascii=False, indent=2),
                        file_name=rec["filename"],
                        mime="application/json",
                        key=f"export_hist_{i}",
                    )
                if st.button("🗑️ Удалить", key=f"del_{i}"):
                    if delete_generation_from_history(rec["filename"]):
                        if st.session_state.get("hist_loaded_rec", {}).get("filename") == rec["filename"]:
                            st.session_state.pop("generated", None)
                            st.session_state.pop("hist_loaded_rec", None)
                        st.success("Пакет удалён из истории.")
                        st.rerun()
                    else:
                        st.error("Ошибка удаления.")


def render_profile_section(vacancy, prof_key, deps):
    profile = parse_profile_input(st.session_state[prof_key])

    corrections = st.text_area(
        "Коррективы к профилю",
        placeholder="Например: добавить требование Excel; уточнить зарплату; расширить стоп-факторы",
        height=80,
        key=f"prof_corr_{vacancy['id']}",
    )
    if st.button("🔄 Перегенерировать профиль", key=f"prof_regen_{vacancy['id']}"):
        with st.spinner("Перегенерация..."):
            try:
                new_prof = deps["regenerate_profile_with_ai"](
                    vacancy["title"], profile, corrections
                )
                st.session_state[prof_key] = json.dumps(new_prof, ensure_ascii=False, indent=2)
                st.success("Профиль обновлён!")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    with st.expander("📝 Редактировать профиль вручную (JSON)", expanded=False):
        edited = st.text_area(
            "JSON профиля",
            value=st.session_state[prof_key],
            height=260,
            key=f"prof_json_{vacancy['id']}",
        )
        if st.button("✅ Сохранить правки профиля", key=f"prof_save_{vacancy['id']}"):
            try:
                json.loads(edited)
                st.session_state[prof_key] = edited
                st.success("Сохранено!")
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Некорректный JSON: {e}")

    st.markdown("##### Текущий профиль")
    render_profile_display(profile)


def render_vacancy_text_section(vacancy, vac_key, prof_key, deps):
    vac_text = st.session_state[vac_key]
    profile = parse_profile_input(st.session_state[prof_key])

    corrections = st.text_area(
        "Коррективы к тексту вакансии",
        placeholder="Например: сделать тон дружелюбнее; добавить блок про ДМС; убрать упоминание офиса",
        height=80,
        key=f"vac_corr_{vacancy['id']}",
    )
    if st.button("🔄 Перегенерировать текст вакансии", key=f"vac_regen_{vacancy['id']}"):
        with st.spinner("Перегенерация..."):
            try:
                new_text = deps["regenerate_vacancy_text_with_ai"](
                    vacancy["title"], profile, vac_text, corrections
                )
                st.session_state[vac_key] = new_text
                st.success("Текст вакансии обновлён!")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    with st.expander("📝 Редактировать текст вакансии вручную", expanded=False):
        edited = st.text_area(
            "Текст вакансии",
            value=vac_text,
            height=280,
            key=f"vac_edit_{vacancy['id']}",
        )
        if st.button("✅ Сохранить правки текста", key=f"vac_save_{vacancy['id']}"):
            st.session_state[vac_key] = edited
            st.success("Сохранено!")
            st.rerun()

    st.markdown("##### Текущий текст вакансии")
    if vac_text.strip():
        st.markdown(vac_text)
    else:
        st.info("Текст вакансии не заполнен.")


def render_keywords_section(vacancy, kw_key, prof_key, deps):
    keywords = st.session_state[kw_key]
    profile = parse_profile_input(st.session_state[prof_key])

    corrections = st.text_area(
        "Коррективы к ключевым словам",
        placeholder="Например: добавить «маркетплейс», убрать «junior»",
        height=60,
        key=f"kw_corr_{vacancy['id']}",
    )
    if st.button("🔄 Перегенерировать ключевые слова", key=f"kw_regen_{vacancy['id']}"):
        with st.spinner("Перегенерация..."):
            try:
                new_kw = deps["regenerate_keywords_with_ai"](
                    vacancy["title"], profile, keywords, corrections
                )
                st.session_state[kw_key] = new_kw
                st.success("Ключевые слова обновлены!")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    with st.expander("📝 Редактировать ключевые слова вручную", expanded=False):
        edited = st.text_area(
            "Ключевые слова (через запятую)",
            value=keywords,
            height=100,
            key=f"kw_edit_{vacancy['id']}",
        )
        if st.button("✅ Сохранить ключевые слова", key=f"kw_save_{vacancy['id']}"):
            st.session_state[kw_key] = edited
            st.success("Сохранено!")
            st.rerun()

    st.markdown("##### Текущие ключевые слова")
    if keywords.strip():
        st.markdown(keywords)
    else:
        st.info("Ключевые слова не заполнены.")


def _doc_field_status(value):
    return "заполнен" if (value or "").strip() else "пуст"


def collect_vacancy_documents_for_template(vacancy):
    """Актуальные документы вакансии: из открытого редактора или из базы."""
    vid = vacancy["id"]
    prof_key = _vac_key(vid, "profile_json")
    docs = vacancy.get("documents", {})
    if prof_key in st.session_state:
        return {
            "profile": st.session_state.get(_vac_key(vid, "profile_json"), ""),
            "vacancy_text": st.session_state.get(_vac_key(vid, "vac_text"), ""),
            "questions": st.session_state.get(_vac_key(vid, "questions"), ""),
            "keywords": st.session_state.get(_vac_key(vid, "keywords"), ""),
            "notes": docs.get("notes") or "",
        }
    return docs


def try_push_vacancy_to_templates(vacancy):
    from vacancy_template_store import add_vacancy_to_templates

    docs = collect_vacancy_documents_for_template(vacancy)
    return add_vacancy_to_templates(vacancy, docs)


def template_editor_entity(template):
    return {
        "id": f"tpl_{template['id']}",
        "title": template.get("title") or template.get("name", ""),
        "documents": template.get("documents", {}),
    }


def render_documents_editor(entity, deps, *, mode="vacancy", template_id=None):
    """Редактор документов для вакансии или шаблона."""
    docs = entity.get("documents", {})
    prof_key, vac_key, q_key, kw_key = _init_doc_state(entity, docs)
    entity_id = entity["id"]
    save_key = f"save_docs_{entity_id}"
    is_template = mode == "template"

    from vacancy_template_store import get_missing_document_fields

    missing = get_missing_document_fields({
        "profile": st.session_state[prof_key],
        "vacancy_text": st.session_state[vac_key],
        "questions": st.session_state[q_key],
        "keywords": st.session_state[kw_key],
    })
    if missing:
        st.warning(f"Не заполнено: {', '.join(missing)}.")
    else:
        st.success("Все основные документы заполнены.")

    st.caption(
        "Статус в базе: "
        f"профиль — {_doc_field_status(docs.get('profile'))}, "
        f"текст вакансии — {_doc_field_status(docs.get('vacancy_text'))}, "
        f"опросник — {_doc_field_status(docs.get('questions'))}, "
        f"ключевые слова — {_doc_field_status(docs.get('keywords'))}."
    )

    profile_expanded = bool((docs.get("profile") or "").strip())
    with st.expander("📋 Профиль должности", expanded=profile_expanded):
        render_profile_section(entity, prof_key, deps)

    with st.expander("📄 Текст вакансии", expanded=False):
        render_vacancy_text_section(entity, vac_key, prof_key, deps)

    with st.expander("❓ Опросник для собеседования", expanded=False):
        def on_q_apply(new_q):
            st.session_state[q_key] = json.dumps(new_q, ensure_ascii=False, indent=2)

        deps["render_questionnaire_edit_panel"](
            job_title=entity["title"],
            profile=st.session_state[prof_key],
            questionnaire=st.session_state[q_key],
            key_prefix=f"vac_doc_{entity_id}",
            on_apply=on_q_apply,
        )

    with st.expander("🔑 Ключевые слова", expanded=False):
        render_keywords_section(entity, kw_key, prof_key, deps)

    if st.button("💾 Сохранить все документы", key=save_key, type="primary"):
        payload = {
            "profile": st.session_state[prof_key],
            "vacancy_text": st.session_state[vac_key],
            "questions": st.session_state[q_key],
            "keywords": st.session_state[kw_key],
        }
        if is_template:
            from vacancy_template_store import update_template_documents

            ok, msg = update_template_documents(template_id, {
                **payload,
                "notes": docs.get("notes") or "",
            })
            if ok:
                entity["documents"].update(payload)
                st.session_state[_vac_key(entity_id, "docs_fp")] = _docs_fingerprint(entity["documents"])
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        else:
            save_documents_from_editor(
                entity,
                payload["profile"],
                payload["vacancy_text"],
                payload["questions"],
                payload["keywords"],
                deps,
            )
            entity["documents"].update(payload)
            st.session_state[_vac_key(entity_id, "docs_fp")] = _docs_fingerprint(entity["documents"])
            st.success("Документы сохранены!")
            st.rerun()

    gen = {
        "должность": entity["title"],
        "профиль": parse_profile_input(st.session_state[prof_key]),
        "текст_вакансии": st.session_state[vac_key],
        "опросник": deps["parse_questionnaire_input"](st.session_state[q_key]),
        "ключевые_слова": [k.strip() for k in st.session_state[kw_key].split(",") if k.strip()],
    }
    exp1, exp2, exp3 = st.columns(3)
    with exp1:
        st.download_button(
            "📥 JSON",
            data=json.dumps(gen, ensure_ascii=False, indent=2),
            file_name=f"{entity['title']}_docs.json",
            mime="application/json",
            key=f"dl_json_{entity_id}",
        )
    with exp2:
        if st.button("📄 Word", key=f"dl_word_{entity_id}"):
            path = deps["export_to_word"](gen)
            if path:
                with open(path, "rb") as f:
                    st.download_button(
                        "Скачать Word",
                        data=f.read(),
                        file_name=f"{entity['title']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_word_file_{entity_id}",
                    )
    with exp3:
        if st.button("📕 PDF", key=f"dl_pdf_{entity_id}"):
            path = deps["export_to_pdf"](gen)
            if path:
                with open(path, "rb") as f:
                    st.download_button(
                        "Скачать PDF",
                        data=f.read(),
                        file_name=f"{entity['title']}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_file_{entity_id}",
                    )


def render_vacancy_candidate_settings(vacancy, deps):
    """Настройки полей карточки кандидата для вакансии."""
    from vacancy_store import migrate_vacancy

    migrate_vacancy(vacancy)
    with st.expander("⚙️ Настройки карточки кандидата", expanded=False):
        show_portfolio = st.checkbox(
            "Поле «Портфолио» в карточке кандидата",
            value=bool(vacancy.get("show_portfolio_field")),
            key=f"vac_portfolio_{vacancy['id']}",
            help=(
                "Если включено — в карточке появится поле ссылки на портфолио. "
                "При заполнении ссылка отобразится в сообщении в Telegram."
            ),
        )
        if st.button("Сохранить настройки", key=f"save_vac_settings_{vacancy['id']}"):
            all_v = deps["load_vacancies"]()
            for v in all_v:
                if v["id"] == vacancy["id"]:
                    v["show_portfolio_field"] = show_portfolio
            deps["save_vacancies"](all_v)
            st.success("Настройки сохранены")
            st.rerun()


def render_existing_documents_zone(vacancy, deps):
    """Подзона «Документы по вакансии» — только просмотр и редактирование."""
    render_vacancy_candidate_settings(vacancy, deps)
    render_documents_editor(vacancy, deps, mode="vacancy")

    with st.expander("📌 Сохранить как шаблон", expanded=False):
        st.caption(
            "Копирует документы и привязку к чату в шаблоны. "
            "Повторное сохранение с тем же именем обновляет шаблон."
        )
        tpl_name = st.text_input(
            "Название шаблона",
            value=vacancy["title"],
            key=f"tpl_name_{vacancy['id']}",
        )
        if st.button("Сделать шаблоном", key=f"tpl_save_{vacancy['id']}"):
            from vacancy_template_store import save_template_from_vacancy

            vacancy_snapshot = {
                **vacancy,
                "documents": collect_vacancy_documents_for_template(vacancy),
            }
            ok, msg, _, missing = save_template_from_vacancy(
                vacancy_snapshot,
                tpl_name,
            )
            if ok:
                if missing:
                    st.warning(msg)
                else:
                    st.success(msg)
            else:
                st.error(msg)


def render_template_documents_zone(template, deps):
    """Редактирование документов шаблона — как у активной вакансии."""
    from vacancy_template_store import get_template

    fresh = get_template(template["id"]) or template
    entity = template_editor_entity(fresh)
    render_documents_editor(
        entity,
        deps,
        mode="template",
        template_id=fresh["id"],
    )


def render_templates_library(deps):
    from vacancy_template_store import delete_template, list_templates

    templates = list_templates()
    if "opened_template_id" not in st.session_state:
        st.session_state.opened_template_id = None

    if not templates:
        st.info(
            "Шаблонов пока нет. Нажмите «Добавить вакансию в шаблоны» в меню вакансии "
            "или сохраните шаблон в документах."
        )
        return

    st.markdown("Выберите шаблон для просмотра и доработки документов.")
    cols_per_row = 2
    for row_start in range(0, len(templates), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, template in enumerate(templates[row_start:row_start + cols_per_row]):
            with cols[col_idx]:
                is_open = st.session_state.opened_template_id == template["id"]
                updated = (template.get("updated_at") or "")[:10]
                label = f"{template.get('name', '—')}\n{updated or '—'}"
                btn_type = "primary" if is_open else "secondary"
                if st.button(
                    label,
                    key=f"tpl_pick_{template['id']}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    if is_open:
                        st.session_state.opened_template_id = None
                    else:
                        st.session_state.opened_template_id = template["id"]
                    st.rerun()

    opened_id = st.session_state.get("opened_template_id")
    if not opened_id:
        st.caption("Шаблон не выбран.")
        return

    template = next((t for t in templates if t["id"] == opened_id), None)
    if not template:
        st.session_state.opened_template_id = None
        st.warning("Шаблон не найден.")
        return

    st.divider()
    head_l, head_r = st.columns([4, 1])
    with head_l:
        st.subheader(template.get("name", "Шаблон"))
        st.caption(
            f"Роль: {template.get('title', '—')} · Chat ID: {template.get('chat_id', '—')}"
        )
    with head_r:
        st.write("")
        if st.button("🗑️ Удалить", key=f"tpl_del_{template['id']}", use_container_width=True):
            ok, msg = delete_template(template["id"])
            if ok:
                st.session_state.opened_template_id = None
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    render_template_documents_zone(template, deps)


def transcribe_uploaded_audio(uploaded_file, method, deps):
    os.makedirs("data/tmp", exist_ok=True)
    audio_path = os.path.join("data/tmp", uploaded_file.name)
    with open(audio_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    try:
        return deps["transcribe_speechkit_cloud"](audio_path), None
    except Exception as e:
        return "", str(e)


def render_transcript_source(vacancy, deps, key_prefix):
    """Получение расшифровки: аудио/видео, файл или текст."""
    tk = _vac_key(vacancy["id"], f"transcript_{key_prefix}")
    if tk not in st.session_state:
        st.session_state[tk] = ""

    source = st.radio(
        "Источник расшифровки",
        ("Аудио/видео", "Готовый файл", "Текст"),
        horizontal=True,
        key=f"src_{key_prefix}_{vacancy['id']}",
    )

    if source == "Аудио/видео":
        method = "Яндекс (SpeechKit)"
        uploaded_audio = st.file_uploader(
            "Аудио/видео файл",
            type=["mp3", "mp4", "wav", "webm", "mkv", "ogg"],
            key=f"audio_{key_prefix}_{vacancy['id']}",
        )
        if uploaded_audio and st.button("🎙️ Расшифровать", key=f"trscr_{key_prefix}_{vacancy['id']}"):
            with st.spinner("Расшифровка... это может занять несколько минут"):
                text, err = transcribe_uploaded_audio(uploaded_audio, method, deps)
                if err:
                    st.error(err)
                elif text:
                    st.session_state[tk] = text
                    st.success("Расшифровка завершена!")
                    st.rerun()
                else:
                    st.error("Не удалось получить текст.")
    elif source == "Готовый файл":
        f = st.file_uploader(
            "Файл с расшифровкой",
            type=["txt", "docx", "pdf"],
            key=f"tr_file_{key_prefix}_{vacancy['id']}",
        )
        if f:
            st.session_state[tk] = deps["extract_text"](f)
    else:
        st.session_state[tk] = st.text_area(
            "Вставьте или отредактируйте расшифровку",
            value=st.session_state[tk],
            height=220,
            key=f"tr_text_{key_prefix}_{vacancy['id']}",
        )

    return st.session_state.get(tk, "")


def _import_form_version(key_prefix):
    vk = f"imp_form_v_{key_prefix}"
    if vk not in st.session_state:
        st.session_state[vk] = 0
    return st.session_state[vk]


def _read_import_source(uploaded_file, url, deps, label):
    if uploaded_file:
        try:
            text = deps["extract_text"](uploaded_file)
        except Exception as e:
            return None, f"{label}: ошибка чтения файла — {e}"
        text = (text or "").strip()
        if not text:
            return None, f"{label}: файл пуст или не удалось извлечь текст"
        return text, None
    if url and url.strip():
        text = (import_text_from_url(url, deps) or "").strip()
        if not text:
            return None, f"{label}: не удалось загрузить по ссылке"
        return text, None
    return None, None


def render_import_mode(vacancy, deps, doc_flags, key_prefix):
    st.markdown("##### Импорт готовых документов")
    st.caption("Поддерживаются форматы: txt, docx, pdf, xlsx, json (для опросника).")

    ok_key = f"imp_ok_{key_prefix}"
    if st.session_state.get(ok_key):
        st.success(st.session_state.pop(ok_key))

    form_ver = _import_form_version(key_prefix)
    fk = f"{key_prefix}_v{form_ver}"

    col1, col2 = st.columns(2)
    with col1:
        prof_file = st.file_uploader(
            "Профиль (файл)", type=["txt", "docx", "pdf", "xlsx"], key=f"imp_prof_{fk}"
        )
        prof_url = st.text_input("Профиль (ссылка на облако)", key=f"imp_prof_url_{fk}")
    with col2:
        quest_file = st.file_uploader(
            "Опросник (файл)", type=["txt", "docx", "pdf", "json", "xlsx"], key=f"imp_q_{fk}"
        )
        quest_url = st.text_input("Опросник (ссылка)", key=f"imp_q_url_{fk}")

    if doc_flags.get("vacancy_text"):
        vac_file = st.file_uploader(
            "Текст вакансии (файл)", type=["txt", "docx", "pdf", "xlsx"], key=f"imp_vac_{fk}"
        )
        vac_url = st.text_input("Текст вакансии (ссылка)", key=f"imp_vac_url_{fk}")
    else:
        vac_file = vac_url = None

    corrections = st.text_area("Коррективы для ИИ после импорта", height=80, key=f"imp_corr_{fk}")

    if st.button("📥 Импортировать и сохранить", key=f"imp_btn_{fk}"):
        imported = {}
        errors = []

        for key, file_obj, url, label in (
            ("profile", prof_file, prof_url, "Профиль"),
            ("questions", quest_file, quest_url, "Опросник"),
        ):
            text, err = _read_import_source(file_obj, url, deps, label)
            if err:
                errors.append(err)
            elif text:
                imported[key] = text

        if doc_flags.get("vacancy_text"):
            text, err = _read_import_source(vac_file, vac_url, deps, "Текст вакансии")
            if err:
                errors.append(err)
            elif text:
                imported["vacancy_text"] = text

        if errors:
            for err in errors:
                st.error(err)

        if not imported:
            if not errors:
                st.warning("Загрузите хотя бы профиль или опросник (файл или ссылка).")
        else:
            try:
                gen = {
                    "должность": vacancy["title"],
                    "профиль": {},
                    "текст_вакансии": "",
                    "опросник": [],
                    "ключевые_слова": [],
                }
                if "profile" in imported:
                    try:
                        gen["профиль"] = json.loads(imported["profile"])
                    except json.JSONDecodeError:
                        gen["профиль"] = {"raw": imported["profile"]}
                if "questions" in imported:
                    try:
                        gen["опросник"] = json.loads(imported["questions"])
                    except json.JSONDecodeError:
                        gen["опросник"] = [{"вопрос": imported["questions"], "пример_ответа": ""}]
                if "vacancy_text" in imported:
                    gen["текст_вакансии"] = imported["vacancy_text"]

                gen = deps["normalize_docs"](gen)
                gen = _prepare_generated_for_save(gen)
                if corrections.strip():
                    with st.spinner("Применение коррективов ИИ..."):
                        gen = refine_documents_with_ai(gen, corrections, deps)
                        gen = _prepare_generated_for_save(gen)

                saved, saved_labels = apply_generated_to_vacancy(
                    vacancy, gen, deps, doc_flags, only_fields=set(imported.keys())
                )
                if _report_generation_result(vacancy, saved, saved_labels):
                    invalidate_doc_session_state(vacancy["id"])
                    st.session_state[f"imp_form_v_{key_prefix}"] = form_ver + 1
                    st.rerun()
            except Exception as e:
                st.error(f"Ошибка импорта: {e}")


def _report_generation_result(vacancy, saved, saved_labels, *, partial_hint=None):
    title = vacancy.get("title", "вакансия")
    if not saved:
        st.error(f"Вакансия «{title}» не найдена в базе.")
        return False
    if not saved_labels:
        st.error(
            "ИИ вернул пустой или нераспознанный результат. "
            "Попробуйте сократить анкету или повторите генерацию."
        )
        return False

    labels = ", ".join(saved_labels)
    message = (
        f"✅ Документы сохранены для «{title}»: {labels}. "
        f"Откройте «Вакансии в работе» → «Документы по вакансии»."
    )
    if partial_hint:
        message += f" {partial_hint}"
    _set_doc_gen_flash(message)
    st.success(message)
    return True


def render_transcript_mode(vacancy, deps, doc_flags, key_prefix):
    st.markdown("##### Генерация из расшифровки")
    transcript = render_transcript_source(vacancy, deps, key_prefix)

    if st.button("✨ Сгенерировать документы", key=f"gen_tr_{key_prefix}"):
        if not transcript.strip():
            st.warning("Сначала получите или введите текст расшифровки.")
        else:
            with st.spinner("Генерация..."):
                try:
                    gen = deps["generate_from_transcript"](
                        transcript, vacancy["title"], doc_flags=doc_flags
                    )
                    gen = _prepare_generated_for_save(gen)
                    saved, saved_labels = apply_generated_to_vacancy(
                        vacancy, gen, deps, doc_flags
                    )
                    if _report_generation_result(vacancy, saved, saved_labels):
                        invalidate_doc_session_state(vacancy["id"])
                        deps["save_generation_to_history"](
                            gen, transcript, vacancy_title=vacancy["title"]
                        )
                except Exception as e:
                    st.error(f"Ошибка генерации: {e}")


def render_wizard_mode(vacancy, deps, doc_flags, key_prefix):
    st.markdown("##### Анкета HR")
    clarify_key = _vac_key(vacancy["id"], f"clarify_q_{key_prefix}")
    if clarify_key not in st.session_state:
        st.session_state[clarify_key] = []

    for field_id, label in WIZARD_FIELDS:
        widget_key = _wizard_field_key(key_prefix, field_id)
        if widget_key not in st.session_state:
            st.session_state[widget_key] = ""
        st.text_area(label, height=80, key=widget_key)

    if st.button("🤖 Запросить уточнения у ИИ", key=f"clarify_btn_{key_prefix}"):
        answers = _collect_wizard_answers(key_prefix)
        if not _wizard_answers_filled(answers):
            st.warning("Заполните хотя бы одно поле анкеты.")
        else:
            with st.spinner("Формируем уточняющие вопросы..."):
                try:
                    st.session_state[clarify_key] = get_clarify_questions(answers, deps)
                    st.rerun()
                except Exception as e:
                    st.error(f"Не удалось получить уточнения: {e}")

    clarify_questions = st.session_state.get(clarify_key, [])
    for i, q in enumerate(clarify_questions):
        st.text_input(q, key=f"clar_{key_prefix}_{i}")

    if st.button("✨ Сгенерировать из анкеты", key=f"wiz_gen_{key_prefix}"):
        answers = _collect_wizard_answers(key_prefix)
        if not _wizard_answers_filled(answers):
            st.warning("Заполните хотя бы одно поле анкеты.")
        else:
            answers["clarifications"] = _collect_clarify_answers(
                key_prefix, clarify_questions
            )
            status = st.status("Генерация документов из анкеты…", expanded=True)
            try:
                status.write("Отправляем данные в ИИ (это может занять 1–3 минуты)…")
                gen = generate_package_from_wizard(
                    answers,
                    deps,
                    doc_flags,
                    vacancy_title=vacancy.get("title"),
                )
                status.write("Сохраняем результат в вакансию…")
                saved, saved_labels = apply_generated_to_vacancy(
                    vacancy, gen, deps, doc_flags
                )
                partial_hint = None
                if saved_labels and "профиль" not in saved_labels:
                    partial_hint = (
                        "Профиль не сформировался полностью — "
                        "при необходимости перегенерируйте его в «Документы по вакансии»."
                    )
                if _report_generation_result(
                    vacancy, saved, saved_labels, partial_hint=partial_hint
                ):
                    status.update(label="Готово", state="complete", expanded=False)
                    invalidate_doc_session_state(vacancy["id"])
                    deps["save_generation_to_history"](
                        gen, None, vacancy_title=vacancy["title"]
                    )
                else:
                    status.update(label="Не удалось сохранить", state="error", expanded=True)
            except Exception as e:
                status.update(label="Ошибка генерации", state="error", expanded=True)
                st.error(f"Ошибка генерации: {e}")


def render_creation_zone(vacancy, deps):
    """Меню создания документов (только для зоны «Создание новой вакансии»)."""
    doc_flags = get_doc_flags_from_ui(f"create_{vacancy['id']}")

    mode = st.radio(
        "Способ подготовки",
        ("Из расшифровки", "Импорт", "Анкета HR"),
        horizontal=True,
        key=f"create_mode_{vacancy['id']}",
    )

    if mode == "Из расшифровки":
        render_transcript_mode(vacancy, deps, doc_flags, f"create_{vacancy['id']}")
    elif mode == "Импорт":
        render_import_mode(vacancy, deps, doc_flags, f"create_{vacancy['id']}")
    else:
        render_wizard_mode(vacancy, deps, doc_flags, f"create_{vacancy['id']}")


def _resolve_chat_from_template(chats, template):
    from telegram_notify import chat_ids_equal

    tpl_chat = template.get("chat_id")
    if tpl_chat is None:
        return None
    return next((c for c in chats if chat_ids_equal(c["id"], tpl_chat)), None)


def render_new_vacancy_form(deps):
    """Создание вакансии + выбор для генерации документов."""
    from vacancy_template_store import list_templates

    _render_doc_gen_flash()
    st.markdown("##### Регистрация вакансии")

    creation_mode = st.radio(
        "Способ создания",
        ("С нуля", "Из шаблона"),
        horizontal=True,
        key="new_vac_mode",
    )

    chats = deps["load_chats"]()
    templates = list_templates()
    selected_template = None

    if creation_mode == "Из шаблона":
        if not templates:
            st.info(
                "Нет шаблонов. Откройте вакансию → «Документы по вакансии» → "
                "«Сохранить как шаблон»."
            )
        else:
            picked_name = selectbox_no_default(
                "Шаблон",
                [t["name"] for t in templates],
                key="new_vac_tpl_picker",
            )
            if picked_name:
                selected_template = next(t for t in templates if t["name"] == picked_name)
                updated = (selected_template.get("updated_at") or "")[:10]
                st.caption(
                    f"Эталон роли: **{selected_template.get('title', '—')}**"
                    + (f" · обновлён {updated}" if updated else "")
                )
                if st.session_state.get("new_vac_active_tpl") != selected_template["id"]:
                    st.session_state.new_vac_active_tpl = selected_template["id"]
                    st.session_state.new_vac_title = selected_template.get("title", "")

    new_title = st.text_input("Название должности", key="new_vac_title")

    chat_id = ""
    client_id = 0
    if chats:
        chat_names = [c["name"] for c in chats]
        selected_chat_name = selectbox_no_default("Чат Telegram", chat_names, key="new_vac_chat")
        if selected_chat_name:
            chat = next(c for c in chats if c["name"] == selected_chat_name)
            chat_id = chat["id"]
            client_id = chat.get("department_id", 0)
            st.caption(f"Подразделение: {chat.get('department_name', '—')}")
        elif selected_template:
            tpl_chat = _resolve_chat_from_template(chats, selected_template)
            if tpl_chat:
                st.caption(
                    f"Чат из шаблона: **{tpl_chat['name']}** "
                    f"(будет использован, если не выберете другой)"
                )
    else:
        st.warning("Добавьте чат во вкладке «Настройки».")

    show_portfolio_field = st.checkbox(
        "Поле «Портфолио» в карточке кандидата",
        value=False,
        key="new_vac_show_portfolio",
        help="Можно включить позже в настройках вакансии.",
    )

    if st.button("Создать вакансию", key="create_vac_btn", type="primary"):
        title = new_title.strip()
        if not title:
            st.warning("Введите название должности.")
        elif creation_mode == "Из шаблона":
            if not selected_template:
                st.warning("Выберите шаблон.")
            else:
                resolved_chat = chat_id or selected_template.get("chat_id")
                resolved_client = client_id if chat_id else selected_template.get("client_id", 0)
                if not resolved_chat:
                    st.warning("Выберите чат Telegram или сохраните чат в шаблоне.")
                else:
                    ok, msg = deps["create_vacancy_from_template"](
                        selected_template["id"],
                        title,
                        chat_id=chat_id or None,
                        client_id=resolved_client if chat_id else None,
                    )
                    if ok:
                        if show_portfolio_field:
                            all_v = deps["load_vacancies"]()
                            for v in all_v:
                                if v["id"] == msg["id"]:
                                    v["show_portfolio_field"] = True
                            deps["save_vacancies"](all_v)
                        st.session_state.opened_vacancy_id = msg["id"]
                        st.session_state.creation_vacancy_title = title
                        st.success(
                            f"Вакансия «{title}» создана из шаблона «{selected_template['name']}». "
                            "Документы уже подставлены — проверьте их во вкладке «Вакансии в работе»."
                        )
                        st.rerun()
                    else:
                        st.error(msg or "Ошибка создания")
        elif not chat_id:
            st.warning("Выберите чат Telegram.")
        else:
            ok, msg = deps["create_vacancy"](
                title, chat_id, client_id, show_portfolio_field=show_portfolio_field
            )
            if ok:
                st.session_state.opened_vacancy_id = None
                st.session_state.creation_vacancy_title = title
                st.success(f"Вакансия «{title}» создана. Теперь сгенерируйте документы ниже.")
                st.rerun()
            else:
                st.error(msg or "Ошибка создания")

    st.divider()
    st.markdown("##### Генерация документов для вакансии")

    vacancies = [v for v in deps["load_vacancies"]() if v.get("active", True)]
    if not vacancies:
        st.info("Сначала создайте вакансию.")
        return

    if st.session_state.get("creation_vacancy_title"):
        st.info(
            f"Недавно создана вакансия: **{st.session_state.creation_vacancy_title}**. "
            "Выберите её в списке ниже для генерации документов."
        )

    titles = [v["title"] for v in vacancies]
    target_title = selectbox_no_default(
        "Выберите вакансию для создания документов",
        titles,
        key="creation_vac_picker",
    )

    if not target_title:
        st.caption("Выберите вакансию, для которой нужно создать документы.")
        return

    vacancy = next(v for v in vacancies if v["title"] == target_title)
    render_creation_zone(vacancy, deps)
