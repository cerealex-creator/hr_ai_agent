"""Общая логика действий заказчика (веб-зона и Telegram)."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram_chat_id import resolve_vacancy_chat_id
from vacancy_store import (
    STATUS_LABEL_TO_KEY,
    get_status_meta,
    load_vacancies,
    migrate_candidate,
    resolve_status_on_save,
    save_vacancies,
)
from models import (
    CLIENT_STATUS_TO_HR_STAGE,
    CLIENT_ZONE_ENTRY_STAGE,
    OFFER_STAGE,
    STARTED_WORK_STAGE,
    is_visible_in_client_zone,
    set_hr_stage,
    sync_hr_stage_from_client_status,
)
from telegram_notify import chat_ids_equal, normalize_chat_id

STATUSES_THAT_CANCEL_MEETING = frozenset({"reject", "think"})

HR_MEETING_CONFIRM_USERNAME = (
    os.getenv("TELEGRAM_HR_CONFIRM_USERNAME", "cerealeks").strip().lower().lstrip("@")
)


def has_client_meeting_scheduled(candidate):
    from interview_schedule import validate_interview_schedule

    return not validate_interview_schedule(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    )


def is_client_confirmed_group_meeting(candidate):
    """Встреча с заказчиком, подтверждённая HR — уведомления в общий чат."""
    return bool(candidate.get("meeting_hr_confirmed")) and has_client_meeting_scheduled(
        candidate
    )


def clear_client_meeting(candidate):
    """Сбрасывает дату/время/формат клиентской встречи. Возвращает True, если встреча была."""
    if not has_client_meeting_scheduled(candidate):
        return False
    from interview_schedule import reset_reminders_if_schedule_changed

    reset_reminders_if_schedule_changed(candidate, "", "")
    candidate["office_interview_date"] = ""
    candidate["office_interview_time"] = ""
    candidate["remote_interview"] = False
    candidate["office_interview"] = False
    candidate["meeting_hr_confirmed"] = False
    from interview_attendance import reset_interview_attendance

    reset_interview_attendance(candidate)
    return True


def can_confirm_hr_meeting(user):
    username = ((user.username if user else None) or "").strip().lower()
    return username == HR_MEETING_CONFIRM_USERNAME


def _meeting_format_label(candidate):
    parts = []
    if candidate.get("remote_interview"):
        parts.append("удалённо")
    if candidate.get("office_interview"):
        parts.append("офис")
    return ", ".join(parts)


def build_meeting_confirmation_html(candidate, *, confirmed=False, confirmer_label=None):
    from interview_schedule import format_interview_display
    from telegram_notify import _esc

    when = format_interview_display(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    )
    name = _esc(candidate.get("name", "кандидатом"))
    fmt = _meeting_format_label(candidate)
    fmt_part = f" ({fmt})" if fmt else ""
    if confirmed:
        who = _esc(confirmer_label or f"@{HR_MEETING_CONFIRM_USERNAME}")
        return (
            f"✅ Встреча с кандидатом <b>{name}</b> на <b>{when}</b>{fmt_part} "
            f"подтверждена HR ({who})."
        )
    return (
        f"📅 Предлагается встреча с кандидатом <b>{name}</b> "
        f"на <b>{when}</b>{fmt_part}.\n"
        f"Требуется подтверждение HR."
    )


def build_meeting_confirmation_keyboard(candidate):
    from vacancy_store import migrate_candidate

    migrate_candidate(candidate)
    callback_id = candidate.get("tg_callback_id") or candidate.get("id")
    return {
        "inline_keyboard": [[
            {"text": "✅ Подтвердить встречу", "callback_data": f"mcf:{callback_id}"},
        ]]
    }


def maybe_request_hr_meeting_confirmation(candidate, vacancy):
    """Отправляет в чат вакансии запрос на подтверждение встречи HR."""
    from interview_schedule import validate_interview_schedule
    from telegram_notify import send_telegram_html
    from vacancy_store import migrate_candidate

    migrate_candidate(candidate)
    if validate_interview_schedule(
        candidate.get("office_interview_date"),
        candidate.get("office_interview_time"),
    ):
        return False
    chat_id = resolve_vacancy_chat_id(vacancy)
    if not chat_id:
        return False

    text = build_meeting_confirmation_html(candidate)
    keyboard = build_meeting_confirmation_keyboard(candidate)
    ok, _msg, message_id = send_telegram_html(chat_id, text, reply_markup=keyboard)
    if ok and message_id:
        candidate["meeting_hr_confirmed"] = False
        candidate["meeting_hr_confirmation_post"] = {
            "chat_id": normalize_chat_id(chat_id),
            "message_id": message_id,
        }
        return True
    return False


def find_candidate_by_id(candidate_id):
    data = load_vacancies()
    for vacancy in data.get("vacancies", []):
        for cand in vacancy.get("candidates", []):
            if cand.get("id") == candidate_id:
                return vacancy, cand, data
    return None, None, data


def remove_telegram_post(candidate_id, chat_id, message_id):
    """Удаляет запись о сообщении Telegram из карточки кандидата."""
    if len(str(candidate_id)) <= 8:
        vacancy, candidate, data = find_candidate_by_tg_callback_id(candidate_id)
    else:
        vacancy, candidate, data = find_candidate_by_id(candidate_id)
    if not candidate:
        return False

    posts = candidate.get("telegram_posts", [])
    filtered = [
        p for p in posts
        if not (
            p.get("message_id") == message_id
            and chat_ids_equal(p.get("chat_id"), chat_id)
        )
    ]
    if len(filtered) == len(posts):
        return False
    candidate["telegram_posts"] = filtered
    save_vacancies(data)
    return True


def find_candidate_by_tg_callback_id(callback_id):
    data = load_vacancies()
    for vacancy in data.get("vacancies", []):
        for cand in vacancy.get("candidates", []):
            migrate_candidate(cand)
            if cand.get("tg_callback_id") == callback_id:
                return vacancy, cand, data
    return None, None, data


def find_candidate_by_telegram_message(chat_id, message_id):
    data = load_vacancies()
    for vacancy in data.get("vacancies", []):
        for cand in vacancy.get("candidates", []):
            for post in cand.get("telegram_posts", []):
                if post.get("message_id") == message_id and chat_ids_equal(
                    post.get("chat_id"), chat_id
                ):
                    return vacancy, cand, data
    return None, None, data


def _department_id_for_chat(chat_id):
    from vacancy_store import load_chats

    for chat in load_chats():
        if chat_ids_equal(chat.get("id"), chat_id):
            return chat.get("department_id")
    return None


def _vacancy_has_posts_in_chat(vacancy, chat_id):
    vac_id = vacancy.get("id")
    for cand in vacancy.get("candidates", []):
        migrate_candidate(cand)
        for post in cand.get("telegram_posts", []):
            if not chat_ids_equal(post.get("chat_id"), chat_id):
                continue
            if post_belongs_to_vacancy(post, vac_id):
                return True
    return False


def vacancy_chat_matches(vacancy, chat_id):
    if chat_ids_equal(resolve_vacancy_chat_id(vacancy, chat_id), chat_id):
        return True
    return _vacancy_has_posts_in_chat(vacancy, chat_id)


def find_vacancy_by_id(vacancy_id):
    for vacancy in load_vacancies().get("vacancies", []):
        if vacancy.get("id") == vacancy_id:
            return vacancy
    return None


def find_vacancies_by_chat_id(chat_id, *, only_active=True):
    """Вакансии чата: актуальный chat_id из chats_db или карточки в этом чате."""
    vacancies = load_vacancies().get("vacancies", [])
    seen = set()
    result = []

    def _take(vacancy):
        vid = vacancy.get("id")
        if vid in seen:
            return
        if only_active and not vacancy.get("active", True):
            return
        seen.add(vid)
        result.append(vacancy)

    for vacancy in vacancies:
        if chat_ids_equal(resolve_vacancy_chat_id(vacancy, chat_id), chat_id):
            _take(vacancy)
        elif _vacancy_has_posts_in_chat(vacancy, chat_id):
            _take(vacancy)

    return result


def post_belongs_to_vacancy(post, vacancy_id):
    """Карточка в telegram_posts относится к вакансии (или legacy без метки)."""
    post_vid = post.get("vacancy_id")
    if post_vid is None:
        return True
    return post_vid == vacancy_id


def post_kind(post, default="primary"):
    """kind в telegram_posts: None и отсутствие ключа — legacy primary."""
    return post.get("kind") or default


def get_primary_telegram_post(candidate, chat_id, *, kind="primary", vacancy_id=None):
    """Последнее primary-сообщение кандидата в указанном чате (опционально по vacancy_id)."""
    posts = [
        p
        for p in candidate.get("telegram_posts", [])
        if chat_ids_equal(p.get("chat_id"), chat_id)
        and post_kind(p) == kind
        and (vacancy_id is None or post_belongs_to_vacancy(p, vacancy_id))
    ]
    if not posts:
        return None
    return max(posts, key=lambda p: p.get("sent_at") or "")


def has_telegram_post_in_chat(candidate, chat_id):
    for post in candidate.get("telegram_posts", []):
        if chat_ids_equal(post.get("chat_id"), chat_id):
            return True
    return False


def ensure_client_zone_for_telegram(candidate, chat_id=None, note="карточка в Telegram-чате"):
    """Разрешает действия в чате: этап «На оценке у заказчика» + привязка к сообщению."""
    migrate_candidate(candidate)
    if is_visible_in_client_zone(candidate):
        return True
    if chat_id is not None and has_telegram_post_in_chat(candidate, chat_id):
        set_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE, note)
        return True
    return False


def _comment_timezone():
    return ZoneInfo(os.getenv("TELEGRAM_REMINDER_TZ", "Europe/Moscow"))


def _format_comment_author(author_note):
    note = (author_note or "").strip()
    if not note:
        return ""
    if note.isdigit():
        return f"id:{note}"
    if note.startswith("@"):
        return note
    return note


def format_telegram_comment_entry(text, at=None, author=None):
    """Комментарий из Telegram с датой, временем и автором для клиентской зоны."""
    clean = (text or "").strip()
    if not clean:
        return ""
    tz = _comment_timezone()
    if at is None:
        moment = datetime.now(tz)
    elif at.tzinfo is None:
        moment = at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    else:
        moment = at.astimezone(tz)
    stamp = moment.strftime("%d.%m.%Y, %H:%M")
    author_label = _format_comment_author(author)
    if author_label:
        return f"[{stamp}, {author_label}] {clean}"
    return f"[{stamp}] {clean}"


def apply_client_update(
    candidate,
    *,
    status_key=None,
    status_label=None,
    comment=None,
    append_comment=False,
    final_verdict=None,
    office_interview_date=None,
    office_interview_time=None,
    remote_interview=None,
    office_interview=None,
    actor="web",
    actor_note="",
    comment_at=None,
):
    """Применяет изменения заказчика к кандидату (без сохранения в файл)."""
    migrate_candidate(candidate)
    note = f"{actor}: {actor_note}" if actor_note else actor

    if status_label:
        status_key = STATUS_LABEL_TO_KEY[status_label]

    if status_key is not None:
        old_status = candidate.get("client_status")
        if status_key != old_status:
            from models import record_client_status_change

            record_client_status_change(
                candidate,
                status_key,
                note=f"{actor}: {actor_note}" if actor_note else actor,
            )
            if status_key == "think" and old_status != "think":
                candidate["think_long_reminder_sent"] = False
            if old_status == "wait" and status_key != "wait":
                candidate["feedback_reminder_last_sent_at"] = ""
        else:
            candidate["client_status"] = status_key

        if status_key == "reject":
            set_hr_stage(candidate, "rejected_client", f"отказ в клиентской зоне ({note})")
        elif status_key == "offer":
            set_hr_stage(candidate, OFFER_STAGE, f"оффер в клиентской зоне ({note})")
        elif status_key == "started":
            set_hr_stage(candidate, STARTED_WORK_STAGE, f"вышел на работу ({note})")
        elif status_key == "ready":
            suggested = sync_hr_stage_from_client_status(candidate)
            if suggested:
                set_hr_stage(candidate, suggested, f"статус «Встреча» ({note})")
        elif status_key == "think":
            suggested = sync_hr_stage_from_client_status(candidate)
            if suggested:
                set_hr_stage(candidate, suggested, f"статус «Подумать» ({note})")

        if status_key in STATUSES_THAT_CANCEL_MEETING:
            clear_client_meeting(candidate)

    if comment is not None:
        text = comment.strip()
        if actor == "telegram" and text:
            text = format_telegram_comment_entry(text, comment_at, author=actor_note)
        if append_comment and (candidate.get("client_comment") or "").strip():
            candidate["client_comment"] = f"{candidate['client_comment'].strip()}\n{text}"
        else:
            candidate["client_comment"] = text

    if final_verdict is not None:
        candidate["client_final_verdict"] = final_verdict

    if office_interview_date is not None:
        candidate["office_interview_date"] = office_interview_date
    if office_interview_time is not None:
        candidate["office_interview_time"] = office_interview_time
    if remote_interview is not None:
        candidate["remote_interview"] = remote_interview
    if office_interview is not None:
        candidate["office_interview"] = office_interview

    return candidate


def apply_client_update_from_web_form(
    candidate,
    *,
    new_status_label,
    new_comment,
    final_verdict,
    show_interview_fields,
    new_date,
    new_time,
    remote_interview,
    office_interview,
    vacancy=None,
):
    """Сохранение из веб-клиентской зоны (эквивалент кнопки «Сохранить»)."""
    saved_status = resolve_status_on_save(candidate, new_status_label)
    apply_client_update(
        candidate,
        status_key=saved_status,
        comment=new_comment,
        final_verdict=final_verdict,
        actor="web",
        actor_note="клиентская зона",
    )
    if show_interview_fields:
        apply_client_update(
            candidate,
            office_interview_date=new_date.strftime("%Y-%m-%d") if new_date else "",
            office_interview_time=new_time,
            remote_interview=remote_interview,
            office_interview=office_interview,
            actor="web",
            actor_note="собеседование",
        )
        if vacancy and new_date and new_time:
            maybe_request_hr_meeting_confirmation(candidate, vacancy)
    return saved_status


def apply_and_save_client_action(
    candidate_id,
    *,
    chat_id=None,
    status_key=None,
    comment=None,
    append_comment=False,
    office_interview_date=None,
    office_interview_time=None,
    remote_interview=None,
    office_interview=None,
    actor="telegram",
    actor_note="",
    comment_at=None,
):
    """Изменение статуса/комментария/собеседования из Telegram с записью в JSON."""
    if len(str(candidate_id)) <= 8:
        vacancy, candidate, data = find_candidate_by_tg_callback_id(candidate_id)
    else:
        vacancy, candidate, data = find_candidate_by_id(candidate_id)
    if not vacancy or not candidate:
        return False, "Кандидат не найден", None, None

    if chat_id is not None and not vacancy_chat_matches(vacancy, chat_id):
        return False, "Этот чат не привязан к вакансии кандидата", None, None

    if not ensure_client_zone_for_telegram(candidate, chat_id):
        return False, "Кандидат ещё не на этапе оценки заказчика", None, None

    apply_client_update(
        candidate,
        status_key=status_key,
        comment=comment,
        append_comment=append_comment,
        office_interview_date=office_interview_date,
        office_interview_time=office_interview_time,
        remote_interview=remote_interview,
        office_interview=office_interview,
        actor=actor,
        actor_note=actor_note,
        comment_at=comment_at,
    )
    if office_interview_date is not None or office_interview_time is not None:
        from interview_schedule import reset_reminders_if_schedule_changed, validate_interview_schedule

        reset_reminders_if_schedule_changed(
            candidate,
            candidate.get("office_interview_date"),
            candidate.get("office_interview_time"),
        )
        if not validate_interview_schedule(
            candidate.get("office_interview_date"),
            candidate.get("office_interview_time"),
        ) and candidate.get("client_status") != "ready":
            apply_client_update(
                candidate,
                status_key="ready",
                actor=actor,
                actor_note="назначена встреча",
            )
            mapped = CLIENT_STATUS_TO_HR_STAGE.get("ready")
            if mapped and candidate.get("hr_stage") != mapped:
                set_hr_stage(candidate, mapped, "встреча назначена в Telegram")
        if not validate_interview_schedule(
            candidate.get("office_interview_date"),
            candidate.get("office_interview_time"),
        ):
            maybe_request_hr_meeting_confirmation(candidate, vacancy)
    save_vacancies(data)
    meta = get_status_meta(candidate.get("client_status", "wait"))
    name = candidate.get("name", "Кандидат")
    if office_interview_date is not None or office_interview_time is not None:
        from interview_schedule import format_interview_display

        when = format_interview_display(
            candidate.get("office_interview_date"),
            candidate.get("office_interview_time"),
        )
        msg = f"📅 {name}: встреча {when}"
    elif status_key:
        msg = f"✅ {name}: {meta['icon']} {meta['label']}"
    else:
        msg = f"💬 Комментарий к {name} сохранён"
    return True, msg, candidate, vacancy


def apply_and_save_cancel_meeting(
    candidate_id,
    *,
    chat_id=None,
    actor="telegram",
    actor_note="",
):
    """Отмена назначенной клиентской встречи (Telegram и др.)."""
    if len(str(candidate_id)) <= 8:
        vacancy, candidate, data = find_candidate_by_tg_callback_id(candidate_id)
    else:
        vacancy, candidate, data = find_candidate_by_id(candidate_id)
    if not vacancy or not candidate:
        return False, "Кандидат не найден", None, None

    if chat_id is not None and not vacancy_chat_matches(vacancy, chat_id):
        return False, "Этот чат не привязан к вакансии кандидата", None, None

    if not ensure_client_zone_for_telegram(candidate, chat_id):
        return False, "Кандидат ещё не на этапе оценки заказчика", None, None

    if not clear_client_meeting(candidate):
        return False, "Встреча не была назначена", None, None

    save_vacancies(data)
    name = candidate.get("name", "Кандидат")
    return True, f"❌ {name}: встреча отменена", candidate, vacancy


def apply_and_save_confirm_hr_meeting(candidate_id, *, confirmer_label=None):
    if len(str(candidate_id)) <= 8:
        vacancy, candidate, data = find_candidate_by_tg_callback_id(candidate_id)
    else:
        vacancy, candidate, data = find_candidate_by_id(candidate_id)
    if not vacancy or not candidate:
        return False, "Кандидат не найден", None, None
    if not has_client_meeting_scheduled(candidate):
        return False, "Встреча не назначена", None, None
    if candidate.get("meeting_hr_confirmed"):
        return False, "Встреча уже подтверждена", candidate, vacancy

    candidate["meeting_hr_confirmed"] = True
    save_vacancies(data)
    return True, "Встреча подтверждена", candidate, vacancy
