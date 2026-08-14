# План реализации: persons, дедуп, аналитика, теги, талант-база

> **Кодовое слово запуска: `ЯКОРЬ`**
>
> Чтобы не перепутать с другими задачами (Bitrix, UI-фиксы, smoke и т.д.), работу по этому
> плану начинаем **только** по явной команде с кодовым словом:
>
> | Команда | Что делаем |
> |---------|------------|
> | **`ЯКОРЬ`** или **`ЯКОРЬ PR1`** | Старт волны D1: persons + дедуп (первый PR) |
> | **`ЯКОРЬ PR2`** | Волна D2+D3: аналитика стадий + теги + сегменты |
> | **`ЯКОРЬ PR3`** | Волна T: талант-база |
> | **`ЯКОРЬ smoke`** | Прогон smoke-чеклиста перед/после PR |
>
> Без слова **`ЯКОРЬ`** в запросе — этот план не трогаем.

**Статус:** одобрен архитектором (v2 + правки) · код — после зелёного smoke, с PR1.  
**Учёт в бэклоге:** [`BACKLOG.md`](BACKLOG.md) → **B-YAKOR-001** (старт только по **`ЯКОРЬ`**).  
**Источник истины по стеку:** `ARCHITECTURE.md` (FastAPI `/api/v1`, Next.js, PostgreSQL, ARQ, RouterAI).

---

## Содержание

