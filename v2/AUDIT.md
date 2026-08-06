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

*Волны A–B закрыты (включая M9). M6 (split endpoints) закрыт. Следующее: Волна D по `ARCHITECTURE_TARGET.md` (auth, messaging multi-provider, SSE jobs, client-zone) или polish.*

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

### Волна C / D
Alembic discipline, auth/tenancy, messaging gateway, SSE jobs widget, client-zone — по `ARCHITECTURE_TARGET.md`.

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
