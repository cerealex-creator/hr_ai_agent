"""Синхронизация файлов кандидатов из опубликованной папки на Яндекс.Диске."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime

from resume_ai import (
    fetch_resume_text_from_url,
    format_yandex_link,
    is_yandex_pdf,
    is_yandex_video_or_audio,
    list_yandex_public_folder,
)

DEFAULT_SUBFOLDERS = {
    "resume": "Резюме",
    "video": "Записи",
    "task": "Задания",
}


def default_yandex_disk_config():
    return {
        "root_url": "",
        "subfolders": dict(DEFAULT_SUBFOLDERS),
        "seen_paths": [],
        "last_sync_at": "",
        "auto_sync": True,
    }


def migrate_vacancy_yandex_disk(vacancy):
    """Дополняет настройки синхронизации с Яндекс.Диском."""
    migrated = False
    cfg = vacancy.get("yandex_disk")
    if not isinstance(cfg, dict):
        vacancy["yandex_disk"] = default_yandex_disk_config()
        return True
    defaults = default_yandex_disk_config()
    for key, val in defaults.items():
        if key not in cfg:
            cfg[key] = val if not isinstance(val, dict) else dict(val)
            migrated = True
    subs = cfg.get("subfolders")
    if not isinstance(subs, dict):
        cfg["subfolders"] = dict(DEFAULT_SUBFOLDERS)
        migrated = True
    else:
        for sk, sv in DEFAULT_SUBFOLDERS.items():
            if sk not in subs:
                subs[sk] = sv
                migrated = True
    if not isinstance(cfg.get("seen_paths"), list):
        cfg["seen_paths"] = []
        migrated = True
    return migrated


def _normalize_name(text):
    return re.sub(r"[^0-9a-zа-яё]+", "", (text or "").lower())


def _filename_stem(name):
    return os.path.splitext(name or "")[0].strip()


def match_candidate_by_filename(filename, candidates):
    """Подбирает кандидата по имени файла или папки."""
    stem = _normalize_name(_filename_stem(filename))
    if not stem:
        return None
    best = None
    best_len = 0
    for cand in candidates:
        cand_name = _normalize_name(cand.get("name", ""))
        if not cand_name:
            continue
        if cand_name in stem or stem in cand_name:
            if len(cand_name) > best_len:
                best = cand
                best_len = len(cand_name)
    return best


def _join_disk_path(parent, name):
    parent = (parent or "").rstrip("/")
    if not parent:
        return f"/{name}"
    return f"{parent}/{name}"


def _seen_set(cfg):
    return {str(p) for p in (cfg.get("seen_paths") or [])}


def _mark_seen(cfg, path):
    paths = cfg.setdefault("seen_paths", [])
    if path not in paths:
        paths.append(path)


@dataclass
class YandexSyncResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self):
        return self.created > 0 or self.updated > 0


def _ingest_resume_file(vacancy, deps, root_url, item, result, *, ingest_new):
    from candidate_funnel import _append_bulk_candidate, populate_from_resume

    name = item.get("name") or ""
    item_path = item.get("path") or ""
    if not is_yandex_pdf(item):
        result.skipped += 1
        return True

    link = format_yandex_link(root_url, item_path)
    candidates = vacancy.get("candidates", [])
    cand = match_candidate_by_filename(name, candidates)

    if cand:
        if (cand.get("resume_link") or "").strip() == link:
            result.skipped += 1
            return True
        cand["resume_link"] = link
        if not (cand.get("resume_text") or "").strip():
            text, err = fetch_resume_text_from_url(
                link,
                deps["extract_text_from_pdf_url"],
                deps.get("transcribe_video_from_link"),
            )
            if text:
                populate_from_resume(cand, text, deps["client"], deps["config"])
            elif err:
                result.errors.append(f"{name}: {err}")
        result.updated += 1
        result.messages.append(f"Резюме → {cand.get('name', name)}")
        return True

    if not ingest_new:
        result.skipped += 1
        result.messages.append(f"Новый файл без пары: {name}")
        return False

    text, err = fetch_resume_text_from_url(
        link,
        deps["extract_text_from_pdf_url"],
        deps.get("transcribe_video_from_link"),
    )
    if not text:
        result.errors.append(f"{name}: {err or 'не удалось прочитать PDF'}")
        return False
    _append_bulk_candidate(
        vacancy,
        deps,
        resume_link=link,
        resume_text=text,
    )
    result.created += 1
    result.messages.append(f"Новый кандидат из {name}")
    return True


def _ingest_video_file(vacancy, root_url, item, result):
    name = item.get("name") or ""
    item_path = item.get("path") or ""
    if not is_yandex_video_or_audio(item):
        result.skipped += 1
        return True
    cand = match_candidate_by_filename(name, vacancy.get("candidates", []))
    if not cand:
        result.skipped += 1
        result.messages.append(f"Видео без пары: {name}")
        return False
    link = format_yandex_link(root_url, item_path)
    if (cand.get("video_link") or "").strip() == link:
        result.skipped += 1
        return True
    cand["video_link"] = link
    result.updated += 1
    result.messages.append(f"Запись → {cand.get('name', name)}")
    return True


def _ingest_task_folder(vacancy, root_url, item, result):
    name = item.get("name") or ""
    item_path = item.get("path") or ""
    cand = match_candidate_by_filename(name, vacancy.get("candidates", []))
    if not cand:
        result.skipped += 1
        result.messages.append(f"Папка задания без пары: {name}")
        return False
    link = format_yandex_link(root_url, item_path)
    if (cand.get("task_link") or "").strip() == link:
        result.skipped += 1
        return True
    cand["task_link"] = link
    result.updated += 1
    result.messages.append(f"Задание → {cand.get('name', name)}")
    return True


def _scan_folder(vacancy, deps, root_url, cfg, folder_name, result, *, mode, ingest_new):
    base_path = f"/{folder_name}" if folder_name else ""
    label = folder_name or "корень"
    try:
        items = list_yandex_public_folder(root_url, base_path)
    except Exception as exc:
        result.errors.append(f"{label}: {exc}")
        return

    seen = _seen_set(cfg)
    for item in items:
        item_type = item.get("type") or ""
        name = item.get("name") or ""
        item_path = item.get("path") or _join_disk_path(base_path, name)
        if item_path in seen:
            continue
        if mode == "task":
            if item_type != "dir":
                continue
            remember = _ingest_task_folder(vacancy, root_url, item, result)
        elif mode == "resume":
            if item_type != "file":
                continue
            remember = _ingest_resume_file(
                vacancy, deps, root_url, item, result, ingest_new=ingest_new
            )
        elif mode == "video":
            if item_type != "file":
                continue
            remember = _ingest_video_file(vacancy, root_url, item, result)
        else:
            remember = True
        if remember:
            _mark_seen(cfg, item_path)
            seen.add(item_path)


def sync_vacancy_yandex_disk(vacancy, deps, *, ingest_new_resumes=True):
    """Сканирует папку на Диске и подставляет ссылки кандидатам."""
    migrate_vacancy_yandex_disk(vacancy)
    cfg = vacancy["yandex_disk"]
    root_url = (cfg.get("root_url") or "").strip()
    result = YandexSyncResult()
    if not root_url:
        result.errors.append("Не указана ссылка на папку вакансии на Яндекс.Диске")
        return result

    subs = cfg.get("subfolders") or {}
    _scan_folder(
        vacancy,
        deps,
        root_url,
        cfg,
        (subs.get("resume") or "").strip(),
        result,
        mode="resume",
        ingest_new=ingest_new_resumes,
    )
    _scan_folder(
        vacancy,
        deps,
        root_url,
        cfg,
        (subs.get("video") or "").strip(),
        result,
        mode="video",
        ingest_new=False,
    )
    _scan_folder(
        vacancy,
        deps,
        root_url,
        cfg,
        (subs.get("task") or "").strip(),
        result,
        mode="task",
        ingest_new=False,
    )

    cfg["last_sync_at"] = datetime.now().isoformat(timespec="seconds")
    return result


def reset_yandex_disk_seen(vacancy):
    """Сбрасывает список обработанных путей (повторная полная синхронизация)."""
    migrate_vacancy_yandex_disk(vacancy)
    vacancy["yandex_disk"]["seen_paths"] = []
