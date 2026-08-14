# План реализации: ИИ-каскад (tier fast / top)

> **Кодовое слово запуска: `КАСКАД`**
>
> | Команда | Что делаем |
> |---------|------------|
> | **`КАСКАД`** или **`КАСКАД P1`** | Инфра: роутинг + логирование (baseline) |
> | **`КАСКАД P2`** | Двухстадийные evaluate_resume + interview_process |
> | **`КАСКАД P3`** | Остальные задачи + UI N7 |
> | **`КАСКАД P4`** | Сравнение baseline vs cascade, включение fast |
>
> Без **`КАСКАД`** — не трогаем. Учёт: [`BACKLOG.md`](BACKLOG.md) → **B-KASKAD-001**.  
> Связь с **ЯКОРЬ**: задачи `suggested_tags` (D3.1), `talent_pool_hh_match` (T4.1) — сразу в `task_map`.

**Статус:** план для ревью архитектора · код после **`КАСКАД P1`**.  
**Текущий ИИ:** один `chat_json()` → `resolve_ai_model_name()` → RouterAI (`ai_json.py`, N7 `/settings/ai`).

---

## 0. Замечания к брифу (учтены в плане)

| Бриф | Уточнение |
|------|-----------|
| HH prefilter (H2) → fast | **H2 — не LLM** (`hh_prefilter.py`, regex/правила). В `task_map` **не включаем**. LLM в HH: `hh_manual_eval`, `hh_search_plan`, `hh_criteria_prefill`, `hh_search_debrief`, cold-search eval (`resume_eval.py`). |
| Оффер «Дописать ИИ» | **fast + top**: fast — структурированные факты (ФИО, ЗП, даты, условия); top — финальный текст оффера. |
| `ai_usage_log` | Отдельно от `ai_error_logs` (ошибки парсинга уже есть). Usage — **каждый успешный** вызов + tier. |
| Baseline | **P1** включает логирование при **старой** схеме (всё top); **мин. 7 дней** или N≥30 jobs по ключевым task перед включением fast в P4. |

---

## 1. Фазы (порядок)

```mermaid
flowchart LR
  P1[P1 Роутинг + log baseline] --> P2[P2 Resume + Interview]
  P2 --> P3[P3 Остальное + UI N7]
  P3 --> P4[P4 Включить fast + сравнить]
```

**Почему не P2 раньше P1:** без `ai_route()` и `ai_usage_log` нет baseline и нет единой точки fallback.

| Фаза | Суть | Меняет качество? |
|------|------|------------------|
| **P1** | `ai_route`, конфиг, миграция `ai_usage_log`, все вызовы через router, tier=top | Нет |
| **P2** | Двухстадийные pipeline + `payload.resume_facts` / `interview_struct` | Да (экономия токенов) |
| **P3** | docs, inbox, HH LLM, offer, stats brief, N7 UI | Да |
| **P4** | Включить fast в task_map, дашборд сравнения, runbook отката | Да |

**Параллельность:** P3 задачи без общего pipeline (offer, stats) — параллельно после merge P1.

---

## 2. Схема конфига (`data/app_settings.json`)

Секция **`ai`** (рядом с `ai_model`, `ai_provider`):