1. [Архитектурные решения](#1-архитектурные-решения)
2. [Волны, PR и порядок](#2-волны-pr-и-порядок)
3. [Alembic: порядок миграций](#3-alembic-порядок-миграций)
4. [Choke-point: refresh_person_keys()](#4-choke-point-refresh_person_keys)
5. [OpenAPI-контракты](#5-openapi-контракты)
6. [PR1 — D1: persons + дедуп](#6-pr1--d1-persons--дедуп)
7. [PR2 — D2+D3: аналитика + теги + сегменты](#7-pr2--d2d3-аналитика--теги--сегменты)
8. [PR3 — T: талант-база](#8-pr3--t-талант-база)
9. [Feature flags](#9-feature-flags)
10. [Smoke-тесты](#10-smoke-тесты)
11. [Риски и runbook](#11-риски-и-runbook)
12. [Оценки](#12-оценки)
13. [Scope control — НЕ делаем](#13-scope-control--не-делаем)

---

## 1. Архитектурные решения

### 1.1 Таблица `persons` — hub идентичности

- Один человек может иметь несколько карточек `candidates` (разные вакансии).
- `talent_pool_entries` привязаны к `person`, не загрязняют воронку.
- **`persons` — без UNIQUE-constraint** на match-колонках (осознанно).
- Возможна гонка: два параллельных create → два `persons` с одним phone. Документировано; лечится **ручным flatten-merge**, не автослиянием.

### 1.2 `merged_into_person_id` — только flatten

При ручном слиянии:

1. Перепривязать все `candidates.person_id` и `talent_pool_entries.person_id` на целевой person.
2. У source-persons выставить `merged_into_person_id = target`.
3. **В runtime-запросах цепочку merged_into не резолвим** — только канонический `person_id` на карточках.

### 1.3 Match-ключи (единая нормализация)

| Ключ | Правило |
|------|---------|
| `match_phone` | только цифры; `8xxx…` → `7xxx…` |
| `match_email` | lower, trim |
| `match_name` | lower, `ё→е`, сжатие пробелов |

Denormalized cache на `candidates` + индексы; источник связи — `person_id`.

### 1.4 Дедупликация

| Уровень | Условие | Поведение |
|---------|---------|-----------|
| **Hard** | `match_phone` OR `match_email` совпал у другого person в org | Блок до «Создать всё равно» (`force_duplicate=true`) |
| **Soft** | только `match_name` | Warning, не блокирует |
| **Copy V10** | `source=copy` / endpoint `/copy` | Hard-check **пропускается**; плашка «также на вакансии X» |
| **PATCH анкеты** | check-duplicate **до** сохранения | Warning в UI; 409 без `force_duplicate` |
| **Infra fail** | DB/timeout при check | **Log + proceed** (не блокировать intake) |

**PATCH не перепривязывает `person_id` автоматически** — только warning. Смена person — через ручной merge.

### 1.5 «Не контактировать»

`persons.do_not_contact BOOLEAN` — не свободный тег (защита от опечаток). Warning при intake/copy.

---

## 2. Волны, PR и порядок

```
Pre-start: зелёный smoke (SMOKE_TEST §1–24)
    ↓
PR1 / D1   persons + match + dedup + retro scripts
    ↓ smoke D1
PR2 / D2   время на стадиях + V13 stale + manager view
    + D3   теги + сегменты + segment_copy job + AI-теги
    ↓ smoke D2+D3
PR3 / T    talent pool 4.0–4.3
    ↓ smoke T
```

| Волна | PR | Feature flag |
|-------|-----|--------------|
| D1 | PR1 | — (dedup всегда on) |
| D2 | PR2 | — |
| D3 | PR2 | `candidate_segments` |
| T | PR3 | `talent_pool` |

**Параллельность:** D2 backend можно начинать после merge `person_match.py` (1.0), не дожидаясь UI dedup.

---

## 3. Alembic: порядок миграций

Текущий head: **`g7h8i9j0k1l2`**

```
g7h8i9j0k1l2  (head)
    ↓
h1a2b3c4d5e6  PR1: persons + candidates.person_id/org_id/match_*
    ↓
h2b3c4d5e6f7  PR2: persons.do_not_contact, persons.tags, candidates.tags, organization_tags
    ↓
h3c4d5e6f7a8  PR2: candidate_segments
    ↓
h4d5e6f7a8b9  PR3: talent_pool_entries + resume_artifacts (задел)
```

### h1a2b3c4d5e6 — PR1

```sql
CREATE TABLE persons (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  match_phone VARCHAR(16),
  match_email VARCHAR(320),
  match_name VARCHAR(512),
  merged_into_person_id UUID REFERENCES persons(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- partial indexes: (organization_id, match_phone|email|name) WHERE NOT NULL

ALTER TABLE candidates ADD COLUMN person_id UUID REFERENCES persons(id);
ALTER TABLE candidates ADD COLUMN organization_id UUID REFERENCES organizations(id);
ALTER TABLE candidates ADD COLUMN match_phone VARCHAR(16);
ALTER TABLE candidates ADD COLUMN match_email VARCHAR(320);
ALTER TABLE candidates ADD COLUMN match_name VARCHAR(512);
-- partial indexes на candidates
```

**После migrate — CLI (не alembic):**

```bash
python -m app.scripts.backfill_persons --all-orgs
python -m app.scripts.verify_person_coverage   # exit 1 если person_id IS NULL > 0
```

### h2b3c4d5e6f7 — PR2

```sql
ALTER TABLE persons ADD COLUMN do_not_contact BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE persons ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE candidates ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}';
CREATE INDEX ix_candidates_tags ON candidates USING GIN (tags);
CREATE INDEX ix_persons_tags ON persons USING GIN (tags);

CREATE TABLE organization_tags (
  organization_id UUID NOT NULL REFERENCES organizations(id),
  tag VARCHAR(128) NOT NULL,
  usage_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (organization_id, tag)
);
```

### h3c4d5e6f7a8 — PR2

```sql
CREATE TABLE candidate_segments (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(255) NOT NULL,
  filter JSONB NOT NULL DEFAULT '{}',
  scope VARCHAR(32) NOT NULL DEFAULT 'candidates',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_segments_org_user ON candidate_segments (organization_id, user_id);
```

### h4d5e6f7a8b9 — PR3

```sql
CREATE TABLE talent_pool_entries (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  person_id UUID REFERENCES persons(id),
  display_name VARCHAR(512) NOT NULL DEFAULT '',
  match_phone VARCHAR(16),
  match_email VARCHAR(320),
  match_name VARCHAR(512),
  resume_year INT,
  source_filename VARCHAR(512),
  s3_key VARCHAR(1024),
  mime_type VARCHAR(128),
  payload JSONB NOT NULL DEFAULT '{}',
  hh_revival JSONB NOT NULL DEFAULT '{}',
  tags TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE resume_artifacts (
  id UUID PRIMARY KEY,
  person_id UUID NOT NULL REFERENCES persons(id),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  source VARCHAR(64) NOT NULL,
  s3_key VARCHAR(1024),
  resume_link VARCHAR(2048),
  resume_text TEXT,
  resume_year INT,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 4. Choke-point: refresh_person_keys()

**Файл:** `app/services/person_match.py`

**Единственная точка** присвоения/обновления `person_id` и match-cache на candidate.

```python
def refresh_person_keys(
    db,
    *,
    candidate: Candidate,
    name: str,
    phone: str,
    email: str,
    mode: Literal["create", "patch", "copy", "import"],
    source_person_id: UUID | None = None,
) -> Person:
    """
    1. normalize → match_*
    2. copy → reuse source_person_id
    3. иначе find person by (org, phone|email) — first match wins
    4. иначе create person (race OK)
    5. sync candidate.person_id, match_*, organization_id
    """
```

**Вызывается только из:**

| Модуль | mode |
|--------|------|
| `candidate_write.create_candidate` | create |
| `candidate_write.patch_candidate` | patch |
| `candidate_copy.copy_candidate_to_vacancy` | copy |
| `hh_to_candidate` (→ create_candidate) | create |
| `disk_inbox_router` | create |
| `yandex_disk_sync` | create |
| `candidate_resume_eval` (bulk/file) | create |
| `talent_pool` import (PR3) | import |

**Runbook гонки:** `.cursor/runbooks/yakor-person-race.md`

**Flatten merge (CLI):** `python -m app.scripts.merge_persons --target UUID --sources UUID,UUID`

---

## 5. OpenAPI-контракты

Базовый префикс: `/api/v1`. Tenancy: `AuthUser.org_id`.

### 5.1 D1 — Dedup & persons

#### `POST /candidates/check-duplicate`

Pre-check для create **и** PATCH (draft fields).

**Request:**
```json
{
  "name": "Иванов Иван",
  "phone": "+7 (999) 123-45-67",
  "email": "ivan@example.com",
  "candidate_id": "uuid|null",
  "vacancy_id": 123
}
```

**Response 200:**
```json
{
  "hard": [{
    "candidate_id": "uuid",
    "person_id": "uuid",
    "name": "Иванов Иван",
    "vacancy_id": 45,
    "vacancy_title": "Менеджер",
    "match_kind": "phone|email"
  }],
  "soft": [{
    "candidate_id": "uuid",
    "person_id": "uuid",
    "name": "Иванов Иван",
    "vacancy_id": 12,
    "vacancy_title": "…",
    "match_kind": "name"
  }]
}
```

#### `POST /vacancies/{vacancy_id}/candidates`

+ `force_duplicate: bool = false`  
**409:** `{ "detail": "duplicate_hard", "duplicates": { "hard": [], "soft": [] } }`  
**Infra skip:** 201 + header `X-Dedup-Check: skipped`

#### `PATCH /candidates/{candidate_id}`

+ `force_duplicate: bool = false` — same 409 semantics.  
UI: debounced `check-duplicate` → banner → save.

#### `GET /candidates/{candidate_id}/related`

```json
{
  "person_id": "uuid",
  "siblings": [{
    "candidate_id": "uuid",
    "vacancy_id": 45,
    "vacancy_title": "…",
    "hr_stage": "client_review"
  }]
}
```

#### `GET /persons/{person_id}/candidates`

Drill-down / admin (read-only в MVP).

#### Intake (5 каналов)

1. Manual — `POST .../candidates`
2. File/link — `bulk-links`
3. File upload — `from-file`
4. HH shortlist — `hh.py` → shortlist transfer
5. Yandex inbox — `disk_inbox_router`

- Bulk: per-item `warnings[]`
- Inbox: hard dup **на той же вакансии** → skip create; другая вакансия → create + warning

#### `CandidateDetail` (расширение)

+ `person_id`, `related_vacancies[]`

---

### 5.2 D2 — Stage durations

#### `GET /stats/dashboard?mode=…&view=manager`

```json
{
  "stage_timing": [{
    "stage": "client_review",
    "count": 12,
    "avg_days": 4.2,
    "median_days": 3,
    "over_threshold_count": 2,
    "data_quality": "exact|partial|estimated"
  }],
  "client_response": {
    "avg_days": 2.1,
    "median_days": 1,
    "sample_size": 8,
    "data_quality": "partial"
  }
}
```

Источники: `payload.hr_stage_history`, `payload.client_status_history`.  
Synthetic backfill: `backfill_stage_history.py` с флагом `synthetic: true`.

#### `GET /stats/stage-durations`

Drill-down — **data_quality на summary и на каждом candidate:**

```json
{
  "summary": { "stage": "client_review", "avg_days": 4.2, "data_quality": "exact" },
  "candidates": [{
    "candidate_id": "uuid",
    "name": "…",
    "vacancy_id": 1,
    "stage": "client_review",
    "days_on_stage": 9,
    "entered_at": "2026-08-01T12:00:00+00:00",
    "data_quality": "estimated"
  }]
}
```

#### V13

`attention_reason()` + `"Завис на этапе «…» N дн"` (порог per-stage + optional SLA из vacancy).

---

### 5.3 D3 — Tags & segments

**Gate:** 403 если `features.candidate_segments !== true`.

#### `GET /tags?q=…`

#### `PATCH /candidates/{id}` + `tags: string[]`

Пишет в `candidate.tags` + union в `person.tags`.

#### `GET /candidates?tags=a,b&segment={uuid}`

#### `POST /candidates/{id}/tags/accept-suggested`

Из `payload.ai_suggested_tags` (job `candidate_evaluate_resume`).

#### Segments CRUD — `/candidate-segments`

**filter:**
```json
{
  "tags": ["опыт: маркетплейсы"],
  "hr_stage": "archived",
  "client_id": null,
  "vacancy_id": null,
  "period": "year",
  "date_from": null,
  "date_to": null
}
```

**scope:** `candidates` | `talent_pool` | `both`

#### `POST /candidate-segments/{id}/copy-to-vacancy`

```json
{ "target_vacancy_id": 123, "candidate_ids": ["uuid"] | null }
```

- ≤5 candidates → **200 sync**
- \>5 → **202** + job `segment_copy_to_vacancy`

**Job result:**
```json
{
  "copied": 20,
  "skipped": 2,
  "target_vacancy_id": 123,
  "target_vacancy_title": "Менеджер по продажам",
  "errors": [{ "candidate_id": "…", "reason": "…" }]
}
```

**UI:** по завершении job — **live-toast** (`JobsLive.tsx`):
«Скопировано 20 из 22 → [Вакансия X](/vacancies/123)»

---

### 5.4 T — Talent pool

**Gate:** 403 если `features.talent_pool !== true`.

#### `GET /talent-pool`, `GET /talent-pool/{id}`

#### `POST /talent-pool/import` → job `talent_pool_import`

**Job result — пропущенные .doc с причиной:**
```json
{
  "imported": 120,
  "skipped_duplicates": 5,
  "skipped_files": [{
    "filename": "resume_old.doc",
    "reason": "doc_format_disabled",
    "hint": "Конвертируйте в PDF или включите TALENT_POOL_ENABLE_DOC=1"
  }],
  "errors": []
}
```

MVP formats: PDF, DOCX, TXT. `.doc` — opt-in через env.

#### `POST /talent-pool/{id}/take` → `{ "vacancy_id": 123 }` → Candidate 201

#### `POST /talent-pool/{id}/hh-search` → job `talent_pool_hh_search`

#### `POST /talent-pool/{id}/hh-revival/confirm|reject`

#### `GET /candidates/{id}/pool-hints` (async, не блокирует create)

Hard keys only (phone/email), не name.

---

## 6. PR1 — D1: persons + дедуп

### Backend checklist

- [ ] Migration `h1a2b3c4d5e6`
- [ ] `person_match.py`
- [ ] Refactor `hh_to_candidate` → `create_candidate`
- [ ] Dedup 5 intake + copy exemption
- [ ] `POST /candidates/check-duplicate`
- [ ] PATCH/create `force_duplicate`
- [ ] `GET /candidates/{id}/related`
- [ ] Replace `disk_inbox_router._find_duplicate`
- [ ] Scripts: `backfill_persons`, `verify_person_coverage`, `find_duplicate_groups`
- [ ] Runbook `yakor-person-race.md`

### Frontend checklist

- [ ] `DuplicateCandidateBanner` — create + **PATCH** (check before save)
- [ ] Related vacancies plaque в `CandidateEditor`
- [ ] `lib/labels.ts`

### Ключевые файлы

`models.py`, `person_match.py`, `candidate_write.py`, `candidate_copy.py`,
`hh_to_candidate.py`, `disk_inbox_router.py`, `yandex_disk_sync.py`,
`candidate_resume_eval.py`, `routes/candidates.py`, `routes/vacancies.py`,
`schemas.py`, `CandidateEditor.tsx`, `AddCandidateForm.tsx`

**Оценка:** 8–10 чел·дней

---

## 7. PR2 — D2+D3: аналитика + теги + сегменты

### D2

- [ ] `stage_duration.py`
- [ ] `backfill_stage_history.py`
- [ ] Extend `stats_service`, `/stats?view=manager`
- [ ] `/stats/stage-durations` + per-row `data_quality`
- [ ] V13 stale

### D3

- [ ] Migrations `h2`, `h3`
- [ ] Tags + AI suggest + accept
- [ ] Segments CRUD + shared filter executor
- [ ] Job `segment_copy_to_vacancy` + toast с ссылкой на вакансию
- [ ] Feature flag UI in `/settings/functions`
- [ ] `do_not_contact`

### Ключевые файлы

`stage_duration.py`, `stats_service.py`, `candidate_query.py`,
`candidate_resume_eval.py`, `routes/stats.py`, `routes/candidates.py`,
`workers/tasks.py`, `app/stats/page.tsx`, `JobsLive.tsx`,
`CandidateTags.tsx`, `CandidateSegmentSave.tsx`, `candidates/page.tsx`

**Оценка:** 10–12 чел·дней

---

## 8. PR3 — T: талант-база

- [ ] Migration `h4`
- [ ] `routes/talent_pool.py`
- [ ] Job `talent_pool_import` (+ skipped_files report)
- [ ] Job `talent_pool_hh_search`, `talent_pool_hh_batch`
- [ ] UI `/talent-pool`, `/talent-pool/[id]`
- [ ] `take`, `pool-hints`
- [ ] Feature flag `talent_pool`
- [ ] Nav item in `RecruitingShell` (hidden if flag off)

**Оценка:** 12–15 чел·дней

---

## 9. Feature flags

Хранение: `organizations.integrations.features` (JSONB, без отдельной миграции).

```json
{
  "talent_pool": false,
  "candidate_segments": false,
  "dedup_soft_mode": false
}
```

- Включает **`platform_owner`** в `/settings/functions`
- API settings отдаёт `features` → фронт скрывает меню и роуты
- Dedup (D1) — **всегда включён**, flag не требуется

---

## 10. Smoke-тесты

Добавить в `v2/testing/SMOKE_TEST.md` раздел **«ЯКОРЬ»**:

### Pre-start (до PR1)

- §1–24 текущего SMOKE — всё зелёное

### D1 (после PR1)

| ID | Сценарий |
|----|----------|
| Y-D1.1 | Manual: тот же phone → 409 → force → OK |
| Y-D1.2 | PATCH phone → warning **до** «Сохранить» |
| Y-D1.3 | Copy V10 → не блокирует + плашка «также на вакансии X» |
| Y-D1.4 | `verify_person_coverage` → 0 без person_id |
| Y-D1.5 | Retro script → JSON группы, без merge |

### D2 (после PR2)

| ID | Сценарий |
|----|----------|
| Y-D2.1 | `/stats?view=manager` — «N чел · X дн» |
| Y-D2.2 | Drill-down `stage-durations` — `data_quality` на строках |
| Y-D2.3 | «Требуют внимания» — «Завис N дн» |

### D3 (после PR2, flag on)

| ID | Сценарий |
|----|----------|
| Y-D3.1 | Тег в карточке → фильтр в хабе |
| Y-D3.2 | AI-теги после evaluate → accept |
| Y-D3.3 | Сегмент → F5 → фильтр воспроизведён |
| Y-D3.4 | Segment copy → toast + ссылка на вакансию |
| Y-D3.5 | `do_not_contact` → warning при copy |

### T (после PR3, flag on)

| ID | Сценарий |
|----|----------|
| Y-T.1 | Import PDF → entries в /talent-pool, не в candidates |
| Y-T.2 | .doc без env → skipped_files с reason |
| Y-T.3 | HH search → confirm → ссылка сохранена |
| Y-T.4 | Take → candidate на вакансии |
| Y-T.5 | pool-hints на новом intake (phone match) |

---

## 11. Риски и runbook

| Риск | Митигация |
|------|-----------|
| Гонка persons | Runbook; retro `merge_persons --flatten` |
| Shared phone false hard-dup | `force_duplicate` + audit log |
| Incomplete hr_stage_history | Synthetic backfill + `data_quality` |
| HH rate limit (T) | Throttle in job; batch cap |
| segment copy timeout | Async job >5 |
| .doc on server | Opt-in env; explicit skip reason in report |

---

## 12. Оценки

| PR | Чел·дни |
|----|---------|
| PR1 D1 | 8–10 |
| PR2 D2+D3 | 10–12 |
| PR3 T | 12–15 |
| **Итого** | **30–37** (+15% QA) |

---

## 13. Scope control — НЕ делаем

- UNIQUE на persons; автослияние / автоподтверждение HH
- Resolve chain `merged_into` в SELECT
- Auto re-link `person_id` на PATCH
- Talent pool / segments без feature flag
- Запись talent_pool в candidates без «Взять в работу»
- LibreOffice `.doc` без `TALENT_POOL_ENABLE_DOC=1`
- UI resume_artifacts (таблица — задел в h4)
- Изменения Bitrix / Telegram / client zone
- Переписывание существующих экранов (только аддитив)

---

## Pre-start checklist

1. Команда **`ЯКОРЬ smoke`** → зелёный §1–24
2. Ветка `feature/yakor-d1` от актуального head
3. `alembic current` = `g7h8i9j0k1l2`
4. Baseline: 55 candidates, snapshot counts
5. Команда **`ЯКОРЬ PR1`** → начало кода

---

*Документ создан: 2026-08-14 · Кодовое слово: **ЯКОРЬ***
