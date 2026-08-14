from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.tasks import (
    candidate_evaluate_resume,
    candidate_interview_process,
    demo_progress,
    disk_inbox_router,
    hh_cold_search,
    import_legacy,
    transcribe_media,
    vacancy_docs_from_brief,
    vacancy_docs_from_materials,
    vacancy_docs_generate,
    yandex_disk_sync,
)

_settings = get_settings()


async def on_startup(ctx) -> None:
    """Cursor/sandbox injects HTTP(S)_PROXY → 403 to routerai.ru. Drop them in worker."""
    import os

    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "SOCKS_PROXY",
        "SOCKS5_PROXY",
        "socks_proxy",
        "socks5_proxy",
    ):
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


class WorkerSettings:
    functions = [
        demo_progress,
        import_legacy,
        transcribe_media,
        candidate_interview_process,
        candidate_evaluate_resume,
        hh_cold_search,
        yandex_disk_sync,
        disk_inbox_router,
        vacancy_docs_from_materials,
        vacancy_docs_from_brief,
        vacancy_docs_generate,
    ]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_jobs = 2
    job_timeout = 60 * 30
    keep_result = 60 * 60
    on_startup = on_startup