```json
{
  "ai_model": "qwen/…",
  "ai_provider": { "id": "routerai", "label": "RouterAI", "console_url": "…" },
  "ai": {
    "cascade_enabled": false,
    "models": {
      "fast": "",
      "top_a": "",
      "top_b": ""
    },
    "task_map": {
      "resume_extract": "fast",
      "resume_eval": "top",
      "interview_transcript_cleanup": "fast",
      "interview_qa_extract": "fast",
      "interview_eval": "top",
      "interview_digest": "top",
      "questionnaire_generate": "top",
      "questionnaire_regenerate": "top",
      "questionnaire_fill_transcript": "fast",
      "vacancy_doc_facts": "fast",
      "vacancy_doc_profile": "top",
      "vacancy_doc_text": "top",
      "vacancy_doc_keywords": "fast",
      "vacancy_doc_questions": "top",
      "disk_inbox_route": "fast",
      "offer_ai_fill_facts": "fast",
      "offer_ai_fill_draft": "top",
      "stats_ai_brief": "top",
      "hh_criteria_prefill": "fast",
      "hh_search_plan": "fast",
      "hh_search_debrief": "top",
      "hh_manual_eval": "top",
      "hh_cold_eval": "top",
      "suggested_tags": "fast",
      "talent_pool_hh_match": "top",
      "message_draft": "fast"
    },
    "task_overrides": {
      "resume_extract": "top"
    },
    "pipeline": {
      "resume_eval": ["resume_extract", "resume_eval"],
      "interview_process": ["interview_transcript_cleanup", "interview_qa_extract", "interview_eval"],
      "vacancy_doc_section": ["vacancy_doc_facts", "vacancy_doc_profile"],
      "offer_ai_fill": ["offer_ai_fill_facts", "offer_ai_fill_draft"]
    },
    "fallback": {
      "fast_unavailable_to_top": true,
      "validate_retry_fast": 1,
      "validate_fail_escalate_to_top": true
    }
  }
}
```

### Правила резолва

1. `models.fast` пуст → **все task → top_a** (поведение как сейчас).
2. `cascade_enabled: false` → игнор `task_map`, всё top (P1 baseline).
3. `task_overrides[task]` перебивает `task_map`.
4. Tier `top` → `top_a`, при 429/5xx/timeout → **один** retry `top_b` (если задан).
5. Ошибка роутинга / unknown task → top + `log warning`.

---

## 3. Дефолтная карта задач (обоснование)

| Task key | Tier | Обоснование |
|----------|------|-------------|
| `resume_extract` | fast | Строгий JSON, факты из резюме |
| `resume_eval` | top | Качество секций A11 критично |
| `suggested_tags` | fast | 2–3 тега, дешёво (ЯКОРЬ D3.1) |
| `interview_transcript_cleanup` | fast | Чистка текста |
| `interview_qa_extract` | fast | Q&A пары JSON |
| `interview_eval` | top | A8 — сложный синтез |
| `interview_digest` | top | Выжимка для заказчика |
| `questionnaire_*` | top | A1/A3 — качество вопросов |
| `vacancy_doc_facts` | fast | Конспект фактов из materials |
| `vacancy_doc_*` (текст) | top | D2/D3 финальный prose |
| `vacancy_doc_keywords` | fast | Короткий вывод |
| `disk_inbox_route` | fast | Y4 routing JSON |
| `offer_ai_fill_facts` / `_draft` | fast / top | Структура → текст |
| `stats_ai_brief` | top | 22.x — аналитика для owner |
| `hh_criteria_prefill` | fast | Черновик критериев |
| `hh_search_plan` | fast | JSON план |
| `hh_search_debrief` | top | Итоговый разбор |
| `hh_manual_eval` / `hh_cold_eval` | top | = resume_eval |
| `talent_pool_hh_match` | top | 4.1 — confidence % |
| `message_draft` | fast | C5 черновики |

**Не в map (не LLM):** `hh_prefilter`, SpeechKit, ffmpeg, HH REST API.

---

## 4. RouterAI-клиент

### Новые модули

| Файл | Назначение |
|------|------------|
| `app/services/ai_route.py` | `resolve_tier(task)`, `resolve_model(tier)`, `chat_json_routed()` |
| `app/services/ai_schemas.py` | Pydantic-схемы fast-выходов per task |
| `app/services/ai_usage.py` | `log_ai_usage(db, …)` |
| `app/services/ai_facts_cache.py` | `get/set resume_facts`, hash `resume_text` |

### `chat_json_routed(settings, *, task, system, user, …, db, job_id=None)`

