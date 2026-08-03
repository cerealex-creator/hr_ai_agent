"""Long-running Telegram getUpdates poller for local / no-public-HTTPS inbound.

Usage (from v2/backend, with .venv):
  python -m app.workers.telegram_poller

Requires:
  TELEGRAM_BOT_TOKEN
  MESSAGING_INBOUND_ENABLED=true
  MESSAGING_POLL_ENABLED=true

Deletes any active webhook on start (getUpdates conflicts with webhook).
Do not run alongside Streamlit bot.py on the same token.
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time

import requests

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.messaging.inbound import process_telegram_update
from app.services.messaging.reminders import run_reminder_tick

logger = logging.getLogger("telegram_poller")

_stop = False


def _handle_signal(signum, _frame) -> None:  # noqa: ANN001
    global _stop
    logger.info("signal %s — stopping", signum)
    _stop = True


def _api(token: str, method: str, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    response = requests.get(url, params=params or None, timeout=40)
    response.raise_for_status()
    return response.json()


def _maybe_reminder_tick(last_tick: float, interval: int) -> float:
    now = time.monotonic()
    if now - last_tick < interval:
        return last_tick
    db = SessionLocal()
    try:
        from app.services.messaging.attendance_jobs import collect_and_queue_morning_jobs

        collect_and_queue_morning_jobs(db)
        result = run_reminder_tick(db)
        logger.info("reminder tick: %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("reminder tick error: %s", exc)
        db.rollback()
    finally:
        db.close()
    return now


def run() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [telegram_poller] %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is empty")
        return 1
    if not settings.messaging_inbound_enabled:
        logger.error("MESSAGING_INBOUND_ENABLED=false — refuse to poll")
        return 1
    if not settings.messaging_poll_enabled:
        logger.error("MESSAGING_POLL_ENABLED=false — set true to run this process")
        return 1

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    drop = _api(token, "deleteWebhook", drop_pending_updates=False)
    logger.info("deleteWebhook: %s", drop)
    me = _api(token, "getMe")
    bot = (me.get("result") or {}) if me.get("ok") else {}
    logger.info(
        "polling as @%s (id=%s) — Ctrl+C to stop",
        bot.get("username") or "?",
        bot.get("id"),
    )

    try:
        from app.services.messaging.commands import ensure_bot_commands

        ensure_bot_commands()
    except Exception as exc:  # noqa: BLE001
        logger.warning("setMyCommands failed: %s", exc)

    offset: int | None = None
    last_tick = 0.0
    interval = max(30, int(settings.messaging_reminder_interval_sec or 60))
    while not _stop:
        last_tick = _maybe_reminder_tick(last_tick, interval)
        params: dict = {"timeout": 25}
        if offset is not None:
            params["offset"] = offset
        try:
            data = _api(token, "getUpdates", **params)
        except Exception as exc:  # noqa: BLE001
            logger.warning("getUpdates error: %s", exc)
            time.sleep(2)
            continue
        if not data.get("ok"):
            logger.warning("getUpdates bad response: %s", data)
            time.sleep(2)
            continue
        for upd in data.get("result") or []:
            if _stop:
                break
            offset = int(upd["update_id"]) + 1
            keys = [k for k in upd if k != "update_id"]
            logger.info("update %s %s", upd.get("update_id"), keys)
            db = SessionLocal()
            try:
                events = process_telegram_update(db, upd)
                logger.info("events: %s", json.dumps(events, ensure_ascii=False)[:800])
            except Exception as exc:  # noqa: BLE001
                logger.exception("process error: %s", exc)
                db.rollback()
            finally:
                db.close()

    logger.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(run())
