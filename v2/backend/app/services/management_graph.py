"""Graph operations for СУП: cycle check, traceability CTE."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.management_models import HIERARCHICAL_LINK_KINDS

MAX_GRAPH_DEPTH = 50


class GraphCycleError(Exception):
    def __init__(self, path: list[str]):
        self.path = path
        super().__init__("GRAPH_CYCLE: " + " → ".join(path))


@dataclass
class GraphLinkRow:
    source_type: str
    source_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    link_kind: str
    depth: int


def check_hierarchical_cycle(
    db: Session,
    *,
    revision_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    link_kind: str,
) -> None:
    """Block link if it creates a cycle in hierarchical kinds (target → … → source)."""
    if link_kind not in HIERARCHICAL_LINK_KINDS:
        return
    if source_type == target_type and source_id == target_id:
        raise GraphCycleError([f"{source_type}:{source_id}"])

    sql = text(
        """
        WITH RECURSIVE walk AS (
            SELECT target_type, target_id, 1 AS depth,
                   ARRAY[target_type || ':' || target_id::text] AS path
            FROM mgmt_entity_links
            WHERE revision_id = :rev
              AND source_type = :st AND source_id = :sid
              AND link_kind = ANY(:kinds)
            UNION ALL
            SELECT el.target_type, el.target_id, w.depth + 1,
                   w.path || (el.target_type || ':' || el.target_id::text)
            FROM mgmt_entity_links el
            JOIN walk w ON el.source_type = w.target_type AND el.source_id = w.target_id
            WHERE el.revision_id = :rev
              AND el.link_kind = ANY(:kinds)
              AND w.depth < :max_depth
              AND NOT (el.target_type || ':' || el.target_id::text) = ANY(w.path)
        )
        SELECT path FROM walk
        WHERE target_type = :tt AND target_id = :tid
        LIMIT 1
        """
    )
    row = db.execute(
        sql,
        {
            "rev": revision_id,
            "st": target_type,
            "sid": target_id,
            "tt": source_type,
            "tid": source_id,
            "kinds": list(HIERARCHICAL_LINK_KINDS),
            "max_depth": MAX_GRAPH_DEPTH,
        },
    ).first()
    if row:
        raise GraphCycleError(list(row[0]) + [f"{source_type}:{source_id}"])


def get_ancestors(
    db: Session,
    *,
    revision_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    max_depth: int = MAX_GRAPH_DEPTH,
) -> list[GraphLinkRow]:
    sql = text(
        """
        WITH RECURSIVE ancestors AS (
            SELECT source_type, source_id, target_type, target_id, link_kind, 1 AS depth
            FROM mgmt_entity_links
            WHERE revision_id = :rev AND target_type = :et AND target_id = :eid
            UNION ALL
            SELECT el.source_type, el.source_id, el.target_type, el.target_id, el.link_kind, a.depth + 1
            FROM mgmt_entity_links el
            JOIN ancestors a ON el.target_type = a.source_type AND el.target_id = a.source_id
            WHERE el.revision_id = :rev AND a.depth < :max_depth
        )
        SELECT source_type, source_id, target_type, target_id, link_kind, depth
        FROM ancestors ORDER BY depth
        """
    )
    rows = db.execute(
        sql,
        {"rev": revision_id, "et": entity_type, "eid": entity_id, "max_depth": max_depth},
    ).all()
    return [
        GraphLinkRow(
            source_type=r[0],
            source_id=r[1],
            target_type=r[2],
            target_id=r[3],
            link_kind=r[4],
            depth=r[5],
        )
        for r in rows
    ]


def get_descendants(
    db: Session,
    *,
    revision_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    max_depth: int = MAX_GRAPH_DEPTH,
) -> list[GraphLinkRow]:
    sql = text(
        """
        WITH RECURSIVE descendants AS (
            SELECT source_type, source_id, target_type, target_id, link_kind, 1 AS depth
            FROM mgmt_entity_links
            WHERE revision_id = :rev AND source_type = :et AND source_id = :eid
            UNION ALL
            SELECT el.source_type, el.source_id, el.target_type, el.target_id, el.link_kind, d.depth + 1
            FROM mgmt_entity_links el
            JOIN descendants d ON el.source_type = d.target_type AND el.source_id = d.target_id
            WHERE el.revision_id = :rev AND d.depth < :max_depth
        )
        SELECT source_type, source_id, target_type, target_id, link_kind, depth
        FROM descendants ORDER BY depth
        """
    )
    rows = db.execute(
        sql,
        {"rev": revision_id, "et": entity_type, "eid": entity_id, "max_depth": max_depth},
    ).all()
    return [
        GraphLinkRow(
            source_type=r[0],
            source_id=r[1],
            target_type=r[2],
            target_id=r[3],
            link_kind=r[4],
            depth=r[5],
        )
        for r in rows
    ]
