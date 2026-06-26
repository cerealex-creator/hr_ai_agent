"""Исключение тестовых вакансий из статистики продуктивности."""


def migrate_vacancy_is_test(vacancy):
    if "is_test" not in vacancy:
        vacancy["is_test"] = False
        return True
    return False


def is_test_vacancy(vacancy):
    return bool(vacancy.get("is_test"))


def filter_vacancies_for_stats(vacancies):
    return [v for v in vacancies if not is_test_vacancy(v)]
