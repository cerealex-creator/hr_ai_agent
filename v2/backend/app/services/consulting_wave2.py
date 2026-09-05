"""Волна 2: Мегамейд, эталон, опрос (вопросы по белым пятнам, пока нет форм)."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import consulting_models as m
from app.services.consulting_coverage import COMPANY_FRAME

# Библиотека «стройка» — подсказка, не вторая доска сравнения.
MEGAMAID_SEED: list[tuple[str, str, str, list[str]]] = [
    ("goals", "Цели и стратегия группы", "process", ["Строительство", "Поставки", "Форсел", "СПЛАВ", "Темп Девелопмент"]),
    ("org", "Оргструктура и ответственность", "process", ["Строительство"]),
    ("proc_order", "Получение заказа", "process", ["Строительство", "Поставки"]),
    ("proc_project", "Реализация проекта", "process", ["Строительство"]),
    ("proc_supply", "Закупки и снабжение", "process", ["Строительство", "Поставки"]),
    ("proc_money", "Управление деньгами", "process", ["Строительство"]),
    ("proc_hire", "Найм и адаптация", "process", ["Строительство"]),
    ("proc_contract", "Договорная работа", "process", ["Строительство"]),
    ("uk_fin", "Финансы УК", "process", ["Строительство"]),
    ("uk_hr", "HR УК", "process", ["Строительство"]),
]

TRAIL_OPTIONS = [
    "Есть регламент и им пользуются",
    "Регламент есть, делают иначе",
    "Делают без регламента (в чате / звонках / таблицах)",
    "Не знаю / не сталкивался",
]


def megamaid_out(n: m.ConsultingMegamaidNode) -> dict:
    return {
        "id": str(n.id),
        "code": n.code,
        "title": n.title,
        "kind": n.kind,
        "body": n.body,
        "be_tags": list(n.be_tags or []),
        "sort_order": n.sort_order,
    }


def etalon_out(n: m.ConsultingEtalonNode) -> dict:
    return {
        "id": str(n.id),
        "code": n.code,
        "title": n.title,
        "kind": n.kind,
        "body": n.body,
        "status": n.status,
        "source_megamaid_id": str(n.source_megamaid_id) if n.source_megamaid_id else None,
        "version": n.version,
        "sort_order": n.sort_order,
    }


def process_out(c: m.ConsultingProcessCard) -> dict:
    return {
        "id": str(c.id),
        "code": c.code,
        "title": c.title,
        "papers_text": c.papers_text,
        "practice_text": c.practice_text,
        "formality": c.formality,
        "status": c.status,
        "folder_code": c.folder_code,
    }


def question_out(q: m.ConsultingSurveyQuestion) -> dict:
    return {
        "id": str(q.id),
        "code": q.code,
        "section": q.section,
        "text": q.text,
        "kind": q.kind,
        "options": list(q.options or []),
        "channel": q.channel,
        "preamble": q.preamble,
        "preamble_status": q.preamble_status,
        "coverage_code": q.coverage_code,
        "sort_order": q.sort_order,
    }


def survey_out(db: Session, s: m.ConsultingSurvey, *, with_questions: bool = True) -> dict:
    questions = []
    if with_questions:
        rows = list(
            db.scalars(
                select(m.ConsultingSurveyQuestion)
                .where(m.ConsultingSurveyQuestion.survey_id == s.id)
                .order_by(m.ConsultingSurveyQuestion.sort_order)
            )
        )
        questions = [question_out(q) for q in rows]
    resp_n = db.scalar(
        select(func.count()).select_from(m.ConsultingSurveyResponse).where(
            m.ConsultingSurveyResponse.survey_id == s.id
        )
    ) or 0
    return {
        "id": str(s.id),
        "title": s.title,
        "status": s.status,
        "public_token": s.public_token,
        "public_url": f"/consulting/s/{s.public_token}" if s.public_token else None,
        "fill_white_spots": s.fill_white_spots,
        "responses_count": resp_n,
        "questions": questions,
        "link_questions": sum(1 for q in questions if q["channel"] == "link"),
        "meeting_questions": sum(1 for q in questions if q["channel"] == "meeting"),
    }


def seed_megamaid(db: Session, project: m.ConsultingProject) -> list[m.ConsultingMegamaidNode]:
    existing = db.scalar(
        select(func.count()).select_from(m.ConsultingMegamaidNode).where(
            m.ConsultingMegamaidNode.project_id == project.id
        )
    )
    if existing:
        return list(
            db.scalars(
                select(m.ConsultingMegamaidNode)
                .where(m.ConsultingMegamaidNode.project_id == project.id)
                .order_by(m.ConsultingMegamaidNode.sort_order)
            )
        )
    rows: list[m.ConsultingMegamaidNode] = []
    for i, (code, title, kind, tags) in enumerate(MEGAMAID_SEED):
        row = m.ConsultingMegamaidNode(
            project_id=project.id,
            code=code,
            title=title,
            kind=kind,
            body=f"Эталон Мегамейд: {title}. Применимо к отмеченным БЕ.",
            be_tags=tags,
            sort_order=i,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def list_megamaid(db: Session, project: m.ConsultingProject) -> list[dict]:
    seed_megamaid(db, project)
    rows = list(
        db.scalars(
            select(m.ConsultingMegamaidNode)
            .where(m.ConsultingMegamaidNode.project_id == project.id)
            .order_by(m.ConsultingMegamaidNode.sort_order)
        )
    )
    return [megamaid_out(x) for x in rows]


def patch_megamaid(db: Session, project: m.ConsultingProject, node_id: uuid.UUID, body: dict[str, Any]) -> dict:
    row = db.get(m.ConsultingMegamaidNode, node_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Узел Мегамейд не найден")
    if "title" in body and body["title"] is not None:
        row.title = str(body["title"]).strip() or row.title
    if "body" in body and body["body"] is not None:
        row.body = str(body["body"])
    if "be_tags" in body and body["be_tags"] is not None:
        row.be_tags = list(body["be_tags"])
    db.commit()
    db.refresh(row)
    return megamaid_out(row)


def list_etalon(db: Session, project: m.ConsultingProject) -> list[dict]:
    rows = list(
        db.scalars(
            select(m.ConsultingEtalonNode)
            .where(m.ConsultingEtalonNode.project_id == project.id)
            .order_by(m.ConsultingEtalonNode.sort_order)
        )
    )
    return [etalon_out(x) for x in rows]


def copy_megamaid_to_etalon(db: Session, project: m.ConsultingProject, node_id: uuid.UUID) -> dict:
    src = db.get(m.ConsultingMegamaidNode, node_id)
    if not src or src.project_id != project.id:
        raise HTTPException(status_code=404, detail="Узел Мегамейд не найден")
    n = db.scalar(
        select(func.count()).select_from(m.ConsultingEtalonNode).where(
            m.ConsultingEtalonNode.project_id == project.id
        )
    ) or 0
    row = m.ConsultingEtalonNode(
        project_id=project.id,
        code=src.code,
        title=src.title,
        kind=src.kind,
        body=src.body,
        status="draft",
        source_megamaid_id=src.id,
        version=1,
        sort_order=n,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return etalon_out(row)


def add_etalon_node(db: Session, project: m.ConsultingProject, *, title: str, body: str = "", code: str = "") -> dict:
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Нужно название")
    n = db.scalar(
        select(func.count()).select_from(m.ConsultingEtalonNode).where(
            m.ConsultingEtalonNode.project_id == project.id
        )
    ) or 0
    row = m.ConsultingEtalonNode(
        project_id=project.id,
        code=(code or "").strip() or f"custom_{n+1}",
        title=title,
        kind="process",
        body=(body or "").strip(),
        status="draft",
        sort_order=n,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return etalon_out(row)


def patch_etalon(db: Session, project: m.ConsultingProject, node_id: uuid.UUID, body: dict[str, Any]) -> dict:
    row = db.get(m.ConsultingEtalonNode, node_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Узел эталона не найден")
    if row.status == "locked" and body.get("status") not in (None, "locked", "na"):
        if any(k in body for k in ("title", "body", "code")):
            raise HTTPException(status_code=400, detail="Зафиксированный эталон не меняем — сначала снимите фиксацию")
    if "title" in body and body["title"] is not None and row.status != "locked":
        row.title = str(body["title"]).strip() or row.title
    if "body" in body and body["body"] is not None and row.status != "locked":
        row.body = str(body["body"])
    if "status" in body and body["status"] in ("draft", "locked", "na"):
        if body["status"] == "locked" and row.status != "locked":
            row.version = int(row.version or 1) + (0 if row.status == "draft" and row.version == 1 else 0)
            if row.status == "draft":
                pass
            else:
                row.version = int(row.version or 1) + 1
        row.status = body["status"]
    db.commit()
    db.refresh(row)
    return etalon_out(row)


def list_process_cards(db: Session, project: m.ConsultingProject) -> list[dict]:
    rows = list(
        db.scalars(
            select(m.ConsultingProcessCard)
            .where(m.ConsultingProcessCard.project_id == project.id)
            .order_by(m.ConsultingProcessCard.title)
        )
    )
    return [process_out(x) for x in rows]


def add_process_card(
    db: Session,
    project: m.ConsultingProject,
    *,
    title: str,
    code: str = "",
    papers_text: str = "",
    practice_text: str = "",
    folder_code: str | None = None,
) -> dict:
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Нужно название")
    formality = "unknown"
    papers = (papers_text or "").strip()
    practice = (practice_text or "").strip()
    if papers and practice:
        formality = "mixed"
    elif practice and not papers:
        formality = "practice_only"
    elif papers and not practice:
        formality = "papers_only"
    row = m.ConsultingProcessCard(
        project_id=project.id,
        code=(code or "").strip(),
        title=title,
        papers_text=papers,
        practice_text=practice,
        formality=formality,
        status="draft",
        folder_code=folder_code,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return process_out(row)


def patch_process_card(db: Session, project: m.ConsultingProject, card_id: uuid.UUID, body: dict[str, Any]) -> dict:
    row = db.get(m.ConsultingProcessCard, card_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Карточка не найдена")
    for key in ("title", "code", "papers_text", "practice_text", "folder_code", "status"):
        if key in body and body[key] is not None:
            setattr(row, key, body[key] if key != "title" else (str(body[key]).strip() or row.title))
    papers = (row.papers_text or "").strip()
    practice = (row.practice_text or "").strip()
    if papers and practice and papers != practice:
        row.formality = "mixed"
    elif practice and not papers:
        row.formality = "practice_only"
    elif papers and not practice:
        row.formality = "papers_only"
    elif papers and practice:
        row.formality = "aligned"
    else:
        row.formality = "unknown"
    db.commit()
    db.refresh(row)
    return process_out(row)


def _build_questions_for_coverage(open_codes: set[str], *, fill_white_spots: bool) -> list[dict[str, Any]]:
    """Полный опрос по умолчанию; при галке — только открытые клетки покрытия."""
    items: list[dict[str, Any]] = []
    order = 0
    for code, title, _prefixes in COMPANY_FRAME:
        if fill_white_spots and code not in open_codes:
            continue
        section = title
        base = [
            {
                "code": f"{code}_how",
                "section": section,
                "text": f"Как у вас устроен «{title}» на практике? Нас интересует, кто ведёт путь и где остаётся след.",
                "kind": "single",
                "options": TRAIL_OPTIONS,
                "channel": "link",
                "preamble": f"Блок про «{title}». Ответьте как есть у вас, без «правильного» ответа.",
                "preamble_status": "draft",
                "coverage_code": code,
            },
            {
                "code": f"{code}_reg",
                "section": section,
                "text": f"Есть ли рабочий регламент или документ по «{title}» (файл, ссылка, название)?",
                "kind": "text",
                "options": [],
                "channel": "link",
                "preamble": "",
                "preamble_status": "none",
                "coverage_code": code,
            },
            {
                "code": f"{code}_cycle",
                "section": section,
                "text": f"Приведите пример завершённого цикла по «{title}» за последний месяц: когда, кто участвовал.",
                "kind": "long",
                "options": [],
                "channel": "link",
                "preamble": "",
                "preamble_status": "none",
                "coverage_code": code,
            },
            {
                "code": f"{code}_trace",
                "section": section,
                "text": f"Где остаётся след по «{title}» (1С, Битрикс, папка, таблица, мессенджер, звонок)?",
                "kind": "text",
                "options": [],
                "channel": "link",
                "preamble": "",
                "preamble_status": "none",
                "coverage_code": code,
            },
        ]
        for q in base:
            q["sort_order"] = order
            order += 1
            items.append(q)
    if not items:
        # Полный каркас, если все клетки закрыты или галка снята без открытых
        for code, title, _ in COMPANY_FRAME[:6]:
            items.append(
                {
                    "code": f"{code}_how",
                    "section": title,
                    "text": f"Как у вас устроен «{title}» на практике?",
                    "kind": "single",
                    "options": TRAIL_OPTIONS,
                    "channel": "link",
                    "preamble": f"Блок про «{title}».",
                    "preamble_status": "draft",
                    "coverage_code": code,
                    "sort_order": order,
                }
            )
            order += 1
    return items


def create_survey(
    db: Session,
    project: m.ConsultingProject,
    *,
    title: str = "Опрос диагностики",
    fill_white_spots: bool = False,
) -> m.ConsultingSurvey:
    from app.services.consulting import coverage_out

    cov = coverage_out(db, project)
    open_codes = {x["code"] for x in cov["items"] if not x["closed"]}
    survey = m.ConsultingSurvey(
        project_id=project.id,
        title=(title or "").strip() or "Опрос диагностики",
        status="draft",
        fill_white_spots=fill_white_spots,
        payload={},
    )
    db.add(survey)
    db.flush()
    for q in _build_questions_for_coverage(open_codes, fill_white_spots=fill_white_spots):
        db.add(
            m.ConsultingSurveyQuestion(
                survey_id=survey.id,
                code=q["code"],
                section=q["section"],
                text=q["text"],
                kind=q["kind"],
                options=q["options"],
                channel=q["channel"],
                preamble=q["preamble"],
                preamble_status=q["preamble_status"],
                coverage_code=q["coverage_code"],
                sort_order=q["sort_order"],
            )
        )
    db.commit()
    db.refresh(survey)
    return survey


def list_surveys(db: Session, project: m.ConsultingProject) -> list[dict]:
    rows = list(
        db.scalars(
            select(m.ConsultingSurvey)
            .where(m.ConsultingSurvey.project_id == project.id)
            .order_by(m.ConsultingSurvey.created_at.desc())
        )
    )
    return [survey_out(db, s, with_questions=False) for s in rows]


def get_survey(db: Session, project: m.ConsultingProject, survey_id: uuid.UUID) -> m.ConsultingSurvey:
    row = db.get(m.ConsultingSurvey, survey_id)
    if not row or row.project_id != project.id:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    return row


def patch_question(
    db: Session, project: m.ConsultingProject, survey_id: uuid.UUID, question_id: uuid.UUID, body: dict[str, Any]
) -> dict:
    survey = get_survey(db, project, survey_id)
    q = db.get(m.ConsultingSurveyQuestion, question_id)
    if not q or q.survey_id != survey.id:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    if "text" in body and body["text"] is not None:
        q.text = str(body["text"]).strip() or q.text
    if "channel" in body and body["channel"] in ("link", "meeting"):
        q.channel = body["channel"]
    if "preamble" in body and body["preamble"] is not None:
        q.preamble = str(body["preamble"])
    if "preamble_status" in body and body["preamble_status"] in ("none", "draft", "approved"):
        q.preamble_status = body["preamble_status"]
    db.commit()
    db.refresh(q)
    return question_out(q)


def publish_survey(db: Session, project: m.ConsultingProject, survey_id: uuid.UUID) -> dict:
    survey = get_survey(db, project, survey_id)
    questions = list(
        db.scalars(
            select(m.ConsultingSurveyQuestion).where(m.ConsultingSurveyQuestion.survey_id == survey.id)
        )
    )
    # Преамбула с текстом должна быть утверждена
    for q in questions:
        if (q.preamble or "").strip() and q.preamble_status != "approved" and q.channel == "link":
            raise HTTPException(
                status_code=400,
                detail=f"Утвердите преамбулу блока «{q.section}» или очистите её",
            )
    if not survey.public_token:
        survey.public_token = secrets.token_urlsafe(24)
    survey.status = "published"
    db.commit()
    db.refresh(survey)
    return survey_out(db, survey)


def get_survey_by_token(db: Session, token: str) -> m.ConsultingSurvey:
    row = db.scalar(select(m.ConsultingSurvey).where(m.ConsultingSurvey.public_token == token))
    if not row or row.status != "published":
        raise HTTPException(status_code=404, detail="Опрос недоступен")
    return row


def survey_public_out(db: Session, survey: m.ConsultingSurvey) -> dict:
    project = db.get(m.ConsultingProject, survey.project_id)
    questions = list(
        db.scalars(
            select(m.ConsultingSurveyQuestion)
            .where(
                m.ConsultingSurveyQuestion.survey_id == survey.id,
                m.ConsultingSurveyQuestion.channel == "link",
            )
            .order_by(m.ConsultingSurveyQuestion.sort_order)
        )
    )
    people = list(
        db.scalars(
            select(m.ConsultingPerson)
            .where(m.ConsultingPerson.project_id == survey.project_id, m.ConsultingPerson.survey.is_(True))
            .order_by(m.ConsultingPerson.full_name)
        )
    )
    # Секции: преамбула только approved
    out_q = []
    for q in questions:
        item = question_out(q)
        if item["preamble_status"] != "approved":
            item["preamble"] = ""
        out_q.append(item)
    return {
        "id": str(survey.id),
        "title": survey.title,
        "customer_name": project.customer_name if project else "",
        "questions": out_q,
        "people": [
            {"id": str(p.id), "full_name": p.full_name, "title": p.title} for p in people
        ],
    }


def submit_response(
    db: Session,
    survey: m.ConsultingSurvey,
    *,
    full_name: str,
    title: str,
    person_id: uuid.UUID | None,
    answers: dict[str, Any],
    mode: str = "self",
) -> dict:
    full_name = (full_name or "").strip()
    title = (title or "").strip()
    if not full_name or not title:
        raise HTTPException(status_code=400, detail="Нужны фамилия, имя и должность")
    if mode not in ("self", "interviewer"):
        raise HTTPException(status_code=400, detail="Режим: сам или интервьюер")
    if person_id:
        person = db.get(m.ConsultingPerson, person_id)
        if not person or person.project_id != survey.project_id:
            raise HTTPException(status_code=400, detail="Человек не из этого проекта")
        full_name = person.full_name
        title = person.title or title
    row = m.ConsultingSurveyResponse(
        survey_id=survey.id,
        person_id=person_id,
        full_name=full_name,
        title=title,
        mode=mode,
        answers=dict(answers or {}),
    )
    db.add(row)
    # Ответ с автором — годный след для покрытия: создаём/обновляем practice на карточках не делаем автоматом факт.
    # Закрытие пятна через ответ: сохраняем как источник-след в payload ответа достаточно;
    # покрытие учитывает ответы через отдельный путь — добавим в coverage_out.
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "full_name": row.full_name,
        "title": row.title,
        "mode": row.mode,
    }


def list_responses(db: Session, project: m.ConsultingProject, survey_id: uuid.UUID) -> list[dict]:
    survey = get_survey(db, project, survey_id)
    rows = list(
        db.scalars(
            select(m.ConsultingSurveyResponse)
            .where(m.ConsultingSurveyResponse.survey_id == survey.id)
            .order_by(m.ConsultingSurveyResponse.created_at.desc())
        )
    )
    return [
        {
            "id": str(r.id),
            "full_name": r.full_name,
            "title": r.title,
            "mode": r.mode,
            "answers": dict(r.answers or {}),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


_WEAK_ANSWERS = {
    "",
    "не знаю",
    "не знаю / не сталкивался",
    "не сталкивался",
    "нет ответа",
}


def _answer_is_substantive(raw: Any) -> bool:
    text = str(raw or "").strip().lower()
    if not text:
        return False
    return text not in _WEAK_ANSWERS


def response_coverage_codes(db: Session, project_id: uuid.UUID) -> set[str]:
    """Коды покрытия, где есть содержательный ответ опроса с автором (не «не знаю»)."""
    surveys = list(db.scalars(select(m.ConsultingSurvey).where(m.ConsultingSurvey.project_id == project_id)))
    codes: set[str] = set()
    for s in surveys:
        questions = {
            q.code: q
            for q in db.scalars(
                select(m.ConsultingSurveyQuestion).where(m.ConsultingSurveyQuestion.survey_id == s.id)
            )
        }
        for resp in db.scalars(
            select(m.ConsultingSurveyResponse).where(m.ConsultingSurveyResponse.survey_id == s.id)
        ):
            answers = dict(resp.answers or {})
            for q_code, value in answers.items():
                if not _answer_is_substantive(value):
                    continue
                q = questions.get(str(q_code))
                if q and q.coverage_code:
                    codes.add(q.coverage_code)
    return codes
