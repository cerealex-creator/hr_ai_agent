"""Telegram inline keyboards for candidate cards (parity with Streamlit bot)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

CHAT_STATUS_BUTTONS: list[tuple[str, str]] = [
    ("ready", "🟢 Встреча"),
    ("think", "🟡 Подумать"),
    ("reject", "🔴 Отказ"),
    ("offer", "🟣 Оффер"),
]

CLIENT_STATUS_META: dict[str, dict[str, str]] = {
    "wait": {"label": "Ждёт оценки", "icon": "⏳"},
    "ready": {"label": "Встреча", "icon": "🟢"},
    "think": {"label": "Подумать", "icon": "🟡"},
    "reject": {"label": "Отказ", "icon": "🔴"},
    "offer": {"label": "Оффер", "icon": "🟣"},
    "started": {"label": "Вышел", "icon": "✅"},
}

STATUSES_REQUIRE_COMMENT = frozenset({"think", "reject"})
STATUSES_THAT_CANCEL_MEETING = frozenset({"reject", "think"})


def _tz() -> ZoneInfo:
    return ZoneInfo("Europe/Moscow")


def build_time_slots() -> list[str]:
    options: list[str] = []
    current = time(9, 0)
    end = time(18, 0)
    while current <= end:
        options.append(current.strftime("%H:%M"))
        minutes = current.hour * 60 + current.minute + 30
        current = time(minutes // 60, minutes % 60)
    return options


def has_meeting_schedule(date_str: str | None, time_str: str | None) -> bool:
    return bool((date_str or "").strip() and (time_str or "").strip())


def build_url_button_keyboard(
    url: str,
    label: str = "Смотреть кандидата",
    *,
    style: str | None = None,
) -> dict[str, Any]:
    href = (url or "").strip()
    if not href.startswith(("http://", "https://")):
        return {"inline_keyboard": []}
    text = (label or "Открыть").strip() or "Открыть"
    btn: dict[str, Any] = {"text": text, "url": href}
    # Bot API 9.4+: primary | success | danger (старые клиенты просто без цвета)
    st = (style or "").strip().lower()
    if st in ("primary", "success", "danger"):
        btn["style"] = st
    return {"inline_keyboard": [[btn]]}


def build_view_candidate_keyboard(url: str) -> dict[str, Any]:
    """Telegram URL button to the candidate page in client zone (no status callbacks)."""
    return build_url_button_keyboard(url, "Смотреть кандидата")


def build_initial_status_keyboard(callback_id: str, current: str = "wait") -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for key, label in CHAT_STATUS_BUTTONS:
        text = f"• {label}" if key == current else label
        row.append({"text": text, "callback_data": f"cs:{callback_id}:{key}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "💬 Комментарий", "callback_data": f"cc:{callback_id}"}])
    return {"inline_keyboard": rows}


def build_locked_keyboard(
    callback_id: str,
    *,
    status: str,
    date_str: str | None = None,
    time_str: str | None = None,
) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = [
        [
            {"text": "💬 Комментарий", "callback_data": f"cc:{callback_id}"},
            {"text": "🔄 Сменить статус", "callback_data": f"cchg:{callback_id}"},
        ]
    ]
    scheduled = has_meeting_schedule(date_str, time_str)
    if status == "ready" or scheduled:
        label = "📅 Изменить встречу" if scheduled else "📅 Встреча"
        rows.append([{"text": label, "callback_data": f"ivi:{callback_id}"}])
    if scheduled:
        rows.append([{"text": "❌ Отменить встречу", "callback_data": f"ivx:{callback_id}"}])
    return {"inline_keyboard": rows}


def build_change_status_keyboard(callback_id: str, current: str = "wait") -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for key, label in CHAT_STATUS_BUTTONS:
        text = f"• {label}" if key == current else label
        row.append({"text": text, "callback_data": f"cs:{callback_id}:{key}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "↩️ Отмена", "callback_data": f"ccl:{callback_id}"}])
    return {"inline_keyboard": rows}


def build_interview_date_keyboard(callback_id: str, *, days: int = 14) -> dict[str, Any]:
    weekday = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
    start = datetime.now(_tz()).date()
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        label = f"{weekday[day.weekday()]} {day.strftime('%d.%m')}"
        row.append(
            {
                "text": label,
                "callback_data": f"ivd:{callback_id}:{day.strftime('%Y%m%d')}",
            }
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "↩️ Отмена", "callback_data": f"ivc:{callback_id}"}])
    return {"inline_keyboard": rows}


def build_interview_time_keyboard(callback_id: str, date_token: str) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for slot in build_time_slots():
        row.append(
            {
                "text": slot,
                "callback_data": f"ivt:{callback_id}:{date_token}:{slot.replace(':', '')}",
            }
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            {"text": "↩️ Назад", "callback_data": f"ivi:{callback_id}"},
            {"text": "✖️ Отмена", "callback_data": f"ivc:{callback_id}"},
        ]
    )
    return {"inline_keyboard": rows}


def build_interview_format_keyboard(
    callback_id: str, date_token: str, time_token: str
) -> dict[str, Any]:
    base = f"ivf:{callback_id}:{date_token}:{time_token}"
    return {
        "inline_keyboard": [
            [
                {"text": "🏢 В офисе", "callback_data": f"{base}:o"},
                {"text": "💻 Удалённо", "callback_data": f"{base}:r"},
            ],
            [{"text": "🏢+💻 Оба", "callback_data": f"{base}:b"}],
            [
                {"text": "↩️ Назад", "callback_data": f"ivd:{callback_id}:{date_token}"},
                {"text": "✖️ Отмена", "callback_data": f"ivc:{callback_id}"},
            ],
        ]
    }


def parse_interview_date_token(date_token: str) -> str:
    return datetime.strptime(date_token, "%Y%m%d").strftime("%Y-%m-%d")


def parse_interview_time_token(time_token: str) -> str:
    return datetime.strptime(time_token, "%H%M").strftime("%H:%M")


def interview_format_flags(flag: str) -> tuple[bool, bool]:
    """Returns (remote, office)."""
    if flag == "r":
        return True, False
    if flag == "b":
        return True, True
    return False, True
