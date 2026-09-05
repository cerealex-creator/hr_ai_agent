"""Consulting API — owner only, hidden from demo."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, require_auth
from app.db import consulting_models as m
from app.db.session import get_db
from app.services import consulting as svc
from app.services import consulting_wave2 as w2

router = APIRouter(prefix="/consulting", tags=["consulting"])
public_router = APIRouter(prefix="/consulting/p", tags=["consulting-public"])
survey_public_router = APIRouter(prefix="/consulting/s", tags=["consulting-survey"])


def _guard(user: AuthUser) -> AuthUser:
    svc.deny_if_not_owner(user)
    return user


class ProjectCreateIn(BaseModel):
    title: str = "Диагностика системы управления"
    customer_name: str = "Грохольский Групп"
    started_on: date | None = None


class ProjectPatchIn(BaseModel):
    title: str | None = None
    customer_name: str | None = None
    started_on: date | None = None
    due_on: date | None = None


class UnitPatchIn(BaseModel):
    name: str


class MilestonePatchIn(BaseModel):
    due_on: date | None = None
    title: str | None = None


class PersonIn(BaseModel):
    full_name: str
    title: str = ""
    unit_id: uuid.UUID | None = None
    interview: bool = False
    survey: bool = True
    level: str = "executor"


class PlanItemPatchIn(BaseModel):
    status: str | None = None
    title: str | None = None


class SourceIn(BaseModel):
    kind: str = "file"
    title: str
    folder_id: uuid.UUID | None = None
    url: str | None = None
    quoted_text: str = ""
    mark: str = "pending"


class SourcePatchIn(BaseModel):
    title: str | None = None
    folder_id: uuid.UUID | None = None
    quoted_text: str | None = None
    mark: str | None = None


class RegistryPatchIn(BaseModel):
    title: str | None = None
    owner_name: str | None = None
    unit_name: str | None = None
    status: str | None = None
    action: str | None = None
    priority: str | None = None
    target_system: str | None = None
    note: str | None = None


class MeetingIn(BaseModel):
    title: str
    held_on: date | None = None
    level: str = "directors"
    notes: str = ""
    transcript: str = ""
    url: str | None = None
    folder_id: uuid.UUID | None = None


class MeetingPatchIn(BaseModel):
    title: str | None = None
    held_on: date | None = None
    level: str | None = None
    notes: str | None = None
    transcript: str | None = None
    digest: str | None = None
    url: str | None = None
    folder_id: uuid.UUID | None = None


class ContradictionIn(BaseModel):
    title: str
    left_text: str = ""
    right_text: str = ""


class ContradictionPatchIn(BaseModel):
    status: str


class GuestCommentIn(BaseModel):
    author_name: str = ""
    body: str


@router.get("/projects")
def list_projects(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    items = svc.list_projects(db, user.org_id)
    return {"items": [{"id": str(p.id), "title": p.title, "customer_name": p.customer_name} for p in items]}


@router.post("/projects")
def create_project(
    body: ProjectCreateIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.create_project(
        db,
        org_id=user.org_id,
        user_id=user.id,
        title=body.title,
        customer_name=body.customer_name,
        started_on=body.started_on,
    )
    return svc.project_out(db, project)


@router.get("/projects/{project_id}")
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return svc.project_out(db, svc.get_project(db, user.org_id, project_id))


@router.patch("/projects/{project_id}")
def patch_project(
    project_id: uuid.UUID,
    body: ProjectPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return svc.project_out(db, svc.patch_project(db, project, body.model_dump(exclude_unset=True)))


@router.get("/projects/{project_id}/hub")
def get_hub(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return svc.hub_out(db, svc.get_project(db, user.org_id, project_id))


@router.patch("/projects/{project_id}/units/{unit_id}")
def patch_unit(
    project_id: uuid.UUID,
    unit_id: uuid.UUID,
    body: UnitPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    unit = db.get(m.ConsultingUnit, unit_id)
    if not unit or unit.project_id != project.id:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")
    unit.name = body.name.strip() or unit.name
    db.commit()
    return svc.unit_out(unit)


@router.patch("/projects/{project_id}/milestones/{milestone_id}")
def patch_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestonePatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    row = db.get(m.ConsultingMilestone, milestone_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Контрольная точка не найдена")
    if body.due_on is not None:
        row.due_on = body.due_on
    if body.title is not None:
        row.title = body.title.strip() or row.title
    db.commit()
    return svc.milestone_out(row)


@router.post("/projects/{project_id}/people")
def add_person(
    project_id: uuid.UUID,
    body: PersonIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    person = m.ConsultingPerson(
        project_id=project.id,
        full_name=body.full_name.strip(),
        title=body.title.strip(),
        unit_id=body.unit_id,
        interview=body.interview,
        survey=body.survey,
        level=body.level,
    )
    if not person.full_name:
        raise HTTPException(status_code=400, detail="Нужны фамилия и имя")
    db.add(person)
    db.commit()
    db.refresh(person)
    return svc.person_out(person)


@router.patch("/projects/{project_id}/people/{person_id}")
def patch_person(
    project_id: uuid.UUID,
    person_id: uuid.UUID,
    body: PersonIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    person = db.get(m.ConsultingPerson, person_id)
    if not person or person.project_id != project.id:
        raise HTTPException(status_code=404, detail="Человек не найден")
    person.full_name = body.full_name.strip() or person.full_name
    person.title = body.title.strip()
    person.unit_id = body.unit_id
    person.interview = body.interview
    person.survey = body.survey
    person.level = body.level
    db.commit()
    return svc.person_out(person)


@router.delete("/projects/{project_id}/people/{person_id}")
def delete_person(
    project_id: uuid.UUID,
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, str]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    person = db.get(m.ConsultingPerson, person_id)
    if not person or person.project_id != project.id:
        raise HTTPException(status_code=404, detail="Человек не найден")
    db.delete(person)
    db.commit()
    return {"ok": "1"}


@router.get("/projects/{project_id}/plan")
def get_plan(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    items = list(
        db.scalars(
            select(m.ConsultingPlanItem)
            .where(m.ConsultingPlanItem.project_id == project.id)
            .order_by(m.ConsultingPlanItem.sort_order)
        )
    )
    return {
        "plan_status": project.plan_status,
        "items": [svc.plan_item_out(x) for x in items],
    }


@router.post("/projects/{project_id}/plan/generate")
def generate_plan(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    svc.seed_plan_items(db, project)
    db.commit()
    return get_plan(project_id, db, user)


@router.post("/projects/{project_id}/plan/approve")
def approve_plan(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    svc.seed_plan_items(db, project)
    project.plan_status = "approved"
    db.commit()
    return get_plan(project_id, db, user)


@router.patch("/projects/{project_id}/plan/{item_id}")
def patch_plan_item(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    body: PlanItemPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    row = db.get(m.ConsultingPlanItem, item_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Пункт не найден")
    if body.status in ("todo", "done", "blocked"):
        row.status = body.status
    if body.title is not None:
        row.title = body.title.strip() or row.title
    db.commit()
    return svc.plan_item_out(row)


@router.get("/projects/{project_id}/folders")
def get_folders(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return {"items": svc.list_folders(db, project)}


@router.get("/projects/{project_id}/sources")
def get_sources(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    items = list(
        db.scalars(
            select(m.ConsultingSource)
            .where(m.ConsultingSource.project_id == project.id)
            .order_by(m.ConsultingSource.created_at.desc())
        )
    )
    return {"items": [svc.source_out(s) for s in items]}


@router.post("/projects/{project_id}/sources")
def add_source(
    project_id: uuid.UUID,
    body: SourceIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    source = svc.add_source(
        db,
        project,
        kind=body.kind,
        title=body.title,
        folder_id=body.folder_id,
        url=body.url,
        quoted_text=body.quoted_text,
        mark=body.mark,
    )
    return svc.source_out(source)


@router.patch("/projects/{project_id}/sources/{source_id}")
def patch_source(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    body: SourcePatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    source = db.get(m.ConsultingSource, source_id)
    if not source or source.project_id != project.id:
        raise HTTPException(status_code=404, detail="Материал не найден")
    if body.title is not None:
        source.title = body.title.strip() or source.title
    if body.folder_id is not None:
        source.folder_id = body.folder_id
    if body.quoted_text is not None:
        source.quoted_text = body.quoted_text
    if body.mark is not None:
        if body.mark not in svc.MARKS:
            raise HTTPException(status_code=400, detail="Неверная метка")
        source.mark = body.mark
    db.commit()
    return svc.source_out(source)


@router.get("/projects/{project_id}/registry")
def get_registry(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    items = list(
        db.scalars(
            select(m.ConsultingRegistryRow)
            .where(m.ConsultingRegistryRow.project_id == project.id)
            .order_by(m.ConsultingRegistryRow.created_at.desc())
        )
    )
    return {"items": [svc.registry_out(r) for r in items]}


@router.patch("/projects/{project_id}/registry/{row_id}")
def patch_registry(
    project_id: uuid.UUID,
    row_id: uuid.UUID,
    body: RegistryPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    row = db.get(m.ConsultingRegistryRow, row_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        next_status = data.pop("status")
        svc.apply_row_status(row, next_status)
        if next_status == "disputed":
            svc.ensure_dispute_contradiction(db, project, row)
    for key in ("title", "owner_name", "unit_name", "action", "priority", "target_system", "note"):
        if key in data and data[key] is not None:
            setattr(row, key, data[key])
    db.commit()
    return svc.registry_out(row)


@router.get("/projects/{project_id}/meetings")
def get_meetings(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return {"items": svc.list_meetings(db, svc.get_project(db, user.org_id, project_id))}


@router.post("/projects/{project_id}/meetings")
def create_meeting(
    project_id: uuid.UUID,
    body: MeetingIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return svc.meeting_out(
        svc.add_meeting(
            db,
            project,
            title=body.title,
            held_on=body.held_on,
            level=body.level,
            notes=body.notes,
            transcript=body.transcript,
            url=body.url,
            folder_id=body.folder_id,
        )
    )


@router.patch("/projects/{project_id}/meetings/{meeting_id}")
def update_meeting(
    project_id: uuid.UUID,
    meeting_id: uuid.UUID,
    body: MeetingPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return svc.meeting_out(svc.patch_meeting(db, project, meeting_id, body.model_dump(exclude_unset=True)))


@router.get("/projects/{project_id}/contradictions")
def get_contradictions(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return {"items": svc.list_contradictions(db, svc.get_project(db, user.org_id, project_id))}


@router.post("/projects/{project_id}/contradictions")
def create_contradiction(
    project_id: uuid.UUID,
    body: ContradictionIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return svc.contradiction_out(
        svc.add_contradiction(db, project, title=body.title, left_text=body.left_text, right_text=body.right_text)
    )


@router.patch("/projects/{project_id}/contradictions/{row_id}")
def update_contradiction(
    project_id: uuid.UUID,
    row_id: uuid.UUID,
    body: ContradictionPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return svc.contradiction_out(svc.patch_contradiction(db, project, row_id, body.status))


@router.get("/projects/{project_id}/coverage")
def get_coverage(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return svc.coverage_out(db, svc.get_project(db, user.org_id, project_id))


@router.post("/projects/{project_id}/showcase/publish")
def publish_showcase(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return svc.publish_showcase(db, svc.get_project(db, user.org_id, project_id))


@public_router.get("/{token}")
def public_showcase(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return svc.showcase_public_out(db, svc.get_project_by_token(db, token))


@public_router.post("/{token}/comments")
def public_comment(token: str, body: GuestCommentIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    project = svc.get_project_by_token(db, token)
    row = svc.add_comment(db, project, author_name=body.author_name, body=body.body)
    return {
        "id": str(row.id),
        "author_name": row.author_name,
        "body": row.body,
    }


@public_router.post("/{token}/approve")
def public_approve(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return svc.approve_showcase(db, svc.get_project_by_token(db, token))


class MegamaidPatchIn(BaseModel):
    title: str | None = None
    body: str | None = None
    be_tags: list[str] | None = None


class EtalonIn(BaseModel):
    title: str
    body: str = ""
    code: str = ""


class EtalonPatchIn(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None


class ProcessCardIn(BaseModel):
    title: str
    code: str = ""
    papers_text: str = ""
    practice_text: str = ""
    folder_code: str | None = None


class ProcessCardPatchIn(BaseModel):
    title: str | None = None
    code: str | None = None
    papers_text: str | None = None
    practice_text: str | None = None
    folder_code: str | None = None
    status: str | None = None


class SurveyCreateIn(BaseModel):
    title: str = "Опрос диагностики"
    fill_white_spots: bool = False


class QuestionPatchIn(BaseModel):
    text: str | None = None
    channel: str | None = None
    preamble: str | None = None
    preamble_status: str | None = None


class SurveyAnswerIn(BaseModel):
    full_name: str = ""
    title: str = ""
    person_id: uuid.UUID | None = None
    answers: dict[str, Any] = {}
    mode: str = "self"


@router.get("/projects/{project_id}/megamaid")
def get_megamaid(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return {"items": w2.list_megamaid(db, svc.get_project(db, user.org_id, project_id))}


@router.patch("/projects/{project_id}/megamaid/{node_id}")
def update_megamaid(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    body: MegamaidPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return w2.patch_megamaid(db, project, node_id, body.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}/etalon")
def get_etalon(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return {"items": w2.list_etalon(db, svc.get_project(db, user.org_id, project_id))}


@router.post("/projects/{project_id}/etalon")
def create_etalon(
    project_id: uuid.UUID,
    body: EtalonIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return w2.add_etalon_node(db, project, title=body.title, body=body.body, code=body.code)


@router.post("/projects/{project_id}/etalon/from-megamaid/{node_id}")
def etalon_from_megamaid(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return w2.copy_megamaid_to_etalon(db, svc.get_project(db, user.org_id, project_id), node_id)


@router.patch("/projects/{project_id}/etalon/{node_id}")
def update_etalon(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    body: EtalonPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return w2.patch_etalon(db, project, node_id, body.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}/process-cards")
def get_process_cards(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return {"items": w2.list_process_cards(db, svc.get_project(db, user.org_id, project_id))}


@router.post("/projects/{project_id}/process-cards")
def create_process_card(
    project_id: uuid.UUID,
    body: ProcessCardIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return w2.add_process_card(
        db,
        project,
        title=body.title,
        code=body.code,
        papers_text=body.papers_text,
        practice_text=body.practice_text,
        folder_code=body.folder_code,
    )


@router.patch("/projects/{project_id}/process-cards/{card_id}")
def update_process_card(
    project_id: uuid.UUID,
    card_id: uuid.UUID,
    body: ProcessCardPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return w2.patch_process_card(db, project, card_id, body.model_dump(exclude_unset=True))


@router.get("/projects/{project_id}/surveys")
def get_surveys(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return {"items": w2.list_surveys(db, svc.get_project(db, user.org_id, project_id))}


@router.post("/projects/{project_id}/surveys")
def create_survey(
    project_id: uuid.UUID,
    body: SurveyCreateIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    survey = w2.create_survey(db, project, title=body.title, fill_white_spots=body.fill_white_spots)
    return w2.survey_out(db, survey)


@router.get("/projects/{project_id}/surveys/{survey_id}")
def get_survey(
    project_id: uuid.UUID,
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return w2.survey_out(db, w2.get_survey(db, project, survey_id))


@router.patch("/projects/{project_id}/surveys/{survey_id}/questions/{question_id}")
def update_question(
    project_id: uuid.UUID,
    survey_id: uuid.UUID,
    question_id: uuid.UUID,
    body: QuestionPatchIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    return w2.patch_question(db, project, survey_id, question_id, body.model_dump(exclude_unset=True))


@router.post("/projects/{project_id}/surveys/{survey_id}/publish")
def publish_survey(
    project_id: uuid.UUID,
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return w2.publish_survey(db, svc.get_project(db, user.org_id, project_id), survey_id)


@router.get("/projects/{project_id}/surveys/{survey_id}/responses")
def get_responses(
    project_id: uuid.UUID,
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    return {"items": w2.list_responses(db, svc.get_project(db, user.org_id, project_id), survey_id)}


@router.post("/projects/{project_id}/surveys/{survey_id}/responses")
def interviewer_response(
    project_id: uuid.UUID,
    survey_id: uuid.UUID,
    body: SurveyAnswerIn,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_auth),
) -> dict[str, Any]:
    _guard(user)
    project = svc.get_project(db, user.org_id, project_id)
    survey = w2.get_survey(db, project, survey_id)
    return w2.submit_response(
        db,
        survey,
        full_name=body.full_name,
        title=body.title,
        person_id=body.person_id,
        answers=body.answers,
        mode="interviewer",
    )


@survey_public_router.get("/{token}")
def public_survey(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return w2.survey_public_out(db, w2.get_survey_by_token(db, token))


@survey_public_router.post("/{token}/responses")
def public_survey_answer(token: str, body: SurveyAnswerIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    survey = w2.get_survey_by_token(db, token)
    return w2.submit_response(
        db,
        survey,
        full_name=body.full_name,
        title=body.title,
        person_id=body.person_id,
        answers=body.answers,
        mode="self",
    )