"""HTML card body for messaging providers (domain-agnostic text)."""

from __future__ import annotations

import html
from typing import Any

from app.services.messaging.keyboards import CLIENT_STATUS_META


def _esc(text: Any) -> str:
    return html.escape(str(text or "").strip())


def _client_https_url(url: str) -> str:
    from app.services.yandex_public import yandex_link_for_display

    display = (yandex_link_for_display(url) or "").strip()
    if display.startswith(("http://", "https://")):
        return display
    return ""


def _link(url: str, label: str) -> str | None:
    """HTML <a> only when URL is openable by the client (https)."""
    display = _client_https_url(url)
    if not display:
        return None
    return f'<a href="{_esc(display)}"><b>{_esc(label)}</b></a>'


def _format_label(remote: bool, office: bool) -> str:
    parts: list[str] = []
    if remote:
        parts.append("удалённо")
    if office:
        parts.append("офис")
    return ", ".join(parts)


def _split_client_comments(raw: str) -> tuple[list[str], list[str]]:
    """Split status-reason comments from free comments for card display."""
    status_lines: list[str] = []
    free_lines: list[str] = []
    for line in (raw or "").splitlines():
        text = line.strip()
        if not text:
            continue
        if "к статусу «" in text or 'к статусу "' in text:
            status_lines.append(text)
        else:
            free_lines.append(text)
    return status_lines, free_lines


def build_candidate_card_html(
    *,
    name: str,
    vacancy_title: str,
    resume_link: str | None = None,
    hh_resume_link: str | None = None,
    video_link: str | None = None,
    portfolio_link: str | None = None,
    task_link: str | None = None,
    hr_comment: str | None = None,
    locked: bool = False,
    status_key: str | None = None,
    client_comment: str | None = None,
    office_interview_date: str | None = None,
    office_interview_time: str | None = None,
    remote_interview: bool = False,
    office_interview: bool = False,
    meeting_hr_confirmed: bool = False,
    interview_prompt: str | None = None,
    interview_digest_url: str | None = None,
) -> str:
    lines = [
        "<b>🆕 Новый кандидат:</b>",
        "",
        f"<b>👤 {_esc(name)}</b>",
        "",
        f"<b>🏢 Вакансия:</b> {_esc(vacancy_title)}",
    ]
    resume = (resume_link or "").strip()
    hh = (hh_resume_link or "").strip()
    resume_row = _link(resume, "Резюме") if resume else None
    if resume_row:
        lines.extend(["", f"📄 {resume_row}"])
    else:
        hh_row = _link(hh, "Резюме HH") if hh else None
        if hh_row:
            lines.extend(["", f"📄 {hh_row}"])
    digest_url = (interview_digest_url or "").strip()
    digest_row = _link(digest_url, "Выжимка собеседования") if digest_url else None
    if digest_row:
        lines.extend(["", f"📝 {digest_row}"])
    video = (video_link or "").strip()
    video_row = _link(video, "Запись собеседования") if video else None
    if video_row:
        lines.extend(["", f"🎥 {video_row}"])
    portfolio = (portfolio_link or "").strip()
    portfolio_row = _link(portfolio, "Портфолио кандидата") if portfolio else None
    if portfolio_row:
        lines.extend(["", f"🎨 {portfolio_row}"])
    task = (task_link or "").strip()
    task_row = _link(task, "Выполненное задание") if task else None
    if task_row:
        lines.extend(["", f"✅ {task_row}"])
    comment = (hr_comment or "").strip()
    if comment:
        lines.extend(["", "<b>Комментарий HR:</b>", _esc(comment)])

    if locked and status_key:
        meta = CLIENT_STATUS_META.get(status_key) or CLIENT_STATUS_META["wait"]
        lines.extend(["", f"<b>Текущий статус:</b> {meta['icon']} {meta['label']}"])
        date_str = (office_interview_date or "").strip()
        time_str = (office_interview_time or "").strip()
        if date_str and time_str and status_key in ("ready", "offer", "started"):
            fmt = _format_label(remote_interview, office_interview)
            when = f"{date_str} {time_str}"
            fmt_part = f" ({fmt})" if fmt else ""
            lines.append(f"<b>Встреча:</b> {when}{fmt_part}")
            if meeting_hr_confirmed:
                lines.append("✅ Встреча подтверждена HR")
            else:
                lines.append("⏳ Ожидает подтверждения HR")
        client_c = (client_comment or "").strip()
        if client_c:
            status_lines, free_lines = _split_client_comments(client_c)
            if status_lines:
                lines.extend(["", "<b>Комментарий к статусу:</b>"])
                lines.extend(_esc(line) for line in status_lines)
            if free_lines:
                lines.extend(["", "<b>Комментарий:</b>"])
                lines.extend(_esc(line) for line in free_lines)
            if not status_lines and not free_lines:
                lines.extend(["", f"<b>Комментарий:</b> {_esc(client_c)}"])
        if interview_prompt:
            lines.extend(["", interview_prompt])
    elif not locked:
        lines.extend(["", "👇 <i>Выберите статус кнопками ниже</i>"])

    lines.extend(["", "<i>Отправлено из HR AI Agent v2</i>"])
    return "\n".join(lines)


def validate_send_fields(*, name: str, resume_link: str | None, hh_resume_link: str | None) -> list[str]:
    missing: list[str] = []
    if not (name or "").strip():
        missing.append("ФИО")
    if not (resume_link or "").strip() and not (hh_resume_link or "").strip():
        missing.append("Ссылка на резюме (PDF или HH)")
    return missing