```
1. tier = resolve_tier(task)
2. model = resolve_model(tier)
3. t0 = now()
4. HTTP chat/completions (как сейчас)
5. parse usage из response.usage (prompt_tokens, completion_tokens)
6. log_ai_usage(…)
7. если task требует schema → validate pydantic
   - fail → retry fast (1x) → escalate top
8. return parsed
```

**`chat_json()`** — thin wrapper → `chat_json_routed(..., task="chat_json")` для обратной совместимости.

### Pipeline helper

```python
def run_pipeline(db, job_id, pipeline_name, ctx) -> dict:
    """resume_eval: extract → persist facts → eval with facts+excerpts only"""
```

Progress labels в job: «Извлечение фактов…» / «Оценка резюме…».

---

## 5. Конвейеры по фазам

### P2 — `candidate_evaluate_resume`

**Было:** один `chat_json` extract+eval смешано в `candidate_resume_eval.py`.  
**Станет:**

1. **fast** `resume_extract` → validate `ResumeFactsSchema` → `payload.resume_facts` + `payload.resume_facts_hash` (sha256 текста).
2. **top** `resume_eval` — prompt: profile + **JSON facts** + **≤3k chars excerpts** (не full resume).
3. **top** `suggested_tags` (если ЯКОРЬ D3 включён) — input: facts + eval summary.

**Кеш:** если `resume_facts_hash` совпадает — skip fast на повторном evaluate.

### P2 — `candidate_interview_process`

**Не трогаем:** ffmpeg, SpeechKit, S3.  
**Меняем LLM-части:**

1. **fast** `interview_transcript_cleanup` (было в `transcription.py`).
2. **fast** `interview_qa_extract` → `payload.interview_qa_pairs`.
3. **top** `interview_eval` (`candidate_interview_eval.py`) — facts + qa + questionnaire, не raw transcript wall.
4. **top** `interview_digest` — по qa + eval.

### P3 — `vacancy_docs_*`

1. **fast** `vacancy_doc_facts` из materials snapshot.
2. **top** section writer (profile/text/questions) — facts + correction prompt.
3. Job `vacancy_docs_from_materials` — progress по стадиям.

### P3 — прочее

- `disk_inbox_router` → task `disk_inbox_route` (fast).
- `offer_draft` → pipeline `offer_ai_fill`.
- `stats_ai_brief` → top only.
- HH LLM tasks — по map выше.

---

## 6. Миграции Alembic

Цепочка — **после head на момент старта КАСКАД** (не смешивать с ЯКОРЬ в одном PR без согласования).

### `h5k6a7s8k9a0` — P1

```sql
CREATE TABLE ai_usage_log (
  id UUID PRIMARY KEY,
  organization_id UUID REFERENCES organizations(id),
  job_id UUID REFERENCES jobs(id),
  task VARCHAR(64) NOT NULL,
  tier VARCHAR(16) NOT NULL,          -- fast | top_a | top_b | fallback_top
  model VARCHAR(128) NOT NULL,
  prompt_tokens INT,
  completion_tokens INT,
  latency_ms INT NOT NULL,
  pipeline VARCHAR(64),
  stage VARCHAR(64),
  meta JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_usage_org_created ON ai_usage_log (organization_id, created_at DESC);
CREATE INDEX ix_ai_usage_task_created ON ai_usage_log (task, created_at DESC);
```

### P2+ — без миграции

Факты в `candidate.payload`:

```json
{
  "resume_facts": { "full_name", "phone", "email", "skills", "companies", … },
  "resume_facts_hash": "sha256…",
  "resume_facts_at": "ISO",
  "interview_qa_pairs": [{ "q", "a", "speaker" }],
  "interview_struct_at": "ISO"
}
```

---

## 7. API и UI

### P1 — settings

