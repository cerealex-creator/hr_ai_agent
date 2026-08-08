# Аудит v2 — findings и план волн

Дата: 2026-08-06  
Область: `v2/backend`, `v2/frontend`, сверка с `ARCHITECTURE.md` / `ARCHITECTURE_TARGET.md`.

---

## Соображения / уточнения к ТЗ

1. **Q1 + `ai_error_logs` / Alembic (M1)**  
   Таблицы Wave A сначала поднимались через `create_all` при старте API. После **M1** источник схемы — `alembic upgrade head` (ревизия `d22a995b8f9c`). `create_all` в lifespan оставлен как safety net для локального bootstrap. В `ai_error_logs` — **санитизированный** сырой ответ (без телефонов/email), усечённый; не полный промпт с резюме.

2. **Q12 Truncation 12 000**  
   Сейчас по отдельности profile≤5000 + resume≤8000 ≈ 13 000. Обрезаем **суммарный user-контент** (и крупные поля) до **12 000** символов перед вызовом LLM — иначе лимит на поле не спасает от суммарного overflow.

3. **Q8 + offset poller**  
   Идемпотентность callback’ов бессмысленна, если update теряется при ошибке. Поэтому в Волне A вместе с Q8: сдвиг `offset` **после** успешной обработки (не до).

4. **Не в Волне A (осознанно):** auth API, HH token persist, circuit breaker — Волны B/D.

---

## Этап 1 — Backend Critical / Warning / Info

### Critical
| ID | Проблема |
|----|----------|
| C1 | Нет Alembic-ревизий (`create_all` only) |
| C2 | API без auth |
| C3 | `delete_candidate` без cleanup messaging → FK |
| C4 | `delete_vacancy` не чистит `inbox_items` |
| C5 | Битый JSON ИИ → rating 0 → бан HH seen |
| C6 | Telegram callbacks без идемпотентности; offset до process |
| C7 | HH refresh token только in-memory |
| C8 | SpeechKit poll без deadline; S3 PCM не удаляется |

### Warning / Info
См. исходный аудит-сессию: tenancy декоративна, Job↛Candidate FK, session в `to_thread`, нет HH 429, Yandex 403→None, god `endpoints.py`, CORS, timestamps как String.

---

## Этап 2 — UX (кратко)

P0: redirect create→docs; next-action strip; filter/attention list; candidates inbox; `loading.tsx`.  
P1: conflicts/jobs labels; compact stage rail; messaging timeline.  
P2: gen flags; Bitrix on card; client-zone.

---

## Этап 3 — Интеграции

AI silent `{}`; HH 429/token; Telegram idempotency; SpeechKit bound; unify parsers.

---

## Волны

### Волна A — Quick Wins (этот спринт)

| ID | Задача | Статус |
|----|--------|--------|
| Q1 | Битый JSON → error + `ai_error_logs`; не банить в HH | **done** |
| Q2 | SpeechKit max deadline | **done** |
| Q3 | `delete_candidate` + messaging cleanup | **done** |
| Q4 | `delete_vacancy` + inbox cleanup | **done** |
| Q8 | Callback idempotency + offset after success | **done** |
| Q6 | После create → `?section=docs` + empty CTA | **done** |
| Q7 | JOB_TYPE_LABELS для всех ARQ types | **done** |
| Q9 | Pause 0.4s между HH eval | **done** |
| Q10 | `loading.tsx` на ключевых маршрутах | **done** |
| Q11 | Санитизация ПДн в логах | **done** |
| Q12 | Truncation входа ИИ ≤ 12 000 | **done** |

*Волны A–C закрыты. Следующее: **Волна D (пилот Timeweb, 2–3 пользователя)** — порядок D1→D5 ниже.*

### Волна B — Среднесрочные

