"""Thin Bitrix24 REST client (incoming webhook)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests

from app.services.app_settings import get_bitrix


class BitrixError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _webhook_base() -> str:
    cfg = get_bitrix()
    raw = str(cfg.get("incoming_webhook_url") or "").strip()
    if not raw:
        raise BitrixError("Не задан Bitrix incoming webhook URL", 400)
    return raw if raw.endswith("/") else raw + "/"


def call_method(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Call REST method via incoming webhook.
    method: e.g. tasks.task.add
    """
    base = _webhook_base()
    url = urljoin(base, method)
    try:
        resp = requests.post(url, json=params or {}, timeout=30)
    except requests.RequestException as exc:
        raise BitrixError(f"Bitrix network error: {exc}", 502) from exc

    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise BitrixError(
            f"Bitrix non-JSON response HTTP {resp.status_code}: {resp.text[:200]}",
            502,
        ) from exc

    if resp.status_code >= 400:
        err = data.get("error_description") or data.get("error") or resp.text[:200]
        raise BitrixError(f"Bitrix HTTP {resp.status_code}: {err}", 502)

    if isinstance(data, dict) and data.get("error"):
        err = data.get("error_description") or data.get("error")
        raise BitrixError(f"Bitrix API error: {err}", 502)

    result = data.get("result") if isinstance(data, dict) else data
    return result if isinstance(result, dict) else {"result": result}


def create_task(fields: dict[str, Any]) -> str:
    """Create task; returns task id as string."""
    result = call_method("tasks.task.add", {"fields": fields})
    # Classic API: {"task": {"id": "123"}}
    if isinstance(result, dict):
        task = result.get("task") if isinstance(result.get("task"), dict) else result
        tid = task.get("id") if isinstance(task, dict) else None
        if tid is None and "result" in result:
            tid = result.get("result")
        if tid is not None:
            return str(tid)
    if result is not None and not isinstance(result, dict):
        return str(result)
    raise BitrixError(f"Bitrix tasks.task.add: unexpected result {result!r}", 502)


def get_task(task_id: str | int) -> dict[str, Any]:
    result = call_method(
        "tasks.task.get",
        {"taskId": int(task_id), "select": ["*", "UF_*"]},
    )
    if isinstance(result, dict) and isinstance(result.get("task"), dict):
        return result["task"]
    if isinstance(result, dict):
        return result
    return {}


def update_task(task_id: str | int, fields: dict[str, Any]) -> None:
    call_method(
        "tasks.task.update",
        {"taskId": int(task_id), "fields": fields},
    )


def add_task_comment(task_id: str | int, message: str, *, author_id: int | None = None) -> None:
    """Add a comment to task feed (task.commentitem.add; works on classic and many new cards)."""
    text = (message or "").strip()
    if not text:
        return
    fields: dict[str, Any] = {"POST_MESSAGE": text}
    if author_id is not None:
        fields["AUTHOR_ID"] = int(author_id)
    call_method(
        "task.commentitem.add",
        {"TASKID": int(task_id), "FIELDS": fields},
    )