| Метод | Путь | Контракт |
|-------|------|----------|
| `GET` | `/api/v1/settings/app` | + `ai: { models, task_map, cascade_enabled, … }` |
| `PATCH` | `/api/v1/settings/app` | owner: `ai.models`, `ai.task_map`, `ai.task_overrides`, `ai.cascade_enabled` |

### P1 — usage (owner)

| Метод | Путь | Контракт |
|-------|------|----------|
| `GET` | `/api/v1/settings/ai/usage` | `?period=week&task=` → aggregates |
| `GET` | `/api/v1/settings/ai/usage/summary` | p50/p90 latency, tokens by tier/task |

**Response summary:**
```json
{
  "period_from": "…",
  "period_to": "…",
  "baseline_mode": true,
  "by_tier": {
    "top_a": { "calls": 120, "prompt_tokens": 400000, "p50_ms": 8200, "p90_ms": 15000 }
  },
  "by_task": {
    "resume_eval": { "calls": 45, "prompt_tokens": …, "p50_ms": … }
  }
}
```

### P3 — UI N7 (`/settings/ai`)

- Селекторы: fast, top A, top B (строки моделей, без хардкода).
- Таблица task → tier + dropdown override.
- Toggle «Каскад включён» (`cascade_enabled`).
- Мини-дашборд: tokens / latency / calls (7d), split baseline vs cascade (после P4).

**Компоненты:** расширить `app/settings/ai/page.tsx`, новый `AiCascadeSettings.tsx`, `AiUsageDashboard.tsx`.

---

## 8. Файлы (сводка)

| Файл | Правки |
|------|--------|
| `ai_json.py` | делегировать в `ai_route`; capture usage |
| `ai_route.py` | **новый** |
| `ai_schemas.py` | **новый** |
| `ai_usage.py` | **новый** |
| `ai_facts_cache.py` | **новый** |
| `app_settings.py` | get/set `ai` section |
| `models.py` | `AiUsageLog` |
| `candidate_resume_eval.py` | pipeline P2 |
| `resume_eval.py` | top stage input |
| `transcription.py` | cleanup → routed |
| `candidate_interview_eval.py` | struct input |
| `interview_digest.py` | routed |
| `candidate_questionnaire.py` | reuse facts |
| `document_generate.py` | facts + top |
| `vacancy_docs_pack.py` | pipeline |
| `disk_inbox_router.py` | task key |
| `offer_draft.py` | fast+top |
| `stats_ai_brief.py` | task key |
| `hh_*.py` (LLM) | task keys |
| `workers/tasks.py` | progress labels |
| `routes/settings.py` | PATCH ai, usage endpoints |
| `schemas.py` | DTO |
| `settings/ai/page.tsx` | N7 UI |

---

## 9. Надёжность и fallback

```
fast call
  ├─ HTTP fail / no fast model → top (log fast_unavailable)
  ├─ JSON parse fail → retry fast (1x)
  ├─ pydantic validate fail → retry fast (1x) → top with full input (log validate_escalate)
  └─ success → persist cache → top stage

top_a call
  ├─ fail → top_b (if set)
  └─ fail → raise (job error as today)
```

Job **не падает** из-за fast-stage fail если escalation на top успешна.

---

## 10. Риски

| Риск | Митигация |
|------|-----------|
| Ошибки fast попадают в top prompt | Escalation на top **с полным** user text; флаг `meta.escalated_from_fast` в log |
| Latency ×2 на двухстадийных | Parallel не возможен; fast модель дешёвая/быстрая; p90 в dashboard; opt-out per task |
| Provider rate limit на 2× calls | fast маленький; batch debrief unchanged |
| Стоимость ретраев | max 1 retry fast; log `retry_count` |
| Regression качества eval | P4 A/B: smoke 16.2 + manual 10 cards; rollback `cascade_enabled=false` |
| `resume_facts` stale после PATCH resume | Invalidate hash on `resume_text` / link change |
| ЯКОРЬ tags vs facts | tags на person (ЯКОРЬ); facts на candidate payload; suggested_tags читает facts |

