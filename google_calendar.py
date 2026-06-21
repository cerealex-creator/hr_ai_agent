"""Интеграция с Google Calendar для собеседований."""

import os
from datetime import timedelta

from dotenv import load_dotenv

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_ROOT_DIR, ".env")
load_dotenv(_ENV_PATH, override=True)

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
    """Читает длительность из .env при каждом создании/обновлении события."""
    load_dotenv(_ENV_PATH, override=True)
    try:
        return int(os.getenv("GOOGLE_CALENDAR_EVENT_MINUTES", "30"))
    except ValueError:
        return 30


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
    _, err = get_calendar_service()
    if err:
        if "invalid_grant" in err.lower() or "expired" in err.lower() or "revoked" in err.lower():
            return "needs_auth", "Токен Google Calendar устарел — нажмите «Подключить Google Calendar»"
        return "error", err
    return "ready", "Google Calendar подключён"


def _load_credentials():
    """Загрузка и refresh без интерактива (для фоновой работы календаря)."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_path = get_token_path()
    if not os.path.exists(token_path):
        return None

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_credentials(creds)
            return creds
        except Exception:
            return None

    return None


def _oauth_flow():
    from google_auth_oauthlib.flow import InstalledAppFlow

    return InstalledAppFlow.from_client_secrets_file(get_credentials_path(), SCOPES)


def _get_credentials():
    """Интерактивная авторизация (открывает браузер). Только по кнопке в настройках."""
    creds = _load_credentials()
    if creds:
        return creds

    token_path = get_token_path()
    if os.path.exists(token_path):
        os.remove(token_path)

    flow = _oauth_flow()
    creds = flow.run_local_server(port=8765, open_browser=True, prompt="consent")
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

        creds = _load_credentials()
        if not creds:
            return None, "Токен Google Calendar устарел — переподключите в Настройках"
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return service, None
    except Exception as e:
        return None, str(e)


def run_oauth_authorization():
    """Запускает OAuth в браузере. Возвращает (ok, message)."""
    if not credentials_file_exists():
        return False, f"Положите credentials JSON в {get_credentials_path()}"
    token_path = get_token_path()
    if os.path.exists(token_path):
        os.remove(token_path)
    try:
        _get_credentials()
        return True, "Авторизация успешна! Календарь подключён."
    except Exception as e:
        return False, (
            f"{e}\n\n"
            "Если в браузере «Подтверждение не отправлено» — не закрывайте Терминал и попробуйте:\n"
            "  python google_calendar_auth.py --console"
        )


def run_oauth_console():
    """Авторизация: ссылка в браузере, код вручную (если localhost не срабатывает)."""
    from urllib.parse import parse_qs, urlparse

    if not credentials_file_exists():
        return False, f"Положите credentials JSON в {get_credentials_path()}"
    token_path = get_token_path()
    if os.path.exists(token_path):
        os.remove(token_path)
    try:
        flow = _oauth_flow()
        flow.redirect_uri = "http://localhost:8765/"
        auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
        print("\n1) Откройте ссылку в браузере и разрешите доступ:\n")
        print(auth_url)
        print(
            "\n2) После входа браузер может показать ошибку — это нормально.\n"
            "   Скопируйте **весь адрес** из строки браузера (начинается с http://localhost:8765/?code=...)\n"
            "   или только длинный код после code=\n"
        )
        pasted = input("3) Вставьте сюда и нажмите Enter:\n").strip()
        if not pasted:
            return False, "Код не введён"
        if "code=" in pasted:
            code = parse_qs(urlparse(pasted).query).get("code", [None])[0]
        else:
            code = pasted
        if not code:
            return False, "Не удалось извлечь code из вставленного текста"
        flow.fetch_token(code=code)
        _save_credentials(flow.credentials)
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
