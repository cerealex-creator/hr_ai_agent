"""СУП U5 — план перехода из gap + трекер покрытия + preview профиля вакансии."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_assignments import list_role_assignments, list_roles
from app.services.management_gap import build_gap_report
from app.services.management_role_docs import list_document_lines, list_role_documents

# gap code → (action_code, recommendation, horizon, default title template)
GAP_TO_ACTION: dict[str, tuple[str, str, str]] = {
    "COVERAGE_NONE": ("hire", "нанять / создать слот", "short"),
    "COVERAGE_PARTIAL": ("reinforce", "усилить headcount", "medium"),
    "OVERLOAD": ("split", "разделить нагрузку", "medium"),
    "STEP_NO_ROLE": ("assign_owner", "назначить владельца шага", "short"),
    "NO_ASSIGNMENTS": ("map_as_is", "сопоставить as-is → to-be", "short"),
    "PACK_SUGGESTED_GOALS": ("review_pack", "принять/отклонить цели пакета", "short"),
    "GOAL_NUMERIC_GAP": ("close_metric", "закрыть цифровой разрыв цели", "long"),
}


class TransitionError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def list_gap_items(db: Session, revision_id: uuid.UUID) -> list[m.MgmtGapItem]:
    return list(
        db.scalars(
            select(m.MgmtGapItem)
            .where(m.MgmtGapItem.revision_id == revision_id)
            .order_by(m.MgmtGapItem.sort_order)
        ).all()
    )


def list_transition_steps(db: Session, revision_id: uuid.UUID) -> list[m.MgmtTransitionStep]:
    return list(
        db.scalars(
            select(m.MgmtTransitionStep)
            .where(m.MgmtTransitionStep.revision_id == revision_id)
            .order_by(m.MgmtTransitionStep.sort_order, m.MgmtTransitionStep.created_at)
        ).all()
    )


def persist_gap_items(db: Session, revision_id: uuid.UUID) -> list[m.MgmtGapItem]:
    """Перезаписать snapshot gap_items из текущего отчёта."""
    report = build_gap_report(db, revision_id)
    for old in list_gap_items(db, revision_id):
        # не удаляем transition_steps с FK — обнулим gap_item_id
        for step in db.scalars(
            select(m.MgmtTransitionStep).where(m.MgmtTransitionStep.gap_item_id == old.id)
        ).all():
            step.gap_item_id = None
        db.delete(old)
    db.flush()

    created: list[m.MgmtGapItem] = []
    for i, item in enumerate(report.get("items") or []):
        code = str(item.get("code") or "UNKNOWN")
        mapping = GAP_TO_ACTION.get(code)
        recommendation = mapping[1] if mapping else None
        entity_id = None
        if item.get("entity_id"):
            try:
                entity_id = uuid.UUID(str(item["entity_id"]))
            except (TypeError, ValueError):
                entity_id = None
        row = m.MgmtGapItem(
            revision_id=revision_id,
            code=code,
            severity=str(item.get("severity") or "info"),
            title=str(item.get("title") or code)[:512],
            message=str(item.get("message") or ""),
            entity_type=item.get("entity_type"),
            entity_id=entity_id,
            recommendation=recommendation,
            sort_order=i,
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def draft_transition_steps_from_gap(
    db: Session,
    revision_id: uuid.UUID,
    *,
    replace_drafts: bool = True,
) -> dict:
    """INSERT from SELECT: gap_items → transition_steps (draft)."""
    gaps = persist_gap_items(db, revision_id)
    if replace_drafts:
        for step in list_transition_steps(db, revision_id):
            if step.status == "draft":
                db.delete(step)
        db.flush()

    existing_gap_ids = {
        s.gap_item_id
        for s in list_transition_steps(db, revision_id)
        if s.gap_item_id is not None
    }

    created = 0
    base = len(list_transition_steps(db, revision_id))
    for i, gap in enumerate(gaps):
        if gap.id in existing_gap_ids:
            continue
        mapping = GAP_TO_ACTION.get(gap.code)
        if not mapping:
            # info-only qualitative — пропускаем как шаг плана
            if gap.severity == "info" and gap.code in ("GOAL_QUALITATIVE",):
                continue
            action, horizon = "review", "medium"
            rec = gap.recommendation or "проработать разрыв"
        else:
            action, rec, horizon = mapping
        title = f"{rec.capitalize()}: {gap.title}"[:512]
        description = gap.message
        step = m.MgmtTransitionStep(
            revision_id=revision_id,
            gap_item_id=gap.id,
            action_code=action,
            title=title,
            description=description,
            horizon=horizon,
            status="draft",
            sort_order=base + i,
            meta={"gap_code": gap.code, "severity": gap.severity},
        )
        db.add(step)
        created += 1
    db.flush()
    return {
        "ok": True,
        "gap_items": len(gaps),
        "steps_created": created,
        "steps_total": len(list_transition_steps(db, revision_id)),
    }


def approve_transition_step(
    db: Session, revision_id: uuid.UUID, step_id: uuid.UUID
) -> m.MgmtTransitionStep:
    step = db.get(m.MgmtTransitionStep, step_id)
    if not step or step.revision_id != revision_id:
        raise TransitionError("NOT_FOUND", "Шаг плана не найден")
    if step.status == "approved":
        return step
    step.status = "approved"
    step.stale = False
    db.flush()
    return step


def reject_transition_step(
    db: Session, revision_id: uuid.UUID, step_id: uuid.UUID
) -> m.MgmtTransitionStep:
    step = db.get(m.MgmtTransitionStep, step_id)
    if not step or step.revision_id != revision_id:
        raise TransitionError("NOT_FOUND", "Шаг плана не найден")
    step.status = "rejected"
    db.flush()
    return step


def update_transition_step(
    db: Session,
    revision_id: uuid.UUID,
    step_id: uuid.UUID,
    *,
    title: str | None = None,
    description: str | None = None,
    horizon: str | None = None,
) -> m.MgmtTransitionStep:
    step = db.get(m.MgmtTransitionStep, step_id)
    if not step or step.revision_id != revision_id:
        raise TransitionError("NOT_FOUND", "Шаг плана не найден")
    if title is not None:
        step.title = title.strip()[:512]
    if description is not None:
        step.description = description.strip() or None
    if horizon is not None:
        if horizon not in ("short", "medium", "long"):
            raise TransitionError("BAD_HORIZON", "horizon: short|medium|long")
        step.horizon = horizon
    if step.status == "approved":
        step.status = "draft"
        step.stale = True
    db.flush()
    return step


def transition_step_out(step: m.MgmtTransitionStep) -> dict:
    return {
        "id": str(step.id),
        "revision_id": str(step.revision_id),
        "gap_item_id": str(step.gap_item_id) if step.gap_item_id else None,
        "action_code": step.action_code,
        "title": step.title,
        "description": step.description,
        "horizon": step.horizon,
        "status": step.status,
        "stale": step.stale,
        "sort_order": step.sort_order,
        "meta": step.meta or {},
    }


def gap_item_out(item: m.MgmtGapItem) -> dict:
    return {
        "id": str(item.id),
        "revision_id": str(item.revision_id),
        "code": item.code,
        "severity": item.severity,
        "title": item.title,
        "message": item.message,
        "entity_type": item.entity_type,
        "entity_id": str(item.entity_id) if item.entity_id else None,
        "recommendation": item.recommendation,
        "sort_order": item.sort_order,
    }


def build_coverage_tracker(db: Session, revision_id: uuid.UUID) -> dict:
    """Трекер: инструкции / чек-листы / KPI / назначения по ролям."""
    roles = list_roles(db, revision_id)
    docs = list_role_documents(db, revision_id)
    docs_by_role: dict[uuid.UUID, dict[str, m.MgmtRoleDocument]] = {}
    for d in docs:
        docs_by_role.setdefault(d.role_id, {})[d.doc_kind] = d
    assignments = list_role_assignments(db, revision_id)
    assigned_roles = {a.target_role_id for a in assignments if a.coverage != "none"}

    rows = []
    for role in roles:
        by_kind = docs_by_role.get(role.id, {})
        instr = by_kind.get("instruction")
        kpi = by_kind.get("kpi")
        check = by_kind.get("checklist")

        def _ok(doc: m.MgmtRoleDocument | None) -> bool:
            if not doc:
                return False
            if doc.status not in ("approved", "published"):
                return False
            return len(list_document_lines(db, doc.id)) > 0

        rows.append(
            {
                "role_id": str(role.id),
                "role_title": role.title,
                "instruction": _ok(instr),
                "checklist": _ok(check),
                "kpi": _ok(kpi) or (kpi is not None and not list_document_lines(db, kpi.id)),
                "assignment": role.id in assigned_roles,
                "instruction_status": instr.status if instr else None,
                "checklist_status": check.status if check else None,
                "kpi_status": kpi.status if kpi else None,
            }
        )

    total = len(rows) or 1
    return {
        "revision_id": str(revision_id),
        "roles": rows,
        "summary": {
            "roles": len(rows),
            "instruction_ok": sum(1 for r in rows if r["instruction"]),
            "checklist_ok": sum(1 for r in rows if r["checklist"]),
            "kpi_ok": sum(1 for r in rows if r["kpi"]),
            "assignment_ok": sum(1 for r in rows if r["assignment"]),
            "pct_instruction": round(100 * sum(1 for r in rows if r["instruction"]) / total),
            "pct_checklist": round(100 * sum(1 for r in rows if r["checklist"]) / total),
            "pct_kpi": round(100 * sum(1 for r in rows if r["kpi"]) / total),
            "pct_assignment": round(100 * sum(1 for r in rows if r["assignment"]) / total),
        },
    }


def build_role_vacancy_profile_preview(db: Session, revision_id: uuid.UUID, role_id: uuid.UUID) -> dict:
    """Preview профиля вакансии из утверждённой роли (без записи в vacancy)."""
    role = db.get(m.MgmtRole, role_id)
    if not role or role.revision_id != revision_id:
        raise TransitionError("NOT_FOUND", "Роль не найдена")

    docs = [d for d in list_role_documents(db, revision_id) if d.role_id == role_id]
    duties: list[str] = []
    checklist: list[str] = []
    kpis: list[dict] = []
    for doc in docs:
        lines = list_document_lines(db, doc.id)
        if doc.doc_kind == "instruction":
            duties = [ln.title for ln in lines]
        elif doc.doc_kind == "checklist":
            checklist = [ln.title for ln in lines]
        elif doc.doc_kind == "kpi":
            kpis = [
                {
                    "title": ln.title,
                    "target": float(ln.target_value) if ln.target_value is not None else None,
                    "unit": ln.metric_unit,
                }
                for ln in lines
            ]

    profile = {
        "source_role_id": str(role.id),
        "title": role.title,
        "external_key": role.external_key,
        "duties": duties,
        "checklist": checklist,
        "kpis": kpis,
        "role_status": role.status,
        "documents_status": {d.doc_kind: d.status for d in docs},
    }
    warnings: list[str] = []
    if role.status not in ("approved", "published"):
        warnings.append("Роль ещё не утверждена (L2b)")
    if not duties:
        warnings.append("Нет обязанностей — соберите/утвердите instruction")
    return {"ok": len(warnings) == 0, "profile": profile, "warnings": warnings}


def apply_role_profile_to_vacancy(
    db: Session,
    *,
    organization_id: uuid.UUID,
    vacancy_id: int,
    revision_id: uuid.UUID,
    role_id: uuid.UUID,
) -> dict:
    """Записать preview профиля в vacancy.documents.profile (U5 bridge)."""
    from app.db import models as core

    vac = db.get(core.Vacancy, vacancy_id)
    if not vac:
        raise TransitionError("NOT_FOUND", "Вакансия не найдена")
    client = db.get(core.Client, vac.client_id) if vac.client_id else None
    if not client or client.organization_id != organization_id:
        raise TransitionError("NOT_FOUND", "Вакансия не принадлежит организации")
    preview = build_role_vacancy_profile_preview(db, revision_id, role_id)
    docs = dict(vac.documents or {})
    docs["profile"] = preview["profile"]
    vac.documents = docs
    db.flush()
    return {
        "ok": True,
        "vacancy_id": str(vacancy_id),
        "warnings": preview["warnings"],
        "profile": preview["profile"],
    }
