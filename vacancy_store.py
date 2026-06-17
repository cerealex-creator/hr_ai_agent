"""Хранение вакансий и статусы клиентской зоны (без Streamlit)."""

import json
import os
import time
import uuid
from datetime import datetime

from models import CLIENT_ZONE_ENTRY_STAGE, is_visible_in_client_zone

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
VACANCIES_FILE = os.path.join(DATA_DIR, "vacancies_db.json")
DEPARTMENTS_FILE = os.path.join(DATA_DIR, "departments.json")
CHATS_FILE = os.path.join(DATA_DIR, "chats_db.json")

STATUS_CONFIG = {
    "wait": {"label": "Ждёт оценки", "icon": "⚪", "badge_class": "status-badge-wait"},
    "ready": {"label": "Встреча", "icon": "🟢", "badge_class": "status-badge-ready"},
    "reject": {"label": "Отказ", "icon": "🔴", "badge_class": "status-badge-reject"},
    "think": {"label": "Подумать", "icon": "🟡", "badge_class": "status-badge-think"},
    "offer": {"label": "Оффер", "icon": "🟢", "badge_class": "status-badge-offer"},
    "started": {"label": "Вышел на работу", "icon": "👑", "badge_class": "status-badge-started"},
}

STATUS_ORDER = {"wait": 0, "ready": 1, "think": 2, "offer": 3, "started": 4, "reject": 5}
STATUS_OPTIONS = [cfg["label"] for cfg in STATUS_CONFIG.values()]
STATUS_LABEL_TO_KEY = {cfg["label"]: key for key, cfg in STATUS_CONFIG.items()}

# Поля, которые обновляет Telegram-бот — не затирать при сохранении из Streamlit
TELEGRAM_MERGE_FIELDS = (
    "client_comment",
    "client_status",
    "status_updated_at",
    "hr_stage",
    "hr_stage_history",
    "telegram_posts",
    "client_final_verdict",
    "tg_callback_id",
    "interview_reminder_60_sent",
    "feedback_reminder_last_sent_at",
    "think_long_reminder_sent",
)


def _try_import_fcntl():
    try:
        import fcntl
        return fcntl
    except ImportError:
        return None


def _lock_file(f, exclusive=False):
    fcntl = _try_import_fcntl()
    if not fcntl:
        return
    fcntl.flock(f.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)


def _unlock_file(f):
    fcntl = _try_import_fcntl()
    if not fcntl:
        return
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _normalize_payload(data):
    if isinstance(data, list):
        return {"vacancies": data}
    return data


def _read_vacancies_file():
    os.makedirs(os.path.dirname(VACANCIES_FILE) or ".", exist_ok=True)
    if not os.path.exists(VACANCIES_FILE):
        return {"vacancies": []}
    last_error = None
    for attempt in range(5):
        try:
            with open(VACANCIES_FILE, "r", encoding="utf-8") as f:
                _lock_file(f, exclusive=False)
                try:
                    return json.load(f)
                finally:
                    _unlock_file(f)
        except json.JSONDecodeError as exc:
            last_error = exc
            time.sleep(0.05 * (attempt + 1))
    raise last_error


def _atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        _lock_file(f, exclusive=True)
        try:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            _unlock_file(f)
    os.replace(tmp_path, path)


