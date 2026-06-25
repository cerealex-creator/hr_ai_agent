"""Правила закрытия вакансии."""

from models import INTERNSHIP_STAGE, STARTED_WORK_STAGE, reached_hr_stage

CLOSE_REASON_SUCCESS = "success"
CLOSE_REASON_CLIENT = "client_cancelled"


def migrate_vacancy_close(vacancy):
    if "close_reason" not in vacancy:
        vacancy["close_reason"] = None
        return True
    return False


def vacancy_has_successful_hire(vacancy):
    """Есть кандидат «Вышел на работу» или «Выход на стажировку»."""
    for cand in vacancy.get("candidates", []):
        if reached_hr_stage(cand, STARTED_WORK_STAGE) or reached_hr_stage(
            cand, INTERNSHIP_STAGE
        ):
            return True
    return False


def can_close_vacancy_normally(vacancy):
    return vacancy_has_successful_hire(vacancy)


def close_reason_label(reason):
    if reason == CLOSE_REASON_CLIENT:
        return "Закрыта заказчиком (поиск не продолжается)"
    if reason == CLOSE_REASON_SUCCESS:
        return "Закрыта после выхода кандидата на работу/стажировку"
    return ""
