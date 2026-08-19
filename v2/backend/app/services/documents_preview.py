KEYWORD_DOC_KEYS = frozenset({"keywords", "ключевые_слова", "ключевые слова"})


def history_preview(snapshot: dict | None, limit: int = 140) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    for key in ("текст_вакансии", "vacancy_text", "профиль", "profile", "preview"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            text = " ".join(value.split())
            if len(text) <= limit:
                return text
            return text[: limit - 1] + "…"
    return None


def strip_keyword_docs(documents: dict | None) -> dict:
    """Drop vacancy-document «keywords» block (demo UI)."""
    if not isinstance(documents, dict):
        return {}
    return {k: v for k, v in documents.items() if k not in KEYWORD_DOC_KEYS}


def nonempty_document_keys(documents: dict | None) -> list[str]:
    if not isinstance(documents, dict):
        return []
    skip = {"hh_search_criteria"}
    keys: list[str] = []
    for key, value in documents.items():
        if key in skip:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        keys.append(str(key))
    return keys