| ID | Задача | Статус |
|----|--------|--------|
| **M11** | JSONB normalize (missing keys) перед Alembic | **done** |
| **M1** | Alembic baseline `d22a995b8f9c` | **done** |
| M2 | Единый AI JSON repair | **done** |
| M3 | HH token persist | **done** |
| M4 | HH 429 backoff | **done** |
| M5 | Thread-safe job sessions | **done** |
| M6 | Split endpoints | **done** |
| M7 | UX next-action / inbox | **done** |
| M8 | HH job dedup | **done** |
| M9 | Pydantic schemas tighten | **done** |
| M10 | S3 cleanup after STT | **done** |

### Волна C
M6 split endpoints + M9 Pydantic — **done**.

### Волна D — Пилот (Timeweb, 2–3 пользователя)

**Контекст пилота (зафиксировано 2026-08-06):**
- Цель: деплой → обратная связь / отзыв → возможная продажа в компанию заказчика.
- Каналы для заказчика: **Bitrix + Web Client Zone**.
- Telegram: код остаётся; для клиентов **feature flag off**; опционально только внутренние уведомления рекрутеру.
- Формат работы: **Бриф → Одобрение → Код** (без кода до «одобрить»).
- RLS Postgres **не** в D1; жёсткая изоляция по `org_id` — в **D2**.

| ID | Этап | Статус | Суть |
|----|------|--------|------|
| **D1** | Auth | **done** | JWT + таблицы `users` / memberships; защита API; login UI. Без RLS. |
| **D2** | Tenancy + Client zone | **done** | Жёсткая изоляция данных по `org_id`; web-зона заказчика (token URL). |
| **D3** | Bitrix + Telegram flag | **done** | Bitrix + web default; provider registry; TG gated; Bitrix test task. |
| **D4** | SSE jobs widget | **done** | Same-origin rewrite; SSE poll DB; topbar badge + toast. |
| **D5** | Polish / deploy | **done** | Fail-fast prod; compose.prod + nginx; DEPLOY.md; empty DB + bootstrap. |

### Волна E — UI polish перед пилотом | **done**
Ребрендинг HR-помогатор; быстрый доступ Zoom/Телемост/Диск; RBAC settings; editable title; manual questionnaire + merge.

См. детальный бриф текущего этапа в конце файла / в чате.

---

## Отчёты Волна A

### Q1 — Битый JSON / ai_error_logs / без HH-бана
**Что:** при отсутствии/битом JSON `evaluate_resume_text` пишет в `ai_error_logs` (санитизированный raw) и **raises**; `mark_ai_low_scores` пропускает строки с `error`/`parse_error`.  
**Файлы:** `db/models.py` (`AiErrorLog`), `services/ai_errors.py`, `services/resume_eval.py`, `services/hh_seen.py`, `services/ai_json.py` (логирует empty parse), `main.py` (`create_all`).  
**Проверка:** перезапустить API; вызвать оценку с мок-ответом без JSON → job/entry `error`, в БД строка `ai_error_logs`, резюме **не** появляется в `hh_seen_resumes` с `ai_low`.

### Q2 — SpeechKit deadline
**Что:** `recognize_long_audio(..., max_wait_seconds=900)` — выход по таймауту ~15 мин.  
**Файл:** `services/transcription.py`  
**Проверка:** unit — нет hang; интеграционно — длинная операция > deadline → RuntimeError с текстом ожидания.

### Q3 — delete_candidate + messaging
**Что:** перед удалением кандидата чистятся `MessagingAction` → `MessagingPost`.  
**Файл:** `services/candidate_write.py`  
**Проверка:** кандидат с Telegram-постом → DELETE `/candidates/{id}` → 204, без IntegrityError.

### Q4 — delete_vacancy + inbox
**Что:** `DELETE FROM inbox_items WHERE vacancy_id=…` перед кандидатами.  
**Файл:** `services/vacancy_write.py`  
**Проверка:** вакансия с inbox row → delete vacancy OK.

### Q8 — Idempotency + offset
**Что:** таблица `processed_messaging_updates`; повторный `callback_query.id` → «Уже обработано»; same-status no-op; poller сдвигает `offset` только после успешного process.  
**Файлы:** `models.py`, `messaging/idempotency.py`, `messaging/inbound.py`, `workers/telegram_poller.py`  
**Проверка:** дважды тот же callback (или retry update) — один side-effect; при exception process offset не растёт.

