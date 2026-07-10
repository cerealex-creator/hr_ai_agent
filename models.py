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
    "client_pause": "Пауза",
    "client_meeting": "Встреча с заказчиком",
    "offer": "Оффер",
    "internship": "Выход на стажировку",
    "started_work": "Вышел на работу",
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
    "client_pause",
})

OFFER_STAGE = "offer"
INTERNSHIP_STAGE = "internship"
STARTED_WORK_STAGE = "started_work"
CLIENT_ZONE_ENTRY_STAGE = "client_review"
CLIENT_PAUSE_STAGE = "client_pause"

HR_STAGE_TO_CLIENT_STATUS = {
    "client_meeting": "ready",
    CLIENT_PAUSE_STAGE: "think",
    OFFER_STAGE: "offer",
    STARTED_WORK_STAGE: "started",
    "rejected_client": "reject",
}

CLIENT_STATUS_TO_HR_STAGE = {
    "ready": "client_meeting",
    "think": CLIENT_PAUSE_STAGE,
    "reject": "rejected_client",
    "offer": OFFER_STAGE,
    "started": STARTED_WORK_STAGE,
}


def received_hr_stage(candidate, target_stage):
    """Кандидат получал этот HR-этап (запись в hr_stage_history или текущий статус)."""
    if candidate.get("hr_stage") == target_stage:
        return True
    return any(
        entry.get("stage") == target_stage
        for entry in (candidate.get("hr_stage_history") or [])
    )


def reached_hr_stage(candidate, target_stage):
    """Был ли у кандидата указанный этап HR (текущий, в истории или пройден по воронке)."""
    if candidate.get("hr_stage") == target_stage:
        return True
    for entry in candidate.get("hr_stage_history", []):
        if entry.get("stage") == target_stage:
            return True
    if target_stage not in HR_STAGE_ORDER:
        return False
    current = candidate.get("hr_stage", "resume_screening")
    if is_rejection_stage(current) or current in ("rejected", "archived"):
        return False
    if current not in HR_STAGE_ORDER:
        return False
    return HR_STAGE_ORDER.index(current) >= HR_STAGE_ORDER.index(target_stage)


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
    "started_work",
    "internship",
    "offer",
    "client_meeting",
    "client_review",
    "client_pause",
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
    if stage in (OFFER_STAGE, INTERNSHIP_STAGE, STARTED_WORK_STAGE):
        return "offer"
    if stage in GREEN_STAGES:
        return "green"
    if stage in YELLOW_STAGES:
        return "yellow"
    return None


def format_stage_option(stage):
    """Подпись статуса в выпадающем списке."""
    label = HR_STAGES.get(stage, stage)
    if stage == STARTED_WORK_STAGE:
        return f"👑 {label}"
    if stage == INTERNSHIP_STAGE:
        return f"🎓 {label}"
    if stage == OFFER_STAGE:
        return f"🟢 {label}"
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
    "ready": "Встреча",
    "reject": "Отказ",
    "think": "Подумать",
    "offer": "Оффер",
    "started": "Вышел на работу",
}

CLIENT_REVIEW_STATUSES = frozenset({"wait", "ready", "think", "offer"})


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
    if "extra_materials" not in candidate or not isinstance(
        candidate.get("extra_materials"), list
    ):
        candidate["extra_materials"] = []
        migrated = True
    if "hh_resume_link" not in candidate:
        candidate["hh_resume_link"] = ""
        migrated = True
    if "portfolio_link" not in candidate:
        candidate["portfolio_link"] = ""
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
    if "interview_reminder_60_sent" not in candidate:
        candidate["interview_reminder_60_sent"] = False
        migrated = True
    if "feedback_reminder_last_sent_at" not in candidate:
        candidate["feedback_reminder_last_sent_at"] = ""
        migrated = True
    if "think_long_reminder_sent" not in candidate:
        candidate["think_long_reminder_sent"] = False
        migrated = True
    if "calendar_event_id" not in candidate:
        candidate["calendar_event_id"] = ""
        migrated = True
    if "meeting_hr_confirmed" not in candidate:
        candidate["meeting_hr_confirmed"] = False
        migrated = True
    if "meeting_hr_confirmation_post" not in candidate:
        candidate["meeting_hr_confirmation_post"] = None
        migrated = True
    if "interview_attendance_status" not in candidate:
        candidate["interview_attendance_status"] = ""
        migrated = True
    if "interview_attendance_morning_date" not in candidate:
        candidate["interview_attendance_morning_date"] = ""
        migrated = True
    if "interview_attendance_morning_last_sent_at" not in candidate:
        candidate["interview_attendance_morning_last_sent_at"] = ""
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
    else:
        raw = candidate.get("interview_questionnaire") or []
        needs_qids = any(
            isinstance(q, str) or (isinstance(q, dict) and not (q.get("_qid") or "").strip())
            for q in raw
        )
        if needs_qids and raw:
            from resume_ai import normalize_questionnaire_list

            candidate["interview_questionnaire"] = normalize_questionnaire_list(raw)
            migrated = True
    if not candidate.get("id"):
        candidate["id"] = str(uuid.uuid4())
        migrated = True
    if not isinstance(candidate.get("client_status_history"), list):
        candidate["client_status_history"] = []
        migrated = True

    return migrated


def record_client_status_change(candidate, new_status, note=""):
    """Фиксирует смену client_status для статистики и истории."""
    old = candidate.get("client_status")
    if old == new_status:
        return
    candidate["client_status"] = new_status
    candidate["status_updated_at"] = datetime.now().isoformat()
    history = candidate.setdefault("client_status_history", [])
    history.append({
        "status": new_status,
        "at": datetime.now().isoformat(),
        "note": note or "",
    })


def reached_client_status(candidate, target_status):
    """Был ли у кандидата указанный статус заказчика (текущий или в истории)."""
    if candidate.get("client_status") == target_status:
        return True
    for entry in candidate.get("client_status_history") or []:
        if entry.get("status") == target_status:
            return True
    return False


def reached_client_interview_invite(candidate):
    """
    Одобрены заказчиком: приглашение на встречу («Встреча») или сразу «Оффер».
    Не путать с HR-этапом «Встреча с заказчиком».
    """
    if reached_client_status(candidate, "ready"):
        return True
    if reached_client_status(candidate, "offer"):
        return True
    for entry in candidate.get("hr_stage_history") or []:
        note = entry.get("note") or ""
        if "статус «Встреча»" in note or "статус «Оффер»" in note:
            return True
    return False


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
    elif reached_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE):
        client_status = HR_STAGE_TO_CLIENT_STATUS.get(new_stage)
        if client_status and candidate.get("client_status") != client_status:
            candidate["client_status"] = client_status
            candidate["status_updated_at"] = datetime.now().isoformat()


def sync_hr_stage_from_client_status(candidate):
    """Предлагает синхронизацию hr_stage при изменении client_status."""
    status = candidate.get("client_status", "wait")
    mapped = CLIENT_STATUS_TO_HR_STAGE.get(status)
    if mapped and candidate.get("hr_stage") != mapped:
        return mapped
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
