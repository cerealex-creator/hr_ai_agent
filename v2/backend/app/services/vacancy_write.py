"""Vacancy create / close / reopen / delete (PostgreSQL only)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
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

logger = logging.getLogger(__name__)

# Hire + terminal reject/archive + offer — не трогаем при закрытии вакансии.
VACANCY_CLOSE_SKIP_STAGES = frozenset(
    {
        "offer",
        "internship",
        "started_work",
        "rejected",
        "rejected_candidate",
        "rejected_client",
        "rejected_hr",
        "rejected_vacancy_closed",
        "archived",
    }
)
VACANCY_CLOSED_CANDIDATE_STAGE = "rejected_hr"
VACANCY_CLOSED_CANDIDATE_NOTE = "Отказ в связи с закрытием вакансии"
VACANCY_REOPEN_GRACE_DAYS = 7


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


def _parse_iso_dt(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _append_hr_comment(payload: dict[str, Any], note: str) -> None:
    clean = (note or "").strip()
    if not clean:
        return
    prev = str(payload.get("hr_comment") or "").strip()
    payload["hr_comment"] = f"{prev}\n{clean}".strip() if prev else clean


def _append_client_close_comment(payload: dict[str, Any], note: str) -> None:
    from app.services.messaging.client_apply import format_telegram_comment_entry

    clean = (note or "").strip()
    if not clean:
        return
    entry = format_telegram_comment_entry(clean, author="система", status_key="reject")
    prev = str(payload.get("client_comment") or "").strip()
    payload["client_comment"] = f"{prev}\n{entry}".strip() if prev else entry


def _refresh_channels_on_vacancy_close(db: Session, candidate: models.Candidate) -> None:
    try:
        from app.services.messaging.ops import refresh_candidate_telegram

        refresh_candidate_telegram(db, candidate, notify=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("vacancy close: telegram refresh failed for %s: %s", candidate.id, exc)
    try:
        from app.services.bitrix.task_sync import sync_decision_task_for_candidate

        comment = str((candidate.payload or {}).get("client_comment") or "").strip() or None
        sync_decision_task_for_candidate(
            db,
            candidate,
            status_key="reject",
            client_comment=comment,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("vacancy close: bitrix sync failed for %s: %s", candidate.id, exc)
        db.rollback()


def _apply_vacancy_close_to_candidate(
    db: Session,
    candidate: models.Candidate,
    *,
    closed_at: str,
) -> None:
    from app.services.candidate_write import apply_hr_stage

    stage = (candidate.hr_stage or "").strip()
    if not stage or stage in VACANCY_CLOSE_SKIP_STAGES:
        return

    payload = dict(candidate.payload or {})
    payload["vacancy_close_snapshot"] = {
        "hr_stage": stage,
        "client_status": candidate.client_status,
        "status_updated_at": candidate.status_updated_at,
        "closed_at": closed_at,
    }
    _append_hr_comment(payload, VACANCY_CLOSED_CANDIDATE_NOTE)
    _append_client_close_comment(payload, VACANCY_CLOSED_CANDIDATE_NOTE)
    candidate.payload = payload
    flag_modified(candidate, "payload")

    apply_hr_stage(candidate, VACANCY_CLOSED_CANDIDATE_STAGE, note=VACANCY_CLOSED_CANDIDATE_NOTE)
    candidate.client_status = "reject"
    candidate.status_updated_at = closed_at
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    _refresh_channels_on_vacancy_close(db, candidate)


def _reject_hanging_candidates_on_close(
    db: Session,
    vacancy_id: int,
    *,
    closed_at: str,
) -> int:
    """Move active candidates to rejected_hr with vacancy-close note."""
    candidates = list(
        db.scalars(select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)).all()
    )
    moved = 0
    for cand in candidates:
        stage = (cand.hr_stage or "").strip()
        if not stage or stage in VACANCY_CLOSE_SKIP_STAGES:
            continue
        try:
            _apply_vacancy_close_to_candidate(db, cand, closed_at=closed_at)
            moved += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "vacancy close: candidate %s stage update failed: %s",
                cand.id,
                exc,
            )
            db.rollback()
    return moved


def _previous_stage_from_history(payload: dict[str, Any], terminal_stage: str) -> str | None:
    history = list(payload.get("hr_stage_history") or [])
    for idx in range(len(history) - 1, -1, -1):
        row = history[idx] if isinstance(history[idx], dict) else {}
        if str(row.get("stage") or "") != terminal_stage:
            continue
        if idx <= 0:
            return None
        prev = history[idx - 1] if isinstance(history[idx - 1], dict) else {}
        stage = str(prev.get("stage") or "").strip()
        return stage or None
    return None


def _restore_candidates_on_reopen(
    db: Session,
    vacancy_id: int,
    *,
    last_closed_at: str | None,
) -> int:
    """Restore vacancy-close rejects if reopen is within VACANCY_REOPEN_GRACE_DAYS."""
    closed_dt = _parse_iso_dt(last_closed_at)
    if closed_dt is None:
        return 0
    now = datetime.now(timezone.utc)
    if now - closed_dt > timedelta(days=VACANCY_REOPEN_GRACE_DAYS):
        return 0

    from app.services.candidate_write import apply_hr_stage

    restored = 0
    candidates = list(
        db.scalars(select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)).all()
    )
    for cand in candidates:
        payload = dict(cand.payload or {})
        if cand.hr_stage not in (VACANCY_CLOSED_CANDIDATE_STAGE, "rejected_vacancy_closed"):
            continue

        snapshot = payload.get("vacancy_close_snapshot")
        prev_stage: str | None = None
        prev_client_status: str | None = None
        prev_status_updated_at: str | None = None

        if isinstance(snapshot, dict) and str(snapshot.get("closed_at") or "") == (last_closed_at or ""):
            prev_stage = str(snapshot.get("hr_stage") or "").strip() or None
            prev_client_status = str(snapshot.get("client_status") or "").strip() or None
            prev_status_updated_at = str(snapshot.get("status_updated_at") or "").strip() or None
        elif cand.hr_stage == "rejected_vacancy_closed":
            prev_stage = _previous_stage_from_history(payload, "rejected_vacancy_closed")
        else:
            continue

        if not prev_stage or prev_stage in VACANCY_CLOSE_SKIP_STAGES:
            continue

        try:
            apply_hr_stage(
                cand,
                prev_stage,
                note=f"вакансия снова открыта (в течение {VACANCY_REOPEN_GRACE_DAYS} дней)",
            )
            if prev_client_status:
                cand.client_status = prev_client_status
            if prev_status_updated_at:
                cand.status_updated_at = prev_status_updated_at
            payload.pop("vacancy_close_snapshot", None)
            cand.payload = payload
            flag_modified(cand, "payload")
            db.add(cand)
            db.commit()
            db.refresh(cand)
            restored += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "vacancy reopen: candidate %s restore failed: %s",
                cand.id,
                exc,
            )
            db.rollback()
    return restored


def reconcile_closed_vacancy_candidates(db: Session, vacancy: models.Vacancy) -> int:
    """Idempotent: apply vacancy-close reject to hanging candidates on archived vacancy."""
    if vacancy.active:
        return 0
    closed_at = (vacancy.closed_at or "").strip()
    if not closed_at:
        return 0
    return _reject_hanging_candidates_on_close(db, vacancy.id, closed_at=closed_at)


def _active_title_conflict(
    db: Session,
    title: str,
    *,
    org_id: uuid.UUID,
    exclude_id: int | None = None,
) -> models.Vacancy | None:
    """Active title duplicate within one organization (not global DB)."""
    from app.services.tenancy import org_client_ids

    client_ids = org_client_ids(db, org_id)
    if not client_ids:
        return None
    q = select(models.Vacancy).where(
        models.Vacancy.title == title,
        models.Vacancy.active.is_(True),
        models.Vacancy.client_id.in_(client_ids),
    )
    if exclude_id is not None:
        q = q.where(models.Vacancy.id != exclude_id)
    return db.scalar(q)


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

    from app.services.tenancy import current_user

    user = current_user()
    if user is None:
        raise VacancyWriteError("Нужна авторизация", 401)

    dup = _active_title_conflict(db, title, org_id=user.org_id)
    if dup:
        raise VacancyWriteError(
            "Уже есть активная вакансия с таким названием. "
            "Переместите предыдущую в архив или укажите другое название."
        )

    if client_id is not None:
        from app.services.tenancy import client_in_org

        client = db.get(models.Client, client_id)
        if not client or not client_in_org(db, client, user.org_id):
            raise VacancyWriteError("Клиент не найден", 404)
    else:
        # Vacancy without client is invisible under org isolation — attach/create root company.
        from app.services.clients_write import ensure_org_root_company

        client = ensure_org_root_company(db, user.org_id)
        client_id = int(client.id)

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
    from app.services.vacancy_avatar import infer_avatar_key, normalize_avatar_key

    payload["avatar_key"] = infer_avatar_key(title)

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
        src_avatar = normalize_avatar_key(src_p.get("avatar_key"))
        if src_avatar:
            payload["avatar_key"] = src_avatar
        else:
            payload["avatar_key"] = infer_avatar_key(title)
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
    closed_at = _now_iso()
    vacancy.closed_at = closed_at
    payload = dict(vacancy.payload or {})
    payload["close_reason"] = reason
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.commit()
    db.refresh(vacancy)

    moved = _reject_hanging_candidates_on_close(db, vacancy.id, closed_at=closed_at)
    if moved:
        logger.info(
            "vacancy %s closed: %s candidates → %s",
            vacancy.id,
            moved,
            VACANCY_CLOSED_CANDIDATE_STAGE,
        )

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
        from app.services.tenancy import vacancy_org_id

        oid = vacancy_org_id(db, vacancy)
        if oid:
            dup = _active_title_conflict(
                db, title, org_id=oid, exclude_id=vacancy.id
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
    from app.services.tenancy import vacancy_org_id

    oid = vacancy_org_id(db, vacancy)
    if oid:
        dup = _active_title_conflict(db, vacancy.title, org_id=oid, exclude_id=vacancy.id)
        if dup:
            raise VacancyWriteError(
                "Уже есть активная вакансия с таким названием — переименуйте одну из них."
            )
    last_closed_at = vacancy.closed_at
    restored = _restore_candidates_on_reopen(
        db,
        vacancy.id,
        last_closed_at=last_closed_at,
    )
    vacancy.active = True
    vacancy.closed_at = None
    payload = dict(vacancy.payload or {})
    payload["close_reason"] = None
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.commit()
    db.refresh(vacancy)
    if restored:
        logger.info(
            "vacancy %s reopened: restored %s candidates from vacancy-close reject",
            vacancy.id,
            restored,
        )
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
