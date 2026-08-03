from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import router as v1_router
from app.core.config import get_settings
from app.workers.redis_pool import close_arq_pool

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_arq_pool()


app = FastAPI(
    title="HR AI Agent API (v2 MVP)",
    version="0.1.0",
    description="v2 MVP. Legacy Streamlit remains the system of record until cutover.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.post("/integrations/{provider}/webhook")
def integrations_webhook_root(provider: str, payload: dict) -> dict:
    """Architecture path; same handler as /api/v1/integrations/.../webhook."""
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.services.messaging.gateway import parse_inbound_webhook

    settings = get_settings()
    db = SessionLocal()
    try:
        events = parse_inbound_webhook(provider, payload or {}, db=db)
    finally:
        db.close()
    handled = any(bool(e.get("handled")) for e in events)
    return {
        "ok": True,
        "handled": handled,
        "provider": provider,
        "events": events,
        "note": (
            "inbound enabled"
            if settings.messaging_inbound_enabled
            else "inbound disabled — Streamlit bot keeps polling until cutover"
        ),
    }


@app.get("/")
def root() -> dict:
    return {
        "app": "hr_ai_agent_v2",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/v1/health",
        "jobs": "/api/v1/jobs",
        "messaging": "/api/v1/messaging/status",
        "webhook_stub": "/integrations/telegram/webhook",
    }
