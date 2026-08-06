"""Minimal HTML pages for Bitrix decision links (no frontend required)."""

from __future__ import annotations

import html


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 32rem;
           margin: 2rem auto; padding: 0 1rem; line-height: 1.45; color: #1a1a1a; }}
    .ok {{ color: #0a7a3e; }}
    .err {{ color: #b00020; }}
    label {{ display: block; margin: 0.75rem 0 0.25rem; font-weight: 600; }}
    input, select {{ width: 100%; font: inherit; padding: 0.5rem; box-sizing: border-box; }}
    textarea {{ width: 100%; min-height: 5rem; font: inherit; padding: 0.5rem; box-sizing: border-box; }}
    button {{ margin-top: 0.75rem; padding: 0.55rem 1rem; font: inherit; cursor: pointer; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }}
    .muted {{ color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def success_html(*, name: str, status_label: str, meeting_when: str | None = None) -> str:
    meeting_line = ""
    if meeting_when:
        meeting_line = f"<p>Встреча: <b>{html.escape(meeting_when)}</b></p>"
    return _page(
        "Статус сохранён",
        f"""
  <h1 class="ok">Статус сохранён</h1>
  <p>Кандидат: <b>{html.escape(name or "—")}</b></p>
  <p>Решение: <b>{html.escape(status_label)}</b></p>
  {meeting_line}
  <p class="muted">Можно закрыть эту вкладку и вернуться в Bitrix24.</p>
""",
    )


def comment_form_html(*, name: str, status_label: str, token: str) -> str:
    t = html.escape(token)
    return _page(
        "Комментарий к решению",
        f"""
  <h1>Комментарий</h1>
  <p>Кандидат: <b>{html.escape(name or "—")}</b></p>
  <p>Статус: <b>{html.escape(status_label)}</b></p>
  <p class="muted">Кратко укажите причину — без комментария статус не сохранится.</p>
  <form method="post" action="/integrations/bitrix/decide">
    <input type="hidden" name="t" value="{t}"/>
    <label for="comment">Комментарий</label>
    <textarea id="comment" name="comment" required maxlength="2000"></textarea>
    <button type="submit">Сохранить решение</button>
  </form>
""",
    )


def meeting_form_html(*, name: str, status_label: str, token: str) -> str:
    t = html.escape(token)
    return _page(
        "Назначить встречу",
        f"""
  <h1>Назначить встречу</h1>
  <p>Кандидат: <b>{html.escape(name or "—")}</b></p>
  <p>Решение: <b>{html.escape(status_label)}</b></p>
  <p class="muted">Укажите дату, время и формат — без этого встреча не сохранится.</p>
  <form method="post" action="/integrations/bitrix/decide">
    <input type="hidden" name="t" value="{t}"/>
    <div class="row">
      <div>
        <label for="meeting_date">Дата</label>
        <input id="meeting_date" name="meeting_date" type="date" required/>
      </div>
      <div>
        <label for="meeting_time">Время</label>
        <input id="meeting_time" name="meeting_time" type="time" required/>
      </div>
    </div>
    <label for="meeting_format">Формат</label>
    <select id="meeting_format" name="meeting_format" required>
      <option value="o">В офисе</option>
      <option value="r">Удалённо</option>
      <option value="b">Офис + удалённо</option>
    </select>
    <button type="submit">Сохранить встречу</button>
  </form>
""",
    )


def error_html(message: str) -> str:
    return _page(
        "Ошибка",
        f"""
  <h1 class="err">Не удалось сохранить</h1>
  <p>{html.escape(message)}</p>
  <p class="muted">Проверьте ссылку или обратитесь к HR.</p>
""",
    )
