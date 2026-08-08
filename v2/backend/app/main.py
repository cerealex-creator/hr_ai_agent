from contextlib import asynccontextmanager
import logging
import threading

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.v1.endpoints import router as v1_router
from app.core.config import get_settings
from app.workers.redis_pool import close_arq_pool

settings = get_settings()
logger = logging.getLogger("hr_api")
_bitrix_tick_stop = threading.Event()


def _bitrix_tick_loop() -> None:
    while not _bitrix_tick_stop.wait(60):
        from app.db.session import SessionLocal
        from app.services.app_settings import get_bitrix
        from app.services.bitrix.think_followup import run_bitrix_maintenance_tick

        if not get_bitrix().get("enabled"):
            continue
        db = SessionLocal()
        try:
            result = run_bitrix_maintenance_tick(db)
            think = result.get("think_followup") or {}
            if think.get("scheduled") or think.get("created"):
                logger.info("bitrix maintenance tick: %s", result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("bitrix maintenance tick error: %s", exc)
            db.rollback()
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.core.startup import validate_startup_settings
    from app.db.base import Base
    from app.db import models  # noqa: F401
    from app.db.session import SessionLocal, engine
    from app.services.clients_write import migrate_legacy_clients

    validate_startup_settings(get_settings())

    # Schema: use `alembic upgrade head` (M1 baseline). Optional create_all
    # remains as a safety net for local bootstraps that skipped Alembic.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:  # noqa: BLE001
        print(f"create_all skipped: {exc}")

    db = SessionLocal()
    try:
        migrate_legacy_clients(db)
    except Exception as exc:  # noqa: BLE001
        print(f"clients migrate skipped: {exc}")
    finally:
        db.close()

    db = SessionLocal()
    try:
        from app.services.users import ensure_bootstrap_user
        from app.services.notify_prefs import ensure_notify_prefs_column
        from app.services.candidate_intake import ensure_candidate_intake_column

        ensure_notify_prefs_column(db)
        ensure_candidate_intake_column(db)
        ensure_bootstrap_user(db)
    except Exception as exc:  # noqa: BLE001
        print(f"auth bootstrap skipped: {exc}")
    finally:
        db.close()

    try:
        from app.services.app_settings import migrate_client_notify_to_pilot

        migrate_client_notify_to_pilot()
    except Exception as exc:  # noqa: BLE001
        print(f"client_notify migrate skipped: {exc}")

    tick_thread = threading.Thread(target=_bitrix_tick_loop, daemon=True, name="bitrix-tick")
    tick_thread.start()
    yield
    _bitrix_tick_stop.set()
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


@app.middleware("http")
async def tenancy_request_context(request: Request, call_next):
    """Expose Request to sync handlers via ContextVar (copied into threadpool)."""
    from app.services.tenancy import bind_request, reset_request

    token = bind_request(request)
    try:
        return await call_next(request)
    finally:
        reset_request(token)


app.include_router(v1_router, prefix="/api/v1")


@app.post("/integrations/{provider}/webhook")
async def integrations_webhook_root(provider: str, request: Request) -> dict:
    """Architecture path; same handler as /api/v1/integrations/.../webhook."""
    from app.api.v1.endpoints import _parse_webhook_payload
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.services.messaging.gateway import parse_inbound_webhook

    settings = get_settings()
    payload = await _parse_webhook_payload(request)
    db = SessionLocal()
    try:
        events = parse_inbound_webhook(provider, payload or {}, db=db)
    finally:
        db.close()
    handled = any(bool(e.get("handled")) for e in events)
    provider_l = (provider or "").strip().lower()
    if provider_l in ("bitrix", "bitrix24"):
        note = "bitrix inbound"
    elif settings.messaging_inbound_enabled:
        note = "inbound enabled"
    else:
        note = "inbound disabled — Streamlit bot keeps polling until cutover"
    return {
        "ok": True,
        "handled": handled,
        "provider": provider,
        "events": events,
        "note": note,
    }


def _bitrix_decide_response(
    db,
    token: str,
    comment: str | None = None,
    *,
    meeting_date: str | None = None,
    meeting_time: str | None = None,
    meeting_format: str | None = None,
) -> HTMLResponse:
    from app.services.bitrix.decide import DecideError, apply_decide_token
    from app.services.bitrix.pages import comment_form_html, error_html, meeting_form_html, success_html

    try:
        result = apply_decide_token(
            db,
            token,
            comment=comment,
            meeting_date=meeting_date,
            meeting_time=meeting_time,
            meeting_format=meeting_format,
        )
    except DecideError as exc:
        return HTMLResponse(error_html(exc.message), status_code=exc.status_code)
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(error_html(str(exc) or "Ошибка"), status_code=500)

    if result.get("needs_comment"):
        return HTMLResponse(
            comment_form_html(
                name=str(result.get("candidate_name") or ""),
                status_label=str(result.get("status_label") or ""),
                token=token,
            )
        )
    if result.get("needs_meeting"):
        return HTMLResponse(
            meeting_form_html(
                name=str(result.get("candidate_name") or ""),
                status_label=str(result.get("status_label") or ""),
                token=token,
            )
        )
    meeting_when = ""
    if result.get("meeting_date") and result.get("meeting_time"):
        try:
            from datetime import datetime

            d = datetime.strptime(str(result["meeting_date"]), "%Y-%m-%d").strftime("%d.%m.%Y")
            meeting_when = f"{d} {result['meeting_time']}"
        except ValueError:
            meeting_when = f"{result['meeting_date']} {result['meeting_time']}"
    return HTMLResponse(
        success_html(
            name=str(result.get("candidate_name") or ""),
            status_label=str(result.get("status_label") or ""),
            meeting_when=meeting_when or None,
        )
    )


@app.get("/integrations/bitrix/decide", response_class=HTMLResponse)
def bitrix_decide_get(t: str = "") -> HTMLResponse:
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        return _bitrix_decide_response(session, t)
    finally:
        session.close()


@app.post("/integrations/bitrix/decide", response_class=HTMLResponse)
def bitrix_decide_post(
    t: str = Form(default=""),
    comment: str = Form(default=""),
    meeting_date: str = Form(default=""),
    meeting_time: str = Form(default=""),
    meeting_format: str = Form(default="o"),
) -> HTMLResponse:
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        return _bitrix_decide_response(
            session,
            t,
            comment=comment,
            meeting_date=meeting_date,
            meeting_time=meeting_time,
            meeting_format=meeting_format,
        )
    finally:
        session.close()


@app.get("/")
def root() -> dict:
    return {
        "app": "hr_ai_agent_v2",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/v1/health",
        "jobs": "/api/v1/jobs",
        "events": "/api/v1/events/stream",
        "messaging": "/api/v1/messaging/status",
        "webhook_stub": "/integrations/telegram/webhook",
        "bitrix_webhook": "/integrations/bitrix/webhook",
        "bitrix_decide": "/integrations/bitrix/decide",
    }