def load_chats():
    if not os.path.exists(CHATS_FILE):
        return []
    with open(CHATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def sync_vacancy_chat_ids_from_chats():
    """
    Выравнивает vacancy.chat_id по chats_db (отдел → чат).
    Источник истины — настройки Telegram в приложении.
    """
    from telegram_notify import chat_ids_equal, normalize_chat_id

    by_dept = {}
    for chat in load_chats():
        dept_id = chat.get("department_id")
        if dept_id is None:
            continue
        by_dept[dept_id] = normalize_chat_id(chat.get("id"))

    data = load_vacancies()
    changed = False
    for vacancy in data.get("vacancies", []):
        canonical = by_dept.get(vacancy.get("client_id"))
        if canonical is None:
            continue
        if not chat_ids_equal(vacancy.get("chat_id"), canonical):
            vacancy["chat_id"] = canonical
            changed = True
    if changed:
        save_vacancies(data)
    return changed


def prune_stale_telegram_posts(data=None):
    """
    Удаляет telegram_posts из устаревших чатов.
    В актуальном чате оставляет последний primary и все task-сообщения.
    """
    from client_actions import post_belongs_to_vacancy, post_kind
    from telegram_chat_id import resolve_vacancy_chat_id
    from telegram_notify import chat_ids_equal

    if data is None:
        data = load_vacancies()
    changed = False
    for vacancy in data.get("vacancies", []):
        active_chat = resolve_vacancy_chat_id(vacancy)
        if active_chat is None:
            continue
        vac_id = vacancy.get("id")
        for cand in vacancy.get("candidates", []):
            migrate_candidate(cand)
            posts = cand.get("telegram_posts") or []
            if not posts:
                continue

            in_active = [
                p for p in posts if chat_ids_equal(p.get("chat_id"), active_chat)
            ]
            if not in_active:
                if any(not chat_ids_equal(p.get("chat_id"), active_chat) for p in posts):
                    cand["telegram_posts"] = []
                    changed = True
                continue

            primaries = [
                p
                for p in in_active
                if post_kind(p) == "primary"
                and post_belongs_to_vacancy(p, vac_id)
            ]
            tasks = [p for p in in_active if post_kind(p) == "task"]
            other = [
                p
                for p in in_active
                if post_kind(p) not in ("primary", "task")
            ]

            compacted = []
            if primaries:
                compacted.append(
                    max(primaries, key=lambda p: p.get("sent_at") or "")
                )
            compacted.extend(tasks)
            compacted.extend(other)

            if len(compacted) != len(posts) or any(
                not chat_ids_equal(p.get("chat_id"), active_chat) for p in posts
            ):
                cand["telegram_posts"] = compacted
                changed = True

    if changed:
        save_vacancies(data)
    return changed


def load_departments():
    if not os.path.exists(DEPARTMENTS_FILE):
        return []
    with open(DEPARTMENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("departments", [])


def load_vacancies():
    return _read_vacancies_file()


def load_vacancies_list():
    return load_vacancies().get("vacancies", [])


def save_vacancies(data):
    _atomic_write_json(VACANCIES_FILE, _normalize_payload(data))


def save_vacancies_list(vacancies_list):
    save_vacancies({"vacancies": vacancies_list})


def delete_vacancy_by_id(vacancy_id):
    """
    Удаляет вакансию из базы.
    Возвращает (ok, message).
    """
    if not vacancy_id:
        return False, "Не указан id вакансии"
    data = load_vacancies()
    vacancies = data.get("vacancies", [])
    before = len(vacancies)
    vacancies = [v for v in vacancies if v.get("id") != vacancy_id]
    if len(vacancies) == before:
        return False, "Вакансия не найдена"
    data["vacancies"] = vacancies
    save_vacancies(data)
    return True, "Вакансия удалена"


def delete_vacancy_by_title(title):
    """
    Удаляет вакансию по названию (в проекте названия уникальны).
    Возвращает (ok, message).
    """
    t = (title or "").strip()
    if not t:
        return False, "Не указано название вакансии"
    data = load_vacancies()
    vacancies = data.get("vacancies", [])
    before = len(vacancies)
    vacancies = [v for v in vacancies if (v.get("title") or "").strip() != t]
    if len(vacancies) == before:
        return False, "Вакансия не найдена"
    data["vacancies"] = vacancies
    save_vacancies(data)
    return True, "Вакансия удалена"


def _latest_hr_stage_change_at(candidate):
    history = candidate.get("hr_stage_history") or []
    if not history:
        return ""
    return max((entry.get("at") or "") for entry in history)


def merge_candidate_from_disk(memory_cand, disk_cand):
    """Подмешивает в память поля, обновлённые ботом/Telegram."""
    if not memory_cand.get("id") or memory_cand.get("id") != disk_cand.get("id"):
        return memory_cand
    mem_stage_at = _latest_hr_stage_change_at(memory_cand)
    disk_stage_at = _latest_hr_stage_change_at(disk_cand)
    for field in TELEGRAM_MERGE_FIELDS:
        if field not in disk_cand:
            continue
        if field in ("hr_stage", "hr_stage_history"):
            if disk_stage_at > mem_stage_at:
                memory_cand[field] = disk_cand[field]
            continue
        memory_cand[field] = disk_cand[field]
    return memory_cand


def merge_vacancy_candidates_from_disk(memory_vacancy, vacancies_list):
    """Перед сохранением из UI подтягивает свежие данные кандидатов с диска."""
    mem_id = memory_vacancy.get("id")
    for vacancy in vacancies_list:
        if vacancy.get("id") != mem_id:
            continue
        disk_map = {
            c["id"]: c
            for c in vacancy.get("candidates", [])
            if c.get("id")
        }
        for mc in memory_vacancy.get("candidates", []):
            dc = disk_map.get(mc.get("id"))
            if dc:
                merge_candidate_from_disk(mc, dc)
        vacancy["candidates"] = memory_vacancy.get("candidates", [])
        break
    return vacancies_list


def get_status_meta(status_key):
    return STATUS_CONFIG.get(status_key, STATUS_CONFIG["wait"])


def migrate_candidate(cand):
    now = datetime.now().isoformat()
    if "created_at" not in cand:
        cand["created_at"] = now
    if "viewed" not in cand:
        cand["viewed"] = True
    if "status_updated_at" not in cand:
        cand["status_updated_at"] = cand.get("created_at", now)
    if "remote_interview" not in cand:
        cand["remote_interview"] = False
    if "office_interview" not in cand:
        cand["office_interview"] = bool(cand.get("office_interview_date"))
    if "meeting_hr_confirmed" not in cand:
        cand["meeting_hr_confirmed"] = False
    if "meeting_hr_confirmation_post" not in cand:
        cand["meeting_hr_confirmation_post"] = None
    if "telegram_posts" not in cand or not isinstance(cand.get("telegram_posts"), list):
        cand["telegram_posts"] = []
    if not cand.get("id"):
        cand["id"] = str(uuid.uuid4())
    if not cand.get("tg_callback_id"):
        cand["tg_callback_id"] = cand["id"].replace("-", "")[:8]
    if "portfolio_link" not in cand:
        cand["portfolio_link"] = ""
    status = cand.get("client_status", "wait")
    if status == "new" or status not in STATUS_CONFIG:
        cand["client_status"] = "wait"
    if is_visible_in_client_zone(cand) and not (cand.get("status_updated_at") or "").strip():
        for entry in reversed(cand.get("hr_stage_history", [])):
            if entry.get("stage") == CLIENT_ZONE_ENTRY_STAGE:
                cand["status_updated_at"] = entry.get("at") or now
                break
        else:
            cand["status_updated_at"] = now
    return cand


def migrate_vacancy(vacancy):
    """Дополняет вакансию недостающими полями настроек."""
    if "show_portfolio_field" not in vacancy:
        vacancy["show_portfolio_field"] = False
    return vacancy


def vacancy_show_portfolio_field(vacancy):
    migrate_vacancy(vacancy)
    return bool(vacancy.get("show_portfolio_field"))


def migrate_vacancies_data(data):
    changed = False
    for vacancy in data.get("vacancies", []):
        before = json.dumps(
            {k: vacancy.get(k) for k in ("show_portfolio_field",)},
            sort_keys=True,
            ensure_ascii=False,
        )
        migrate_vacancy(vacancy)
        after = json.dumps(
            {k: vacancy.get(k) for k in ("show_portfolio_field",)},
            sort_keys=True,
            ensure_ascii=False,
        )
        if before != after:
            changed = True
        for cand in vacancy.get("candidates", []):
            before = json.dumps(cand, sort_keys=True, ensure_ascii=False)
            migrate_candidate(cand)
            after = json.dumps(cand, sort_keys=True, ensure_ascii=False)
            if before != after:
                changed = True
    if changed:
        save_vacancies(data)
    return data


def resolve_status_on_save(cand, selected_label):
    selected_key = STATUS_LABEL_TO_KEY[selected_label]
    if selected_key != cand.get("client_status"):
        cand["status_updated_at"] = datetime.now().isoformat()
    return selected_key
