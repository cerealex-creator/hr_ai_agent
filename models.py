"""Модели данных: HR-воронка, миграции кандидатов."""

import uuid
from datetime import datetime

HR_STAGES = {
    "resume_screening": "Отсев резюме",
    "primary_contact": "Первичный контакт",
    "interview_scheduled": "Собеседование назначено",
    "interview_done": "Собеседование проведено",
    "test_task": "Тестовое задание",
    "client_review": "На оценке у заказчика",
    "client_meeting": "Встреча с заказчиком",
    "offer": "Оффер",
    "rejected": "Отказ",
    "archived": "Архив",
    "rejected_candidate": "Отказ кандидата",
    "rejected_client": "Отказ Заказчика",
    "rejected_hr": "Отказ мой",
}

HR_STAGE_ORDER = list(HR_STAGES.keys())
HR_STAGE_ORDER_UI = [s for s in HR_STAGE_ORDER if s != "rejected"]

REJECTION_STAGES = frozenset({
    "rejected_candidate",
    "rejected_client",
    "rejected_hr",
})

GREEN_STAGES = frozenset({
    "interview_scheduled",
    "interview_done",
    "client_meeting",
})

YELLOW_STAGES = frozenset({
    "primary_contact",
    "test_task",
    "client_review",
})

OFFER_STAGE = "offer"
CLIENT_ZONE_ENTRY_STAGE = "client_review"


def reached_hr_stage(candidate, target_stage):
    """Был ли у кандидата указанный этап HR (текущий или в истории)."""
    if candidate.get("hr_stage") == target_stage:
        return True
    if target_stage not in HR_STAGE_ORDER:
        return False
    target_idx = HR_STAGE_ORDER.index(target_stage)
    current = candidate.get("hr_stage", "resume_screening")
    if current in HR_STAGE_ORDER and HR_STAGE_ORDER.index(current) >= target_idx:
        return True
    for entry in candidate.get("hr_stage_history", []):
        if entry.get("stage") == target_stage:
            return True
    return False


def is_visible_in_client_zone(candidate):
    """Кандидат доступен в клиентской зоне после этапа «На оценке у заказчика»."""
    stage = candidate.get("hr_stage", "resume_screening")
    if stage == "archived":
        return False
    if stage == "rejected" or is_rejection_stage(stage):
        return False
    return reached_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE)


# Порядок кандидатов в списке (сверху вниз)
LIST_DISPLAY_STAGE_ORDER = [
    "resume_screening",
    "offer",
    "client_meeting",
    "client_review",
    "test_task",
    "interview_done",
    "interview_scheduled",
    "primary_contact",
    "rejected_hr",
    "rejected_client",
    "rejected_candidate",
    "rejected",
    "archived",
]


def list_stage_sort_key(stage):
    try:
        return LIST_DISPLAY_STAGE_ORDER.index(stage)
    except ValueError:
        return len(LIST_DISPLAY_STAGE_ORDER)


def sort_candidates_for_list(candidates):
    """Сортировка кандидатов для вкладки «Список»."""
    return sorted(
        candidates,
        key=lambda c: (
            list_stage_sort_key(c.get("hr_stage", "resume_screening")),
            c.get("created_at") or "",
        ),
    )


def is_rejection_stage(stage):
    return stage in REJECTION_STAGES


def get_stage_tone(stage):
    """Тон подсветки строки кандидата: rejected, offer, green, yellow или None."""
    if stage in REJECTION_STAGES or stage == "rejected":
        return "rejected"
    if stage == OFFER_STAGE:
        return "offer"
    if stage in GREEN_STAGES:
        return "green"
    if stage in YELLOW_STAGES:
        return "yellow"
    return None


def format_stage_option(stage):
    """Подпись статуса в выпадающем списке."""
    label = HR_STAGES.get(stage, stage)
    if stage == OFFER_STAGE:
        return f"👑 {label}"
    tone = get_stage_tone(stage)
    if tone == "rejected":
        return f"🔴 {label}"
    if tone == "green":
        return f"🟢 {label}"
    if tone == "yellow":
        return f"🟡 {label}"
    return label


def format_stage_title_label(stage):
    """Подпись статуса в заголовке строки кандидата."""
    return format_stage_option(stage)


def stage_for_selectbox(stage):
    """Нормализует этап для выпадающего списка (без устаревшего «Отказ»)."""
    if stage == "rejected":
        return "rejected_client"
    if stage in HR_STAGE_ORDER_UI:
        return stage
    return "resume_screening"

CLIENT_STATUS_LABELS = {
    "new": "Новый",
    "wait": "Ждёт оценки",
    "ready": "Рассматриваем",
    "reject": "Отказ",
    "think": "Надо подумать",
}


