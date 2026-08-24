"""СУП — документы ролей L3: materialize (INSERT from SELECT), approve, KPI invariant."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_assignments import list_roles
from app.services.management_graph import get_descendants
from app.services.management_system import create_link, list_links, list_tasks

DOC_KINDS = ("instruction", "kpi", "checklist")
DOC_TITLES = {
    "instruction": "Должностная инструкция",
    "kpi": "KPI",
    "checklist": "Чек-лист",
}


class RoleDocError(Exception):
    def __init__(self, code: str, message: str, errors: list[str] | None = None):
        self.code = code
        self.message = message
        self.errors = errors or []
        super().__init__(message)


def list_role_documents(db: Session, revision_id: uuid.UUID) -> list[m.MgmtRoleDocument]:
    return list(
        db.scalars(
            select(m.MgmtRoleDocument)
            .where(m.MgmtRoleDocument.revision_id == revision_id)
            .order_by(m.MgmtRoleDocument.role_id, m.MgmtRoleDocument.doc_kind)
        ).all()
    )


def list_document_lines(db: Session, document_id: uuid.UUID) -> list[m.MgmtRoleDocumentLine]:
    return list(
        db.scalars(
            select(m.MgmtRoleDocumentLine)
            .where(m.MgmtRoleDocumentLine.document_id == document_id)
            .order_by(m.MgmtRoleDocumentLine.sort_order)
        ).all()
    )


def _get_or_create_doc(
    db: Session,
    revision_id: uuid.UUID,
    role: m.MgmtRole,
    doc_kind: str,
) -> m.MgmtRoleDocument:
    doc = db.scalar(
        select(m.MgmtRoleDocument).where(
            m.MgmtRoleDocument.revision_id == revision_id,
            m.MgmtRoleDocument.role_id == role.id,
            m.MgmtRoleDocument.doc_kind == doc_kind,
        )
    )
    if doc:
        return doc
    doc = m.MgmtRoleDocument(
        revision_id=revision_id,
        role_id=role.id,
        doc_kind=doc_kind,
        title=f"{DOC_TITLES[doc_kind]} — {role.title}",
        status="draft",
    )
    db.add(doc)
    db.flush()
    return doc


def _clear_generated_lines(db: Session, document_id: uuid.UUID) -> None:
    """Удалить только автосгенерированные строки; is_manual сохраняем."""
    for line in list_document_lines(db, document_id):
        if not line.is_manual:
            # Убрать measures-links с этой строки
            for link in db.scalars(
                select(m.MgmtEntityLink).where(
                    m.MgmtEntityLink.source_type == "role_document_line",
                    m.MgmtEntityLink.source_id == line.id,
                )
            ).all():
                db.delete(link)
            db.delete(line)
    db.flush()


def _steps_for_role(db: Session, revision_id: uuid.UUID, role_id: uuid.UUID) -> list[m.MgmtProcessStep]:
    return list(
        db.scalars(
            select(m.MgmtProcessStep)
            .where(
                m.MgmtProcessStep.revision_id == revision_id,
                m.MgmtProcessStep.role_id == role_id,
            )
            .order_by(m.MgmtProcessStep.sort_order)
        ).all()
    )


def _io_for_steps(db: Session, step_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[m.MgmtStepIoItem]]:
    out: dict[uuid.UUID, list[m.MgmtStepIoItem]] = {sid: [] for sid in step_ids}
    if not step_ids:
        return out
    for item in db.scalars(
        select(m.MgmtStepIoItem)
        .where(m.MgmtStepIoItem.step_id.in_(step_ids))
        .order_by(m.MgmtStepIoItem.sort_order)
    ).all():
        out.setdefault(item.step_id, []).append(item)
    return out


def _tasks_linked_to_role(db: Session, revision_id: uuid.UUID, role_id: uuid.UUID) -> list[m.MgmtTask]:
    """Задачи, связанные с ролью через assigned_to / covers / implements."""
    links = list_links(db, revision_id)
    task_ids: set[uuid.UUID] = set()
    for link in links:
        if link.link_kind not in ("assigned_to", "covers", "implements"):
            continue
        if link.source_type == "role" and link.source_id == role_id and link.target_type == "task":
            task_ids.add(link.target_id)
        if link.target_type == "role" and link.target_id == role_id and link.source_type == "task":
            task_ids.add(link.source_id)
    if not task_ids:
        return []
    return [t for t in list_tasks(db, revision_id) if t.id in task_ids and t.metric_target is not None]


def materialize_role_documents(
    db: Session,
    revision_id: uuid.UUID,
    *,
    role_id: uuid.UUID | None = None,
) -> dict:
    """Собрать/обновить документы ролей из процессов и задач (без ИИ)."""
    roles = list_roles(db, revision_id)
    if role_id:
        roles = [r for r in roles if r.id == role_id]
        if not roles:
            raise RoleDocError("NOT_FOUND", "Роль не найдена")

    docs_touched = 0
    lines_created = 0

    for role in roles:
        steps = _steps_for_role(db, revision_id, role.id)
        io_map = _io_for_steps(db, [s.id for s in steps])

        # instruction
        instr = _get_or_create_doc(db, revision_id, role, "instruction")
        if instr.status == "approved":
            instr.stale = True
        else:
            instr.status = "draft"
            instr.stale = False
        _clear_generated_lines(db, instr.id)
        for i, step in enumerate(steps):
            line = m.MgmtRoleDocumentLine(
                document_id=instr.id,
                title=step.title,
                source_step_id=step.id,
                is_manual=False,
                sort_order=i,
            )
            db.add(line)
            lines_created += 1
        docs_touched += 1

        # checklist
        check = _get_or_create_doc(db, revision_id, role, "checklist")
        if check.status == "approved":
            check.stale = True
        else:
            check.status = "draft"
            check.stale = False
        _clear_generated_lines(db, check.id)
        ci = 0
        for step in steps:
            ios = io_map.get(step.id) or []
            if ios:
                for io in ios:
                    db.add(
                        m.MgmtRoleDocumentLine(
                            document_id=check.id,
                            title=io.title,
                            source_step_id=step.id,
                            is_manual=False,
                            sort_order=ci,
                        )
                    )
                    ci += 1
                    lines_created += 1
            else:
                db.add(
                    m.MgmtRoleDocumentLine(
                        document_id=check.id,
                        title=f"Выполнить: {step.title}",
                        source_step_id=step.id,
                        is_manual=False,
                        sort_order=ci,
                    )
                )
                ci += 1
                lines_created += 1
        docs_touched += 1

        # kpi — только задачи с явной связью на роль + metric_target
        kpi = _get_or_create_doc(db, revision_id, role, "kpi")
        if kpi.status == "approved":
            kpi.stale = True
        else:
            kpi.status = "draft"
            kpi.stale = False
        _clear_generated_lines(db, kpi.id)
        for i, task in enumerate(_tasks_linked_to_role(db, revision_id, role.id)):
            line = m.MgmtRoleDocumentLine(
                document_id=kpi.id,
                title=task.title,
                target_value=task.metric_target,
                metric_unit=task.metric_unit,
                source_task_id=task.id,
                is_manual=False,
                sort_order=i,
            )
            db.add(line)
            db.flush()
            try:
                create_link(
                    db,
                    revision_id,
                    source_type="role_document_line",
                    source_id=line.id,
                    target_type="task",
                    target_id=task.id,
                    link_kind="measures",
                )
            except Exception:
                pass
            lines_created += 1
        docs_touched += 1

    db.flush()
    return {
        "ok": True,
        "roles": len(roles),
        "documents": docs_touched,
        "lines_created": lines_created,
    }


def _kpi_measures_task_ids(db: Session, revision_id: uuid.UUID, line_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        link.target_id
        for link in list_links(db, revision_id)
        if link.link_kind == "measures"
        and link.source_type == "role_document_line"
        and link.source_id == line_id
        and link.target_type == "task"
    ]


def validate_kpi_document(db: Session, revision_id: uuid.UUID, doc: m.MgmtRoleDocument) -> list[str]:
    errors: list[str] = []
    if doc.doc_kind != "kpi":
        return errors
    for line in list_document_lines(db, doc.id):
        if line.target_value is None:
            errors.append(f"KPI_NO_TARGET: «{line.title[:60]}»")
        task_ids = _kpi_measures_task_ids(db, revision_id, line.id)
        if not task_ids and not line.source_task_id:
            errors.append(f"KPI_NO_METRIC_LINK: «{line.title[:60]}»")
        elif not task_ids and line.source_task_id:
            # auto-heal: создать measures link
            try:
                create_link(
                    db,
                    revision_id,
                    source_type="role_document_line",
                    source_id=line.id,
                    target_type="task",
                    target_id=line.source_task_id,
                    link_kind="measures",
                )
            except Exception:
                errors.append(f"KPI_NO_METRIC_LINK: «{line.title[:60]}»")
    return errors


def approve_role_document(db: Session, revision_id: uuid.UUID, document_id: uuid.UUID) -> m.MgmtRoleDocument:
    doc = db.get(m.MgmtRoleDocument, document_id)
    if not doc or doc.revision_id != revision_id:
        raise RoleDocError("NOT_FOUND", "Документ не найден")
    if doc.doc_kind == "kpi":
        errors = validate_kpi_document(db, revision_id, doc)
        if errors:
            raise RoleDocError("KPI_INVARIANT", "KPI не проходит проверки", errors)
    if doc.doc_kind == "instruction" and not list_document_lines(db, doc.id):
        raise RoleDocError("EMPTY_INSTRUCTION", "Инструкция пуста — сначала соберите документы из процессов")
    doc.status = "approved"
    doc.stale = False
    for line in list_document_lines(db, doc.id):
        line.stale = False
    db.flush()
    return doc


def approve_all_role_documents_for_role(
    db: Session, revision_id: uuid.UUID, role_id: uuid.UUID
) -> dict:
    docs = [
        d
        for d in list_role_documents(db, revision_id)
        if d.role_id == role_id and d.status != "approved"
    ]
    approved = 0
    errors: list[str] = []
    for doc in docs:
        try:
            approve_role_document(db, revision_id, doc.id)
            approved += 1
        except RoleDocError as exc:
            errors.extend(exc.errors or [exc.message])
    return {"approved_count": approved, "errors": errors}


def add_manual_line(
    db: Session,
    revision_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    title: str,
    target_value: Decimal | None = None,
    metric_unit: str | None = None,
    source_task_id: uuid.UUID | None = None,
) -> m.MgmtRoleDocumentLine:
    doc = db.get(m.MgmtRoleDocument, document_id)
    if not doc or doc.revision_id != revision_id:
        raise RoleDocError("NOT_FOUND", "Документ не найден")
    n = len(list_document_lines(db, document_id))
    line = m.MgmtRoleDocumentLine(
        document_id=document_id,
        title=title.strip(),
        target_value=target_value,
        metric_unit=metric_unit,
        source_task_id=source_task_id,
        is_manual=True,
        sort_order=n,
    )
    db.add(line)
    db.flush()
    if doc.doc_kind == "kpi" and source_task_id:
        create_link(
            db,
            revision_id,
            source_type="role_document_line",
            source_id=line.id,
            target_type="task",
            target_id=source_task_id,
            link_kind="measures",
        )
    if doc.status == "approved":
        doc.stale = True
        doc.status = "draft"
    db.flush()
    return line


def document_out(db: Session, doc: m.MgmtRoleDocument, role: m.MgmtRole | None = None) -> dict:
    role = role or db.get(m.MgmtRole, doc.role_id)
    lines = list_document_lines(db, doc.id)
    return {
        "id": str(doc.id),
        "revision_id": str(doc.revision_id),
        "role_id": str(doc.role_id),
        "role_title": role.title if role else "",
        "doc_kind": doc.doc_kind,
        "title": doc.title,
        "status": doc.status,
        "stale": doc.stale,
        "lines": [
            {
                "id": str(ln.id),
                "title": ln.title,
                "target_value": float(ln.target_value) if ln.target_value is not None else None,
                "metric_unit": ln.metric_unit,
                "source_step_id": str(ln.source_step_id) if ln.source_step_id else None,
                "source_task_id": str(ln.source_task_id) if ln.source_task_id else None,
                "is_manual": ln.is_manual,
                "sort_order": ln.sort_order,
                "stale": ln.stale,
            }
            for ln in lines
        ],
    }


def get_impact_set(
    db: Session,
    *,
    revision_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> list[dict]:
    """Потомки в графе + связанные документы ролей (для UI «Изменения»)."""
    rows = get_descendants(db, revision_id=revision_id, entity_type=entity_type, entity_id=entity_id)
    out = [
        {
            "source_type": r.source_type,
            "source_id": str(r.source_id),
            "target_type": r.target_type,
            "target_id": str(r.target_id),
            "link_kind": r.link_kind,
            "depth": r.depth,
        }
        for r in rows
    ]
    # Документы роли, если затронута роль / шаг
    if entity_type == "role":
        for doc in list_role_documents(db, revision_id):
            if doc.role_id == entity_id:
                out.append(
                    {
                        "source_type": "role",
                        "source_id": str(entity_id),
                        "target_type": "role_document",
                        "target_id": str(doc.id),
                        "link_kind": "covers",
                        "depth": 1,
                    }
                )
    if entity_type == "process_step":
        step = db.get(m.MgmtProcessStep, entity_id)
        if step and step.role_id:
            for doc in list_role_documents(db, revision_id):
                if doc.role_id == step.role_id:
                    out.append(
                        {
                            "source_type": "process_step",
                            "source_id": str(entity_id),
                            "target_type": "role_document",
                            "target_id": str(doc.id),
                            "link_kind": "covers",
                            "depth": 1,
                        }
                    )
    return out


def mark_stale_downstream(
    db: Session,
    *,
    revision_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> int:
    """Пометить stale документы ролей и assignments после правки предка."""
    n = 0
    impact = get_impact_set(
        db, revision_id=revision_id, entity_type=entity_type, entity_id=entity_id
    )
    doc_ids = {
        uuid.UUID(item["target_id"])
        for item in impact
        if item.get("target_type") == "role_document"
    }
    if entity_type == "role":
        for doc in list_role_documents(db, revision_id):
            if doc.role_id == entity_id:
                doc_ids.add(doc.id)
    if entity_type == "process_step":
        step = db.get(m.MgmtProcessStep, entity_id)
        if step and step.role_id:
            for doc in list_role_documents(db, revision_id):
                if doc.role_id == step.role_id:
                    doc_ids.add(doc.id)

    for did in doc_ids:
        doc = db.get(m.MgmtRoleDocument, did)
        if doc and not doc.stale:
            doc.stale = True
            n += 1
        for line in list_document_lines(db, did):
            if not line.stale:
                line.stale = True
                n += 1

    if entity_type in ("role", "current_position"):
        for a in db.scalars(
            select(m.MgmtRoleAssignment).where(m.MgmtRoleAssignment.revision_id == revision_id)
        ).all():
            if entity_type == "role" and a.target_role_id == entity_id and not a.stale:
                a.stale = True
                n += 1
            if entity_type == "current_position" and a.current_position_id == entity_id and not a.stale:
                a.stale = True
                n += 1
    db.flush()
    return n


def publish_role_documents(
    db: Session,
    revision_id: uuid.UUID,
    *,
    document_ids: list[uuid.UUID] | None = None,
) -> dict:
    """Перевести approved → published. Только не-stale."""
    docs = list_role_documents(db, revision_id)
    if document_ids:
        idset = set(document_ids)
        docs = [d for d in docs if d.id in idset]
    published = 0
    skipped: list[str] = []
    for doc in docs:
        if doc.status != "approved":
            skipped.append(f"{doc.doc_kind}:{doc.id}:status={doc.status}")
            continue
        if doc.stale:
            skipped.append(f"{doc.doc_kind}:{doc.id}:stale")
            continue
        if doc.doc_kind == "kpi":
            errs = validate_kpi_document(db, revision_id, doc)
            if errs:
                skipped.append(f"kpi:{doc.id}:{errs[0]}")
                continue
        doc.status = "published"
        published += 1
    db.flush()
    return {"published_count": published, "skipped": skipped}


def build_changes_summary(db: Session, revision_id: uuid.UUID) -> dict:
    """Сводка для экрана «Изменения»: stale docs / assignments / статусы L3."""
    docs = list_role_documents(db, revision_id)
    roles = {r.id: r for r in list_roles(db, revision_id)}
    stale_docs = []
    by_status: dict[str, int] = {}
    for doc in docs:
        by_status[doc.status] = by_status.get(doc.status, 0) + 1
        if doc.stale:
            role = roles.get(doc.role_id)
            stale_docs.append(
                {
                    "id": str(doc.id),
                    "role_id": str(doc.role_id),
                    "role_title": role.title if role else "",
                    "doc_kind": doc.doc_kind,
                    "title": doc.title,
                    "status": doc.status,
                }
            )

    assignments = list(
        db.scalars(
            select(m.MgmtRoleAssignment).where(m.MgmtRoleAssignment.revision_id == revision_id)
        ).all()
    )
    stale_assignments = []
    for a in assignments:
        if not a.stale:
            continue
        role = roles.get(a.target_role_id)
        pos = db.get(m.MgmtCurrentPosition, a.current_position_id)
        stale_assignments.append(
            {
                "id": str(a.id),
                "role_title": role.title if role else "",
                "position_title": pos.title if pos else "",
                "coverage": a.coverage,
            }
        )

    return {
        "revision_id": str(revision_id),
        "documents_total": len(docs),
        "by_status": by_status,
        "stale_documents": stale_docs,
        "stale_assignments": stale_assignments,
        "stale_documents_count": len(stale_docs),
        "stale_assignments_count": len(stale_assignments),
    }
