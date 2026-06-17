"""Хранение шаблонов вакансий (эталон: документы + привязка к чату)."""

import copy
import json
import os
import time
import uuid
from datetime import datetime

from vacancy_store import _atomic_write_json, _lock_file, _unlock_file

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_FILE = os.path.join(_PROJECT_ROOT, "data", "vacancy_templates.json")

EMPTY_DOCUMENTS = {
    "profile": "",
    "vacancy_text": "",
    "questions": "",
    "keywords": "",
    "notes": "",
}

DOCUMENT_FIELD_LABELS = {
    "profile": "Профиль должности",
    "vacancy_text": "Текст вакансии",
    "questions": "Опросник для собеседования",
    "keywords": "Ключевые слова",
}


def _read_templates_file():
    os.makedirs(os.path.dirname(TEMPLATES_FILE) or ".", exist_ok=True)
    if not os.path.exists(TEMPLATES_FILE):
        return {"templates": []}
    last_error = None
    for attempt in range(5):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                _lock_file(f, exclusive=False)
                try:
                    data = json.load(f)
                finally:
                    _unlock_file(f)
            if isinstance(data, list):
                return {"templates": data}
            return data
        except json.JSONDecodeError as exc:
            last_error = exc
            time.sleep(0.05 * (attempt + 1))
    raise last_error


def load_templates_data():
    return _read_templates_file()


def list_templates():
    templates = load_templates_data().get("templates", [])
    return sorted(
        templates,
        key=lambda t: t.get("updated_at") or t.get("created_at") or "",
        reverse=True,
    )


def _save_templates_data(data):
    _atomic_write_json(TEMPLATES_FILE, data)


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


def _field_has_content(key, value):
    if key == "profile":
        if isinstance(value, str) and value.strip():
            try:
                return _profile_has_content(json.loads(value))
            except json.JSONDecodeError:
                return _profile_has_content(value)
        return _profile_has_content(value)
    if key == "questions":
        if isinstance(value, str) and value.strip():
            try:
                return _questionnaire_has_content(json.loads(value))
            except json.JSONDecodeError:
                return _questionnaire_has_content(value)
        return _questionnaire_has_content(value)
    return bool((value or "").strip())


def _documents_have_content(documents):
    docs = documents or {}
    for key in DOCUMENT_FIELD_LABELS:
        if _field_has_content(key, docs.get(key, "")):
            return True
    return False


def get_missing_document_fields(documents):
    docs = documents or {}
    missing = []
    for key, label in DOCUMENT_FIELD_LABELS.items():
        if not _field_has_content(key, docs.get(key, "")):
            missing.append(label)
    return missing


def validate_template_documents(documents):
    missing = get_missing_document_fields(documents)
    if not _documents_have_content(documents):
        return (
            False,
            missing,
            "Невозможно сохранить шаблон: все документы пусты. Заполните хотя бы один раздел.",
        )
    if missing:
        return True, missing, f"Не заполнено: {', '.join(missing)}."
    return True, missing, None


def update_template_documents(template_id, documents):
    data = load_templates_data()
    templates = data.get("templates", [])
    changed = False
    for template in templates:
        if template.get("id") != template_id:
            continue
        template["documents"] = _copy_documents(documents)
        template["updated_at"] = datetime.now().isoformat()
        changed = True
        break
    if not changed:
        return False, "Шаблон не найден"
    data["templates"] = templates
    _save_templates_data(data)
    return True, "Документы шаблона сохранены"


def _copy_documents(documents):
    docs = documents or {}
    return {
        key: copy.deepcopy(docs.get(key, ""))
        for key in EMPTY_DOCUMENTS
    }


def find_template_by_name(name):
    name = (name or "").strip()
    if not name:
        return None
    for template in list_templates():
        if (template.get("name") or "").strip() == name:
            return template
    return None


def find_template_for_vacancy_title(vacancy_title):
    """Шаблон с тем же именем, что и название вакансии."""
    return find_template_by_name((vacancy_title or "").strip())


