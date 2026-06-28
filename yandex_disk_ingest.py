"""Синхронизация файлов кандидатов из опубликованной папки на Яндекс.Диске."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from resume_ai import (
    fetch_resume_text_from_url,
    format_yandex_link,
    is_yandex_pdf,
    is_yandex_video_or_audio,
    list_yandex_public_folder,
    parse_yandex_link,
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


def default_yandex_disk_config():
    return {
        "root_url": "",
        "subfolders": dict(DEFAULT_SUBFOLDERS),
        "seen_paths": [],
        "last_sync_at": "",
        "ingest_new_resumes": True,
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


def _name_tokens(text):
    """Значимые слова из имени файла/папки/ФИО для нечёткого сопоставления."""
    tokens = []
    for raw in re.split(r"[\s_\-–—.]+", (text or "").strip()):
        token = _normalize_name(raw)
        if len(token) < 3 or token in _MATCH_NOISE_WORDS:
            continue
        tokens.append(token)
    return tokens


def _filename_stem(name):
    return os.path.splitext(name or "")[0].strip()


def _name_similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


_MIN_MATCH_SCORE = 43


def _file_matches_candidate(filename, candidate_name):
    """Файл/папка относится к этому кандидату (фамилия или полное ФИО)."""
    stem = _normalize_name(_filename_stem(filename))
    file_tokens = _name_tokens(_filename_stem(filename))
    cand_name = _normalize_name(candidate_name)
    if not cand_name:
        return False
    if stem and (cand_name in stem or stem in cand_name):
        return True
    if file_tokens and file_tokens[0] in cand_name:
        return True
    return False


def match_candidate_by_filename(filename, candidates):
    """Подбирает кандидата по имени файла или папки."""
    stem = _normalize_name(_filename_stem(filename))
    file_tokens = _name_tokens(_filename_stem(filename))
    if not stem and not file_tokens:
        return None
    best = None
    best_score = 0
    for cand in candidates:
        cand_name = _normalize_name(cand.get("name", ""))
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
        for ct in _name_tokens(cand.get("name", "")):
            if len(ct) >= 4 and stem and ct in stem:
                score = max(score, len(ct) + 40)
        if score > best_score:
            best_score = score
            best = cand
    if best_score < _MIN_MATCH_SCORE:
        return None
    return best


def _repair_mismatched_resume_links(vacancy, result):
    """Убирает ошибочно привязанные резюме (другая фамилия в имени файла)."""
    for cand in vacancy.get("candidates", []):
        link = (cand.get("resume_link") or "").strip()
        if not link:
            continue
        _, path = parse_yandex_link(link)
        filename = (path or "").rsplit("/", 1)[-1]
        if filename and not _file_matches_candidate(filename, cand.get("name", "")):
            cand["resume_link"] = ""
            result.messages.append(
                f"Сброшена неверная ссылка на резюме у {cand.get('name', 'кандидата')}"
            )


def _repair_broken_yandex_links(vacancy, root_url, result):
    """Сбрасывает yadisk-ссылки с несуществующим путём (папку переименовали и т.п.)."""
    root_norm = (root_url or "").strip().rstrip("/")
    for cand in vacancy.get("candidates", []):
        for field, label in (
            ("resume_link", "резюме"),
            ("video_link", "запись"),
            ("task_link", "задание"),
        ):
            link = (cand.get(field) or "").strip()
            if not link.startswith("yadisk:"):
                continue
            public_key, path = parse_yandex_link(link)
            if public_key.rstrip("/") != root_norm:
                continue
            if not path:
                continue
            if yandex_path_is_valid(public_key, path):
                continue
            cand[field] = ""
            result.messages.append(
                f"Сброшена устаревшая ссылка ({label}) у {cand.get('name', 'кандидата')}"
            )


def _resolve_subfolder_name(root_url, configured_name):
    """
    Находит реальную подпапку на Диске.
    Если «Записи» в настройках, а на диске «Записи собеседований» — подберёт её.
    Учитывает опечатки в названии (например «собесдований» вместо «собеседований»).
    """
    configured = (configured_name or "").strip().strip("/")
    if not configured:
        return ""
    exact_path = f"/{configured}"
    try:
        exact_items = list_yandex_public_folder(root_url, exact_path)
        if exact_items:
            return configured
    except Exception:
        exact_items = None
    norm_cfg = _normalize_name(configured)
    if not norm_cfg:
        return configured
    try:
        root_items = list_yandex_public_folder(root_url, "")
    except Exception:
        return configured
    root_dir_names = {
        (item.get("name") or "").strip()
        for item in root_items
        if item.get("type") == "dir"
    }
    if configured in root_dir_names:
        return configured
    best_name = ""
    best_score = 0
    for item in root_items:
        if item.get("type") != "dir":
            continue
        name = (item.get("name") or "").strip()
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
    for existing in candidates:
        if (existing.get("resume_link") or "").strip() == link:
            if _file_matches_candidate(name, existing.get("name", "")):
                result.skipped += 1
                return True
            existing["resume_link"] = ""
    cand = match_candidate_by_filename(name, candidates)

    if cand and not _file_matches_candidate(name, cand.get("name", "")):
        cand = None

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
        result.messages.append(f"Не видео/аудио, пропуск: {name}")
        return False
    link = format_yandex_link(root_url, item_path)
    for existing in vacancy.get("candidates", []):
        if (existing.get("video_link") or "").strip() == link:
            if _file_matches_candidate(name, existing.get("name", "")):
                result.skipped += 1
                return True
            existing["video_link"] = ""
    cand = match_candidate_by_filename(name, vacancy.get("candidates", []))
    if not cand or not _file_matches_candidate(name, cand.get("name", "")):
        result.skipped += 1
        result.messages.append(f"Видео без пары: {name}")
        return False
    current = (cand.get("video_link") or "").strip()
    if current and current != link:
        pk, old_path = parse_yandex_link(current)
        if old_path and not yandex_path_is_valid(pk, old_path):
            cand["video_link"] = ""
            current = ""
    if current == link:
        result.skipped += 1
        return True
    cand["video_link"] = link
    result.updated += 1
    result.messages.append(f"Запись → {cand.get('name', name)}")
    return True


def _ingest_task_folder(vacancy, root_url, item, result):
    name = item.get("name") or ""
    item_path = item.get("path") or ""
    link = format_yandex_link(root_url, item_path)
    for existing in vacancy.get("candidates", []):
        if (existing.get("task_link") or "").strip() == link:
            if _file_matches_candidate(name, existing.get("name", "")):
                result.skipped += 1
                return True
            existing["task_link"] = ""
    cand = match_candidate_by_filename(name, vacancy.get("candidates", []))
    if not cand or not _file_matches_candidate(name, cand.get("name", "")):
        result.skipped += 1
        result.messages.append(f"Папка задания без пары: {name}")
        return False
    if (cand.get("task_link") or "").strip() == link:
        result.skipped += 1
        return True
    cand["task_link"] = link
    result.updated += 1
    result.messages.append(f"Задание → {cand.get('name', name)}")
    return True


def _guess_item_mode(path, name):
    lower = (name or "").lower()
    if lower.endswith(".pdf"):
        return "resume"
    if lower.endswith((".mp4", ".webm", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".ogg", ".m4a")):
        return "video"
    return "task"


def _prune_unapplied_seen_paths(vacancy, root_url, cfg, result):
    """Убирает из seen_paths файлы, которые так и не привязались к карточкам."""
    kept = []
    removed = 0
    for path in list(cfg.get("seen_paths", [])):
        name = path.rsplit("/", 1)[-1]
        mode = _guess_item_mode(path, name)
        item = {
            "name": name,
            "path": path,
            "type": "dir" if mode == "task" else "file",
        }
        if _item_link_applied(vacancy, root_url, item, mode):
            kept.append(path)
        else:
            removed += 1
    if removed:
        result.messages.append(f"Повторная проверка: {removed} файл(ов) без ссылки в карточке")
    cfg["seen_paths"] = kept


def _link_field_for_mode(mode):
    return {"resume": "resume_link", "video": "video_link", "task": "task_link"}.get(mode)


def _item_link_applied(vacancy, root_url, item, mode):
    """Файл уже привязан к карточке кандидата (можно не обрабатывать повторно)."""
    field = _link_field_for_mode(mode)
    if not field:
        return True
    name = item.get("name") or ""
    item_path = item.get("path") or ""
    link = format_yandex_link(root_url, item_path)
    cand = match_candidate_by_filename(name, vacancy.get("candidates", []))
    if not cand or not _file_matches_candidate(name, cand.get("name", "")):
        return False
    stored = (cand.get(field) or "").strip()
    if stored != link:
        return False
    if not item_path:
        return True
    return yandex_path_is_valid(root_url, item_path)


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
        if item_path in seen and _item_link_applied(vacancy, root_url, item, mode):
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

    _repair_mismatched_resume_links(vacancy, result)
    _repair_broken_yandex_links(vacancy, root_url, result)
    _prune_unapplied_seen_paths(vacancy, root_url, cfg, result)

    subs = cfg.get("subfolders") or {}
    folder_plan = (
        ("resume", (subs.get("resume") or "").strip(), "resume", ingest_new_resumes),
        ("video", (subs.get("video") or "").strip(), "video", False),
        ("task", (subs.get("task") or "").strip(), "task", False),
    )
    for kind, configured, mode, ingest_new in folder_plan:
        resolved = _resolve_subfolder_name(root_url, configured)
        if configured and resolved and resolved != configured:
            result.messages.append(f"Подпапка «{configured}» → «{resolved}»")
        _scan_folder(
            vacancy,
            deps,
            root_url,
            cfg,
            resolved,
            result,
            mode=mode,
            ingest_new=ingest_new,
        )

    cfg["last_sync_at"] = datetime.now().isoformat(timespec="seconds")
    return result


def reset_yandex_disk_seen(vacancy):
    """Сбрасывает список обработанных путей (повторная полная синхронизация)."""
    migrate_vacancy_yandex_disk(vacancy)
    vacancy["yandex_disk"]["seen_paths"] = []
