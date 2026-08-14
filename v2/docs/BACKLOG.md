# BACKLOG — крупные и несрочные задачи

> **Кодовое слово:** **`БЭКЛОГ`** — записать сюда / спланировать / не брать в ближайший PR без явной команды.  
> Ближайшие задачи → [`QUEUE.md`](QUEUE.md).  
> Сделано → `.cursor/DEVLOG.md`.

## Правила

| Критерий | Сюда (BACKLOG) |
|----------|----------------|
| Новая сущность / таблица / отдельный модуль | ✅ |
| >3 чел·дней или несколько PR | ✅ |
| Зависит от незавершённой волны | ✅ |
| Feature flag, архитектурное ревью | ✅ |

**Статусы:** `inbox` → `planned` → `in_progress` → `done` (перенос в DEVLOG)

**Шаблон записи:**
```markdown
### [B-YYYY-MM-DD-NN] Название
- **Источник:** …
- **Суть:** …
- **Модуль:** …
- **Сложность:** S | M | L
- **Зависимости:** …
- **Статус:** inbox | planned | in_progress | done
- **Документ / план:** ссылка
```

---

## Inbox

*(пусто — новые крупные идеи добавляются сюда)*

---

## Planned

### [B-YAKOR-001] ЯКОРЬ — persons, дедуп, аналитика, теги, талант-база

- **Источник:** продуктовый бриф + ревью архитектора (2026-08-14)
- **Суть:** таблица `persons`, дедуп по match-ключам, время на стадиях, теги/сегменты, talent pool (отдельная сущность). Кодовое слово запуска: **`ЯКОРЬ`**.
- **Модуль:** candidates, stats, talent-pool, persons
- **Сложность:** L (3 PR, ~30–37 чел·дней)
- **Зависимости:** зелёный smoke §1–24 перед PR1
- **Статус:** planned
- **Документ / план:** [`IMPLEMENTATION_PLAN_YAKOR.md`](IMPLEMENTATION_PLAN_YAKOR.md)  
- **Runbook:** [`.cursor/runbooks/yakor-person-race.md`](../../.cursor/runbooks/yakor-person-race.md)

**Волны:**
| PR | Волна | Содержание |
|----|-------|------------|
| PR1 | D1 | persons + dedup |
| PR2 | D2+D3 | stage analytics + tags + segments |
| PR3 | T | talent pool |

**Старт:** только по команде **`ЯКОРЬ PR1`** (не путать с **`ОЧЕРЕДЬ`**).

---

### [B-KASKAD-001] КАСКАД — ИИ tier fast/top, двухстадийные pipeline

- **Источник:** продуктовый бриф ИИ-каскад (2026-08-14)
- **Суть:** детерминированная маршрутизация задач fast/top; extract→eval для резюме и интервью; `ai_usage_log`; UI N7; baseline vs cascade. Кодовое слово: **`КАСКАД`**.
- **Модуль:** ai_json, jobs, settings/ai, все LLM-сервисы
- **Сложность:** L (4 фазы, ~16–21 чел·день)
- **Зависимости:** координация payload keys с ЯКОРЬ (tags); migrations отдельным PR от ЯКОРЬ
- **Статус:** planned
- **Документ / план:** [`IMPLEMENTATION_PLAN_KASKAD.md`](IMPLEMENTATION_PLAN_KASKAD.md)

**Волны:** P1 router+log → P2 resume/interview → P3 rest+UI → P4 rollout

---

## In progress

*(нет)*

---

## Done

*(переносить в DEVLOG, здесь оставлять ссылку на запись)*
