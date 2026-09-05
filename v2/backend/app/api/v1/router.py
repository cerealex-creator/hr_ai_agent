"""Aggregate v1 API routers (audit M6 + D1 Auth)."""
from fastapi import APIRouter, Depends

from app.api.v1.routes import (
    auth,
    candidates,
    client_zone,
    clients,
    events,
    health_meta,
    hh,
    integrations,
    interview_digest,
    jobs,
    messaging,
    resume_preview,
    settings,
    stats_history,
    talent_pool,
    management_system,
    consulting,
    vacancies,
)
from app.core.auth import require_auth

router = APIRouter()

# Public (no auth)
router.include_router(auth.router)
router.include_router(health_meta.public_router)
router.include_router(integrations.public_router)
router.include_router(client_zone.router)
router.include_router(resume_preview.router)
router.include_router(interview_digest.router)
router.include_router(consulting.public_router)
router.include_router(consulting.survey_public_router)

# Protected
protected = APIRouter(dependencies=[Depends(require_auth)])
protected.include_router(candidates.router)
protected.include_router(clients.router)
protected.include_router(events.router)
protected.include_router(health_meta.router)
protected.include_router(hh.router)
protected.include_router(integrations.router)
protected.include_router(jobs.router)
protected.include_router(messaging.router)
protected.include_router(settings.router)
protected.include_router(stats_history.router)
protected.include_router(talent_pool.router)
protected.include_router(management_system.router)
protected.include_router(consulting.router)
protected.include_router(vacancies.router)
router.include_router(protected)
