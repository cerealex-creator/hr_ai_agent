# ЯКОРЬ: гонка при создании persons

## Контекст

Таблица `persons` **намеренно без UNIQUE** на `match_phone` / `match_email`.
Два одновременных запроса на create могут создать два person с одним телефоном.

## Поведение системы

- `refresh_person_keys()` — единственный choke-point.
- Алгоритм: find by (org, phone|email) → first match wins → иначе INSERT person.
- Это не баг — trade-off за простоту и отсутствие блокировок intake.

## Что делать при обнаружении дублей persons

1. Запустить группировку:
   ```bash
   python -m app.scripts.find_duplicate_groups --org-id <UUID> --output /tmp/dup.json
   ```
2. Ручное слияние (flatten, **не** chain resolve):
   ```bash
   python -m app.scripts.merge_persons --target <UUID> --sources <UUID>,<UUID>
   ```
3. Скрипт merge:
   - `UPDATE candidates SET person_id = target WHERE person_id IN (sources)`
   - `UPDATE talent_pool_entries SET person_id = target WHERE person_id IN (sources)`
   - `UPDATE persons SET merged_into_person_id = target WHERE id IN (sources)`
4. Проверка:
   ```bash
   python -m app.scripts.verify_person_coverage
   ```

## Запросы в runtime

- **Не** резолвим цепочку `merged_into_person_id` в SELECT.
- На карточках всегда канонический `person_id` после flatten.

## Опционально (не в MVP)

Advisory lock `pg_advisory_xact_lock(hash(org_id, match_phone))` внутри
`refresh_person_keys()` — снижает гонку без UNIQUE.
