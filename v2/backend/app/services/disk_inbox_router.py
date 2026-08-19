"""Yandex Disk inbox L3: PDF → AI route to Резюме/; video/audio → match FIO → Записи/."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.db import models
from app.services.ai_json import chat_json
from app.services.app_settings import _load as load_app_settings
from app.services.app_settings import _save as save_app_settings
from app.services.candidate_write import create_candidate
from app.services.pdf_extract import _pdf_text_from_bytes
from app.services.vacancy_docs import extract_profile_text
from app.services.yandex_disk_oauth import (
    DEFAULT_SUBFOLDERS,
    DiskApiError,
    _headers,
    download_disk_path_bytes,
    ensure_app_root,
    ensure_folder,
    get_disk_token,
    list_inbox_files,
)
from app.services.yandex_disk_sync import (
    ensure_yandex_config,
    file_matches_candidate,
    match_candidate_by_filename,
)
from app.services.yandex_public import is_yandex_pdf, is_yandex_video_or_audio

ROUTER_SYSTEM = """Ты маршрутизатор резюме. По тексту резюме выбери наиболее подходящую активную вакансию
и извлеки поля анкеты кандидата.
Верни JSON:
{
  "vacancy_id": число или null,
  "confidence": 0.0-1.0,
  "full_name": "ФИО или пусто",
  "phone": "телефон или пусто",
  "email": "email или пусто",
  "age": "возраст числом или пусто",
  "city": "город или пусто",
  "metro": "метро или пусто",
  "salary": "ожидания по ЗП текстом или пусто",
  "position": "желаемая должность из резюме или пусто",
  "reason": "кратко почему эта вакансия"
}
Не выдумывай данные, которых нет в резюме. Если ни одна вакансия не подходит уверенно — vacancy_id=null, confidence низкий.
"""

_VIDEO_EXTS = (".mp4", ".webm", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".ogg", ".m4a")
_PDF_EXTS = (".pdf",)

def inbox_settings() -> dict[str, Any]:
    data = load_app_settings()
    try:
        conf = float(data.get("disk_inbox_confidence") or 0.75)
    except (TypeError, ValueError):
        conf = 0.75
    conf = max(0.4, min(0.95, conf))
    return {
        "auto": bool(data.get("disk_inbox_auto", False)),
        "confidence": conf,
        "evaluate_on_route": bool(data.get("disk_inbox_evaluate", False)),
    }


def set_inbox_settings(
    *,
    auto: bool | None = None,
    confidence: float | None = None,
    evaluate_on_route: bool | None = None,
) -> dict[str, Any]:
    data = load_app_settings()
    if auto is not None:
        data["disk_inbox_auto"] = bool(auto)
    if confidence is not None:
        data["disk_inbox_confidence"] = float(confidence)
    if evaluate_on_route is not None:
        data["disk_inbox_evaluate"] = bool(evaluate_on_route)
    save_app_settings(data)
    return inbox_settings()


def _download_disk_file(token: str, path: str) -> bytes:
    return download_disk_path_bytes(path, token=token)


def move_disk_file(token: str, from_path: str, to_path: str) -> str:
    """Move file on Disk; returns actual destination path (may get a unique suffix)."""
    resp = requests.post(
        "https://cloud-api.yandex.net/v1/disk/resources/move",
        headers=_headers(token),
        params={"from": from_path, "path": to_path, "overwrite": "false"},
        timeout=60,
    )
    if resp.status_code in (201, 202):
        return to_path
    if resp.status_code == 409:
        stem = Path(to_path).stem
        suffix = Path(to_path).suffix
        parent = str(Path(to_path).parent).replace("\\", "/")
        alt = f"{parent}/{stem}_{datetime.now(timezone.utc).strftime('%H%M%S')}{suffix}"
        resp2 = requests.post(
            "https://cloud-api.yandex.net/v1/disk/resources/move",
            headers=_headers(token),
            params={"from": from_path, "path": alt, "overwrite": "false"},
            timeout=60,
        )
        if resp2.status_code in (201, 202):
            return alt
        raise DiskApiError(f"Move conflict {resp2.status_code}: {resp2.text[:200]}")
    raise DiskApiError(f"Move {resp.status_code}: {resp.text[:200]}")


def _active_vacancies_brief(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.execute(select(models.Vacancy).where(models.Vacancy.active.is_(True)).limit(40))
        .scalars()
        .all()
    )
    out = []
    for v in rows:
        profile = extract_profile_text(v.documents)[:500]
        out.append({"id": v.id, "title": v.title, "profile_excerpt": profile})
    return out


def _route_text(text: str, vacancies: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    data = chat_json(
        settings,
        system=ROUTER_SYSTEM,
        user=f"ВАКАНСИИ:\n{vacancies}\n\nРЕЗЮМЕ:\n{text[:6000]}",
        temperature=0.1,
        max_tokens=1200,
    )
    if not isinstance(data, dict):
        return {
            "vacancy_id": None,
            "confidence": 0,
            "full_name": "",
            "phone": "",
            "email": "",
            "age": "",
            "city": "",
            "metro": "",
            "salary_expected": "",
            "position": "",
        }
    try:
        conf = float(data.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    vid = data.get("vacancy_id")
    try:
        vid_i = int(vid) if vid not in (None, "") else None
    except (TypeError, ValueError):
        vid_i = None
    from app.services.candidate_resume_eval import _format_phone

    email_raw = str(data.get("email") or "").strip()
    email = email_raw if "@" in email_raw else ""
    return {
        "vacancy_id": vid_i,
        "confidence": conf,
        "full_name": str(data.get("full_name") or "").strip(),
        "phone": _format_phone(data.get("phone")),
        "email": email,
        "age": str(data.get("age") or "").strip(),
        "city": str(data.get("city") or "").strip(),
        "metro": str(data.get("metro") or "").strip(),
        "salary_expected": str(data.get("salary") or data.get("salary_expected") or "").strip(),
        "position": str(data.get("position") or "").strip(),
        "reason": str(data.get("reason") or "").strip(),
    }


def _anketa_fields_from_route(
    routed: dict[str, Any],
    *,
    resume_link: str = "",
    video_link: str = "",
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in ("phone", "email", "age", "city", "metro", "salary_expected"):
        val = str(routed.get(key) or "").strip()
        if val:
            fields[key] = val
    if resume_link:
        fields["resume_link"] = resume_link
    if video_link:
        fields["video_link"] = video_link
    return fields


def _resolve_vacancy_org_id(db: Session, vacancy: models.Vacancy) -> UUID | None:
    if not vacancy.client_id:
        return None
    client = db.get(models.Client, vacancy.client_id)
    return client.organization_id if client else None


def _find_duplicate(db: Session, vacancy_id: int, name: str, phone: str) -> models.Candidate | None:
    name_n = (name or "").strip().lower()
    phone_n = "".join(ch for ch in (phone or "") if ch.isdigit())
    rows = (
        db.execute(select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id))
        .scalars()
        .all()
    )
    for c in rows:
        if name_n and (c.name or "").strip().lower() == name_n:
            return c
        if phone_n:
            p = "".join(ch for ch in str((c.payload or {}).get("phone") or "") if ch.isdigit())
            if p and p == phone_n:
                return c
    return None


def _file_kind(name: str, meta: dict[str, Any] | None = None) -> str:
    """Return 'video' | 'pdf' | 'other' from filename / Disk meta."""
    meta = meta or {}
    probe = {
        "name": name or meta.get("name") or "",
        "mime_type": meta.get("mime_type") or "",
        "media_type": meta.get("media_type") or "",
    }
    if is_yandex_video_or_audio(probe) or (name or "").lower().endswith(_VIDEO_EXTS):
        return "video"
    if is_yandex_pdf(probe) or (name or "").lower().endswith(_PDF_EXTS):
        return "pdf"
    return "other"


def _vacancy_subfolder(db: Session, vacancy: models.Vacancy, token: str, kind: str) -> str:
    """kind: resume | video | task → absolute Disk path under vacancy tree."""
    cfg = ensure_yandex_config(vacancy)
    app_path = str(cfg.get("app_disk_path") or "").strip()
    if not app_path:
        from app.services.yandex_disk_oauth import ensure_vacancy_folders

        created = ensure_vacancy_folders(db, vacancy, publish=True)
        app_path = created["path"]
    label = (cfg.get("subfolders") or {}).get(kind) or DEFAULT_SUBFOLDERS.get(kind) or kind
    folder = f"{app_path.rstrip('/')}/{label}"
    ensure_folder(token, folder)
    return folder


def _vacancy_resume_folder(db: Session, vacancy: models.Vacancy, token: str) -> str:
    return _vacancy_subfolder(db, vacancy, token, "resume")


def _vacancy_video_folder(db: Session, vacancy: models.Vacancy, token: str) -> str:
    return _vacancy_subfolder(db, vacancy, token, "video")


def _active_candidates(db: Session) -> list[models.Candidate]:
    vac_ids = list(
        db.execute(select(models.Vacancy.id).where(models.Vacancy.active.is_(True))).scalars().all()
    )
    if not vac_ids:
        return []
    return list(
        db.execute(select(models.Candidate).where(models.Candidate.vacancy_id.in_(vac_ids)))
        .scalars()
        .all()
    )


def _match_candidate_by_fio_filename(
    filename: str, candidates: list[models.Candidate]
) -> models.Candidate | None:
    """Match by ФИО in filename (full name preferred)."""
    cand = match_candidate_by_filename(filename, candidates)
    if cand and file_matches_candidate(filename, cand.name or ""):
        return cand
    return None


def _attach_video_link(cand: models.Candidate, dest: str) -> None:
    payload = dict(cand.payload or {})
    payload["video_link"] = f"yadisk-app:{dest}"
    payload["disk_inbox_video_path"] = dest
    cand.payload = payload
    flag_modified(cand, "payload")


def _route_media_by_filename(
    db: Session,
    *,
    token: str,
    row: models.InboxItem,
    disk_path: str,
    name: str,
    unsorted: str,
    stats: dict[str, Any],
    details: list[str],
) -> None:
    """Video/audio: match candidate by FIO in filename → vacancy «Записи»."""
    candidates = _active_candidates(db)
    cand = _match_candidate_by_fio_filename(name, candidates)
    if not cand:
        dest = move_disk_file(token, disk_path, f"{unsorted}/{name}")
        row.disk_path = dest
        row.status = "unsorted"
        row.processed_at = datetime.now(timezone.utc)
        row.note = "Не найден кандидат по ФИО в имени файла (видео/аудио)"
        row.extracted = {**(row.extracted or {}), "full_name": Path(name).stem, "kind": "video"}
        stats["unsorted"] += 1
        details.append(f"{name}: unsorted (нет ФИО-матча)")
        return

    vac = db.get(models.Vacancy, cand.vacancy_id)
    if not vac or not vac.active:
        dest = move_disk_file(token, disk_path, f"{unsorted}/{name}")
        row.disk_path = dest
        row.status = "unsorted"
        row.processed_at = datetime.now(timezone.utc)
        row.note = "Вакансия кандидата неактивна"
        stats["unsorted"] += 1
        details.append(f"{name}: unsorted (вакансия)")
        return

    video_dir = _vacancy_video_folder(db, vac, token)
    dest = move_disk_file(token, disk_path, f"{video_dir}/{name}")
    _attach_video_link(cand, dest)
    db.add(cand)
    row.disk_path = dest
    row.vacancy_id = vac.id
    row.status = "routed"
    row.processed_at = datetime.now(timezone.utc)
    row.confidence = "1.00"
    row.extracted = {
        "full_name": cand.name or Path(name).stem,
        "kind": "video",
        "candidate_id": str(cand.id),
        "reason": "Матч по ФИО в имени файла → Записи",
    }
    row.note = f"Видео → {cand.name} (#{vac.id})"
    stats["routed"] += 1
    details.append(f"{name} → Записи #{vac.id} / {cand.name}")


def process_inbox(db: Session, *, limit: int = 20) -> dict[str, Any]:
    token = get_disk_token()
    if not token:
        raise DiskApiError("Нет OAuth-токена Яндекс.Диска")
    paths = ensure_app_root(token)
    unsorted = f"{paths['root']}/_unsorted"
    ensure_folder(token, unsorted)
    cfg = inbox_settings()
    threshold = float(cfg["confidence"])

    listed = list_inbox_files(limit=limit)
    vacancies = _active_vacancies_brief(db)
    stats = {"scanned": 0, "routed": 0, "unsorted": 0, "errors": 0, "skipped": 0}
    details: list[str] = []

    for file_meta in listed.get("items") or []:
        disk_path = str(file_meta.get("path") or "").strip()
        name = str(file_meta.get("name") or "").strip()
        if not disk_path or not name:
            continue
        # Disk API returns path like disk:/HR_AI_Agent/_inbox/file.pdf
        if disk_path.startswith("disk:"):
            disk_path = disk_path[5:]
        existing = db.execute(
            select(models.InboxItem).where(models.InboxItem.disk_path == disk_path)
        ).scalar_one_or_none()
        # Skip only fully finished routes; allow retry on error (file may still be in inbox).
        if existing and existing.status in ("routed", "unsorted"):
            stats["skipped"] += 1
            continue

        row = existing or models.InboxItem(disk_path=disk_path, file_name=name, status="new")
        row.file_name = name
        stats["scanned"] += 1
        kind = _file_kind(name, file_meta if isinstance(file_meta, dict) else None)
        try:
            if kind == "video":
                _route_media_by_filename(
                    db,
                    token=token,
                    row=row,
                    disk_path=disk_path,
                    name=name,
                    unsorted=unsorted,
                    stats=stats,
                    details=details,
                )
            elif kind == "pdf":
                content = _download_disk_file(token, disk_path)
                text = _pdf_text_from_bytes(content)
                if len(text.strip()) < 50:
                    row.status = "error"
                    row.note = "Мало текста (скан?) — нужна ручная обработка"
                    row.processed_at = datetime.now(timezone.utc)
                    dest = move_disk_file(token, disk_path, f"{unsorted}/{name}")
                    row.disk_path = dest
                    stats["errors"] += 1
                    details.append(f"{name}: error (scan)")
                else:
                    routed = _route_text(text, vacancies)
                    row.extracted = {
                        "full_name": routed.get("full_name") or "",
                        "phone": routed.get("phone") or "",
                        "email": routed.get("email") or "",
                        "age": routed.get("age") or "",
                        "city": routed.get("city") or "",
                        "metro": routed.get("metro") or "",
                        "salary_expected": routed.get("salary_expected") or "",
                        "position": routed.get("position") or "",
                        "reason": routed.get("reason") or "",
                        "kind": "pdf",
                    }
                    conf = float(routed.get("confidence") or 0)
                    row.confidence = f"{conf:.2f}"
                    vid = routed.get("vacancy_id")
                    vac = db.get(models.Vacancy, int(vid)) if vid else None
                    if vac and vac.active and conf >= threshold:
                        resume_dir = _vacancy_resume_folder(db, vac, token)
                        dest = move_disk_file(token, disk_path, f"{resume_dir}/{name}")
                        row.disk_path = dest
                        row.vacancy_id = vac.id
                        row.status = "routed"
                        row.processed_at = datetime.now(timezone.utc)
                        dup = _find_duplicate(
                            db,
                            vac.id,
                            str(row.extracted.get("full_name") or ""),
                            str(row.extracted.get("phone") or ""),
                        )
                        if not dup:
                            _oid = _resolve_vacancy_org_id(db, vac)
                            cand = create_candidate(
                                db,
                                vacancy_id=vac.id,
                                name=str(row.extracted.get("full_name") or name),
                                fields=_anketa_fields_from_route(
                                    routed,
                                    resume_link=f"yadisk-app:{dest}",
                                ),
                                org_id=_oid,
                            )
                            payload = dict(cand.payload or {})
                            payload["source"] = "yandex_inbox"
                            payload["disk_inbox_path"] = dest
                            cand.payload = payload
                            flag_modified(cand, "payload")
                            db.add(cand)
                            from app.services.candidate_photo import try_attach_candidate_photo

                            try_attach_candidate_photo(db, cand, pdf_bytes=content)
                        stats["routed"] += 1
                        details.append(f"{name} → #{vac.id} ({conf:.2f})")
                    else:
                        dest = move_disk_file(token, disk_path, f"{unsorted}/{name}")
                        row.disk_path = dest
                        row.status = "unsorted"
                        row.vacancy_id = int(vid) if vid and vac else None
                        row.processed_at = datetime.now(timezone.utc)
                        row.note = routed.get("reason") or "Низкая уверенность"
                        stats["unsorted"] += 1
                        details.append(f"{name}: unsorted ({conf:.2f})")
            else:
                dest = move_disk_file(token, disk_path, f"{unsorted}/{name}")
                row.disk_path = dest
                row.status = "unsorted"
                row.processed_at = datetime.now(timezone.utc)
                row.note = "Неизвестный тип файла (нужен PDF или видео/аудио)"
                stats["unsorted"] += 1
                details.append(f"{name}: unsorted (тип)")
        except Exception as exc:  # noqa: BLE001
            row.status = "error"
            row.note = str(exc)[:400]
            row.processed_at = datetime.now(timezone.utc)
            stats["errors"] += 1
            details.append(f"{name}: {exc}")
        db.add(row)
        db.commit()

    return {**stats, "details": details[:40], "settings": cfg}


def list_inbox_db(db: Session, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    q = select(models.InboxItem).order_by(models.InboxItem.created_at.desc()).limit(limit)
    if status:
        q = q.where(models.InboxItem.status == status)
    rows = db.execute(q).scalars().all()
    out = []
    for r in rows:
        out.append(
            {
                "id": str(r.id),
                "file_name": r.file_name,
                "disk_path": r.disk_path,
                "status": r.status,
                "vacancy_id": r.vacancy_id,
                "confidence": r.confidence,
                "extracted": r.extracted or {},
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
            }
        )
    return out


def bind_unsorted(
    db: Session,
    item_id: UUID,
    vacancy_id: int,
) -> dict[str, Any]:
    token = get_disk_token()
    if not token:
        raise DiskApiError("Нет OAuth-токена")
    row = db.get(models.InboxItem, item_id)
    if not row:
        raise ValueError("Элемент inbox не найден")
    vac = db.get(models.Vacancy, vacancy_id)
    if not vac or not vac.active:
        raise ValueError("Вакансия не найдена или неактивна")
    name = row.file_name or Path(row.disk_path).name
    kind = _file_kind(name, row.extracted if isinstance(row.extracted, dict) else None)
    # Prefer extracted.kind from prior routing attempt
    extracted = row.extracted if isinstance(row.extracted, dict) else {}
    if str(extracted.get("kind") or "") == "video":
        kind = "video"

    cand_id = None
    if kind == "video":
        video_dir = _vacancy_video_folder(db, vac, token)
        dest = move_disk_file(token, row.disk_path, f"{video_dir}/{name}")
        vac_cands = list(
            db.execute(select(models.Candidate).where(models.Candidate.vacancy_id == vac.id))
            .scalars()
            .all()
        )
        cand = _match_candidate_by_fio_filename(name, vac_cands)
        if cand:
            _attach_video_link(cand, dest)
            db.add(cand)
            cand_id = str(cand.id)
            row.note = (row.note or "") + f" · видео привязано к {cand.name}"
        else:
            row.note = (row.note or "") + " · файл в Записи, кандидат по ФИО не найден"
        row.extracted = {**extracted, "kind": "video", "full_name": (cand.name if cand else Path(name).stem)}
    else:
        resume_dir = _vacancy_resume_folder(db, vac, token)
        dest = move_disk_file(token, row.disk_path, f"{resume_dir}/{name}")
        dup = _find_duplicate(
            db,
            vac.id,
            str(extracted.get("full_name") or ""),
            str(extracted.get("phone") or ""),
        )
        if not dup:
            _oid = _resolve_vacancy_org_id(db, vac)
            c = create_candidate(
                db,
                vacancy_id=vac.id,
                name=str(extracted.get("full_name") or name),
                fields=_anketa_fields_from_route(
                    extracted if isinstance(extracted, dict) else {},
                    resume_link=f"yadisk-app:{dest}",
                ),
                org_id=_oid,
            )
            cand_id = str(c.id)
        else:
            cand_id = str(dup.id)
        row.note = (row.note or "") + " · привязано вручную"

    row.disk_path = dest
    row.vacancy_id = vac.id
    row.status = "routed"
    row.processed_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "item_id": str(row.id),
        "vacancy_id": vac.id,
        "candidate_id": cand_id,
        "path": dest,
        "kind": kind,
    }
