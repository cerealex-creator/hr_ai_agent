"""Safe merge updates for vacancy.documents (v2 / PostgreSQL only)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models

# Editable HR docs — never include hh_search_criteria (owned by HH endpoints)
EDITABLE_DOCUMENT_KEYS = (
    "profile",
    "vacancy_text",
    "questions",
    "keywords",
    "notes",
)


def _serialize_value(value: Any) -> Any:
    """Store values in a shape Streamlit / readers already tolerate."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return value
    return str(value)


def merge_vacancy_documents(
    vacancy: models.Vacancy,
    updates: dict[str, Any],
    *,
    clear_missing: bool = False,
) -> dict:
    """
    Shallow-merge known keys into vacancy.documents.
    Unknown keys ignored. hh_search_criteria never overwritten here.
    - Key omitted from updates → unchanged
    - Key present with "" / null → cleared to ""
    """
    docs = dict(vacancy.documents or {})
    for key in EDITABLE_DOCUMENT_KEYS:
        if key not in updates:
            if clear_missing:
                docs[key] = ""
            continue
        docs[key] = _serialize_value(updates[key])
    vacancy.documents = docs
    flag_modified(vacancy, "documents")
    return docs


def documents_for_editor(documents: dict | None) -> dict[str, str]:
    """Flatten current docs to textarea-friendly strings for the UI."""
    docs = documents or {}
    out: dict[str, str] = {}
    for key in EDITABLE_DOCUMENT_KEYS:
        val = docs.get(key)
        if val is None:
            out[key] = ""
        elif isinstance(val, str):
            out[key] = val
        else:
            try:
                out[key] = json.dumps(val, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                out[key] = str(val)
    return out


def save_documents(
    db: Session,
    vacancy: models.Vacancy,
    updates: dict[str, Any],
) -> models.Vacancy:
    merge_vacancy_documents(vacancy, updates)
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy
