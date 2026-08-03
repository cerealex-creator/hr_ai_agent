"""Google Calendar integration for interview events (v2 port of Streamlit google_calendar.py)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.core.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _root_data() -> Path:
    return get_settings().resolved_legacy_data_dir()


def get_credentials_path() -> str:
    env = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "").strip()
    if env:
        return env
    return str(_root_data() / "google_calendar_credentials.json")


def get_token_path() -> str:
    env = os.getenv("GOOGLE_CALENDAR_TOKEN", "").strip()
    if env:
        return env
    return str(_root_data() / "google_calendar_token.json")


def get_calendar_id() -> str:
    return os.getenv("GOOGLE_CALENDAR_ID", "primary")


def get_event_duration_minutes() -> int:
    try:
        return int(os.getenv("GOOGLE_CALENDAR_EVENT_MINUTES", "30"))
    except ValueError:
        return 30


def credentials_file_exists() -> bool:
    return os.path.isfile(get_credentials_path())


def token_exists() -> bool:
    return os.path.isfile(get_token_path())


def is_calendar_ready() -> bool:
    return credentials_file_exists() and token_exists()


def get_calendar_status() -> tuple[str, str]:
    if not credentials_file_exists():
        return "not_configured", f"Нет credentials ({get_credentials_path()})"
    if not token_exists():
        return "needs_auth", "Credentials есть — нужна авторизация"
    _, err = get_calendar_service()
    if err:
        low = err.lower()
        if "invalid_grant" in low or "expired" in low or "revoked" in low:
            return "needs_auth", "Токен устарел — переподключите Google Calendar"
        return "error", err
    return "ready", "Google Calendar подключён"


def _save_credentials(creds: Any) -> None:
    path = get_token_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def _load_credentials():
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


def get_calendar_service():
    if not is_calendar_ready():
        return None, "Google Calendar не настроен"
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return None, "Установите google-api-python-client / google-auth-oauthlib"
    try:
        creds = _load_credentials()
        if not creds:
            return None, "Токен Google Calendar устарел — переподключите в Настройках"
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return service, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def _oauth_pending_path() -> str:
    return str(_root_data() / "google_calendar_oauth_pending.json")


def _save_oauth_pending(data: dict) -> None:
    path = _oauth_pending_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _load_oauth_pending() -> dict:
    path = _oauth_pending_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def extract_oauth_code(pasted: str) -> str | None:
    """Accept full redirect URL, `code=...`, or bare code value."""
    text = (pasted or "").strip().strip('"').strip("'")
    if not text:
        return None
    # Full URL with query
    if "://" in text or text.startswith("http"):
        code = parse_qs(urlparse(text).query).get("code", [None])[0]
        if code:
            return code
    # Query-only fragment: code=xxx&scope=...
    if "code=" in text:
        # Try as fake query string
        q = text if text.startswith("?") else f"?{text.lstrip('?')}"
        code = parse_qs(urlparse(f"http://local{q}").query).get("code", [None])[0]
        if code:
            return code
        # Prefix form without &
        if text.startswith("code="):
            return text[5:].split("&", 1)[0].strip() or None
    # Bare code (often starts with 4/)
    if " " not in text and len(text) >= 8:
        return text
    return None


def oauth_auth_url() -> tuple[bool, str, str | None]:
    """Start console-style OAuth: return auth URL (user pastes redirect URL later)."""
    if not credentials_file_exists():
        return False, f"Положите credentials JSON в {get_credentials_path()}", None
    try:
        flow = _oauth_flow()
        flow.redirect_uri = "http://localhost:8765/"
        auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
        pending = {
            "state": state,
            "code_verifier": getattr(flow, "code_verifier", None),
            "redirect_uri": flow.redirect_uri,
        }
        _save_oauth_pending(pending)
        return (
            True,
            "Откройте ссылку в браузере. После входа скопируйте весь адрес "
            "из строки (http://localhost:8765/?code=...) или только значение code — "
            "и вставьте ниже. Код одноразовый: при ошибке получите новую ссылку.",
            auth_url,
        )
    except Exception as e:  # noqa: BLE001
        return False, str(e), None


def oauth_complete_with_code(pasted: str) -> tuple[bool, str]:
    pasted = (pasted or "").strip()
    if not pasted:
        return False, "Код не введён"
    if not credentials_file_exists():
        return False, f"Нет credentials ({get_credentials_path()})"
    code = extract_oauth_code(pasted)
    if not code:
        return (
            False,
            "Не удалось извлечь code. Вставьте целиком URL вида "
            "http://localhost:8765/?code=4/0A... или только 4/0A... без префикса code=",
        )
    token_path = get_token_path()
    if os.path.exists(token_path):
        os.remove(token_path)
    try:
        flow = _oauth_flow()
        pending = _load_oauth_pending()
        flow.redirect_uri = pending.get("redirect_uri") or "http://localhost:8765/"
        verifier = pending.get("code_verifier")
        if verifier:
            flow.code_verifier = verifier
        flow.fetch_token(code=code)
        _save_credentials(flow.credentials)
        try:
            os.remove(_oauth_pending_path())
        except OSError:
            pass
        return True, "Авторизация успешна! Календарь подключён."
    except Exception as e:  # noqa: BLE001
        return (
            False,
            f"{e}\n\nКод мог устареть или не совпасть с PKCE — нажмите «Получить ссылку OAuth» заново.",
        )


def run_oauth_local_server() -> tuple[bool, str]:
    """Interactive local server on :8765 (for CLI / settings button when UI can wait)."""
    if not credentials_file_exists():
        return False, f"Положите credentials JSON в {get_credentials_path()}"
    token_path = get_token_path()
    if os.path.exists(token_path):
        os.remove(token_path)
    try:
        flow = _oauth_flow()
        creds = flow.run_local_server(port=8765, open_browser=True, prompt="consent")
        _save_credentials(creds)
        return True, "Авторизация успешна! Календарь подключён."
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _cand_dict(cand: dict | Any) -> dict:
    if isinstance(cand, dict):
        return cand
    payload = dict(getattr(cand, "payload", None) or {})
    return {
        "name": getattr(cand, "name", "") or "",
        "phone": payload.get("phone") or "",
        "resume_link": payload.get("resume_link") or "",
        "video_link": payload.get("video_link") or "",
        "hr_comment": payload.get("hr_comment") or "",
        "calendar_event_id": payload.get("calendar_event_id") or "",
    }


def build_event_title(cand: dict | Any, vacancy_title: str) -> str:
    d = _cand_dict(cand)
    name = (d.get("name") or "Кандидат").strip()
    vac = (vacancy_title or "Вакансия").strip()
    return f"{name}, {vac}"


def build_event_description(cand: dict | Any, vacancy_title: str) -> str:
    d = _cand_dict(cand)
    lines = [f"Вакансия: {vacancy_title}"]
    if d.get("phone"):
        lines.append(f"Телефон: {d['phone']}")
    if d.get("resume_link"):
        lines.append(f"Резюме: {d['resume_link']}")
    if d.get("video_link"):
        lines.append(f"Запись: {d['video_link']}")
    if d.get("hr_comment"):
        lines.append(f"Комментарий HR: {d['hr_comment']}")
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


def create_or_update_interview_event(
    cand: dict,
    vacancy_title: str,
    start_dt: datetime,
    tz_name: str,
) -> tuple[bool, str, str | None]:
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
        created = service.events().insert(calendarId=calendar_id, body=body).execute()
        return True, "Событие добавлено в Google Calendar", created.get("id")
    except Exception as e:  # noqa: BLE001
        err_text = str(e)
        if event_id and ("404" in err_text or "Not Found" in err_text):
            cand["calendar_event_id"] = ""
            return create_or_update_interview_event(cand, vacancy_title, start_dt, tz_name)
        return False, f"Ошибка Calendar API: {e}", event_id


def delete_interview_event(cand: dict) -> tuple[bool, str]:
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
        service.events().delete(calendarId=get_calendar_id(), eventId=event_id).execute()
        cand["calendar_event_id"] = ""
        return True, "Событие удалено из календаря"
    except Exception as e:  # noqa: BLE001
        if "404" in str(e) or "Not Found" in str(e):
            cand["calendar_event_id"] = ""
            return True, ""
        return False, str(e)
