from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://hr_v2:hr_v2_dev@localhost:5433/hr_v2"
    legacy_data_dir: str = "../data"
    cors_origins: str = "http://localhost:3000"
    redis_url: str = "redis://localhost:6379/0"
    default_org_name: str = "Default Organization"
    default_org_slug: str = "default"

    # Auth (D1) — JWT in httpOnly cookies; AUTH_DISABLED only outside production
    app_env: str = "local"  # local | production
    auth_disabled: bool = False
    jwt_secret: str = "dev-change-me-hr-v2-jwt-secret-min-32b"
    jwt_access_ttl_minutes: int = 30
    jwt_refresh_ttl_days: int = 14
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"  # lax | strict | none
    auth_cookie_domain: str = ""
    auth_bootstrap_email: str = ""
    auth_bootstrap_password: str = ""
    auth_bootstrap_role: str = "platform_owner"

    # Yandex SpeechKit / Object Storage (same keys as Streamlit .env)
    yandex_api_key: str = ""
    yandex_bucket_name: str = ""
    yandex_access_key_id: str = ""
    yandex_secret_access_key: str = ""
    ffmpeg_binary: str = ""

    # Yandex Disk OAuth (folder create / inbox) — separate from SpeechKit keys
    yandex_disk_oauth_token: str = ""
    yandex_disk_oauth_token_path: str = ""
    yandex_disk_client_id: str = ""

    # HeadHunter (system-wide employer manager token — option A)
    hh_client_id: str = ""
    hh_client_secret: str = ""
    hh_access_token: str = ""
    hh_refresh_token: str = ""
    hh_api_base: str = "https://api.hh.ru"
    hh_user_agent: str = "HR_AI_Agent_v2/1.0 (dialex307@gmail.com)"

    # AI (same as Streamlit RouterAI by default)
    routerai_api_key: str = ""
    ai_api_key: str = ""
    ai_base_url: str = "https://routerai.ru/api/v1"
    ai_model_name: str = "qwen/qwen3.5-plus-20260420"

    # Messaging Gateway (Telegram). Inbound off by default — do not steal polling from Streamlit.
    telegram_bot_token: str = ""
    messaging_outbound_enabled: bool = True
    messaging_inbound_enabled: bool = False
    # Local/dev: long-poll getUpdates (python -m app.workers.telegram_poller). Off when using HTTPS webhook.
    messaging_poll_enabled: bool = False
    telegram_hr_user_id: str = ""
    telegram_reminder_tz: str = "Europe/Moscow"
    messaging_reminder_interval_sec: int = 60

    # Zoom User OAuth (Marketplace app) — create meetings for connected user
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    zoom_redirect_uri: str = "http://localhost:8765/"
    zoom_token_path: str = ""
    zoom_oauth_scopes: str = "meeting:write user:read offline_access"

    model_config = SettingsConfigDict(
        env_file=("../../.env", "../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolved_legacy_data_dir(self) -> Path:
        """Resolve Streamlit `data/` in local tree or Docker (/app)."""
        raw = Path(self.legacy_data_dir)
        if raw.is_absolute():
            return raw
        here = Path(__file__).resolve()
        candidates: list[Path] = [(Path.cwd() / raw).resolve()]
        # Walk up safely — Docker image is shallow (/app/app/core/...), no parents[4].
        for parent in list(here.parents)[:6]:
            candidates.append((parent / "data").resolve())
            candidates.append((parent / raw).resolve())
        markers = (
            "vacancies.json",
            "app_settings.json",
            "google_calendar_credentials.json",
            "clients.json",
            "yandex_disk_oauth.json",
        )
        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            if any((path / m).exists() for m in markers):
                return path
        # Writable fallback inside the API container
        fallback = Path("/app/data")
        try:
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        except OSError:
            return candidates[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()
