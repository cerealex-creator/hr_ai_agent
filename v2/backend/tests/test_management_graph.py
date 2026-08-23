"""Graph Checker unit test (E1)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.db import management_models as m
from app.services.management_graph import GraphCycleError, check_hierarchical_cycle
from app.services.management_system import create_goal, create_link, create_task, get_or_create_system


@pytest.fixture
def draft_revision(db: Session, test_org_id: uuid.UUID, test_user_id: uuid.UUID):
    system = get_or_create_system(db, test_org_id, test_user_id)
    rev = db.get(m.MgmtRevision, system.draft_revision_id)
    assert rev is not None
    return rev


def test_graph_cycle_blocked(db: Session, draft_revision: m.MgmtRevision):
    goal = create_goal(db, draft_revision.id, title="Цель A")
    task = create_task(db, draft_revision.id, title="Задача 1")
    create_link(
        db,
        draft_revision.id,
        source_type="goal",
        source_id=goal.id,
        target_type="task",
        target_id=task.id,
        link_kind="decomposes",
    )
    with pytest.raises(GraphCycleError):
        check_hierarchical_cycle(
            db,
            revision_id=draft_revision.id,
            source_type="task",
            source_id=task.id,
            target_type="goal",
            target_id=goal.id,
            link_kind="decomposes",
        )


def test_references_link_no_cycle_check(db: Session, draft_revision: m.MgmtRevision):
    goal = create_goal(db, draft_revision.id, title="Цель B")
    task = create_task(db, draft_revision.id, title="Задача 2")
    # references — not hierarchical, should not raise
    check_hierarchical_cycle(
        db,
        revision_id=draft_revision.id,
        source_type="goal",
        source_id=goal.id,
        target_type="task",
        target_id=task.id,
        link_kind="references",
    )
