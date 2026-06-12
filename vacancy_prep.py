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
    deps["update_vacancy_docs"](vacancy["title"], {
        "profile": profile,
        "vacancy_text": vacancy_text,
        "questions": questions,
        "keywords": keywords,
    })


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


def render_existing_documents_zone(vacancy, deps):
    """Подзона «Документы по вакансии» — только просмотр и редактирование."""
    docs = vacancy.get("documents", {})
    prof_key, vac_key, q_key, kw_key = _init_doc_state(vacancy, docs)

    st.caption(
        "Статус в базе: "
        f"профиль — {_doc_field_status(docs.get('profile'))}, "
        f"текст вакансии — {_doc_field_status(docs.get('vacancy_text'))}, "
        f"опросник — {_doc_field_status(docs.get('questions'))}, "
        f"ключевые слова — {_doc_field_status(docs.get('keywords'))}."
    )

    profile_expanded = bool((docs.get("profile") or "").strip())
    with st.expander("📋 Профиль должности", expanded=profile_expanded):
        render_profile_section(vacancy, prof_key, deps)

    with st.expander("📄 Текст вакансии", expanded=False):
        render_vacancy_text_section(vacancy, vac_key, prof_key, deps)

    with st.expander("❓ Опросник для собеседования", expanded=False):
        def on_q_apply(new_q):
            st.session_state[q_key] = json.dumps(new_q, ensure_ascii=False, indent=2)

        deps["render_questionnaire_edit_panel"](
            job_title=vacancy["title"],
            profile=st.session_state[prof_key],
            questionnaire=st.session_state[q_key],
            key_prefix=f"vac_doc_{vacancy['id']}",
            on_apply=on_q_apply,
        )

    with st.expander("🔑 Ключевые слова", expanded=False):
        render_keywords_section(vacancy, kw_key, prof_key, deps)

    if st.button("💾 Сохранить все документы", key=f"save_docs_{vacancy['id']}", type="primary"):
        save_documents_from_editor(
            vacancy,
            st.session_state[prof_key],
            st.session_state[vac_key],
            st.session_state[q_key],
            st.session_state[kw_key],
            deps,
        )
        vacancy["documents"].update({
            "profile": st.session_state[prof_key],
            "vacancy_text": st.session_state[vac_key],
            "questions": st.session_state[q_key],
            "keywords": st.session_state[kw_key],
        })
        st.session_state[_vac_key(vacancy["id"], "docs_fp")] = _docs_fingerprint(vacancy["documents"])
        st.success("Документы сохранены!")
        st.rerun()

    gen = {
        "должность": vacancy["title"],
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
            file_name=f"{vacancy['title']}_docs.json",
            mime="application/json",
            key=f"dl_json_{vacancy['id']}",
        )
    with exp2:
        if st.button("📄 Word", key=f"dl_word_{vacancy['id']}"):
            path = deps["export_to_word"](gen)
            if path:
                with open(path, "rb") as f:
                    st.download_button(
                        "Скачать Word",
                        data=f.read(),
                        file_name=f"{vacancy['title']}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_word_file_{vacancy['id']}",
                    )
    with exp3:
        if st.button("📕 PDF", key=f"dl_pdf_{vacancy['id']}"):
            path = deps["export_to_pdf"](gen)
            if path:
                with open(path, "rb") as f:
                    st.download_button(
                        "Скачать PDF",
                        data=f.read(),
                        file_name=f"{vacancy['title']}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_file_{vacancy['id']}",
                    )


def transcribe_uploaded_audio(uploaded_file, method, deps):
    os.makedirs("data/tmp", exist_ok=True)
    audio_path = os.path.join("data/tmp", uploaded_file.name)
    with open(audio_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    if method == "Локально (Whisper)":
        return deps["transcribe_whisper_local"](audio_path), None
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
        method = st.radio(
            "Метод расшифровки",
            ("Локально (Whisper)", "Яндекс (SpeechKit)"),
            horizontal=True,
            key=f"meth_{key_prefix}_{vacancy['id']}",
        )
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


def render_new_vacancy_form(deps):
    """Создание вакансии + выбор для генерации документов."""
    _render_doc_gen_flash()
    st.markdown("##### Регистрация вакансии")
    chats = deps["load_chats"]()
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
    else:
        st.warning("Добавьте чат во вкладке «Настройки».")

    created_vacancy = None
    if st.button("Создать вакансию", key="create_vac_btn", type="primary"):
        if not new_title.strip():
            st.warning("Введите название должности.")
        elif not chat_id:
            st.warning("Выберите чат Telegram.")
        else:
            ok, msg = deps["create_vacancy"](new_title.strip(), chat_id, client_id)
            if ok:
                st.session_state.opened_vacancy_id = None
                st.session_state.creation_vacancy_title = new_title.strip()
                st.success(f"Вакансия «{new_title}» создана. Теперь сгенерируйте документы ниже.")
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