### Q11 — Санитизация логов
**Что:** `log_sanitize.sanitize_text` маскирует email/phone; poller events, job `error`, AI HTTP errors проходят через sanitize.  
**Файлы:** `services/log_sanitize.py`, `workers/tasks.py`, `workers/telegram_poller.py`, `ai_json.py`, `resume_eval.py`, `ai_errors.py`  
**Проверка:** `sanitize_text('a@b.ru +79001112233')` → `[email] [phone]`.

### Q12 — Truncation 12 000
**Что:** `MAX_AI_INPUT_CHARS=12000`; `truncate_ai_input` в `chat_json` и суммарный user в `resume_eval`.  
**Файлы:** `services/ai_json.py`, `services/resume_eval.py`  
**Проверка:** resume+profile > 12k → в запрос уходит ≤ 12000 символов user content.

### Q6 — Redirect после создания вакансии
**Что:** `router.push(/vacancies/{id}?section=docs)`; на пустом профиле CTA «С чего начать».  
**Файлы:** `CreateVacancyForm.tsx`, `DocumentsEditor.tsx`  
**Проверка:** создать вакансию → открывается вкладка Документы с подсказкой.

### Q7 — Job type labels
**Что:** добавлены `disk_inbox_router`, `vacancy_docs_from_materials`.  
**Файл:** `app/jobs/page.tsx`  
**Проверка:** `/jobs` показывает русские названия для всех типов из WorkerSettings.

### Q9 — HH pause между оценками
**Что:** `await asyncio.sleep(0.4)` между resume eval в cold search.  
**Файл:** `workers/tasks.py`  
**Проверка:** HH job с несколькими оценками — пауза в логах/времени между шагами.

### Q10 — Route loading
**Что:** `loading.tsx` + CSS skeleton для vacancies, vacancy detail, candidates, jobs, stats.  
**Файлы:** `app/**/loading.tsx`, `globals.css`  
**Проверка:** медленная сеть / soft navigation — виден скелетон «Загрузка…».

---

## Отчёты Волна B (начало)

### M11 — JSONB normalize
**Что:** deep-fill missing keys в `Candidate.payload`, `Vacancy.documents`, `Vacancy.payload` (не перезаписывает существующие значения).  
**Файлы:** `services/jsonb_defaults.py`, `scripts/normalize_jsonb.py`  
**Проверка:**
```bash
cd v2/backend && set -a && source ../.env && set +a
python -m app.scripts.normalize_jsonb --dry-run
python -m app.scripts.normalize_jsonb
```
На локальной БД применено: candidates=99, vacancies documents/payload=12.

### M1 — Alembic baseline
**Что:** ревизия `d22a995b8f9c` — `Base.metadata.create_all` + недостающие индексы `clients`.  
**Файлы:** `alembic/versions/d22a995b8f9c_baseline_v2_schema.py`, `README.md`, `main.py` (комментарий)  
**Проверка:** `alembic upgrade head` → `alembic current` показывает `d22a995b8f9c (head)`.

### M2 — Единый AI JSON repair
**Что:** в `parse_ai_json` перенесён repair из legacy `ai_helpers` (fence/think, trailing commas, missing commas, newlines в строках, truncated close, unquoted keys, `literal_eval`). `resume_eval` и `hh_criteria_prefill` ходят через `chat_json` (без локальных `_parse_json` / дублирующих HTTP).  
**Файлы:** `services/ai_json.py`, `services/resume_eval.py`, `services/hh_criteria_prefill.py`  
**Проверка:** unit — trailing comma / missing commas / fences → dict; пустой мусор → `{}`.

