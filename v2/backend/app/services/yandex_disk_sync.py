"""Sync vacancy Yandex Disk folder → candidate resume/video/task links (PostgreSQL)."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.services.candidate_write import create_candidate
from app.services.transcription import parse_yandex_link
from app.services.yandex_public import (
    format_yandex_link,
    is_yandex_pdf,
    is_yandex_video_or_audio,
    list_yandex_public_folder,
    yandex_path_is_valid,
)

DEFAULT_SUBFOLDERS = {
    "resume": "Резюме",
    "video": "Записи",
    "task": "Задания",
}

_MATCH_NOISE_WORDS = frozenset({
    "задание",
    "задания",
    "task",
    "tasks",
    "папка",
    "folder",
    "видео",
    "video",
    "запись",
    "записи",
    "собеседование",
    "собеседования",
    "резюме",
    "resume",
    "cv",
    "pdf",
    "mp4",
    "mov",
    "avi",
})

_MIN_MATCH_SCORE = 43

FIELD_BY_MODE = {
    "resume": "resume_link",
    "video": "video_link",
    "task": "task_link",
}


@dataclass
class YandexSyncResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    evaluate_candidate_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "messages": self.messages[:40],
            "errors": self.errors[:20],
            "changed": self.created > 0 or self.updated > 0,
            "evaluate_candidate_ids": list(self.evaluate_candidate_ids),
        }


def default_yandex_disk_config() -> dict[str, Any]:
    return {
        "root_url": "",
        "subfolders": dict(DEFAULT_SUBFOLDERS),
        "seen_paths": [],
        "last_sync_at": "",
        "ingest_new_resumes": True,
        "auto_sync": False,
    }


def ensure_yandex_config(vacancy: models.Vacancy) -> dict[str, Any]:
    payload = dict(vacancy.payload or {})
    cfg = payload.get("yandex_disk")
    if not isinstance(cfg, dict):
        cfg = default_yandex_disk_config()
    else:
        base = default_yandex_disk_config()
        for key, val in base.items():
            if key not in cfg:
                cfg[key] = val if not isinstance(val, dict) else dict(val)
        subs = cfg.get("subfolders")
        if not isinstance(subs, dict):
            cfg["subfolders"] = dict(DEFAULT_SUBFOLDERS)
        else:
            for sk, sv in DEFAULT_SUBFOLDERS.items():
                if sk not in subs:
                    subs[sk] = sv
        if not isinstance(cfg.get("seen_paths"), list):
            cfg["seen_paths"] = []
    payload["yandex_disk"] = cfg
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    return cfg


def update_yandex_config(
    vacancy: models.Vacancy,
    *,
    root_url: str | None = None,
    ingest_new_resumes: bool | None = None,
    subfolders: dict[str, str] | None = None,
    reset_seen: bool = False,
) -> dict[str, Any]:
    cfg = ensure_yandex_config(vacancy)
    if root_url is not None:
        cfg["root_url"] = root_url.strip()
    if ingest_new_resumes is not None:
        cfg["ingest_new_resumes"] = bool(ingest_new_resumes)
    if subfolders:
        subs = dict(cfg.get("subfolders") or {})
        for key in ("resume", "video", "task"):
            if key in subfolders and subfolders[key] is not None:
                subs[key] = str(subfolders[key]).strip()
        cfg["subfolders"] = subs
    if reset_seen:
        cfg["seen_paths"] = []
    payload = dict(vacancy.payload or {})
    payload["yandex_disk"] = cfg
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    return cfg


def _normalize_name(text: str) -> str:
    return re.sub(
        r"[^0-9a-zа-яё]+",
        "",
        unicodedata.normalize("NFC", (text or "")).lower(),
    )


def _name_tokens(text: str) -> list[str]:
    tokens = []
    for raw in re.split(r"[\s_\-–—.]+", (text or "").strip()):
        token = _normalize_name(raw)
        if len(token) < 3 or token in _MATCH_NOISE_WORDS:
            continue
        tokens.append(token)
    return tokens


def _filename_stem(name: str) -> str:
    return os.path.splitext(name or "")[0].strip()


def _name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def person_name_in_text(name: str, text: str) -> bool:
    """True if candidate ФИО looks present in resume text (for de-dupe)."""
    cand_name = _normalize_name(name)
    hay = _normalize_name((text or "")[:8000])
    if cand_name and len(cand_name) >= 5 and cand_name in hay:
        return True
    tokens = _name_tokens(name)
    if not tokens:
        return False
    surname = tokens[0]
    if len(surname) < 3 or surname not in hay:
        return False
    if len(tokens) == 1:
        return True
    return any(len(t) >= 3 and t in hay for t in tokens[1:])


def file_matches_candidate(filename: str, candidate_name: str) -> bool:
    stem = _normalize_name(_filename_stem(filename))
    file_tokens = _name_tokens(_filename_stem(filename))
    cand_name = _normalize_name(candidate_name)
    if not cand_name:
        return False
    if stem and (cand_name in stem or stem in cand_name):
        return True
    if file_tokens and file_tokens[0] in cand_name:
        return True
    cand_tokens = _name_tokens(candidate_name)
    if cand_tokens:
        surname = cand_tokens[0]
        if len(surname) >= 3 and (surname in file_tokens or (stem and surname in stem)):
            return True
    return False


def match_candidate_by_filename(
    filename: str, candidates: list[models.Candidate]
) -> models.Candidate | None:
    stem = _normalize_name(_filename_stem(filename))
    file_tokens = _name_tokens(_filename_stem(filename))
    if not stem and not file_tokens:
        return None
    best: models.Candidate | None = None
    best_score = 0
    for cand in candidates:
        cand_name = _normalize_name(cand.name or "")
        if not cand_name:
            continue
        score = 0
        if stem and (cand_name in stem or stem in cand_name):
            score = max(score, len(cand_name) + 200)
        if file_tokens and file_tokens[0] in cand_name:
            score = max(score, len(file_tokens[0]) + 150)
        for ft in file_tokens:
            if len(ft) >= 3 and ft in cand_name:
                score = max(score, len(ft) + 50)
        for ct in _name_tokens(cand.name or ""):
            if len(ct) >= 4 and stem and ct in stem:
                score = max(score, len(ct) + 40)
        if score > best_score:
            best_score = score
            best = cand
    if best_score < _MIN_MATCH_SCORE:
        return None
    return best


def _guess_name_from_filename(filename: str) -> str:
    stem = _filename_stem(filename)
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return stem or filename


def _payload_get(cand: models.Candidate, key: str) -> str:
    return str((cand.payload or {}).get(key) or "").strip()


def _payload_set(cand: models.Candidate, key: str, value: str) -> None:
    payload = dict(cand.payload or {})
    payload[key] = value
    cand.payload = payload
    flag_modified(cand, "payload")


def _queue_resume_eval(result: YandexSyncResult, cand: models.Candidate) -> None:
    cid = str(cand.id)
    if cid in result.evaluate_candidate_ids:
        return
    if (cand.payload or {}).get("ai_score") is not None:
        return
    result.evaluate_candidate_ids.append(cid)


def _normalize_disk_path(path: str) -> str:
    return unicodedata.normalize("NFC", (path or "").strip())


def _join_disk_path(parent: str, name: str) -> str:
    parent = (parent or "").rstrip("/")
    if not parent:
        return f"/{name}"
    return f"{parent}/{name}"


def _seen_set(cfg: dict) -> set[str]:
    return {_normalize_disk_path(p) for p in (cfg.get("seen_paths") or [])}


def _mark_seen(cfg: dict, path: str) -> None:
    path = (path or "").strip()
    paths = cfg.setdefault("seen_paths", [])
    if path and path not in paths:
        paths.append(path)


def _resolve_subfolder_name(root_url: str, configured_name: str) -> str:
    configured = (configured_name or "").strip().strip("/")
    if not configured:
        return ""
    exact_path = f"/{configured}"
    try:
        if list_yandex_public_folder(root_url, exact_path):
            return configured
    except Exception:
        pass
    norm_cfg = _normalize_name(configured)
    if not norm_cfg:
        return configured
    try:
        roots = list_yandex_public_folder(root_url, "")
    except Exception:
        return configured
    best_name = ""
    best_score = 0
    for item in roots:
        if (item.get("type") or "") != "dir":
            continue
        name = item.get("name") or ""
        norm_name = _normalize_name(name)
        if not norm_name:
            continue
        score = 0
        if norm_name == norm_cfg:
            score = 1000
        elif norm_name.startswith(norm_cfg) or norm_cfg.startswith(norm_name):
            score = 500 + len(norm_name)
        elif norm_cfg in norm_name or norm_name in norm_cfg:
            score = 200 + len(norm_name)
        else:
            ratio = _name_similarity(norm_name, norm_cfg)
            if ratio >= 0.82:
                score = int(ratio * 900) + len(norm_name)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name or configured


def _load_candidates(db: Session, vacancy_id: int) -> list[models.Candidate]:
    return list(
        db.scalars(
            select(models.Candidate).where(models.Candidate.vacancy_id == vacancy_id)
        ).all()
    )


def _attach_link(
    candidates: list[models.Candidate],
    *,
    filename: str,
    link: str,
    field: str,
    result: YandexSyncResult,
    label: str,
) -> bool:
    """Attach link to matched candidate. Returns True if path should be marked seen."""
    for existing in candidates:
        if _payload_get(existing, field) == link:
            if file_matches_candidate(filename, existing.name or ""):
                result.skipped += 1
                return True
            _payload_set(existing, field, "")

    cand = match_candidate_by_filename(filename, candidates)
    if not cand or not file_matches_candidate(filename, cand.name or ""):
        result.skipped += 1
        result.messages.append(f"{label} без пары: {filename}")
        return False

    current = _payload_get(cand, field)
    if current == link:
        result.skipped += 1
        return True
    if current and field == "video_link":
        pk, old_path = parse_yandex_link(current)
        if old_path and not yandex_path_is_valid(pk, old_path):
            current = ""
            _payload_set(cand, field, "")
    if current and current != link and field != "video_link":
        # replace only if old path broken
        pk, old_path = parse_yandex_link(current)
        if old_path and yandex_path_is_valid(pk, old_path):
            result.skipped += 1
            result.messages.append(f"У {cand.name} уже есть {label.lower()}, пропуск {filename}")
            return True

    _payload_set(cand, field, link)
    result.updated += 1
    result.messages.append(f"{label} → {cand.name or filename}")
    return True


def _ingest_resume(
    db: Session,
    vacancy: models.Vacancy,
    candidates: list[models.Candidate],
    *,
    root_url: str,
    item: dict,
    result: YandexSyncResult,
    ingest_new: bool,
) -> bool:
    name = item.get("name") or ""
    item_path = item.get("path") or ""
    if not is_yandex_pdf(item):
        result.skipped += 1
        return True
    link = format_yandex_link(root_url, item_path)

    for existing in candidates:
        if _payload_get(existing, "resume_link") == link:
            if file_matches_candidate(name, existing.name or ""):
                if (existing.payload or {}).get("ai_score") is None:
                    _queue_resume_eval(result, existing)
                    result.messages.append(
                        f"Оценка резюме в очереди: {existing.name or name}"
                    )
                else:
                    result.skipped += 1
                return True
            _payload_set(existing, "resume_link", "")

    cand = match_candidate_by_filename(name, candidates)
    if cand and not file_matches_candidate(name, cand.name or ""):
        cand = None

    if cand:
        if _payload_get(cand, "resume_link") != link:
            _payload_set(cand, "resume_link", link)
            result.updated += 1
            result.messages.append(f"Резюме → {cand.name or name}")
        else:
            result.skipped += 1
        if (cand.payload or {}).get("ai_score") is None:
            _queue_resume_eval(result, cand)
            result.messages.append(f"Оценка резюме в очереди: {cand.name or name}")
        return True

    if not ingest_new:
        result.skipped += 1
        result.messages.append(f"Новый файл без пары: {name}")
        return False

    new_name = _guess_name_from_filename(name)
    created = create_candidate(
        db,
        vacancy_id=vacancy.id,
        name=new_name,
        fields={"resume_link": link},
    )
    payload = dict(created.payload or {})
    payload["source"] = "yandex_disk"
    created.payload = payload
    flag_modified(created, "payload")
    db.commit()
    candidates.append(created)
    result.created += 1
    _queue_resume_eval(result, created)
    result.messages.append(f"Новый кандидат из {name} — оценка в очереди")
    return True


def _scan_folder(
    db: Session,
    vacancy: models.Vacancy,
    candidates: list[models.Candidate],
    *,
    root_url: str,
    cfg: dict,
    folder_name: str,
    result: YandexSyncResult,
    mode: str,
    ingest_new: bool,
) -> None:
    base_path = f"/{folder_name}" if folder_name else ""
    label = folder_name or "корень"
    try:
        items = list_yandex_public_folder(root_url, base_path)
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"{label}: {exc}")
        return

    seen = _seen_set(cfg)
    for item in items:
        item_type = item.get("type") or ""
        name = item.get("name") or ""
        item_path = item.get("path") or _join_disk_path(base_path, name)
        field = FIELD_BY_MODE.get(mode)
        if not field:
            continue
        if _normalize_disk_path(item_path) in seen:
            # already processed; skip unless link missing on matched card
            link = format_yandex_link(root_url, item_path)
            matched = match_candidate_by_filename(name, candidates)
            if matched and _payload_get(matched, field) == link:
                continue

        remember = False
        if mode == "resume":
            if item_type != "file":
                continue
            remember = _ingest_resume(
                db,
                vacancy,
                candidates,
                root_url=root_url,
                item=item,
                result=result,
                ingest_new=ingest_new,
            )
        elif mode == "video":
            if item_type != "file" or not is_yandex_video_or_audio(item):
                if item_type == "file":
                    result.skipped += 1
                continue
            link = format_yandex_link(root_url, item_path)
            remember = _attach_link(
                candidates,
                filename=name,
                link=link,
                field="video_link",
                result=result,
                label="Запись",
            )
        elif mode == "task":
            if item_type not in ("file", "dir"):
                continue
            link = format_yandex_link(root_url, item_path)
            remember = _attach_link(
                candidates,
                filename=name,
                link=link,
                field="task_link",
                result=result,
                label="Задание",
            )
        if remember:
            _mark_seen(cfg, item_path)
            seen.add(_normalize_disk_path(item_path))


def sync_vacancy_yandex_disk(
    db: Session,
    vacancy: models.Vacancy,
    *,
    ingest_new_resumes: bool | None = None,
) -> YandexSyncResult:
    cfg = ensure_yandex_config(vacancy)
    root_url = (cfg.get("root_url") or "").strip()
    result = YandexSyncResult()
    if not root_url:
        result.errors.append("Не указана ссылка на папку вакансии на Яндекс.Диске")
        return result

    if ingest_new_resumes is None:
        ingest_new_resumes = bool(cfg.get("ingest_new_resumes", True))

    candidates = _load_candidates(db, vacancy.id)
    subs = cfg.get("subfolders") or {}
    folder_plan = (
        ("resume", (subs.get("resume") or "").strip(), "resume", ingest_new_resumes),
        ("video", (subs.get("video") or "").strip(), "video", False),
        ("task", (subs.get("task") or "").strip(), "task", False),
    )
    for _kind, configured, mode, ingest_new in folder_plan:
        resolved = _resolve_subfolder_name(root_url, configured)
        if configured and resolved and resolved != configured:
            result.messages.append(f"Подпапка «{configured}» → «{resolved}»")
        _scan_folder(
            db,
            vacancy,
            candidates,
            root_url=root_url,
            cfg=cfg,
            folder_name=resolved,
            result=result,
            mode=mode,
            ingest_new=bool(ingest_new),
        )

    cfg["last_sync_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = dict(vacancy.payload or {})
    payload["yandex_disk"] = cfg
    vacancy.payload = payload
    flag_modified(vacancy, "payload")
    db.commit()
    return result
