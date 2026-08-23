# План реализации: Система управления (СУП)

> **Кодовое слово запуска: `СИСТЕМА`**
>
> | Команда | Что делаем |
> |---------|------------|
> | **`СИСТЕМА`** или **`СИСТЕМА U1`** | Модель данных + ручной конструктор + слой «как есть» (без ИИ) |
> | **`СИСТЕМА U2`** | Интервью собственника → цели/задачи + ворота |
> | **`СИСТЕМА U3`** | Процессы/оргсхема (L2a/L2b) + контент-пакеты + gap-отчёт |
> | **`СИСТЕМА U4`** | Документы ролей + критик на стыках + impact analysis |
> | **`СИСТЕМА U5`** | Внедрение: план перехода + мост в вакансии + экспорт |
>
> Без слова **`СИСТЕМА`** — этот план не трогаем.  
> Учёт: [`BACKLOG.md`](BACKLOG.md) → **B-SISTEMA-001**.

**Статус:** **утверждён с правками ревью №5** (2026-08-23) — измерения целей (BSC) + baseline/target на целях. U1 backend реализован; миграция `i9j0k1l2m3n4`. Старт U2 — по **`СИСТЕМА U2`**.  
**Источник истины по стеку:** `ARCHITECTURE.md` (FastAPI `/api/v1`, Next.js, PostgreSQL, ARQ, RouterAI).  
**SKU:** отдельный продукт «Система управления» для SME; флаг `org.features.management_system`.

---

## Содержание

