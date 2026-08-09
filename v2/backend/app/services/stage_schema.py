"""Per-vacancy stage schema: enable/rename catalog stages without changing storage keys."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.candidate_write import HR_STAGES

# Stable catalog order for HR funnel (+ rejects at end). Keys never rename in storage.
HR_CATALOG_ORDER = [
    "resume_screening",
    "primary_contact",
    "no_response_3d",
    "interview_scheduled",
    "interview_done",
    "test_task",
    "client_review",
    "client_pause",
    "client_meeting",
    "offer",
    "internship",
    "started_work",
    "rejected_candidate",
    "rejected_client",
    "rejected_hr",
    "archived",
]

CLIENT_STATUS_CATALOG = {
    "new": "Новый",
    "wait": "Ждёт оценки",
    "ready": "Встреча",
    "think": "Подумать",
    "reject": "Отказ",
    "offer": "Оффер",
    "started": "Вышел на работу",
}

CLIENT_STATUS_ORDER = ["new", "wait", "ready", "think", "reject", "offer", "started"]

# Must stay enabled — warranty / Telegram / hire metrics.
PROTECTED_HR_STAGES = frozenset(
    {
        "resume_screening",
        "client_review",
        "offer",
        "internship",
        "started_work",
        "rejected_candidate",
        "rejected_client",
        "rejected_hr",
    }
)

PROTECTED_CLIENT_STATUSES = frozenset({"wait", "ready", "think", "reject", "offer", "started"})


def default_hr_items() -> list[dict[str, Any]]:
    return [
        {
            "id": sid,
            "label": HR_STAGES.get(sid, sid),
            "enabled": True,
            "protected": sid in PROTECTED_HR_STAGES,
        }
        for sid in HR_CATALOG_ORDER
        if sid in HR_STAGES
    ]


def default_client_items() -> list[dict[str, Any]]:
    return [
        {
            "id": sid,
            "label": CLIENT_STATUS_CATALOG[sid],
            "enabled": True,
            "protected": sid in PROTECTED_CLIENT_STATUSES,
        }
        for sid in CLIENT_STATUS_ORDER
    ]


def default_stage_schema() -> dict[str, Any]:
    return {
        "version": 1,
        "hr_stages": default_hr_items(),
        "client_statuses": default_client_items(),
    }


def catalog() -> dict[str, Any]:
    return {
        "hr_stages": default_hr_items(),
        "client_statuses": default_client_items(),
        "protected_hr_stages": sorted(PROTECTED_HR_STAGES),
        "protected_client_statuses": sorted(PROTECTED_CLIENT_STATUSES),
        "note": (
            "Ключи этапов в БД не меняются — только подписи и видимость в UI. "
            "После появления кандидатов структурные правки (вкл/выкл) блокируются."
        ),
    }


def _normalize_items(
    items: list[Any] | None,
    *,
    catalog_ids: list[str],
    default_labels: dict[str, str],
    protected: frozenset[str],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(items, list):
        for raw in items:
            if not isinstance(raw, dict):
                continue
            sid = str(raw.get("id") or "").strip()
            if sid not in catalog_ids:
                continue
            label = str(raw.get("label") or default_labels.get(sid) or sid).strip()
            enabled = bool(raw.get("enabled", True))
            if sid in protected:
                enabled = True
            by_id[sid] = {
                "id": sid,
                "label": label or default_labels.get(sid, sid),
                "enabled": enabled,
                "protected": sid in protected,
            }
    out: list[dict[str, Any]] = []
    for sid in catalog_ids:
        if sid in by_id:
            out.append(by_id[sid])
        else:
            out.append(
                {
                    "id": sid,
                    "label": default_labels.get(sid, sid),
                    "enabled": True,
                    "protected": sid in protected,
                }
            )
    return out


def normalize_stage_schema(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_stage_schema()
    if not isinstance(raw, dict):
        return base
    schema = {
        "version": int(raw.get("version") or 1),
        "hr_stages": _normalize_items(
            raw.get("hr_stages"),
            catalog_ids=HR_CATALOG_ORDER,
            default_labels=HR_STAGES,
            protected=PROTECTED_HR_STAGES,
        ),
        "client_statuses": _normalize_items(
            raw.get("client_statuses"),
            catalog_ids=CLIENT_STATUS_ORDER,
            default_labels=CLIENT_STATUS_CATALOG,
            protected=PROTECTED_CLIENT_STATUSES,
        ),
    }
    return _repair_swapped_interview_labels(schema)


def _repair_swapped_interview_labels(schema: dict[str, Any]) -> dict[str, Any]:
    """Undo mis-renames that break date/time UI (scheduled ↔ «не отвечает» / done)."""
    items = list(schema.get("hr_stages") or [])
    by_id = {str(i.get("id") or ""): i for i in items if isinstance(i, dict)}
    sched = by_id.get("interview_scheduled")
    done = by_id.get("interview_done")
    no_resp = by_id.get("no_response_3d")
    if not sched:
        return schema

    no_resp_label = HR_STAGES.get("no_response_3d", "")
    sched_label = HR_STAGES.get("interview_scheduled", "")
    done_label = HR_STAGES.get("interview_done", "")

    corrupted = False
    if str(sched.get("label") or "").strip() == no_resp_label:
        corrupted = True
    if done and str(done.get("label") or "").strip() == sched_label:
        corrupted = True
    if (
        no_resp
        and str(no_resp.get("label") or "").strip() == no_resp_label
        and str(sched.get("label") or "").strip() == no_resp_label
    ):
        corrupted = True
    if not corrupted:
        return schema

    sched["label"] = sched_label
    if done:
        done["label"] = done_label
    if no_resp:
        no_resp["label"] = no_resp_label
    schema["hr_stages"] = items
    return schema


def vacancy_has_candidates(db: Session, vacancy_id: int) -> bool:
    n = db.execute(
        select(func.count())
        .select_from(models.Candidate)
        .where(models.Candidate.vacancy_id == vacancy_id)
    ).scalar_one()
    return int(n or 0) > 0


def lock_info(db: Session, vacancy: models.Vacancy) -> dict[str, Any]:
    has_cands = vacancy_has_candidates(db, vacancy.id)
    reasons: list[str] = []
    if has_cands:
        reasons.append("У вакансии уже есть кандидаты — нельзя отключать этапы (только подписи).")
    return {
        "structure_locked": has_cands,
        "labels_editable": True,
        "reasons": reasons,
    }


def get_vacancy_stage_schema(db: Session, vacancy: models.Vacancy) -> dict[str, Any]:
    payload = vacancy.payload or {}
    raw = payload.get("stage_schema") if isinstance(payload, dict) else None
    schema = normalize_stage_schema(raw if isinstance(raw, dict) else None)
    lock = lock_info(db, vacancy)
    return {**schema, **lock}


def set_vacancy_stage_schema(
    db: Session,
    vacancy: models.Vacancy,
    patch: dict[str, Any],
) -> dict[str, Any]:
    current = get_vacancy_stage_schema(db, vacancy)
    lock = lock_info(db, vacancy)
    incoming = normalize_stage_schema(patch if isinstance(patch, dict) else {})

    if lock["structure_locked"]:
        # Keep enabled flags from current; allow label changes only.
        cur_hr = {i["id"]: i for i in current["hr_stages"]}
        cur_cl = {i["id"]: i for i in current["client_statuses"]}
        for item in incoming["hr_stages"]:
            item["enabled"] = cur_hr.get(item["id"], item).get("enabled", True)
            if item["id"] in PROTECTED_HR_STAGES:
                item["enabled"] = True
        for item in incoming["client_statuses"]:
            item["enabled"] = cur_cl.get(item["id"], item).get("enabled", True)
            if item["id"] in PROTECTED_CLIENT_STATUSES:
                item["enabled"] = True

    payload = dict(vacancy.payload or {})
    payload["stage_schema"] = {
        "version": 1,
        "hr_stages": incoming["hr_stages"],
        "client_statuses": incoming["client_statuses"],
    }
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return get_vacancy_stage_schema(db, vacancy)


def enabled_hr_stage_ids(schema: dict[str, Any]) -> list[str]:
    return [i["id"] for i in schema.get("hr_stages") or [] if i.get("enabled")]


def hr_label_map(schema: dict[str, Any] | None) -> dict[str, str]:
    out = dict(HR_STAGES)
    if not schema:
        return out
    for item in schema.get("hr_stages") or []:
        if isinstance(item, dict) and item.get("id"):
            out[str(item["id"])] = str(item.get("label") or out.get(item["id"], item["id"]))
    return out


def ensure_default_schema_on_vacancy(vacancy: models.Vacancy) -> None:
    """Copy default schema into payload if missing (new vacancies)."""
    payload = dict(vacancy.payload or {})
    if isinstance(payload.get("stage_schema"), dict):
        return
    payload["stage_schema"] = deepcopy(default_stage_schema())
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
