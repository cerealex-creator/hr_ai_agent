"""Aggregate v1 API routers (audit M6)."""
from fastapi import APIRouter

from app.api.v1.routes import (
    candidates,
    clients,
    health_meta,
    hh,
    integrations,
    jobs,
    messaging,
    settings,
    stats_history,
    vacancies
)

router = APIRouter()
router.include_router(candidates.router)
router.include_router(clients.router)
router.include_router(health_meta.router)
router.include_router(hh.router)
router.include_router(integrations.router)
router.include_router(jobs.router)
router.include_router(messaging.router)
router.include_router(settings.router)
router.include_router(stats_history.router)
router.include_router(vacancies.router)