---

## 11. Smoke и тесты

### Pre-existing (must pass unchanged)

6.4, 7.4–7.8, 15.3, 16.2–16.9, 22.x, 24.10

### Новые (раздел «КАСКАД» в SMOKE_TEST.md)

| ID | Сценарий |
|----|----------|
| K-P1.1 | `cascade_enabled=false` → все calls tier=top в `ai_usage_log` |
| K-P1.2 | Запись usage: tokens > 0, latency_ms, task name |
| K-P2.1 | Evaluate resume → `payload.resume_facts` заполнен |
| K-P2.2 | Повтор evaluate без смены резюме → один fast call (check log count) |
| K-P2.3 | fast model пуст → поведение как до КАСКАД |
| K-P2.4 | Симulate fast fail → job completes via top escalation |
| K-P3.1 | N7: смена task override → следующий job другой tier |
| K-P4.1 | Dashboard: baseline vs cascade tokens ↓ на resume_eval |

---

## 12. Оценки

| Фаза | Чел·дни |
|------|---------|
| P1 — router + log + baseline | 4–5 |
| P2 — resume + interview pipelines | 5–7 |
| P3 — docs/HH/offer/inbox + N7 UI | 5–6 |
| P4 — rollout + dashboard compare | 2–3 |
| **Итого** | **16–21** |

---

## 13. НЕ делаем

- LLM-оркестратор / routing через top model
- Хардкод имён моделей
- Изменение кнопок/экранов (кроме N7 owner settings)
- SpeechKit / HH API / messaging
- Переписывание `hh_prefilter` (не LLM)
- Удаление `ai_error_logs`
- Обязательный fast (всегда opt-in через config)

---

## 14. Ответы на вопросы брифа

### Где факты и стык с persons/тегами (ЯКОРЬ)

| Данные | Хранение | Потребители |
|--------|----------|-------------|
| `resume_facts` | `candidate.payload` | resume_eval, questionnaire, suggested_tags |
| `interview_qa_pairs` | `candidate.payload` | interview_eval, digest |
| `person.tags` | ЯКОРЬ PR2 `persons.tags` | сегменты, фильтры |
| `ai_suggested_tags` | `payload` до accept | UI accept → person.tags |

Каскад **не дублирует** persons: facts — снимок резюме на карточке; person — идентичность.

### Baseline метрики и сравнение

**Baseline (P1, `cascade_enabled=false`, ≥7d):**

- `resume_eval`: calls, sum(prompt_tokens), p50/p90 latency_ms
- `questionnaire_generate`
- `vacancy_doc_profile` (или job vacancy_docs_from_materials)

**После P4 (`cascade_enabled=true`, тот же период):**

- Δ tokens % по task
- Δ p50/p90 latency (ожидаем: tokens↓, latency может ↑slightly на 2-stage)
- Quality guard: smoke 16.x + error rate `ai_error_logs` не выше baseline + 10%

### «Перегенерировать с правкой» (опросник)

| Действие | Fast stage |
|----------|------------|
| Первый generate | extract facts если нет hash |
| Regenerate с notes (`questionnaire_regenerate`) | **Skip fast** — reuse `resume_facts` + existing eval |
| Regenerate после смены resume PDF/text | Re-run fast только если `resume_facts_hash` изменился |
| Fill from transcript | fast `interview_qa_extract` если нет pairs; иначе reuse |

Флаг в job meta: `facts_cache_hit: true/false`.

---

## Pre-start

1. **`КАСКАД`** только после согласования порядка с **ЯКОРЬ** (общие payload keys — OK, migrations — разные PR).
2. P1 можно параллельно **ОЧЕРЕДЬ** (queue fixes) — разные файлы, кроме осторожности в `candidate_resume_eval.py` (координировать merge).

---

*Документ: 2026-08-14 · Кодовое слово: **КАСКАД***
