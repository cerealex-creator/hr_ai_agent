# Откат версии приложения

## Точка отката перед шаблонами вакансий

| Метка | Коммит | Описание |
|-------|--------|----------|
| Тег `pre-vacancy-templates` | `46360d5` | Полная Telegram-зона, обновление карточек при досылке задания, индикатор несохранённых изменений |
| Ветка `backup/pre-vacancy-templates` | `46360d5` | То же самое |

Откат:

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
git checkout pre-vacancy-templates
# или вернуть main: git reset --hard pre-vacancy-templates
```

Данные в `data/` не затрагиваются. Файл `data/vacancy_templates.json` появится только после внедрения шаблонов.

---

## Точка отката перед полноценной Telegram-клиентской зоной

| Метка | Коммит | Описание |
|-------|--------|----------|
| Тег `pre-telegram-full-chat` | `a4c04f6` | Стабильная версия до доработки бота (напоминания, обязательный комментарий, /pending) |
| Ветка `backup/pre-telegram-full-chat` | `a4c04f6` | То же самое |

---

## Как откатиться (на Mac, в папке проекта)

### Вариант А — временно посмотреть старую версию

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
git stash
git checkout pre-telegram-full-chat
```

Вернуться к новой версии:

```bash
git checkout main
git stash pop
```

### Вариант Б — полностью вернуть main к старой версии

**Осторожно:** удалит коммиты после точки отката из ветки `main`.

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
git checkout main
git reset --hard pre-telegram-full-chat
```

Новая версия останется в истории reflog (`git reflog`).

### Вариант В — откат только отдельных файлов

```bash
git checkout pre-telegram-full-chat -- bot.py telegram_bot_handlers.py telegram_workflow.py telegram_reminders.py
```

---

## Предыдущая точка отката (Telegram MVP)

| Метка | Коммит |
|-------|--------|
| `pre-telegram-client-mvp` | `41b81d4` |

---

## После отката

1. Перезапустите Streamlit: `streamlit run hri_full_v1.py`
2. Перезапустите бота: `python bot.py` или `docker compose restart hr-bot`
3. Данные в `data/` **не затрагиваются** откатом кода

---

## Что добавлено после `pre-telegram-full-chat` (незакоммичено поверх `a4c04f6`)

Сейчас `HEAD` = тег отката; весь новый функционал — **локальные изменения**, не отдельные коммиты.

| Блок | Файлы | Назначение |
|------|-------|------------|
| Статусы и комментарии | `telegram_workflow.py`, `telegram_bot_handlers.py` | Статус + уведомление, обязательный комментарий для Отказ/Подумать, смена статуса, собеседование |
| Напоминания | `telegram_reminders.py`, `telegram_scheduler_state.py` | Встреча −1ч, просрочка оценки, «Подумать» 5д |
| Навигатор `/candidates` | `telegram_candidate_nav.py`, `telegram_nav_session.py` | Стрелки, переход к карточке, ephemeral-сообщения |
| Chat ID | `telegram_chat_id.py`, `telegram_notify.py`, `vacancy_store.py` | Синхронизация chat_id из `chats_db`, сравнение legacy/супергруппа |
| Привязка карточек | `telegram_posts` в кандидатах, `telegram_client.py` | message_id для reply и навигатора |
| Прочее | `telegram_bot_commands.py`, `telegram_chat_stats.py`, `models.py`, `client_actions.py` | Команды бота, статистика, этапы HR |

### Когда имеет смысл откат

- **Полный откат к `pre-telegram-full-chat`** — если нужна стабильная MVP-зона без `/candidates` и напоминаний. Данные в `data/` сохранятся, но `telegram_posts` и статусы останутся.
- **Частичный откат** — только `telegram_candidate_nav.py` + связанные handlers, если ломается только навигатор.
- **Не откатываться** — если баги локализованы (устаревший `message_id` после удаления сообщений в чате, рассинхрон chat_id). Исправляется синхронизацией привязки, без потери функционала.

### После удаления сообщений в Telegram

Код **не узнаёт** об удалении автоматически. Нужно одно из:

1. Нажать любую кнопку на **актуальной** карточке (обновит `message_id` в базе), или
2. Отправить кандидата заново из HR («Отправить в общий чат»).