def _normalize_doc_value(key, value):
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if key in ("profile", "questions") and text:
            try:
                return json.dumps(json.loads(text), ensure_ascii=False, sort_keys=True)
            except json.JSONDecodeError:
                pass
        return text
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def documents_equal(docs_a, docs_b):
    left = docs_a or {}
    right = docs_b or {}
    for key in DOCUMENT_FIELD_LABELS:
        if _normalize_doc_value(key, left.get(key)) != _normalize_doc_value(key, right.get(key)):
            return False
    return True


def vacancy_matches_template(vacancy, documents, template):
    from telegram_notify import chat_ids_equal

    if not documents_equal(documents, template.get("documents") or {}):
        return False
    if not chat_ids_equal(vacancy.get("chat_id"), template.get("chat_id")):
        return False
    return vacancy.get("client_id", 0) == template.get("client_id", 0)


def get_template_sync_status(vacancy, documents=None):
    """
    Сравнение активной вакансии с шаблоном того же названия.
    Возвращает (status, template):
      no_content — нечего сохранять в шаблон;
      same — совпадает с шаблоном;
      missing — шаблона с таким именем нет;
      differs — шаблон есть, но данные отличаются.
    """
    docs = documents if documents is not None else (vacancy.get("documents") or {})
    if not _documents_have_content(docs):
        return "no_content", None

    title = (vacancy.get("title") or "").strip()
    template = find_template_for_vacancy_title(title)
    if not template:
        return "missing", None
    if vacancy_matches_template(vacancy, docs, template):
        return "same", template
    return "differs", template


def get_template(template_id):
    for template in list_templates():
        if template.get("id") == template_id:
            return template
    return None


def build_template_snapshot(vacancy, name):
    now = datetime.now().isoformat()
    docs = vacancy.get("documents") or {}
    return {
        "id": str(uuid.uuid4()),
        "name": (name or vacancy.get("title") or "").strip(),
        "title": (vacancy.get("title") or "").strip(),
        "chat_id": vacancy.get("chat_id"),
        "client_id": vacancy.get("client_id", 0),
        "documents": _copy_documents(docs),
        "source_vacancy_id": vacancy.get("id"),
        "created_at": now,
        "updated_at": now,
    }


def save_template_from_vacancy(vacancy, name, *, overwrite=True):
    name = (name or "").strip()
    if not name:
        return False, "Укажите название шаблона", None, []

    docs = vacancy.get("documents") or {}
    can_save, missing, validation_msg = validate_template_documents(docs)
    if not can_save:
        return False, validation_msg, None, missing

    data = load_templates_data()
    templates = data.setdefault("templates", [])
    existing = find_template_by_name(name)

    snapshot = build_template_snapshot(vacancy, name)
    if existing:
        snapshot["id"] = existing["id"]
        snapshot["created_at"] = existing.get("created_at") or snapshot["created_at"]
        templates[:] = [t for t in templates if t.get("id") != existing["id"]]

    templates.append(snapshot)
    _save_templates_data(data)
    action = "обновлён" if existing else "сохранён"
    base_msg = f"Шаблон «{name}» {action}"
    if validation_msg:
        return True, f"{base_msg}. {validation_msg}", snapshot, missing
    return True, base_msg, snapshot, missing


def add_vacancy_to_templates(vacancy, documents=None):
    """Добавляет или обновляет шаблон по названию вакансии."""
    docs = documents if documents is not None else (vacancy.get("documents") or {})
    vacancy_payload = {**vacancy, "documents": docs}
    name = (vacancy.get("title") or "").strip()
    if not name:
        return False, "У вакансии нет названия", [], None
    return save_template_from_vacancy(vacancy_payload, name, overwrite=True)


def delete_template(template_id):
    data = load_templates_data()
    templates = data.get("templates", [])
    before = len(templates)
    templates[:] = [t for t in templates if t.get("id") != template_id]
    if len(templates) == before:
        return False, "Шаблон не найден"
    data["templates"] = templates
    _save_templates_data(data)
    return True, "Шаблон удалён"
