"""Интеграция с Google Calendar для собеседований."""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
DEFAULT_CREDENTIALS_PATH = "data/google_calendar_credentials.json"
DEFAULT_TOKEN_PATH = "data/google_calendar_token.json"


def get_credentials_path():
    return os.getenv("GOOGLE_CALENDAR_CREDENTIALS", DEFAULT_CREDENTIALS_PATH)


def get_token_path():
    return os.getenv("GOOGLE_CALENDAR_TOKEN", DEFAULT_TOKEN_PATH)


def get_calendar_id():
    return os.getenv("GOOGLE_CALENDAR_ID", "primary")


def get_event_duration_minutes():
    try:
        return int(os.getenv("GOOGLE_CALENDAR_EVENT_MINUTES", "45"))
    except ValueError:
        return 45


def credentials_file_exists():
    return os.path.isfile(get_credentials_path())


def token_exists():
    return os.path.isfile(get_token_path())


def is_calendar_ready():
    return credentials_file_exists() and token_exists()


def get_calendar_status():
    if not credentials_file_exists():
        return "not_configured", "Нет файла credentials (data/google_calendar_credentials.json)"
    if not token_exists():
        return "needs_auth", "Credentials есть — нужна авторизация (кнопка ниже)"
    return "ready", "Google Calendar подключён"


def _get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = get_token_path()
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds)
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(get_credentials_path(), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    _save_credentials(creds)
    return creds


def _save_credentials(creds):
    os.makedirs(os.path.dirname(get_token_path()) or ".", exist_ok=True)
    with open(get_token_path(), "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def get_calendar_service():
    if not is_calendar_ready():
        return None, "Google Calendar не настроен"
    try:
        from googleapiclient.discovery import build

        creds = _get_credentials()
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return service, None
    except Exception as e:
        return None, str(e)


def run_oauth_authorization():
    """Запускает OAuth в браузере. Возвращает (ok, message)."""
    if not credentials_file_exists():
        return False, f"Положите credentials JSON в {get_credentials_path()}"
    try:
        _get_credentials()
        return True, "Авторизация успешна! Календарь подключён."
    except Exception as e:
        return False, str(e)


def build_event_title(cand, vacancy_title):
    name = (cand.get("name") or "Кандидат").strip()
    vac = (vacancy_title or "Вакансия").strip()
    return f"{name}, {vac}"


def build_event_description(cand, vacancy_title):
    lines = [f"Вакансия: {vacancy_title}"]
    if cand.get("phone"):
        lines.append(f"Телефон: {cand['phone']}")
    if cand.get("resume_link"):
        lines.append(f"Резюме: {cand['resume_link']}")
    if cand.get("video_link"):
        lines.append(f"Запись: {cand['video_link']}")
    if cand.get("hr_comment"):
        lines.append(f"Комментарий HR: {cand['hr_comment']}")
    return "\n".join(lines)


def _event_body(cand, vacancy_title, start_dt, end_dt, tz_name):
    return {
        "summary": build_event_title(cand, vacancy_title),
        "description": build_event_description(cand, vacancy_title),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_name},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz_name},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 30},
                {"method": "popup", "minutes": 10},
            ],
        },
    }


def create_or_update_interview_event(cand, vacancy_title, start_dt, tz_name):
    """Создаёт или обновляет событие. Возвращает (ok, message, event_id)."""
    service, err = get_calendar_service()
    if err:
        return False, err, None

    duration = get_event_duration_minutes()
    end_dt = start_dt + timedelta(minutes=duration)
    body = _event_body(cand, vacancy_title, start_dt, end_dt, tz_name)
    calendar_id = get_calendar_id()
    event_id = cand.get("calendar_event_id")

    try:
        if event_id:
            updated = (
                service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=body)
                .execute()
            )
            return True, "Событие в календаре обновлено", updated.get("id", event_id)

        created = (
            service.events().insert(calendarId=calendar_id, body=body).execute()
        )
        return True, "Событие добавлено в Google Calendar", created.get("id")
    except Exception as e:
        err_text = str(e)
        if event_id and ("404" in err_text or "Not Found" in err_text):
            cand["calendar_event_id"] = ""
            return create_or_update_interview_event(
                cand, vacancy_title, start_dt, tz_name
            )
        return False, f"Ошибка Calendar API: {e}", event_id


def delete_interview_event(cand):
    """Удаляет событие из календаря. Возвращает (ok, message)."""
    event_id = cand.get("calendar_event_id")
    if not event_id:
        return True, ""

    if not is_calendar_ready():
        cand["calendar_event_id"] = ""
        return True, ""

    service, err = get_calendar_service()
    if err:
        return False, err

    try:
        service.events().delete(
            calendarId=get_calendar_id(), eventId=event_id
        ).execute()
        cand["calendar_event_id"] = ""
        return True, "Событие удалено из календаря"
    except Exception as e:
        if "404" in str(e) or "Not Found" in str(e):
            cand["calendar_event_id"] = ""
            return True, ""
        return False, str(e)
