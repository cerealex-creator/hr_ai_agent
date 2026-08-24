"""СУП — загрузка отраслевых контент-пакетов (U3)."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_system import (
    create_goal,
    create_link,
    create_task,
    list_goals,
    list_links,
    list_tasks,
)

PACKS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "management_packs"


def _read_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def list_industry_packs() -> list[dict]:
    out: list[dict] = []
    if not PACKS_ROOT.is_dir():
        return out
    for pack_dir in sorted(PACKS_ROOT.iterdir()):
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = _read_json(manifest_path)
        if isinstance(manifest, dict):
            out.append(
                {
                    "id": manifest.get("id") or pack_dir.name,
                    "title": manifest.get("title") or pack_dir.name,
                    "version": manifest.get("version"),
                    "description": manifest.get("description"),
                }
            )
    return out


def load_pack_manifest(pack_id: str) -> dict:
    path = PACKS_ROOT / pack_id / "manifest.json"
    if not path.is_file():
        raise ValueError(f"Pack not found: {pack_id}")
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError("Invalid manifest")
    return data


def _clear_pack_seeds(db: Session, revision_id) -> None:
    """Удалить предыдущие suggested seeds и черновики L2 из пакета."""
    goal_ids = [g.id for g in list_goals(db, revision_id) if g.status == "suggested"]
    task_ids = [t.id for t in list_tasks(db, revision_id) if t.status == "suggested"]

    for link in list_links(db, revision_id):
        if link.link_kind == "decomposes" and (
            (link.source_type == "goal" and link.source_id in goal_ids)
            or (link.target_type == "task" and link.target_id in task_ids)
        ):
            db.delete(link)

    for gid in goal_ids:
        for dl in db.scalars(
            select(m.MgmtGoalDimensionLink).where(m.MgmtGoalDimensionLink.goal_id == gid)
        ).all():
            db.delete(dl)
        g = db.get(m.MgmtGoal, gid)
        if g:
            db.delete(g)

    for tid in task_ids:
        t = db.get(m.MgmtTask, tid)
        if t:
            db.delete(t)

    for step in db.scalars(
        select(m.MgmtProcessStep).where(m.MgmtProcessStep.revision_id == revision_id)
    ).all():
        if step.status != "approved":
            for io in db.scalars(
                select(m.MgmtStepIoItem).where(m.MgmtStepIoItem.step_id == step.id)
            ).all():
                db.delete(io)
            db.delete(step)

    for pmap in db.scalars(
        select(m.MgmtProcessMap).where(m.MgmtProcessMap.revision_id == revision_id)
    ).all():
        if pmap.status != "approved":
            db.delete(pmap)

    for role in db.scalars(select(m.MgmtRole).where(m.MgmtRole.revision_id == revision_id)).all():
        if role.status != "approved":
            db.delete(role)

    for node in db.scalars(select(m.MgmtOrgNode).where(m.MgmtOrgNode.revision_id == revision_id)).all():
        if node.status != "approved":
            db.delete(node)

    db.flush()


def apply_industry_pack(
    db: Session,
    *,
    system: m.MgmtSystem,
    revision_id,
    pack_id: str,
) -> dict:
    load_pack_manifest(pack_id)
    pack_dir = PACKS_ROOT / pack_id
    if not pack_dir.is_dir():
        raise ValueError(f"Pack not found: {pack_id}")

    _clear_pack_seeds(db, revision_id)
    system.industry_pack_id = pack_id

    goals_created = 0
    tasks_created = 0
    roles_created = 0
    steps_created = 0

    role_by_title: dict[str, m.MgmtRole] = {}
    org_path = pack_dir / "org_chart.json"
    if org_path.is_file():
        org_data = _read_json(org_path)
        if isinstance(org_data, dict):
            for item in org_data.get("roles") or []:
                if not isinstance(item, dict):
                    continue
                role = m.MgmtRole(
                    revision_id=revision_id,
                    title=str(item.get("title") or "").strip(),
                    external_key=str(item.get("external_key") or "") or None,
                    status="draft",
                    sort_order=roles_created,
                )
                db.add(role)
                db.flush()
                role_by_title[role.title] = role
                roles_created += 1

            def _import_nodes(nodes: list, parent_id=None) -> None:
                for i, node in enumerate(nodes):
                    if not isinstance(node, dict):
                        continue
                    rt = str(node.get("role_title") or "").strip()
                    role_id = role_by_title[rt].id if rt in role_by_title else None
                    org = m.MgmtOrgNode(
                        revision_id=revision_id,
                        title=str(node.get("title") or rt or "Узел"),
                        role_id=role_id,
                        parent_node_id=parent_id,
                        sort_order=i,
                        status="draft",
                    )
                    db.add(org)
                    db.flush()
                    children = node.get("children") or []
                    if isinstance(children, list):
                        _import_nodes(children, org.id)

            roots = org_data.get("org_nodes") or []
            if isinstance(roots, list):
                _import_nodes(roots)

    proc_path = pack_dir / "processes.json"
    if proc_path.is_file():
        proc_data = _read_json(proc_path)
        maps = proc_data.get("process_maps") if isinstance(proc_data, dict) else []
        if isinstance(maps, list):
            for mi, pmap in enumerate(maps):
                if not isinstance(pmap, dict):
                    continue
                pm = m.MgmtProcessMap(
                    revision_id=revision_id,
                    title=str(pmap.get("title") or "Процесс"),
                    status="draft",
                    sort_order=mi,
                )
                db.add(pm)
                db.flush()
                for si, step in enumerate(pmap.get("steps") or []):
                    if not isinstance(step, dict):
                        continue
                    rt = str(step.get("role_title") or "").strip()
                    role_id = role_by_title[rt].id if rt in role_by_title else None
                    ps = m.MgmtProcessStep(
                        revision_id=revision_id,
                        process_map_id=pm.id,
                        role_id=role_id,
                        title=str(step.get("title") or "Шаг"),
                        frequency=str(step.get("frequency") or "") or None,
                        status="draft",
                        sort_order=si,
                    )
                    db.add(ps)
                    steps_created += 1
                db.flush()

    goals_path = pack_dir / "goals_seed.json"
    goal_by_title: dict[str, m.MgmtGoal] = {}
    if goals_path.is_file():
        gdata = _read_json(goals_path)
        for item in (gdata.get("goals") if isinstance(gdata, dict) else []) or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            weight = item.get("weight")
            goal = create_goal(
                db,
                revision_id,
                title=title,
                weight=Decimal(str(weight)) if weight is not None else None,
                metric_source=str(item.get("metric_source") or "pack_hint"),
                dimension_codes=[str(c) for c in (item.get("dimension_codes") or [])],
                primary_dimension_code=str(item["primary_dimension_code"])
                if item.get("primary_dimension_code")
                else None,
            )
            goal.status = "suggested"
            goals_created += 1
            goal_by_title[title] = goal
        db.flush()

    tasks_path = pack_dir / "tasks_seed.json"
    if tasks_path.is_file():
        tdata = _read_json(tasks_path)
        for item in (tdata.get("tasks") if isinstance(tdata, dict) else []) or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            task = create_task(db, revision_id, title=title)
            task.status = "suggested"
            tasks_created += 1
            hint = str(item.get("goal_title_hint") or "").strip()
            parent = goal_by_title.get(hint)
            if parent:
                create_link(
                    db,
                    revision_id,
                    source_type="goal",
                    source_id=parent.id,
                    target_type="task",
                    target_id=task.id,
                    link_kind="decomposes",
                )
        db.flush()

    return {
        "ok": True,
        "pack_id": pack_id,
        "goals_suggested": goals_created,
        "tasks_suggested": tasks_created,
        "roles_draft": roles_created,
        "process_steps_draft": steps_created,
    }
