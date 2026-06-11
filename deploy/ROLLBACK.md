# Откат версии приложения

## Точка отката перед Telegram-клиентской зоной

| Метка | Коммит | Описание |
|-------|--------|----------|
| Тег `pre-telegram-client-mvp` | `41b81d4` | Стабильная версия до MVP Telegram |
| Ветка `backup/pre-telegram-client-mvp` | `41b81d4` | То же самое |

---

## Как откатиться (на Mac, в папке проекта)

### Вариант А — временно посмотреть старую версию

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
git stash
git checkout pre-telegram-client-mvp
```

Вернуться к новой версии:

```bash
git checkout feature/telegram-client-mvp
git stash pop
```

### Вариант Б — полностью вернуть main к старой версии

**Осторожно:** удалит коммиты Telegram MVP из ветки `main`.

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
git checkout main
git reset --hard pre-telegram-client-mvp
```

Новая версия останется в ветке `feature/telegram-client-mvp`.

### Вариант В — откат только одного файла

```bash
git checkout pre-telegram-client-mvp -- bot.py client_zone.py
```

---

## После отката

1. Перезапустите Streamlit: `streamlit run hri_full_v1.py`
2. Если бот был запущен — остановите: `docker compose stop hr-bot` или Ctrl+C в терминале с `bot.py`
3. Данные в `data/` **не затрагиваются** откатом кода (папка в `.gitignore`)

---

## Текущая рабочая ветка MVP

`feature/telegram-client-mvp` — Telegram-клиентская зона (кнопки статуса в чате).
