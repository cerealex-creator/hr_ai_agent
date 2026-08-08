"""Vacancy create / close / reopen / delete (PostgreSQL only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.app_settings import get_default_warranty_months
from app.services.stage_schema import default_stage_schema
from app.services.vacancy_outcome import HIRE_STAGES

CLOSE_REASON_SUCCESS = "success"
CLOSE_REASON_CLIENT = "client_cancelled"
CLOSE_REASONS = frozenset({CLOSE_REASON_SUCCESS, CLOSE_REASON_CLIENT})


class VacancyWriteError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_vacancy_documents() -> dict[str, Any]:
    return {
        "profile": "",
        "vacancy_text": "",
        "questions": "",
        "keywords": "",
        "notes": "",
    }


def next_vacancy_id(db: Session) -> int:
    current = db.scalar(select(func.max(models.Vacancy.id)))
    return int(current or 0) + 1


def vacancy_has_hire(db: Session, vacancy_id: int) -> bool:
    cnt = db.scalar(
        select(func.count())
        .select_from(models.Candidate)
        .where(
            models.Candidate.vacancy_id == vacancy_id,
            models.Candidate.hr_stage.in_(HIRE_STAGES),
        )
    )
    return int(cnt or 0) > 0


def create_vacancy(
    db: Session,
    *,
    title: str,
    client_id: int | None = None,
    chat_id: str | None = None,
    is_test: bool = False,
    source_vacancy_id: int | None = None,
) -> models.Vacancy:
    import copy

    title = (title or "").strip()
    if not title:
        raise VacancyWriteError("Введите название должности")

    dup = db.scalar(
        select(models.Vacancy).where(
            models.Vacancy.title == title,
            models.Vacancy.active.is_(True),
        )
    )
    if dup:
        raise VacancyWriteError(
            "Уже есть активная вакансия с таким названием. "
            "Переместите предыдущую в архив или укажите другое название."
        )

    if client_id is not None:
        from app.services.tenancy import client_in_org, current_user

        client = db.get(models.Client, client_id)
        user = current_user()
        if not client or (user is not None and not client_in_org(db, client, user.org_id)):
            raise VacancyWriteError("Клиент не найден", 404)

    documents = empty_vacancy_documents()
    payload: dict[str, Any] = {
        "close_reason": None,
        "is_test": bool(is_test),
        "vacancy_summary": "",
        "show_portfolio_field": False,
        "control_word_enabled": False,
        "control_word": "",
        "search_mode": "normal",
        "warranty_source_vacancy_id": None,
        "warranty": {
            "active": False,
            "start_date": "",
            "months": get_default_warranty_months(),
            "candidate_id": "",
            "start_kind": "",
        },
        "yandex_disk": {
            "root_url": "",
            "subfolders": {
                "resume": "Резюме",
                "video": "Записи",
                "task": "Задания",
            },
            "seen_paths": [],
            "last_sync_at": "",
            "ingest_new_resumes": True,
        },
        "stage_schema": default_stage_schema(),
    }

    if source_vacancy_id is not None:
        source = db.get(models.Vacancy, int(source_vacancy_id))
        if not source:
            raise VacancyWriteError("Исходная вакансия не найдена", 404)
        documents = copy.deepcopy(source.documents or empty_vacancy_documents())
        src_p = dict(source.payload or {})
        payload["vacancy_summary"] = str(src_p.get("vacancy_summary") or "")
        payload["show_portfolio_field"] = bool(src_p.get("show_portfolio_field"))
        payload["control_word_enabled"] = bool(src_p.get("control_word_enabled"))
        payload["control_word"] = str(src_p.get("control_word") or "")
        yandex = src_p.get("yandex_disk")
        if isinstance(yandex, dict):
            yd = copy.deepcopy(yandex)
            yd["seen_paths"] = []
            yd["last_sync_at"] = ""
            if "ingest_new_resumes" not in yd:
                yd["ingest_new_resumes"] = True
            payload["yandex_disk"] = yd
        if isinstance(src_p.get("stage_schema"), dict):
            payload["stage_schema"] = copy.deepcopy(src_p["stage_schema"])
        payload["cloned_from_vacancy_id"] = source.id

    chat = (chat_id or "").strip() or None
    vac = models.Vacancy(
        id=next_vacancy_id(db),
        title=title,
        client_id=client_id,
        chat_id=chat,
        active=True,
        created_at=_now_iso(),
        closed_at=None,
        documents=documents,
        version=1,
        payload=payload,
    )
    db.add(vac)
    db.commit()
    db.refresh(vac)
    return vac


def close_vacancy(
    db: Session,
    vacancy: models.Vacancy,
    *,
    close_reason: str,
) -> models.Vacancy:
    if not vacancy.active:
        raise VacancyWriteError("Вакансия уже в архиве")
    reason = (close_reason or "").strip()
    if reason not in CLOSE_REASONS:
        raise VacancyWriteError(
            f"close_reason: {', '.join(sorted(CLOSE_REASONS))}"
        )
    if reason == CLOSE_REASON_SUCCESS and not vacancy_has_hire(db, vacancy.id):
        raise VacancyWriteError(
            "Нельзя закрыть как успешную: нет кандидата на стажировке / вышедшего на работу. "
            "Если заказчик передумал — используйте «закрыта заказчиком»."
        )

    vacancy.active = False
    vacancy.closed_at = _now_iso()
    payload = dict(vacancy.payload or {})
    payload["close_reason"] = reason
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.commit()
    db.refresh(vacancy)
    return vacancy


def rename_vacancy(db: Session, vacancy: models.Vacancy, title: str) -> models.Vacancy:
    title = (title or "").strip()
    if not title:
        raise VacancyWriteError("Название не может быть пустым", 400)
    if len(title) > 512:
        raise VacancyWriteError("Название слишком длинное", 400)
    if title == vacancy.title:
        return vacancy
    if vacancy.active:
        dup = db.scalar(
            select(models.Vacancy).where(
                models.Vacancy.title == title,
                models.Vacancy.active.is_(True),
                models.Vacancy.id != vacancy.id,
            )
        )
        if dup:
            raise VacancyWriteError(
                "Уже есть активная вакансия с таким названием",
                400,
            )
    vacancy.title = title
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def reopen_vacancy(db: Session, vacancy: models.Vacancy) -> models.Vacancy:
    if vacancy.active:
        raise VacancyWriteError("Вакансия уже в работе")
    # uniqueness among active titles
    dup = db.scalar(
        select(models.Vacancy).where(
            models.Vacancy.title == vacancy.title,
            models.Vacancy.active.is_(True),
            models.Vacancy.id != vacancy.id,
        )
    )
    if dup:
        raise VacancyWriteError(
            "Уже есть активная вакансия с таким названием — переименуйте одну из них."
        )
    vacancy.active = True
    vacancy.closed_at = None
    payload = dict(vacancy.payload or {})
    payload["close_reason"] = None
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.commit()
    db.refresh(vacancy)
    return vacancy


def delete_vacancy(db: Session, vacancy: models.Vacancy) -> None:
    vac_id = vacancy.id
    # Messaging actions → posts
    post_ids = list(
        db.scalars(
            select(models.MessagingPost.id).where(models.MessagingPost.vacancy_id == vac_id)
        ).all()
    )
    if post_ids:
        db.execute(
            delete(models.MessagingAction).where(models.MessagingAction.post_id.in_(post_ids))
        )
        db.execute(
            delete(models.MessagingPost).where(models.MessagingPost.vacancy_id == vac_id)
        )
    db.execute(delete(models.HhShortlistItem).where(models.HhShortlistItem.vacancy_id == vac_id))
    db.execute(delete(models.HhSeenResume).where(models.HhSeenResume.vacancy_id == vac_id))
    db.execute(delete(models.InboxItem).where(models.InboxItem.vacancy_id == vac_id))
    db.execute(delete(models.Candidate).where(models.Candidate.vacancy_id == vac_id))
    # Keep history/jobs rows but detach
    for row in db.scalars(
        select(models.DocumentGeneration).where(models.DocumentGeneration.vacancy_id == vac_id)
    ).all():
        row.vacancy_id = None
    for row in db.scalars(select(models.Job).where(models.Job.vacancy_id == vac_id)).all():
        row.vacancy_id = None
    db.delete(vacancy)
    db.commit()
