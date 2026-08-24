"""СУП U4 — полировка формулировок строк L3 (без смены id / structure)."""
from __future__ import annotations

import re
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import management_models as m
from app.services.ai_json import chat_json
from app.services.management_role_docs import list_document_lines, list_role_documents

POLISH_SYSTEM = """Ты редактор HR-документов для SME.
Улучши формулировки пунктов должностной инструкции / чек-листа / KPI.
Правила:
- Не меняй смысл и не добавляй новые пункты.
- Не выдумывай цифры.
- Сохрани id каждой строки.
- Для KPI: title — короткое имя метрики; не трогай target.
Верни ТОЛЬКО JSON:
{"lines":[{"id":"uuid","title":"улучшенный текст"}]}"""


def _deterministic_polish(title: str, *, doc_kind: str) -> str:
    t = " ".join((title or "").split()).strip()
    if not t:
        return t
    # убрать дубли «Выполнить: Выполнить:»
    t = re.sub(r"^(Выполнить:\s*)+", "Выполнить: ", t, flags=re.IGNORECASE)
    if doc_kind == "instruction":
        # глагол с заглавной, без точки в конце для единообразия
        t = t[0].upper() + t[1:] if len(t) > 1 else t.upper()
        t = t.rstrip(".")
    elif doc_kind == "checklist":
        if not t.lower().startswith("выполнить:") and not t.endswith("?"):
            # оставить как есть, только capitalize
            t = t[0].upper() + t[1:] if len(t) > 1 else t.upper()
        t = t.rstrip(".")
    elif doc_kind == "kpi":
        t = t[0].upper() + t[1:] if len(t) > 1 else t.upper()
    return t[:512]


def polish_document_lines_deterministic(db: Session, document: m.MgmtRoleDocument) -> int:
    """Локальная полировка без LLM. Не трогает is_manual."""
    n = 0
    for line in list_document_lines(db, document.id):
        if line.is_manual:
            continue
        new_title = _deterministic_polish(line.title, doc_kind=document.doc_kind)
        if new_title and new_title != line.title:
            line.title = new_title
            n += 1
    db.flush()
    return n


def polish_document_lines_ai(
    settings: Settings,
    db: Session,
    document: m.MgmtRoleDocument,
    *,
    max_retries: int = 2,
) -> tuple[int, list[str]]:
    """ИИ-полировка неручных строк. Возвращает (updated_count, warnings)."""
    warnings: list[str] = []
    lines = [ln for ln in list_document_lines(db, document.id) if not ln.is_manual]
    if not lines:
        return 0, ["Нет строк для полировки (все ручные или пусто)"]

    payload_lines = [{"id": str(ln.id), "title": ln.title} for ln in lines]
    user = (
        f"Документ: {document.doc_kind} — {document.title}\n"
        f"Строки:\n{payload_lines}"
    )
    last_err: str | None = None
    raw: dict[str, Any] | None = None
    for attempt in range(max_retries):
        try:
            raw = chat_json(
                settings,
                system=POLISH_SYSTEM,
                user=user,
                temperature=0.2,
                max_tokens=2500,
                db=db,
                task="mgmt_l3_polish_lines",
            )
            if isinstance(raw, dict) and isinstance(raw.get("lines"), list):
                break
            last_err = "AI_SCHEMA_INVALID"
            time.sleep(0.3 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(0.3 * (attempt + 1))
            raw = None

    if not isinstance(raw, dict) or not isinstance(raw.get("lines"), list):
        # fallback deterministic
        n = polish_document_lines_deterministic(db, document)
        warnings.append(f"ИИ-полировка недоступна ({last_err}); применена локальная ({n})")
        return n, warnings

    by_id = {ln.id: ln for ln in lines}
    updated = 0
    for item in raw["lines"]:
        if not isinstance(item, dict):
            continue
        try:
            lid = uuid.UUID(str(item.get("id")))
        except (TypeError, ValueError):
            continue
        line = by_id.get(lid)
        if not line or line.is_manual:
            continue
        new_title = str(item.get("title") or "").strip()
        if not new_title or new_title == line.title:
            continue
        line.title = new_title[:512]
        updated += 1
    db.flush()
    if document.status == "approved":
        document.stale = True
    return updated, warnings


def polish_revision_documents(
    settings: Settings,
    db: Session,
    revision_id: uuid.UUID,
    *,
    document_id: uuid.UUID | None = None,
    use_ai: bool = True,
) -> dict:
    docs = list_role_documents(db, revision_id)
    if document_id:
        docs = [d for d in docs if d.id == document_id]
        if not docs:
            raise ValueError("Документ не найден")

    total = 0
    warnings: list[str] = []
    for doc in docs:
        if use_ai:
            n, w = polish_document_lines_ai(settings, db, doc)
        else:
            n = polish_document_lines_deterministic(db, doc)
            w = []
        total += n
        warnings.extend(w)
    return {"updated_lines": total, "documents": len(docs), "warnings": warnings}