### M3 — HH token persist
**Что:** `data/hh_oauth.json` (приоритет над `.env`); после refresh пишем access + новый refresh; in-memory Settings обновляется. Cold search job — один `HhClient` на поиск+оценку. `hh_oauth.py` тоже пишет файл.  
**Файлы:** `services/hh_tokens.py`, `services/hh_client.py`, `workers/tasks.py`, `scripts/hh_oauth.py`  
**Проверка:** refresh → файл обновлён; рестарт worker без правки `.env` продолжает работать с файловым токеном.

### M4 — HH 429 backoff
**Что:** при `429` — sleep по `Retry-After` (cap 90s) или exponential `2^attempt`; до 5 повторов, затем ошибка.  
**Файл:** `services/hh_client.py`  
**Проверка:** unit `_wait_seconds_for_429`; при реальном 429 в логах `HH 429 … sleep`.

### M5 — Thread-safe job Session
**Что:** `update_job_isolated` / `is_cancelled_isolated` — своя Session на вызов. Progress/cancel callbacks в `transcribe_media` и `candidate_interview_process` больше не шарят Session async-воркера с `to_thread`.  
**Файлы:** `services/jobs.py`, `workers/tasks.py`  
**Проверка:** длинная расшифровка + cancel из UI — прогресс обновляется без SQLAlchemy thread errors.

### M8 — HH job dedup
**Что:** повторный `POST /jobs` `hh_cold_search` при активном queued/running по той же вакансии → `reused=true` (как interview).  
**Файлы:** `services/jobs.py` (`find_active_job_for_vacancy`), `api/v1/endpoints.py`  
**Проверка:** два старта поиска подряд → один job id.

### M10 — S3 cleanup после STT
**Что:** после SpeechKit (успех/ошибка) `delete_s3_object` для PCM в `finally` (`transcribe_from_url` / `transcribe_from_path`).  
**Файл:** `services/transcription.py`  
**Проверка:** после job в бакете нет временного `.pcm`/`.wav` объекта.

### M7 — Next-action + attention inbox
**Что:** sticky «Следующий шаг» + авто-open секции в `CandidateEditor`; `/candidates` hub = список `preset=attention` (активные вакансии) + поиск.  
**Файлы:** `lib/nextAction.ts`, `CandidateEditor.tsx`, `candidates/page.tsx`, `candidate_query.py`, `schemas.py`, `globals.css`  
**Проверка:** кандидат без AI-оценки → strip «Оценить резюме»; `/candidates` показывает блок «Требуют внимания».

### M9 — Pydantic request bodies
**Что:** вместо `body: dict` — схемы `VacancySettingsPatchIn`, `AppSettingsPatchIn`, `OauthTokenIn`, HH soften/manual, messaging, history/template и др.  
**Файлы:** `schemas.py`, handlers в `api/v1/routes/*`  
**Проверка:** OpenAPI показывает typed requestBody; невалидный PATCH settings → 422.

### M6 — Split endpoints
**Что:** монолит `endpoints.py` (~3k) → `common.py` + `routes/{vacancies,hh,candidates,messaging,jobs,…}` + `router.py`; `endpoints.py` — тонкий re-export.  
**Файлы:** `app/api/v1/common.py`, `router.py`, `routes/*.py`, `endpoints.py`  
**Проверка:** `app.openapi()` содержит `/api/v1/health`, vacancies, hh-*, candidates (~98 paths).

---

## Волна D — брифы

### D1 — Auth (**done**)

**Проблема:** API/UI без входа — нельзя безопасно отдать пилот 2–3 людям.

**Сделано:**
- Таблицы `users`, `organization_members`, `refresh_tokens` + Alembic `a1b2c3d4e5f6`.
- JWT access (cookie `hr_access`) + refresh (`hr_refresh`, rotate); bcrypt passwords.
- `POST /auth/login|refresh|logout`, `GET /auth/me`; protected v1 router; public: health, auth login/refresh/logout, integrations webhook.
- `AUTH_DISABLED` only when `APP_ENV!=production`; bootstrap via `AUTH_BOOTSTRAP_*` or `python -m app.scripts.create_user`.
- Frontend: `/login`, `AuthGate`, `apiFetch` + credentials + SSR cookie forward, logout in shell.

