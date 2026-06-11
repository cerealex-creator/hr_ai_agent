"""Общая логика действий заказчика (веб-зона и Telegram)."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from vacancy_store import (
    STATUS_LABEL_TO_KEY,
    get_status_meta,
    load_vacancies,
    migrate_candidate,
    resolve_status_on_save,
    save_vacancies,
)
from models import (
    OFFER_STAGE,
    STARTED_WORK_STAGE,
    is_visible_in_client_zone,
    set_hr_stage,
    sync_hr_stage_from_client_status,
)
from telegram_notify import normalize_chat_id


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

    norm_chat = normalize_chat_id(chat_id)
    posts = candidate.get("telegram_posts", [])
    filtered = [
        p for p in posts
        if not (
            p.get("message_id") == message_id
            and normalize_chat_id(p.get("chat_id")) == norm_chat
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
    norm_chat = normalize_chat_id(chat_id)
    for vacancy in data.get("vacancies", []):
        for cand in vacancy.get("candidates", []):
            for post in cand.get("telegram_posts", []):
                post_chat = normalize_chat_id(post.get("chat_id"))
                if post.get("message_id") == message_id and post_chat == norm_chat:
                    return vacancy, cand, data
    return None, None, data


def vacancy_chat_matches(vacancy, chat_id):
    return normalize_chat_id(vacancy.get("chat_id")) == normalize_chat_id(chat_id)


def _comment_timezone():
    return ZoneInfo(os.getenv("TELEGRAM_REMINDER_TZ", "Europe/Moscow"))


def format_telegram_comment_entry(text, at=None):
    """Комментарий из Telegram с датой и временем для клиентской зоны."""
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
        if status_key != candidate.get("client_status"):
            candidate["status_updated_at"] = datetime.now().isoformat()
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
                set_hr_stage(candidate, suggested, f"статус «Рассматриваем» ({note})")
        elif status_key == "think":
            suggested = sync_hr_stage_from_client_status(candidate)
            if suggested:
                set_hr_stage(candidate, suggested, f"статус «Подумать» ({note})")

    if comment is not None:
        text = comment.strip()
        if actor == "telegram" and text:
            text = format_telegram_comment_entry(text, comment_at)
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
    return saved_status


def apply_and_save_client_action(
    candidate_id,
    *,
    chat_id=None,
    status_key=None,
    comment=None,
    append_comment=False,
    actor="telegram",
    actor_note="",
    comment_at=None,
):
    """Изменение статуса/комментария из Telegram с записью в JSON."""
    if len(str(candidate_id)) <= 8:
        vacancy, candidate, data = find_candidate_by_tg_callback_id(candidate_id)
    else:
        vacancy, candidate, data = find_candidate_by_id(candidate_id)
    if not vacancy or not candidate:
        return False, "Кандидат не найден", None, None

    if chat_id is not None and not vacancy_chat_matches(vacancy, chat_id):
        return False, "Этот чат не привязан к вакансии кандидата", None, None

    if not is_visible_in_client_zone(candidate):
        return False, "Кандидат ещё не на этапе оценки заказчика", None, None

    apply_client_update(
        candidate,
        status_key=status_key,
        comment=comment,
        append_comment=append_comment,
        actor=actor,
        actor_note=actor_note,
        comment_at=comment_at,
    )
    save_vacancies(data)
    meta = get_status_meta(candidate.get("client_status", "wait"))
    name = candidate.get("name", "Кандидат")
    if status_key:
        msg = f"✅ {name}: {meta['icon']} {meta['label']}"
    else:
        msg = f"💬 Комментарий к {name} сохранён"
    return True, msg, candidate, vacancy
