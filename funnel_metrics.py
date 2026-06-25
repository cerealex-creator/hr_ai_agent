"""Метрики воронки по истории смен HR-этапов."""

from models import (
    CLIENT_ZONE_ENTRY_STAGE,
    INTERNSHIP_STAGE,
    OFFER_STAGE,
    STARTED_WORK_STAGE,
    is_rejection_stage,
    reached_client_interview_invite,
    received_hr_stage,
)

PRIMARY_CONTACT = "primary_contact"
RESUME_SCREENING = "resume_screening"
INTERVIEW_SCHEDULED = "interview_scheduled"
INTERVIEW_DONE = "interview_done"
TEST_TASK = "test_task"
REJECTED_HR = "rejected_hr"
REJECTED_CLIENT = "rejected_client"
REJECTED_CANDIDATE = "rejected_candidate"

_REJECTION_STAGES = frozenset({
    REJECTED_HR,
    REJECTED_CLIENT,
    REJECTED_CANDIDATE,
    "rejected",
})


def get_stage_sequence(candidate):
    """Хронология этапов: hr_stage_history + текущий hr_stage."""
    seq = []
    for entry in candidate.get("hr_stage_history") or []:
        stage = entry.get("stage")
        if stage:
            seq.append(stage)
    current = candidate.get("hr_stage")
    if current and (not seq or seq[-1] != current):
        seq.append(current)
    elif current and not seq:
        seq.append(current)
    return seq


def _went_screening_to_reject_only(candidate):
    """Отсев резюме → сразу отказ, без контакта и без собеседования."""
    seq = get_stage_sequence(candidate)
    if PRIMARY_CONTACT in seq or INTERVIEW_SCHEDULED in seq:
        return False
    if RESUME_SCREENING not in seq:
        return False
    after = seq[seq.index(RESUME_SCREENING) + 1 :]
    return bool(after) and all(
        is_rejection_stage(s) or s in _REJECTION_STAGES for s in after
    )


def had_primary_contact_communication(candidate):
    """
    Первый контакт (сообщение):
    — явный этап «Первичный контакт» в истории;
    — или «Отсев резюме» → сразу «Назначено собеседование» (звонок до внесения в приложение);
    — или любой «Назначено собеседование» (иначе о собеседовании не договориться).
    Исключение: отсев → сразу отказ без контакта.
    """
    if _went_screening_to_reject_only(candidate):
        return False
    if received_hr_stage(candidate, PRIMARY_CONTACT):
        return True
    seq = get_stage_sequence(candidate)
    for i in range(len(seq) - 1):
        if seq[i] == RESUME_SCREENING and seq[i + 1] == INTERVIEW_SCHEDULED:
            return True
    if received_hr_stage(candidate, INTERVIEW_SCHEDULED):
        return True
    return False


def no_contact_lost_funnel(candidate, vacancy=None):
    """
    Не общался / пропали со связи:
    в истории был «Первичный контакт» → затем отказ,
    либо на момент закрытия вакансии остался на «Первичном контакте».
    """
    seq = get_stage_sequence(candidate)
    for i in range(len(seq) - 1):
        if seq[i] == PRIMARY_CONTACT and (
            is_rejection_stage(seq[i + 1]) or seq[i + 1] in _REJECTION_STAGES
        ):
            return True
    if vacancy and not vacancy.get("active", True):
        if candidate.get("hr_stage") == PRIMARY_CONTACT:
            return True
    return False


def passed_primary_interview_funnel(candidate):
    """
    Прошли первичное собеседование — по истории:
    «Назначено собеседование» → «Собеседование проведено» или «Тестовое задание»,
    либо когда-либо получали «На оценке у заказчика».
    """
    if received_hr_stage(candidate, CLIENT_ZONE_ENTRY_STAGE):
        return True
    seq = get_stage_sequence(candidate)
    for i in range(len(seq) - 1):
        if seq[i] == INTERVIEW_SCHEDULED and seq[i + 1] in (INTERVIEW_DONE, TEST_TASK):
            return True
    return False


def _count_c(entries, predicate):
    return sum(1 for candidate, _vacancy in entries if predicate(candidate))


def _count_cv(entries, predicate):
    return sum(1 for candidate, vacancy in entries if predicate(candidate, vacancy))


def compute_funnel_metrics(entries):
    """
    entries: список пар (candidate, vacancy).
    Каждый показатель — сколько кандидатов **получали** соответствующий статус
    (по hr_stage_history). Показатели не подгоняются друг под друга.
    """
    total = len(entries)
    primary_contact = _count_c(entries, had_primary_contact_communication)
    no_contact = _count_cv(entries, no_contact_lost_funnel)
    client_review = _count_c(
        entries, lambda c: received_hr_stage(c, CLIENT_ZONE_ENTRY_STAGE)
    )
    passed_interview = _count_c(entries, passed_primary_interview_funnel)
    test_task = _count_c(entries, lambda c: received_hr_stage(c, TEST_TASK))
    test_task = min(test_task, client_review) if client_review else test_task
    client_approved = _count_c(entries, reached_client_interview_invite)

    return {
        "total_selected": total,
        "primary_contact": primary_contact,
        "no_contact": no_contact,
        "interview_done": passed_interview,
        "client_review": client_review,
        "client_approved": client_approved,
        "test_task": test_task,
        "internship": _count_c(entries, lambda c: received_hr_stage(c, INTERNSHIP_STAGE)),
        "offer": _count_c(entries, lambda c: received_hr_stage(c, OFFER_STAGE)),
        "started_work": _count_c(
            entries, lambda c: received_hr_stage(c, STARTED_WORK_STAGE)
        ),
        "rejected_hr": _count_c(entries, lambda c: received_hr_stage(c, REJECTED_HR)),
        "rejected_client": _count_c(
            entries, lambda c: received_hr_stage(c, REJECTED_CLIENT)
        ),
        "rejected_candidate": _count_c(
            entries, lambda c: received_hr_stage(c, REJECTED_CANDIDATE)
        ),
    }


def candidate_vacancy_entries(candidates, vacancy=None):
    return [(c, vacancy) for c in candidates]


def candidates_from_vacancies(vacancies):
    entries = []
    for vacancy in vacancies:
        for candidate in vacancy.get("candidates", []):
            entries.append((candidate, vacancy))
    return entries