**Файлы:** `core/auth.py`, `services/users.py`, `api/v1/routes/auth.py`, `router.py`, `models.py`, `alembic/versions/a1b2c3d4e5f6_*`, frontend `lib/api.ts`, `AuthGate`, `login/page.tsx`

**Не в D1:** RLS, org data filtering (→ D2), client-zone invites.

### D2 — Tenancy + Client zone (бриф, код после одобрения)

**Проблема:** после D1 любой залогиненный HR видит **все** clients/vacancies/candidates в БД. Для пилота с несколькими компаниями (и позже продажи) утечка между организациями недопустима. Параллельно нужна **веб-зона заказчика** (без Telegram на Timeweb).

**Требования (два слоя):**

**Слой A — изоляция организации (`org_id`) — обязательно**
- Все list/get/write по `clients`, `vacancies`, `candidates`, `jobs` (где есть client/vacancy), `document_generations`, messaging channels, inbox, HH shortlist/seen — только сущности своей org.
- Цепочка: `Candidate → Vacancy.client_id → Client.organization_id == AuthUser.org_id` (аналогично для vacancy-less? не допускать orphan вне org).
- Create client/vacancy всегда с `organization_id` текущего пользователя.
- IDOR: запрос чужого `vacancy_id` / `candidate_id` → **404** (не 403), чтобы не светить существование.
- `platform_owner` и `hr_recruiter` в D2: **вся org** (урезание recruiter по назначенным вакансиям — опционально позже, не блокер пилота).
- Без Postgres RLS (как договорились); фильтры в сервисах + единый helper `assert_org_*`.

**Слой B — Client zone (веб для заказчика)**
- Роль `hiring_manager` (или доступ по invite-токену без полноценного HR-логина — см. неоднозначности).
- UI: `/client-zone` (или `/c/[token]`) — список кандидатов «на стороне клиента» по своему `client_id` (+ дочерние departments?), действия: approve / reject / comment / meeting (паритет с Bitrix decide, без HR-полей: телефоны HR-only).
- Уже есть `Client.client_zone_token` — использовать или заменить на `invitations` / `client_memberships`.
- HR в настройках компании: «Ссылка / сброс токена клиентской зоны».
- Заказчик **не** видит: настройки, HH, jobs, чужих клиентов org, ПДн сверх необходимого для решения.

**Неоднозначности:**
1. Вход заказчика: **A)** magic link / пароль + `client_memberships`, **B)** только секретный URL `?token=` / `/c/{token}` без отдельного user (быстрее к пилоту), **C)** оба.
2. Scope зоны: один token на **компанию (root client)** или на каждый department?
3. Действия в зоне в D2: полный паритет Bitrix decide или минимум approve/reject/comment?
4. `hr_recruiter` видит всю org или только назначенные vacancies? (рекомендация пилота: **вся org**, как owner).
5. Jobs без `client_id`: показывать только jobs, связанные с vacancy своей org; demo jobs — только своей сессии/org metadata?

**Риски:**
- Пропустить один list-endpoint без фильтра → утечка.
- Token в URL утекает через Referer/логи — для B нужен httpOnly session после первого захода или короткий TTL.
- Смешать «клиент» (company) и «organization» в коде/API.
- Client zone write без тех же stage-machine правил, что Bitrix → рассинхрон статусов.

**План (после «одобрить»):**
1. `tenancy.py`: helpers resolve/filter/assert org; пройти list/get/write routes.
2. Миграция при необходимости: `client_memberships` / invitations; роль `hiring_manager`.
3. API client-zone (read candidates + apply decision) + UI `/client-zone` или `/c/[token]`.
4. HR: показать/ротировать `client_zone_token` в карточке компании.
5. Не трогаем: RLS, SSE (D4), Telegram flags (D3), полный multi-provider messaging.

**Acceptance:**
- User org1 не получает clients/vacancies org2 (пустой list / 404 по id).
- Client zone token org1 не открывает кандидатов org2 / другого client.
- Health и auth без регрессии; Bitrix webhook по-прежнему public.

