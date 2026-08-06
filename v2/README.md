# hr_ai_agent v2 (MVP)

Параллельная версия приложения (Next.js + FastAPI + PostgreSQL).  
**Cutover 2026-08-03:** рабочая SoT — PostgreSQL + v2 UI; Streamlit/`bot.py` не запускать параллельно с v2 poller на том же токене. Откат: см. [CUTOVER.md](./CUTOVER.md).

## План реализации (актуально)

Пилот Timeweb (2–3 пользователя): **Bitrix + Web Client Zone** для заказчика; Telegram — optional (flag).  
Порядок: см. [`AUDIT.md`](./AUDIT.md) Волна D — D1–D4 **done** → **D5** Polish/deploy.

Auth: JWT httpOnly cookies; создать пользователя:
`cd backend && .venv/bin/python -m app.scripts.create_user --email you@example.com --password '…' --role platform_owner`

1. ~~Каркас, импорт, read UI, jobs~~  
2. ~~HH cold search (критерии, pre-filter, seen, shortlist)~~ — дожим по необходимости  
3. ~~HH shortlist → кандидат~~  
4. ~~Write path: этап / карточка / create / delete~~ (Calendar & warranty — позже; контакты HH — вручную)  
5. ~~Документы вакансии (редактор + PATCH merge)~~  
6. ~~Статистика: scope вакансии, HH efficiency, активность по периоду~~  
7. ~~Messaging Gateway slice 1: outbound карточка + stub webhook~~ → **slice 2: кнопки + inbound (`MESSAGING_INBOUND_ENABLED`)**  
8. ~~Я.Диск sync → resume/video/task в PG~~  
9. ~~Паритет slice 1: оценка по резюме + bulk PDF-ссылки~~  
10. ~~CRUD вакансий: создать / закрыть / reopen / удалить~~  
11. ~~Опросник на карточке кандидата (view/save/generate)~~  
12. ~~Паритет P0: оценка по интервью + автоген опросника после resume eval~~  
13. Дальше: smoke inbound → стабильный poller/webhook → cutover Messaging  
14. **Cutover** (см. [CUTOVER.md](./CUTOVER.md))

**Ссылки на резюме в карточке:** `hh_resume_link` = HH без контактов; `resume_link` = PDF на Яндекс.Диске. Синк папки вакансии: вкладка «Я.Диск» / `POST …/yandex-disk/sync` (пишет только в PG).

Целевая архитектура и таблица фаз: [`../ARCHITECTURE_TARGET.md`](../ARCHITECTURE_TARGET.md).

## Что есть в MVP

- PostgreSQL-схема (clients, vacancies, candidates, history, jobs)
- Импортёр snapshot `data/*.json` → PostgreSQL
- FastAPI API (`/api/v1/...`) + Redis/ARQ worker (фоновые задачи)
- Next.js UI (вакансии, история, статистика, задачи)
- Job `transcribe_media`: Яндекс.Диск → ffmpeg → SpeechKit (ключи из корневого `.env`)
- Job `hh_cold_search`: холодный поиск резюме HH + ИИ-оценка без открытия контактов
- Messaging Gateway **slice 2**: outbound с inline-кнопками; inbound webhook → PG (`MESSAGING_INBOUND_ENABLED`, по умолчанию off)
- **Telegram poller** (dev): `python -m app.workers.telegram_poller` или `docker compose --profile messaging up -d telegram-poller`
- Паритет: `POST …/evaluate-resume` + автоген опросника при первой оценке, bulk PDF-ссылки на вакансии
- Паритет: CRUD вакансий (`POST /vacancies`, close / reopen / delete)
- Паритет: опросник кандидата (GET/PUT + generate из шаблона вакансии)
- Паритет: `POST …/evaluate-interview` по резюме + первичной AI-оценке + опроснику/заметкам интервью
- Отдельный `docker-compose.yml` (порты 5433 / 6380 / 8000 / 3000)

## Что не трогает

- Корневой `docker-compose.yml` (hr-app, hr-bot)
- Рабочий `data/` (импортёр только **читает**)
- Telegram-бот и Streamlit-код

## Быстрый старт

```bash
cd v2
cp .env.example .env
docker compose up -d db
# API
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head   # baseline M1; предпочтительнее init_db
# Опционально после импорта старых данных / перед сменой схемы:
# python -m app.scripts.normalize_jsonb --dry-run
# python -m app.scripts.normalize_jsonb
python -m app.scripts.import_json --data-dir ../../data
uvicorn app.main:app --reload --port 8000
# Worker (другой терминал; нужен Redis на 6380)
set -a && source ../.env && set +a
arq app.workers.settings.WorkerSettings
# Telegram inbound без HTTPS (тестовый токен; не вместе с bot.py)
# В .env: MESSAGING_INBOUND_ENABLED=true, MESSAGING_POLL_ENABLED=true
python -m app.workers.telegram_poller
# UI (другой терминал)
cd ../frontend && npm install && npm run dev
```

Расшифровка: на `/jobs` вставьте ссылку и нажмите «Расшифровать». Нужны `YANDEX_*` в корневом `.env` и `ffmpeg` в PATH.

Или всё через Docker:

```bash
cd v2 && docker compose up --build
# inbound poller (опционально):
docker compose --profile messaging up -d telegram-poller
```

Cutover: см. [CUTOVER.md](./CUTOVER.md). Целевая архитектура: [`../ARCHITECTURE_TARGET.md`](../ARCHITECTURE_TARGET.md).
