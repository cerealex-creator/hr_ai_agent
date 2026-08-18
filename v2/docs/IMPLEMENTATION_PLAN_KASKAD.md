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

**Статус:** дизайн утверждён архитектором (2026-08-14) · слайсинг исполнения зафиксирован ниже.  
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

## 1. Фазы, слайсинг и оценки

### 1.1 Утверждённый порядок исполнения (слайсинг)

```mermaid
flowchart LR
  P1[КАСКАД P1 + ОЧЕРЕДЬ] --> Y[ЯКОРЬ PR1+PR2]
  Y --> P2[КАСКАД P2]
  P2 --> P3[КАСКАД P3+P4 после пилота]
```

| Слайс | Что | Оценка | Меняет качество? |
|-------|-----|--------|------------------|
| **КАСКАД P1** сейчас, параллельно ОЧЕРЕДИ | `ai_route`, миграция `ai_usage_log`, все LLM через router, `cascade_enabled=false`, **task keys на call sites** | **4–5 чел·дн** | Нет |
| **ЯКОРЬ PR1+PR2** | persons/dedup, аналитика стадий, теги/сегменты | 18–22 (см. ЯКОРЬ) | Нет для ИИ-качества |
| **КАСКАД P2** после ЯКОРЬ PR2 | двухстадийные `evaluate_resume` + `interview_process`, `resume_facts` | **5–7 чел·дн** | Да (экономия токенов) |
| **КАСКАД P3+P4** после стабилизации пилота | docs/HH/offer/inbox + N7 UI; затем включение fast | **5–6 + 2–3 = 7–9 чел·дн** | Да |

**Итого КАСКАД:** 16–21 чел·дн (без ЯКОРЬ).

**Почему так, а не P2 сразу после P1:** конфликт по `candidate_resume_eval.py` с ЯКОРЬ PR2 (теги); P1 накапливает baseline, пока идёт ЯКОРЬ.

**ЯКОРЬ PR3 (talent pool):** не блокирует P2. Делать после PR2, можно параллельно с КАСКАД P3 (разные файлы). `talent_pool_hh_match` в `task_map` с P1, реализация — в ЯКОРЬ PR3.

**ОЧЕРЕДЬ на момент слайса:** Q-01…Q-04 уже done локально — пересечения с P1 почти нет (`ai_json.py` vs воронка/UI). Если появятся новые queue-задачи — не трогать `ai_json.py` / `ai_route.py` в том же PR.

### 1.2 Гейты

| Переход | Гейт |
|---------|------|
| P1 → merge | smoke ИИ без регрессии (16.2, 7.x, 15.3); usage пишется; `cascade_enabled=false` |
| ЯКОРЬ PR2 → КАСКАД P2 | PR2 влит; `candidate_resume_eval` стабилен |
| **Старт P4 (включить fast)** | (1) baseline-выборка: ≥7 дней **или** N≥30 jobs по `resume_eval` / `questionnaire_generate` / `vacancy_doc_*`; (2) P2+P3 влиты; (3) зелёный smoke **16.x / 7.x / 15.3 на новых конвейерах** |
| **Оставить fast (конец P4)** | сравнение с baseline: tokens↓ на ключевых task; error rate `ai_error_logs` не выше baseline + 10%; иначе откат `cascade_enabled=false` |

**Уточнение к формулировке «подтверждённая baseline-экономика»:** на старте P4 экономика ещё не доказана (P1 считает только all-top). Гейт старта P4 = **достаточная выборка baseline**. Доказанная экономия — гейт **оставить fast** после замера.

### 1.3 Зачем P1 раньше P2

Без `ai_route()` и `ai_usage_log` нет baseline и нет единой точки fallback.

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
      "message_draft": "fast",
      "video_interview_script": "top",
      "avatar_pitch_compress": "fast"
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
| `video_interview_script` | top | ЭФИР A — сценарий для камеры (качество = эфир) |
| `avatar_pitch_compress` | fast | ЭФИР B — ужать vacancy_text под лимит аватара |