### D2 — Tenancy + Client zone (**done**)

**Решения:** token URL (без логина заказчика); token на root-компанию (+ departments); действия ready/think/reject + встреча; recruiter = вся org; jobs через vacancy→org.

**Сделано:**
- `services/tenancy.py` + request ContextVar middleware; `get_*_or_404` на routes.
- Org filter: vacancies/clients/candidates/search/stats/history/jobs/messaging channels.
- Public `GET/POST /api/v1/client-zone/{token}…`; UI `/c/[token]`; HR rotate в CompanyEditor.
- AuthGate пропускает `/c/*`.

**Файлы:** `tenancy.py`, `client_zone.py`, `routes/client_zone.py`, `main.py` middleware, routes/*, `CompanyEditor`, `app/c/[token]/page.tsx`

### D3 — Bitrix + Telegram flag (**done**)

**Решения (одобрено):** UI из реестра провайдеров (TG серый если blocked + WhatsApp/Max stubs); HR-notify только при outbound+`TELEGRAM_HR_USER_ID`; migrate channels → `["bitrix","web"]`; smoke test Bitrix.

**Сделано:**
- `MessagingProvider` + `providers/registry.py` (bitrix/web/telegram/whatsapp/max).
- Default + lifespan migrate `client_notify` → bitrix+web; gateway dispatch через registry.
- Settings UI: provider tiles, checklist, «Отправить тестовую задачу».
- HR notify gated via `telegram_hr_notify_allowed()`.

**Acceptance:**
- Свежий settings: заказчику по умолчанию Bitrix+web, не Telegram.
- `client_notify` без telegram → send-to-chat не дергает Telegram API.
- Bitrix enabled + webhook → карточка/задача уходит; decide HTML жив.
- Inbound/poller off на Timeweb без ошибок в логах.

**Файлы:** `messaging/providers/*`, `gateway.py`, `app_settings.py`, `routes/settings.py`, `bitrix/outbound.py`, `frontend/.../bitrix/page.tsx`, `hr_notify.py`

### D4 — SSE jobs widget (**done**)

**Решения (одобрено):** Next rewrite same-origin; SSE poll Postgres ~1.5s; badge + toast; pollers не трогаем.

**Сделано:**
- `GET /api/v1/events/stream` — org-scoped jobs, snapshot / job.updated / ping, `X-Accel-Buffering: no`.
- Next `rewrites` `/api/v1/*` → backend; browser `getApiBase()=""`.
- `JobsLiveProvider` + topbar badge + toast; skip `/login` и `/c/*`.

**Acceptance:**
- Залогинен → SSE жив; demo job обновляет badge без `/jobs`.
- Complete/fail → toast; `/c/*` и login без SSE.

**Файлы:** `routes/events.py`, `router.py`, `next.config.js`, `lib/api.ts`, `JobsLive.tsx`, `AppShell.tsx`, `layout.tsx`, `globals.css`, `docker-compose.yml`

### D5 — Polish / deploy (**done**)

**Решения (одобрено):** один домен + Next rewrite; compose.prod + nginx; пустая БД + bootstrap owner; пример nginx TLS в репо.

**Сделано:**
- Fail-fast: `APP_ENV=production` → сильный `JWT_SECRET` + `AUTH_COOKIE_SECURE`.
- `docker-compose.prod.yml`, `deploy/nginx.conf`, `.env.production.example`, `DEPLOY.md`.
- Login hint «Нет аккаунта?…»; API Dockerfile → `alembic upgrade head`.

**Acceptance:**
- С `APP_ENV=production` и слабым JWT API не стартует.
- По runbook: compose.prod + TLS → login owner (bootstrap).
- Telegram outbound off в prod-примере; Bitrix+web — каналы пилота.

**Файлы:** `core/startup.py`, `main.py`, `Dockerfile`, `docker-compose.prod.yml`, `deploy/*`, `DEPLOY.md`, `.env.production.example`, `login/page.tsx`