def default_candidate_fields():
    return {
        "phone": "",
        "age": "",
        "city": "",
        "metro": "",
        "salary_expected": "",
        "age_location": "",
        "resume_text": "",
        "hr_stage": "resume_screening",
        "hr_stage_history": [],
        "ai_score_source": None,
        "interview_focus_questions": [],
        "interview_questionnaire": [],
        "cold_screening": False,
    }


def migrate_candidate(candidate, default_ignore_flags_fn):
    """Дополняет кандидата недостающими полями. Возвращает True если были изменения."""
    migrated = False
    defaults = default_candidate_fields()

    for key, val in defaults.items():
        if key not in candidate:
            candidate[key] = val if not isinstance(val, list) else []
            migrated = True

    if "task_link" not in candidate:
        candidate["task_link"] = ""
        migrated = True
    if "office_interview_date" not in candidate:
        candidate["office_interview_date"] = ""
        migrated = True
    if "office_interview_time" not in candidate:
        candidate["office_interview_time"] = ""
        migrated = True
    if "interview_schedule_key" not in candidate:
        candidate["interview_schedule_key"] = ""
        migrated = True
    if "interview_reminder_30_sent" not in candidate:
        candidate["interview_reminder_30_sent"] = False
        migrated = True
    if "interview_reminder_10_sent" not in candidate:
        candidate["interview_reminder_10_sent"] = False
        migrated = True
    if "calendar_event_id" not in candidate:
        candidate["calendar_event_id"] = ""
        migrated = True
    if "client_final_verdict" not in candidate:
        candidate["client_final_verdict"] = ""
        migrated = True
    if "ignore_flags" not in candidate or not isinstance(candidate.get("ignore_flags"), dict):
        candidate["ignore_flags"] = default_ignore_flags_fn()
        migrated = True
    else:
        for flag_key, flag_val in default_ignore_flags_fn().items():
            if flag_key not in candidate["ignore_flags"]:
                candidate["ignore_flags"][flag_key] = flag_val
                migrated = True
    if "profile_checked" not in candidate:
        candidate["profile_checked"] = False
        migrated = True
    if "transcript" not in candidate:
        candidate["transcript"] = ""
        migrated = True
    if "ai_strengths" not in candidate:
        candidate["ai_strengths"] = []
        migrated = True
    if "ai_weaknesses" not in candidate:
        candidate["ai_weaknesses"] = []
        migrated = True
    if "ai_profile_requirements_met" not in candidate:
        candidate["ai_profile_requirements_met"] = {}
        migrated = True
    if "ai_flags_applied" not in candidate:
        candidate["ai_flags_applied"] = []
        migrated = True
    if candidate.get("hr_stage") == "rejected":
        candidate["hr_stage"] = "rejected_client"
        migrated = True
    if candidate.get("hr_stage") not in HR_STAGES:
        candidate["hr_stage"] = "resume_screening"
        migrated = True
    if not isinstance(candidate.get("hr_stage_history"), list):
        candidate["hr_stage_history"] = []
        migrated = True
    if not isinstance(candidate.get("interview_focus_questions"), list):
        candidate["interview_focus_questions"] = []
        migrated = True
    if not isinstance(candidate.get("interview_questionnaire"), list):
        candidate["interview_questionnaire"] = []
        migrated = True
    if not candidate.get("id"):
        candidate["id"] = str(uuid.uuid4())
        migrated = True

    return migrated


def set_hr_stage(candidate, new_stage, note=""):
    if new_stage not in HR_STAGES:
        return
    old = candidate.get("hr_stage")
    if old == new_stage:
        return
    candidate["hr_stage"] = new_stage
    history = candidate.setdefault("hr_stage_history", [])
    history.append({
        "stage": new_stage,
        "at": datetime.now().isoformat(),
        "note": note or "",
    })
    if new_stage == CLIENT_ZONE_ENTRY_STAGE and old != CLIENT_ZONE_ENTRY_STAGE:
        candidate["client_status"] = "wait"
        candidate["status_updated_at"] = datetime.now().isoformat()


def sync_hr_stage_from_client_status(candidate):
    """Предлагает синхронизацию hr_stage при изменении client_status."""
    status = candidate.get("client_status", "wait")
    if status == "ready" and candidate.get("hr_stage") == "client_review":
        return "client_meeting"
    if status == "reject":
        return "rejected_client"
    return None


def stage_counts(candidates):
    counts = {k: 0 for k in HR_STAGES}
    for c in candidates:
        stage = c.get("hr_stage", "resume_screening")
        if stage in counts:
            counts[stage] += 1
        else:
            counts["resume_screening"] += 1
    return counts
