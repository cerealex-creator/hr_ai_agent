from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.tasks import (
    candidate_interview_process,
    demo_progress,
    disk_inbox_router,
    hh_cold_search,
    import_legacy,
    transcribe_media,
    vacancy_docs_from_materials,
    yandex_disk_sync,
)

_settings = get_settings()


class WorkerSettings:
    functions = [
        demo_progress,
        import_legacy,
        transcribe_media,
        candidate_interview_process,
        hh_cold_search,
        yandex_disk_sync,
        disk_inbox_router,
        vacancy_docs_from_materials,
    ]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_jobs = 2
    job_timeout = 60 * 30
    keep_result = 60 * 60
