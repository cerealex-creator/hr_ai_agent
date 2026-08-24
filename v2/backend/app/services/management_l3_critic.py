"""СУП U4 — критик перед publish L3 (код + опциональный LLM)."""
from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import management_models as m
from app.services.ai_json import chat_json
from app.services.management_assignments import list_roles
from app.services.management_role_docs import (
    list_document_lines,
    list_role_documents,
    validate_kpi_document,
)

CRITIC_SYSTEM = """Ты — критик пакета документов ролей (L3) для SME.
Проверь связность и ясность. Не предлагай менять id или структуру.
Верни ТОЛЬКО JSON:
{
  "blocking": [{"code":"...", "message":"..."}],
  "warnings": [{"code":"...", "message":"..."}]
}
blocking — нельзя публиковать; warnings — можно, но показать человеку."""


def run_deterministic_l3_critic(db: Session, revision_id: uuid.UUID) -> dict:
    blocking: list[dict] = []
    warnings: list[dict] = []

    roles = list_roles(db, revision_id)
    docs = list_role_documents(db, revision_id)
    docs_by_role: dict[uuid.UUID, list[m.MgmtRoleDocument]] = {}
    for d in docs:
        docs_by_role.setdefault(d.role_id, []).append(d)

    steps = list(
        db.scalars(select(m.MgmtProcessStep).where(m.MgmtProcessStep.revision_id == revision_id)).all()
    )
    for step in steps:
        if not step.role_id:
            warnings.append(
                {"code": "STEP_NO_ROLE", "message": f"Шаг «{step.title[:80]}» без роли"}
            )

    for role in roles:
        role_docs = docs_by_role.get(role.id, [])
        kinds = {d.doc_kind for d in role_docs}
        if "instruction" not in kinds:
            blocking.append(
                {
                    "code": "MISSING_INSTRUCTION",
                    "message": f"Роль «{role.title}»: нет instruction — сначала соберите L3",
                }
            )
            continue

        instr = next(d for d in role_docs if d.doc_kind == "instruction")
        if instr.status not in ("approved", "published"):
            blocking.append(
                {
                    "code": "INSTRUCTION_NOT_APPROVED",
                    "message": f"Роль «{role.title}»: инструкция не утверждена",
                }
            )
        if not list_document_lines(db, instr.id):
            blocking.append(
                {
                    "code": "EMPTY_INSTRUCTION",
                    "message": f"Роль «{role.title}»: пустая инструкция",
                }
            )
        if instr.stale:
            warnings.append(
                {
                    "code": "STALE_INSTRUCTION",
                    "message": f"Роль «{role.title}»: инструкция stale",
                }
            )

        kpi = next((d for d in role_docs if d.doc_kind == "kpi"), None)
        if kpi:
            for e in validate_kpi_document(db, revision_id, kpi):
                blocking.append({"code": "KPI_INVARIANT", "message": f"«{role.title}»: {e}"})
            if kpi.status not in ("approved", "published") and list_document_lines(db, kpi.id):
                warnings.append(
                    {
                        "code": "KPI_NOT_APPROVED",
                        "message": f"Роль «{role.title}»: KPI не утверждён",
                    }
                )

        check = next((d for d in role_docs if d.doc_kind == "checklist"), None)
        if check and check.status not in ("approved", "published") and list_document_lines(db, check.id):
            warnings.append(
                {
                    "code": "CHECKLIST_NOT_APPROVED",
                    "message": f"Роль «{role.title}»: чек-лист не утверждён",
                }
            )

    stale_docs = [d for d in docs if d.stale]
    if stale_docs:
        warnings.append({"code": "STALE_DOCS", "message": f"Stale-документов: {len(stale_docs)}"})

    return {
        "ok": len(blocking) == 0,
        "blocking": blocking,
        "warnings": warnings,
        "source": "deterministic",
    }


def run_llm_l3_critic(
    settings: Settings,
    db: Session,
    revision_id: uuid.UUID,
    *,
    max_retries: int = 2,
) -> dict:
    docs = list_role_documents(db, revision_id)
    summary = []
    for doc in docs[:20]:
        lines = list_document_lines(db, doc.id)[:12]
        summary.append(
            {
                "role_id": str(doc.role_id),
                "doc_kind": doc.doc_kind,
                "status": doc.status,
                "stale": doc.stale,
                "lines": [ln.title for ln in lines],
            }
        )
    user = f"Пакет L3 (сжато):\n{summary}"
    raw: dict[str, Any] | None = None
    for attempt in range(max_retries):
        try:
            raw = chat_json(
                settings,
                system=CRITIC_SYSTEM,
                user=user,
                temperature=0.1,
                max_tokens=2000,
                db=db,
                task="mgmt_l3_critic_before_publish",
            )
            if isinstance(raw, dict):
                break
            time.sleep(0.3 * (attempt + 1))
        except Exception:  # noqa: BLE001
            time.sleep(0.3 * (attempt + 1))
            raw = None

    if not isinstance(raw, dict):
        return {"blocking": [], "warnings": [], "source": "llm_unavailable"}

    def _norm(items: Any) -> list[dict]:
        out: list[dict] = []
        if not isinstance(items, list):
            return out
        for it in items:
            if not isinstance(it, dict):
                continue
            code = str(it.get("code") or "LLM_NOTE")[:64]
            message = str(it.get("message") or "").strip()
            if message:
                out.append({"code": code, "message": message[:500]})
        return out

    return {
        "blocking": _norm(raw.get("blocking")),
        "warnings": _norm(raw.get("warnings")),
        "source": "llm",
    }


def run_l3_publish_critic(
    settings: Settings | None,
    db: Session,
    revision_id: uuid.UUID,
    *,
    use_llm: bool = False,
) -> dict:
    det = run_deterministic_l3_critic(db, revision_id)
    blocking = list(det["blocking"])
    warnings = list(det["warnings"])
    sources = [det["source"]]
    if use_llm and settings is not None:
        llm = run_llm_l3_critic(settings, db, revision_id)
        # LLM в MVP не блокирует publish — только warnings
        warnings.extend(llm.get("blocking") or [])
        warnings.extend(llm.get("warnings") or [])
        sources.append(llm.get("source") or "llm")
    return {
        "ok": len(blocking) == 0,
        "blocking": blocking,
        "warnings": warnings,
        "sources": sources,
    }