1. [Принято / правки к брифу](#1-принято--правки-к-брифу)
2. [Ядро продукта](#2-ядро-продукта)
3. [Онбординг-мастер (WIZARD)](#3-онбординг-мастер-wizard)
4. [Модель данных](#4-модель-данных)
5. [Каскад уровней и ворота](#5-каскад-уровней-и-ворота)
6. [Анти-глюки](#6-анти-глюки)
7. [D1 — как есть / как надо](#7-d1--как-есть--как-надо)
8. [D2 — отраслевые контент-пакеты](#8-d2--отраслевые-контент-пакеты)
9. [D3 — глубина MVP](#9-d3--глубина-mvp)
10. [E1–E6 — финальные дельты (ревью №3)](#10-e1e6--финальные-дельты-ревью-3)
11. [Фазы U1–U5](#11-фазы-u1u5)
12. [Права и feature flag](#12-права-и-feature-flag)
13. [Переиспользование стека](#13-переиспользование-стека)
14. [Оценки](#14-оценки)
15. [Scope control — НЕ делаем в MVP](#15-scope-control--не-делаем)
16. [Гейты ревью](#16-гейты-ревью)

---

## 1. Принято / правки к брифу

### 1.1 Архитектор принял (зафиксировано)

Правки Cursor п.1–9:

| # | Решение |
|---|---------|
| 1 | Граф `entity_links`, не один `derived_from` FK |
| 2 | L2a процессы / L2b оргсхема — отдельные ворота |
| 3 | LLM-критик только на стыках уровней; связи не меняет LLM |
| 4 | `OwnerInterviewSession` + immutable answers + `cited_answer_ids` |
| 5 | `task=` на всех ИИ-вызовах с U1; КАСКАД не блокер |
| 6 | Контент-пакеты вместо «полной библиотеки в коде» |
| 7 | Версии (`ManagementRevision`) first-class с U1 |
| 8 | Мост `source_role_id` → вакансия закладывается с U1 |
| 9 | Оценки пересчитаны (см. §14) |

Пять анти-глюков — в ТЗ (§6). Дельты **D1–D3** — в продуктовый scope (§7–9).

### 1.2 Что Cursor принимает в D1–D3

| Дельта | Вердикт | Почему |
|--------|---------|--------|
| **D1** слой «как есть / как надо» в MVP | **Принять** | Обещание продукта — «внедряет», не только «рисует идеал». Без gap СУП остаётся документогенератором. |
| **D2** контент-пакеты (стройка → …) без смены кода | **Принять** | Правильное разделение eng vs content; пилот = стройка. |
| **D3** L0→L1→L3 через базис + gap в MVP; права и flag до U2 | **Принять** | Реалистичный срез глубины без отказа от внедрения. |

### 1.3 Правки Cursor к формулировкам архитектора (внести в ТЗ)

| Тема | Было в брифе | Правка | Почему |
|------|--------------|--------|--------|
| **Фазирование D1** | «захват + gap + план перехода» как один слой | **Разнести:** модель+CRUD → U1; блок «текущая команда» в интервью → U2; детерминированный gap-отчёт → U3; ИИ-черновик плана перехода → U5 | Иначе U1/U3 раздуваются и ломают «сначала руками» |
| **`actual_duties`** | свободный текст на позиции | **Atomic line items** (как обязанности целевой роли) или JSON-список пунктов с id | Иначе нарушаем свой же анти-глюк №1 и нельзя считать coverage |
| **Правила gap** | «перегруз → разделить» | Явные инварианты: `coverage=partial` при headcount&lt;1 на роль; `overload` если одна `current_position` закрывает &gt;N целевых ролей или &gt;M process steps (N/M в конфиге пакета, дефолт 2/8) | Иначе gap — мнение LLM |
| **План перехода** | ИИ черновит шаги | Сборка = **INSERT from SELECT из gap-строк** + лёгкая полировка формулировок; человек утверждает каждый шаг; шаги версионируются | Тот же принцип, что L3 |
| **Родовые цели пакета** | «брать за основу» | Seed в статусе **`suggested`**, не `approved`. Собственник принимает/отклоняет в L0/L1 | Иначе чужие цели тихо становятся «истиной» |
| **Контент-бюджет** | внутри eng-оценок U3 | **Отдельная строка:** методолог 3–5 чел·дн на пилот «стройка» (не в eng 33–46) | Иначе U3 недооценён или пакет пустой |
| **Имена сущностей** | `current_positions` | Оставить `current_positions` в API; в UI — «Текущие должности / слоты». Не путать с целевой `Role` | Путаница «должность vs роль» — главный UX-риск |
| **Связь с Person** | не сказано | **Не в MVP.** `current_positions` — орг-слоты без привязки к `persons` | Person-hub уже сложный (ЯКОРЬ); смешивать рано |

### 1.4 С чем не согласен / откладываю

| Идея | Решение |
|------|---------|
| Полная библиотека KPI/чек-листов на 4 отрасли в MVP | **Нет.** MVP: SME-базис + пилот «стройка» (цели/задачи seed, 10–20 процессов, типовая оргсхема, 5–8 ролей с KPI/чек-листами). Остальные отрасли — контент-релизы после U5. |
| ИИ сам предлагает «идеальную» оргсхему против текущей без шаблона | **Нет.** Сначала пакет/базис → адаптация под утверждённые задачи → сопоставление с as-is. |
| LLM-критик на каждом уровне | **Нет** (уже принято): только стыки + код-инварианты внутри уровня. |

---

## 2. Ядро продукта

**Один принцип:** ИИ не пишет документы — ИИ заполняет структуру. Связность гарантирует БД. Человек утверждает каждый уровень.

**Обещание MVP:** собственник получает не только «как надо», но и **разрыв с «как есть»** и утверждённый **план перехода** (найм / перераспределение / временные назначения).

**Главный экран модуля:** два сценария входа — **Мастер (онбординг)** для собственника и **экспертный режим** для HR/консультанта.

| Режим | Аудитория | Назначение |
|-------|-----------|------------|
| **Мастер (онбординг)** | собственник | точка входа; пошаговый поток U1–U3 за одну resumable-сессию (§3) |
| **Карта** *(эксперт)* | HR / консультант | интерактивный граф (React Flow); на гейтах — поклик-утверждение узлов |
| **Документ** *(эксперт)* | HR / консультант | структура слева, читаемый рендер справа, traceability |
| **Внедрение** *(эксперт)* | HR / консультант + собственник | как есть → как надо → разрыв → план перехода |
| **Изменения** *(эксперт)* | HR / консультант | diff ревизий + impact queue + stale |

После завершения мастера пользователь попадает в экспертный режим для доработки и утверждения L3-документов.

---

## 3. Онбординг-мастер (WIZARD)

> **Ревью №4 (К1):** продуктовый фасад поверх U1–U3. Архитектура и ворота **не отменяются** — мастер сжимает их в одну сессию.

### 3.1 Два сценария, одна модель

| Сценарий | Кто | Когда |
|----------|-----|-------|
| **Мастер** | собственник (первый запуск) | онбординг; resumable стейт-машина |
| **Экспертный режим** | HR / консультант | после мастера или сразу (пропуск мастера) |

Мастер **не заменяет** CRUD, карту и 4 режима — он скрывает их на старте.

### 3.2 Шаги мастера (5)

| Шаг | UI (собственник) | Backend (фазы) | Ворота |
|-----|------------------|----------------|--------|
| **1. Команда** | CSV / ручной ввод текущих должностей; **шаг пропускаемый** (greenfield) | `current_positions` (**U1** модель; CRUD **U2**) | — |
| **2. Интервью** | 5–7 вопросов → черновик целей | `OwnerInterviewSession` + goals draft (**U2**) | утверждение целей в конце шага |
| **3. Отрасль** | выбор пакета (SME-базис / стройка) | импорт seeds как `suggested` + L2a/L2b из пакета (**U3**) | seeds не auto-approved |
| **4. Сводка** | таблица «цели + процессы пакета + команда» → **«Сгенерировать разрыв»**; React Flow как **визуализация уже созданной** структуры; **preview L3 read-only** | gap-отчёт (код, **U3**) + сборка preview L3 без approve (**U4** preview only) | gap детерминирован; **L3 approve — вне мастера** |
| **5. План** | утверждение плана перехода | `transition_steps` из gap_items (**U5**) | каждый шаг плана — отдельное approve |

**Критично (спор специалистов, решение №4):** в шаге 4 **нет** «утвердить L3 одним кликом». Preview — read-only; approve документов ролей — в экспертном режиме (режим «Документ» + ворота L3).

### 3.3 Resumable стейт-машина

```
wizard_sessions(
  org_id,
  revision_id?,          -- создаётся при первом шаге с данными
  step,                  -- 1..5
  payload jsonb,         -- черновики шагов (не дублирует immutable answers)
  status,                -- in_progress | completed | abandoned
  updated_at
)
```

- Прогресс сохраняется после каждого шага; «бросил на шаге 2 — вернулся через неделю» — resume.  
- `payload` — указатели и UI-state; источник истины — сущности ревизии (`current_positions`, `answers`, …).  
- Завершение мастера (`status=completed`) → редирект в экспертный режим «Карта» с подсказкой «утвердите документы ролей».

### 3.4 Прототип до frontend U2

Figma / бумажный прототип мастера — **продуктовая работа ∥ U1**, не блокирует backend U1.  
Гейт frontend U2: прототип утверждён собственником или тест-пользователем (§16).

---

## 4. Модель данных

### 4.1 Корневые сущности

```
Organization
  └─ ManagementSystem (org_id, status, industry_pack_id?, published_revision_id?)
        ├─ wizard_sessions (онбординг, resumable)
        └─ ManagementRevision (version_number, parent_revision_id, created_by, note)
              ├─ goals (weight), tasks (deadline, metrics)
              ├─ process_maps, process_steps (+ step_io_items)
              ├─ roles, org_nodes
              ├─ role_documents (instructions / kpi / checklists) — atomic lines + is_manual
              ├─ glossary_terms
              ├─ current_positions, role_assignments
              ├─ gap_items, transition_steps
              └─ entity_links (граф)
```

Все рабочие сущности несут `revision_id` + `status` (`draft` | `approved` | `published`) где применимо.  
Публикация = immutable snapshot ревизии.

### 4.2 Граф связей

```
entity_links(
  revision_id,
  source_type, source_id,
  target_type, target_id,
  link_kind,          -- decomposes | implements | measures | assigned_to | references | covers
  meta jsonb          -- опционально (weight, note)
)
```

UI по умолчанию показывает дерево; модель — граф.  
Traceability: клик → рекурсивный обход предков (CTE, §10 E4) до цели / ответа интервью.

**Graph Checker (E1):** перед INSERT/UPDATE `entity_links` — проверка циклов по иерархическим `link_kind` (`decomposes`, `implements`, `measures`) через `WITH RECURSIVE`. Цикл → **422** + сообщение с путём; при генерации ИИ — ошибка в контексте регенерации. Ссылки `references` / `covers` / `assigned_to` циклом не блокируют (не иерархия).

### 4.2.1 Цели и задачи (поля)

```
mgmt_goal_dimensions(code unique, pack_id?, title, icon?, default_weight_hint, sort_order)
mgmt_goal_dimension_links(goal_id, dimension_id, is_primary)  -- multi, не UUID[]
goals(revision_id, title, weight, metric_unit?,
      baseline_value, baseline_date?, target_value, target_date?,
      metric_source owner|pack_hint, status, cited_answer_ids[], …)
tasks(revision_id, title, deadline date?, metric_target numeric?, metric_unit?, status, …)
```

**Измерения (ревью №5, BSC-like):** справочник `mgmt_goal_dimensions` + связи `mgmt_goal_dimension_links`. Коды: `finance`, `customers`, `processes`, `people` (UI: «Команда / развитие»). Seed 4 измерений при миграции (`sme_base`). Не `category`, не `dimension_ids UUID[]`.

**Baseline / target на целях:** `baseline_value` + `baseline_date` (текущее), `target_value` + `target_date?` (цель). `metric_unit` — единица. `metric_source`: `owner` (цифра от собственника) или `pack_hint` (ориентир пакета). Цифровой разрыв в U3: `target − baseline` (без FTE-калькулятора; **ProductivityGapCalculator → не в MVP**).

`goal.weight` — приоритет / доля вклада (сумма по ревизии не обязана = 100%, но валидатор warning при явном дисбалансе).  
**Warning `DIMENSION_BALANCE`** — если ни одна цель не покрывает одно из 4 измерений; **не блокер** (показ в overview.warnings).  
`task.deadline` — опционально; обязателен только если цель родителя имеет горизонт с датой.

### 4.2.2 Шаг процесса — BPMN-подобная схема (E2)

Таблица `process_steps` (нормализованные колонки, не JSONB-массив):

```
process_steps(
  revision_id, process_map_id, sort_order,
  title,
  role_id,              -- FK на roles
  frequency,            -- optional: daily | weekly | monthly | ad_hoc | …
  status
)
```

Входы/выходы — **отдельные строки** `step_io_items` (не массив в JSONB):

```
step_io_items(step_id, direction in|out, title, glossary_term_id?, sort_order)
```

Сборка L3: обязанности = шаги с `role_id`; KPI = метрики задач через `entity_links.measures`; чек-листы = шаги + `step_io_items`.

### 4.3 Интервью собственника

```
OwnerInterviewSession(org_id, status, pack_hint?)
  └─ answers[]  -- immutable: append + soft-deprecate, без перезаписи текста
  └─ goals.cited_answer_ids[]  -- обязательны при approve цели
```

Блок **«Текущая команда»** в L0 пишет в `current_positions` (не в свободный markdown).

### 4.4 As-is / to-be

```
current_positions(org_id, revision_id, title, headcount, duties[])  -- duties = atomic items
role_assignments(
  revision_id,
  target_role_id,
  current_position_id,
  coverage,   -- full | partial | none
  note        -- «временно до найма»
)
```

`stale` применяется к assignments при правке целевой роли или as-is слота.

### 4.5 Мост в найм (с U1, включение в U5)

```
Role.external_key
Vacancy.documents.profile.source_role_id   -- preview с U1; автозаполнение с U5
```

---

## 5. Каскад уровней и ворота

| Уровень | ИИ | Человек | Анти-глюк |
|---------|----|---------|-----------|
| **L0** Цели + as-is команда | Структурированное интервью → answers + черновик целей + захват current_positions | Правит/утверждает цели; правит слоты команды | Цитаты answers; цифры только из answers или плашка «ориентир отрасли» |
| **L1** Задачи | Декомпозиция целей → задачи + метрики | Утверждает каждую | Метрики из answers / ориентир; FK на цели |
| **L2a** Процессы | Адаптация карты из пакета под утверждённые задачи | Правит/утверждает | Не изобретение с нуля |
| **L2b** Оргсхема/роли | Типовая схема пакета → адаптация | Правит/утверждает | Отдельный gate; L3 ждёт оба L2* |
| **L3** Документы ролей | **INSERT from SELECT** шагов/метрик + полировка wording | Утверждает версию | LLM не назначает role_id / step_id |
| **Внедрение** | Черновик transition_steps из gap_items | Утверждает шаги плана | Gap считает код; ИИ только формулировки |

**Вниз идёт только `approved`.**  
На стыках L0→L1, L1→L2, перед publish L3, перед publish плана перехода — LLM-критик (top, когда будет КАСКАД; до него — тот же `chat_json` + `task=`).

**MVP-срез глубины (D3):** допускается L0→L1→L3 через SME-базис / пилот-пакет с **импортом** L2a/L2b из пакета и минимальной адаптацией (без глубокой кастомной генерации процессов). Gap-карта при этом **обязательна**.

---

## 6. Анти-глюки

1. **Schema-first** — генерация только в JSON-схемы; текст — шаблоны рендера.  
2. **Каскад через граф** — связи в БД, не в промпте.  
3. **Ворота утверждения** — draft → approved → published.  
4. **Отраслевые пакеты** — адаптация, не изобретение.  
5. **Глоссарий** — инжект в каждый промпт.  
6. **Цифры** — от собственника или плашка «ориентир отрасли».  
7. **Impact + scoped regen** — без тихих перезаписей; diff + версии.  
8. **Traceability** — цепочка «из чего следует».  
9. **Atomic line items** — каждый пункт = строка БД.  
10. **Immutable owner answers**.  
11. **Generation = INSERT from SELECT** (L3 и transition_steps).  
12. **Stale marker** на потомках и на `role_assignments`.  
13. **Invariant catalog** — детерминированные проверки + показ в UI.  
14. **Graph Checker** — циклы в иерархических связях блокируются до сохранения (E1).  
15. **Impact/traceability CTE** — рекурсивный обход графа, не ad-hoc в коде (E4).  
16. **KPI invariant** — числовой таргет + связь с метрикой задачи; иначе 422 (E5).  
17. **Scoped regen строк** — регенерация по `line_id`; `is_manual=true` не перезаписывается (E5).  
18. **Bottom-up fixtures** — unit-тесты промптов до выкатки верхних уровней (E6).  
19. **Prompt-инварианты L0/L1 (W4):** не более **5 целей**; не более **5 задач на цель**; `max_tokens` в промпте + **`maxItems` в JSON-схеме**; warning-валидатор `GOAL_COUNT_EXCEEDED` / `TASK_COUNT_EXCEEDED` при превышении.  
20. **Измерения целей (F1, ревью №5):** только через `mgmt_goal_dimension_links`; warning `DIMENSION_BALANCE` при непокрытых BSC-измерениях — не 422.  
21. **Baseline/target (F2):** цифры на цели с `metric_source`; gap MVP = `target − baseline`; ProductivityGap → FTE **не в MVP**.

---

## 7. D1 — как есть / как надо

### 6.1 Продукт

Режим **Внедрение**:

1. **Как есть** — текущие должности/слоты и фактические обязанности.  
2. **Как надо** — утверждённые роли и процессы.  
3. **Разрыв** — gap-отчёт (код).  
4. **План перехода** — утверждаемые шаги с горизонтами.

### 6.2 Gap-типы (детерминировано)

| Сигнал | Рекомендация (код) |
|--------|-------------------|
| `coverage=none` у целевой роли | «нанять» / создать слот |
| `coverage=partial` | «усилить» / добрать headcount |
| одна current_position → слишком много ролей/шагов | «разделить» (overload) |
| process_step без `assigned_to` роли | «назначить владельца» |
| роль без инструкции/KPI/чек-листа после L3 | «закрыть документами» (трекер покрытия) |

### 6.3 Разнос по фазам

| Что | Фаза |
|-----|------|
| Таблицы + ручной CRUD as-is + assignments | **U1** |
| Блок интервью «текущая команда» + импорт списком | **U2** |
| Gap-отчёт + UI «Внедрение» (без ИИ-плана) | **U3** |
| ИИ-черновик transition_steps + утверждение + трекер | **U5** |

---

## 8. D2 — отраслевые контент-пакеты

### 7.1 Приоритет

1. **Универсальный SME-базис** (обязателен для MVP)  
2. **Стройка** — пилот пакета  
3. Производство  
4. Поставки  
5. Маркетплейсы  

Пункты 3–5 — **контент-релизы** после стабилизации пилота; архитектура не меняется.

### 7.2 Состав пакета (версия в репо, без миграций кода)

```
packs/<id>/
  manifest.json          -- id, title, version, defaults N/M для overload
  glossary.json
  goals_seed.json        -- status on import: suggested
  tasks_seed.json
  processes.json         -- 10–20 процессов + steps (схема E2: role, step_io_items, frequency)
  org_chart.json         -- типовые роли / узлы
  roles/
    <role>.json          -- KPI lines, checklist lines, instruction outline
  prompts/               -- отраслевые system/user фрагменты (опционально)
  renders/               -- шаблоны читаемого вида (опционально)
```

Импорт пакета → сущности в **новой draft-ревизии**, seeds целей/задач = `suggested`.

### 7.3 Производство контента

`AI-черновик → правка методологом → валидация на клиенте (стройка)`.  
Eng делает **loader + валидатор манифеста**; наполнение — отдельный контент-бюджет (§14.2).

---

## 9. D3 — глубина MVP

| В MVP | Не в MVP |
|-------|----------|
| L0→L1 + импорт L2 из базиса/стройки + L3 сборка | Глубокая кастомная генерация уникальных процессов «с нуля» |
| Gap-карта + ручные assignments | Автоматический org redesign |
| План перехода с воротами (U5) | Полный HRIS / учёт сотрудников |
| Мост role → профиль вакансии | Авто-скрининг кандидатов по всем KPI |
| 1 пилот-пакет (стройка) + SME-базис | 4 полные отраслевые библиотеки |

**До старта U2 зафиксировать:**

- матрицу прав (§12);  
- `org.features.management_system`.

---

## 10. E1–E6 — финальные дельты (ревью №3)

> **Не меняем:** `entity_links` (не parent_id-дерево); нормализованные строки (не JSONB-массивы); порядок фаз U1–U5.

### 10.1 Принято в план

| ID | Суть | Фаза | Примечание Cursor |
|----|------|------|-------------------|
| **E1** | Graph Checker: `WITH RECURSIVE` на иерархических `link_kind` перед сохранением связи; цикл → 422 + путь; в invariant catalog | **U1** | Проверка только `decomposes` / `implements` / `measures`; `references`/`covers` не блокируем |
| **E2** | Шаг процесса BPMN-подобный: `title`, `role_id`, `frequency?`, `step_io_items` (in/out) | **U1** модель; **U3** контент | inputs/outputs — таблица строк, не JSONB-массив |
| **E3** | Режим «Карта»: React Flow; на гейтах — поклик-утверждение узлов | **U1** базовый граф; **U2+** gate UX | Read-only traceability в U1; approve-on-click — когда появляются ворота |
| **E4** | Impact + traceability — рекурсивный CTE по `entity_links` | **U1** traceability API; **U4** impact | `max_depth` (дефолт 50) + индексы на `(revision_id, source_type, source_id)` |
| **E5** | KPI: числовой таргет + `entity_links.measures` на метрику задачи; иначе 422. Regen по `line_id`, `is_manual` сохраняется | **U4** | Паттерн как `_merge_keep_manual` в опроснике |
| **E6** | Bottom-up fixtures = unit-тесты промптов (процесс→KPI/чек-лист) до верхних уровней; продукт top-down | **∥ каждая фаза** | `v2/backend/tests/fixtures/management/` + smoke перед gate фазы |

### 10.2 Схема — дополнительные поля

- `goals.weight` — numeric, nullable; UI + валидатор warning при сумме ≠ 100% (если все цели с weight).  
- `tasks.deadline` — date, nullable; связь с горизонтом родительской цели через валидатор, не hard FK.

### 10.3 Invariant catalog (расширение)

| Код | Проверка | Уровень |
|-----|----------|---------|
| `GRAPH_CYCLE` | цикл в иерархических links | error → 422 |
| `KPI_NO_TARGET` | KPI-строка без numeric target | error → 422 |
| `KPI_NO_METRIC_LINK` | KPI без `measures` → task.metric | error → 422 |
| `STEP_NO_ROLE` | process_step без role_id при approve L2a | error |
| `ORPHAN_ENTITY` | сущность без входящих/исходящих links (кроме корня) | warning |
| `STALE_DOWNSTREAM` | потомок не обновлён после правки предка | warning + stale flag |
| `GOAL_COUNT_EXCEEDED` | целей &gt; 5 после генерации L0 | warning (+ truncate в схеме) |
| `TASK_COUNT_EXCEEDED` | задач на цель &gt; 5 | warning (+ truncate в схеме) |

### 10.4 E6 — dev-практика (fixtures)

**Порядок разработки промптов (bottom-up):**

1. Фикстура: 1 процесс + 3–5 шагов + роли (`tests/fixtures/management/l3_process_to_role_docs.json`).  
2. Unit-тест: промпт L3 → JSON-схема → INSERT from SELECT → KPI/чек-лист без сирот.  
3. Фикстура L1: цели + задачи с метриками.  
4. Unit-тест: промпт L1 → задачи с `deadline` / metric links.  
5. Интеграционный smoke: top-down с воротами на фикстурной ревизии.

**Продуктовый порядок для клиента** остаётся top-down (L0→…→L5); fixtures не меняют UX.

### 10.5 E3 — React Flow (UI)

- Библиотека: `@xyflow/react` (React Flow).  
- Узлы: типы `goal` | `task` | `process` | `role` | `current_position`; цвет по `status` / `stale`.  
- Рёбра: из `entity_links`; клик по ребру → `link_kind` + meta.  
- **Gate mode:** узлы уровня с `status=draft` — кнопка «Утвердить» на узле (bulk approve уровня — отдельно).  
- Layout: elkjs или dagre для первичной раскладки; ручной drag → `node_layout(revision_id, node_type, node_id, x, y)`.  
- **Правило layout (W5):** привязка к `revision_id`; **draft** — редактируемый; **published** — read-only (заморожен). При fork новой ревизии layout не копируется автоматически — первичная autolayout.

### 10.6 E4 — SQL-паттерн (reference)

```sql
-- Предки сущности (traceability)
WITH RECURSIVE ancestors AS (
  SELECT target_type, target_id, source_type, source_id, link_kind, 1 AS depth
  FROM entity_links
  WHERE revision_id = :rev AND target_type = :t AND target_id = :id
  UNION ALL
  SELECT el.target_type, el.target_id, el.source_type, el.source_id, el.link_kind, a.depth + 1
  FROM entity_links el
  JOIN ancestors a ON el.target_type = a.source_type AND el.target_id = a.source_id
  WHERE el.revision_id = :rev AND a.depth < :max_depth
)
SELECT * FROM ancestors;

-- Потомки (impact после правки)
-- то же с обратным направлением по source → target
```

Сервис: `management_graph.py` — `check_cycle()`, `get_ancestors()`, `get_impact_set()`, `mark_stale_downstream()`.

---

## 11. Фазы U1–U5

### U1 — скелет руками + as-is модель (без ИИ)

**Сделано, когда:**

- миграции: system, revision, **wizard_sessions**, goals (`weight`, **baseline/target/metric_unit/metric_source**, **dimension_links**), tasks (`deadline`), process_steps + step_io_items, roles, entity_links, glossary, current_positions, role_assignments, stale, **node_layout**, **`mgmt_goal_dimensions` (seed BSC)**;  
- CRUD + **React Flow** карта (read-only layout + traceability click) — **экспертный режим**; форма цели: измерения + baseline/target;  
- **Graph Checker (E1)** + invariant catalog v0 + **`DIMENSION_BALANCE` warning**;  
- **traceability API (E4)** — ancestors CTE;  
- статусы draft/approved/published на сущностях уровня;  
- версии ревизий + простой diff список;  
- preview «профиль вакансии из Role» (read-only);  
- `task=` заготовки в сервисах (no-op);  
- **fixtures E6:** каркас `tests/fixtures/management/` + тест Graph Checker.

**Параллельно (не блокирует backend):** Figma / бумажный **прототип мастера** (W6).

**Не делаем:** генерацию ИИ, gap-отчёт, пакеты, frontend мастера, gate approve-on-click (→ U2).

### U2 — интервью + цели/задачи + мастер шаги 1–2

- `OwnerInterviewSession` + immutable answers;  
- блок «текущая команда» → `current_positions`;  
- импорт списка должностей (CSV/paste);  
- генерация черновика целей/задач (schema-first) + **prompt-инварианты (≤5 целей, ≤5 задач/цель)** + ворота;  
- **frontend: мастер шаги 1–2** (resumable через `wizard_sessions`);  
- **React Flow gate mode (E3)** — в экспертном режиме; поклик-утверждение L0/L1;  
- seeds из пакета (если выбран) только как `suggested`;  
- код-валидаторы L0/L1; критик на стыке L0→L1;  
- **fixtures E6:** unit-тест промпта L0/L1 на фикстурных answers.

### U3 — процессы / оргсхема / пакеты / gap + мастер шаги 3–4

- loader контент-пакетов + SME-базис + пилот «стройка» (process_steps по схеме E2);  
- L2a / L2b отдельные ворота + **gate mode на карте (E3)** — эксперт;  
- адаптация шагов под утверждённые задачи (не с нуля);  
- **gap-отчёт** + UI режим «Внедрение» (as-is / to-be / gap); **цифровой разрыв целей** `target − baseline` (без ProductivityGap/FTE);  
- **frontend: мастер шаги 3–4** — сводка, «Сгенерировать разрыв», React Flow визуализация, **preview L3 read-only**;  
- ручные `role_assignments`;  
- валидаторы L2 + Graph Checker на новых links;  
- **fixtures E6:** процесс→шаги→роли в пакете «стройка».

### U4 — документы ролей + impact

- L3: INSERT from SELECT + полировка wording;  
- **KPI invariant (E5):** target + measures-link; regen по line_id, `is_manual` сохраняется;  
- **impact CTE (E4):** `get_impact_set()` + stale cascade + scoped regen;  
- критик перед publish;  
- diff UI («Изменения»);  
- **fixtures E6:** unit-тест промпта process→KPI/checklist (главный bottom-up gate).  
- **Утверждение L3** — только экспертный режим «Документ» (не в мастере).

### U5 — внедрение + найм + экспорт + мастер шаг 5

- **frontend: мастер шаг 5** — утверждение плана перехода;  
- ИИ-черновик `transition_steps` из gap_items + утверждение;  
- трекер покрытия (инструкции / чек-листы / KPI / назначения);  
- автопредзаполнение `vacancy.documents.profile` из Role;  
- проверка «профиль вакансии ↔ утверждённая роль» (базовые поля);  
- экспорт PDF/DOCX (паттерн `offer_docx` / docs-конвейер).

---

## 12. Права и feature flag

| Действие | Роль (MVP) |
|----------|------------|
| Мастер (онбординг) | собственник | шаги 1–2: owner; шаг 5: owner/delegat |
| L0/L1 утверждение | собственник / `platform_owner` или org-роль `owner` | в мастере — inline на шаге 2 |
| L2/L3 правка и утверждение | HR / консультант (`hr_recruiter` + флаг модуля) |
| As-is CRUD, assignments | HR / консультант |
| План перехода утверждение | собственник или делегат |
| Публикация ревизии | собственник |

```json
// org settings / features
"management_system": true
```

Навигация: отдельный пункт продукта (не «ещё одна вкладка настроек»), виден только при флаге.

*Точные ключи ролей — зафиксированы до U2 (см. таблицу выше).*

---

## 13. Переиспользование стека

| Компонент | Готовность | Использование |
|-----------|------------|---------------|
| Паттерн опросника (normalize, panel, merge manual) | ✅ | L0 интервью |
| Jobs + ARQ + JobsLive | ✅ | генерации уровней, impact regen |
| document_generate / DocumentGeneration | ✅ | L3 + история версий документов |
| offer_docx | ✅ | образец экспорта |
| labels.ts | ✅ | EN keys / RU UI |
| Vacancy tab / shell layout | ✅ | навигация модуля |
| chat_json + `task=` | ✅ сейчас | все LLM |
| КАСКАД fast/top | ❌ план | подключить позже; fast = полировка L3 |
| Documents Lab D6 | ❌ stub | не опираться |
| @xyflow/react (React Flow) | новая зависимость | режим «Карта» (E3) + мастер шаг 4 |

---

## 14. Оценки

### 14.1 Engineering (чел·дн)

| Фаза | E1–E6 | **Финал (+ W1–W9)** | **+ F1–F2 (№5)** | **Итого №5** |
|------|-------|---------------------|------------------|--------------|
| **U1** | 11–14 | **11–14** | **+1** (dimensions + baseline fields) | **12–15** |
| **U2** | 5–7 | **7–9** | **+1** (интервью: текущие цифры + измерения) | **8–10** |
| **U3** | 8–11 | **10–13** | **+0.5–1** (numeric gap в отчёте) | **10.5–14** |
| **U4** | 7–9 | **7–9** | — | **7–9** |
| **U5** | 5–8 | **6–9** | — | **6–9** |
| **Итого** | 36–49 | **41–54** | **+2.5–3** | **43.5–57** |

*Округление для планирования: **~44–57 eng** (+2.5–3 к 41–54).*

### 14.2 Контент (отдельно от eng)

| Пакет | Оценка | Когда |
|-------|--------|-------|
| SME-базис (минимальный) | 1–2 дн | ∥ U1 |
| **Стройка (пилот)** | **6–10 дн** (методолог + отраслевой эксперт part-time, 3–5 консультаций) | **старт ∥ U1**; гейт: валидация экспертом + реальным клиентом перед U3→U4 |
| Производство / поставки / маркетплейсы | по 2–4 дн каждый | после U5 |

### 14.3 Зависимости по календарю

- КАСКАД **не** блокирует U2–U5.  
- ЯКОРЬ / ЭФИР / АССИСТЕНТ — параллельные ветки; СУП — отдельный SKU, минимальное пересечение файлов (`labels.ts`, shell nav, jobs whitelist).  
- Рекомендуемая git-ветка: отдельно от `feature/kaskad-yakor-assistent-efir` **или** та же feature-ветка с префиксом коммитов `sistema:` — решить при старте U1.

---

## 15. Scope control — НЕ делаем в MVP

- Привязка `current_positions` → `persons` / табель сотрудников  
- Зарплатные вилки и финмодель в целях  
- Мобильное приложение / отдельный клиентский портал СУП  
- Полный OKR-цикл с квартальными check-in  
- Автоматическое закрытие gap наймом без участия HR  
- Четыре полные отраслевые библиотеки  
- LLM, меняющий `entity_links` или coverage без человека  
- **Утверждение L3 одним кликом в мастере** (только preview)  
- **`dimension_ids UUID[]`** на целях (только link-таблица)  
- **ProductivityGapCalculator** → автонайм из productivity

---

## 16. Гейты ревью

| Переход | Гейт |
|---------|------|
| Старт U1 | План утверждён (ревью №3) ✅; правки №4 — на финальное подтверждение |
| U1 → U2 | CRUD + React Flow + Graph Checker + traceability CTE + `wizard_sessions`; fixtures; feature flag |
| **Frontend U2** | **Прототип мастера утверждён** (собственник / тест-пользователь) |
| U2 → U3 | Мастер шаги 1–2; prompt-инварианты; answers immutable; unit-тест L0/L1 |
| **U3 → U4** | Пакет «стройка» **валидирован экспертом и реальным клиентом**; gap; мастер шаги 3–4 (preview L3 only) |
| U4 → U5 | L3 approve в экспертном режиме; KPI invariant; impact CTE; unit-тест process→docs |
| U5 → release SKU | Мастер шаг 5; план перехода; вакансия из Role; экспорт |

---

## История правок плана

| Дата | Что |
|------|-----|
| 2026-08-23 | Первый черновик: п.1–9 Cursor + анти-глюки + D1–D3; оценки 34–47 eng |
| 2026-08-23 | **Ревью №3 — утверждён:** E1–E6, `goal.weight`, `task.deadline`; оценки **36–49 eng** |
| 2026-08-24 | **Ревью №4 (продуктовое):** W К1–К9 — мастер, prompt-инварианты, layout-per-revision, контент 6–10 дн; **41–54 eng** |
| 2026-08-23 | **Ревью №5 (метрики целей):** F1 BSC `mgmt_goal_dimensions` + links; F2 baseline/target + numeric gap; warning `DIMENSION_BALANCE`; ProductivityGap **не MVP**; **~44–57 eng** |