**Не в map (не LLM):** `hh_prefilter`, SpeechKit, ffmpeg, HH REST API, рендер HeyGen/D-ID.

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

### 9.1 Матрица (4 обязательных случая)

| # | Случай | Действие | Лог `tier` / meta | Job падает? |
|---|--------|----------|-------------------|-------------|
| 1 | **Провал валидации** fast (JSON parse или pydantic schema) | **1 ретрай на fast** → если снова fail → **эскалация на top** с **полным** исходным user text (не битый JSON) | `retry_count=1`; затем `tier=fallback_top`, `meta.escalated_from_fast=validate` | Нет, если top успешен |
| 2 | **Fast недоступен** (модель не задана, HTTP 5xx/timeout/сеть) | **Сразу top**, без ретрая fast | `tier=fallback_top`, `meta.reason=fast_unavailable` | Нет, если top успешен |
| 3 | **Top A упал** (429 / 5xx / timeout) | **Один** вызов **top B**, если `models.top_b` задан; иначе как сегодня | `tier=top_b`; если top_b нет — ошибка job | Да, только если A и B (или A без B) упали |
| 4 | **Ошибка роутинга** (unknown task, битый `task_map`, исключение в `resolve_tier`) | **Сразу top** + **log warning** | `tier=fallback_top`, `meta.reason=routing_error` | Нет, если top успешен |

P1 (`cascade_enabled=false`): случаи 1–2 на практике не срабатывают (всё и так top). Реализовать матрицу в `ai_route` **сразу в P1**, чтобы P2 не изобретал fallback заново. На P1 обязательны **#3 и #4**; #1–#2 — код есть, ветки dormant до включения fast.

### 9.2 Дерево (то же)

```
fast call
  ├─ HTTP fail / no fast model → top (log fast_unavailable)     [#2]
  ├─ JSON parse / schema fail → retry fast (1x) → top            [#1]
  └─ success → persist cache → top stage

resolve_tier fail → top + warning                                [#4]

top_a call
  ├─ fail → top_b (if set)                                       [#3]
  └─ fail → raise (job error as today)
```

Job **не падает** из-за fast-stage fail, если escalation на top успешна.

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

## 12. Оценки (для управления слайсами)

Дублирует §1.1 — здесь разбивка внутри фазы.

| Фаза | Состав | Чел·дни |
|------|--------|---------|
| **P1** | миграция `ai_usage_log`; `ai_route` + fallback-матрица §9.1; `chat_json` → routed; **проставить `task=` на всех существующих вызовах** (~15 call sites); GET usage summary; `cascade_enabled=false` | **4–5** |
| **P2** | `ResumeFactsSchema` + cache hash; pipeline evaluate_resume; cleanup+QA+eval interview; прогресс job | **5–7** |
| **P3** | docs facts→prose; inbox; HH LLM keys; offer fast+top; stats brief; N7 селекторы + таблица task→tier + мини-дашборд | **5–6** |
| **P4** | включить fast; сравнить 7d vs baseline; runbook отката; ручной прогон 10 карточек | **2–3** |
| **Итого КАСКАД** | | **16–21** |

P1 без `task=` на call sites **не принимаем**: baseline тогда не режется по `resume_eval` / опросник / документы, и гейт P4 слепой.

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

1. Слайсинг утверждён: **P1 сейчас** → **ЯКОРЬ PR1+PR2** → **КАСКАД P2** → **P3+P4 после пилота**.
2. Миграции КАСКАД и ЯКОРЬ — **разные PR**, не одна цепочка без нужды (P1 `h5…` vs ЯКОРЬ `h1…h3`).
3. P1 не меняет `candidate_resume_eval` логику — только `chat_json(..., task=...)`.
4. Старт кода: команда **`КАСКАД P1`**.

---

*Документ: 2026-08-14 · Кодовое слово: **КАСКАД***
