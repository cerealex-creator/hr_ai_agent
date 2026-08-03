# Cutover: Streamlit → v2

Переключение **только по явному решению и только после полной готовности v2**.  
До cutover рабочая система — Streamlit + JSON + Telegram (заказчик реагирует в мессенджере).

## Принципы

1. **Нет dual-write.** Пока Streamlit пишет в `data/`, PostgreSQL — копия для проверки / параллельной разработки, не источник истины.
2. **Откат = снова Streamlit.** `data/` не удаляем и не перезаписываем из v2 до (и сразу после) cutover без snapshot.
3. Импортёр **только читает** `data/`.
4. **Auth / роли в UI не блокер cutover** на текущем этапе (один оператор; заказчик — в Telegram).
5. **Актуальность данных:** cutover только из свежего snapshot после остановки записи в JSON; сверка счётчиков и выборочных карточек обязательна. Не переключаться «на глаз», если PG отстаёт от боевого `data/`.

## Когда можно cutover

- [x] Write path закрывает нужные сценарии HR (кандидаты, этапы; документы — ещё нет)
- [x] HH-поиск → shortlist → кандидат (базовый путь; открытие контактов — отдельно)
- [x] Messaging: outbound с кнопками + inbound в PG (флаг; боевой перехват — в день cutover)
- [x] Регресс по боевым вакансиям пройден
- [x] План отката и snapshot согласованы

## Чеклист cutover

### Подготовка (можно заранее, без остановки работы)

- [x] `cd v2 && docker compose up -d db`
- [x] Применить схему (`alembic upgrade head` или `python -m app.db.init_db`)
- [x] Пробный импорт: `cd backend && python -m app.scripts.import_json --data-dir ../../data --replace`
- [x] Сверить счётчики: `python -m app.scripts.import_json --verify-only` + `/api/v1/stats/import`
- [x] Сверить вручную 5–10 карточек (этап, статус, ссылки, `telegram_posts` → `messaging_posts`)
- [x] Открыть UI `:3000` и API `/api/v1/health`, `/api/v1/vacancies`

### День переключения

1. ~~Остановить запись в JSON~~ — Streamlit/`bot.py` уже были остановлены (2026-08-03).
2. ~~Snapshot~~ — `data_snapshot_20260803/` (без `*.webm`).
3. ~~Финальный импорт~~ — `--replace` из snapshot: 8 clients / 11 vac / 99 cand / 36 posts.
4. ~~Сверка~~ — verify-only совпал с PG.
5. ~~API/UI~~ — `:8000` / `:3000` up.
6. ~~Боевой токен~~ — v2 `TELEGRAM_BOT_TOKEN` = prod; poller `@hr_yourboxBot`; inbound+poll on.
7. **Не удалять** `data/` / `data_snapshot_20260803/` минимум N дней.

**Статус:** cutover выполнен 2026-08-03. SoT = PostgreSQL + v2 UI. Streamlit не запускать параллельно с poller на том же токене.

### Откат

1. Остановить v2 (API/UI/poller) и `cd v2 && docker compose down` при необходимости.
2. Запустить Streamlit + `bot.py` из **snapshot** `data_snapshot_YYYYMMDD/` (или текущего `data/`, если не трогали).
3. Вернуть привычный URL Streamlit. PG можно оставить — это копия, не источник истины до следующего cutover.

### Как сверить счётчики

```bash
cd v2/backend && source .venv/bin/activate
python -m app.scripts.import_json --verify-only
# Сравнить с JSON:
# clients ≈ departments.json
# vacancies/candidates ≈ vacancies_db.json
# messaging_posts ≈ число записей telegram_posts у кандидатов
# document_generations ≈ файлов в data/history (без index.json)
```

Открыть `/api/v1/stats/import` или главную UI. Выборочно: 5–10 кандидатов — ФИО, `hr_stage`, `client_status`, resume/video links.

## Что импортируется сейчас

| Источник | Таблица v2 |
|----------|-----------|
| `departments.json` | `clients` |
| `chats_db.json` | `messaging_channels` |
| `vacancies_db.json` → vacancies | `vacancies` |
| `vacancies_db.json` → candidates | `candidates` |
| `candidates[].telegram_posts` | `messaging_posts` (+ channel при необходимости) |
| `data/history/*.json` | `document_generations` (`vacancy_id`/`client_id` по title, если однозначно) |
| `vacancy_templates.json` | `vacancy_templates` |

`--replace` также очищает `messaging_actions`, `hh_shortlist_items`, `hh_seen_resumes`.

Статистика воронки в v2 строится из тех же кандидатов/этапов после импорта.

## Пока не обязательно для cutover

- Auth / RLS / веб-кабинет заказчика (заказчик остаётся в мессенджере)
- Полный multi-tenant

## Ещё нужно до cutover (ориентир)

- Write API из Next.js (паритет сценариев)
- Messaging Gateway (бот через API, не в обход)
- Паритет критичных сценариев со Streamlit
