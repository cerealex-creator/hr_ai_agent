# Запуск HR-приложения на Timeweb Cloud (4 ГБ RAM)

Пошаговая инструкция для **Ubuntu 22.04**, **Docker Compose**, конфигурация **2 vCPU / 4 ГБ / 50 ГБ NVMe** (тариф вроде **Cloud MSK 50**).

**Результат:** одно приложение Streamlit (`:8501`) + Telegram-бот на одном сервере, общая папка `data/`.

---

## Что будет работать после запуска

Замените `IP` на публичный адрес сервера:

| Кому | URL |
|------|-----|
| HR (вы) | `http://IP:8501/` |
| Генеральный директор | `http://IP:8501/master` |
| Руководитель отдела | `http://IP:8501/client?dept=Маркетинг` |

Список отделов — в `data/departments.json` (поле `name` должно **точно** совпадать с `dept=` в ссылке).

> Главную `/` клиентам не отправляйте — только `/master` и `/client?dept=...`.

---

## Что подготовить на Mac до старта

- [ ] Проект: `/Users/aleksandr/Desktop/hr_ai_agent`
- [ ] Файл **`.env`** с ключами (скопируйте из `.env.example` и заполните минимум):
  - `ROUTERAI_API_KEY` — ИИ
  - `TELEGRAM_BOT_TOKEN` — бот
  - `YANDEX_*` — если используете расшифровку SpeechKit
- [ ] Папка **`data/`** с `vacancies_db.json`, `departments.json`, `chats_db.json`
- [ ] Терминал на Mac
- [ ] ~30–40 минут на первый запуск (сборка Docker-образа)

Проверка локально (по желанию):

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run hri_full_v1.py
# В другом терминале:
python bot.py
```

---

## Шаг 1. Регистрация и создание сервера в Timeweb

1. Откройте https://timeweb.cloud/ → **Регистрация** → подтвердите email.
2. Пополните баланс (для 4 ГБ обычно хватает **500–1000 ₽** на первый месяц + IPv4, если тарифицируется отдельно).
3. Меню слева: **Облачные серверы** → **Создать**.

### Параметры сервера

| Параметр | Значение |
|----------|----------|
| ОС | **Ubuntu 22.04 LTS** |
| Регион | **Москва** или **Санкт-Петербург** |
| Конфигурация | **4 ГБ RAM**, **2 vCPU**, **50 ГБ** NVMe (Cloud MSK 50 или аналог) |
| IPv4 | **Включить** (публичный адрес обязателен) |
| Имя | `hr-app` |

Не берите 2 ГБ — для приложения + бота + Docker будет тесно.

### SSH-ключ (рекомендуется)

На **Mac**:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/timeweb_hr -N ""
cat ~/.ssh/timeweb_hr.pub
```

Скопируйте строку `ssh-ed25519 AAAA...` → в Timeweb при создании сервера → **SSH-ключи** → вставить.

4. Нажмите **Создать** → дождитесь статуса **Активен** (2–5 мин).
5. Запишите **публичный IPv4** (например `185.123.45.67`).

### Первый вход

```bash
ssh -i ~/.ssh/timeweb_hr root@ВАШ_IP
```

Если ключа не добавляли — пароль `root` придёт на email. На вопрос `Are you sure...` ответьте `yes`.

---

## Шаг 2. Базовая настройка сервера

На сервере (после `ssh`):

```bash
apt-get update && apt-get upgrade -y
apt-get install -y git rsync
mkdir -p /opt/hr_ai_agent
```

Опционально — часовой пояс Москвы:

```bash
timedatectl set-timezone Europe/Moscow
```

---

## Шаг 3. Копирование проекта с Mac на сервер

Команды выполняются **на Mac**:

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
chmod +x deploy/*.sh
./deploy/sync-to-server.sh root@ВАШ_IP
```

Скрипт кладёт проект в `/opt/hr_ai_agent/` и копирует папку `data/`.

> **Важно:** `sync-to-server.sh` использует `rsync --delete` — содержимое на сервере в этих папках **приводится к копии с Mac**. Если на сервере уже вели работу, сначала скачайте `data/` с сервера на Mac.

Если используете SSH-ключ:

```bash
rsync -avz -e "ssh -i ~/.ssh/timeweb_hr" \
  --exclude 'venv/' --exclude '__pycache__/' --exclude '.git/' \
  ./ root@ВАШ_IP:/opt/hr_ai_agent/
```

(или отредактируйте `sync-to-server.sh`, добавив `-e "ssh -i ~/.ssh/timeweb_hr"`.)

---

## Шаг 4. Установка Docker

На **сервере**:

```bash
cd /opt/hr_ai_agent
chmod +x deploy/install-docker.sh
bash deploy/install-docker.sh
```

Ожидаемый вывод:

```
Docker version ...
Docker Compose version ...
```

---

## Шаг 5. Секреты `.env`

Файл `.env` **не в git**. Скопируйте с Mac:

```bash
scp -i ~/.ssh/timeweb_hr \
  /Users/aleksandr/Desktop/hr_ai_agent/.env \
  root@ВАШ_IP:/opt/hr_ai_agent/.env
```

Проверка на сервере:

```bash
ls -la /opt/hr_ai_agent/.env
ls -la /opt/hr_ai_agent/data/vacancies_db.json
```

Права (на сервере):

```bash
chmod 600 /opt/hr_ai_agent/.env
```

---

## Шаг 6. Сборка и запуск

На **сервере**:

```bash
cd /opt/hr_ai_agent
docker compose up -d --build
```

Первый запуск **5–15 минут** (скачивание образа Python, установка зависимостей).

Статус контейнеров:

```bash
docker compose ps
```

Оба сервиса должны быть **Up**:

| Контейнер | Сервис | Назначение |
|-----------|--------|------------|
| `hr-ai-agent` | `hr-app` | Streamlit, порт 8501 |
| `hr-ai-bot` | `hr-bot` | Telegram-бот |

Логи:

```bash
# Приложение
docker compose logs -f hr-app

# Бот (в другом окне ssh)
docker compose logs -f hr-bot
```

Выход из логов: `Ctrl+C`.

Успешный бот в логах: строка вроде «Бот @username подключён» / «Напоминание отправлено» без циклических ошибок сети.

---

## Шаг 7. Открыть порт 8501 в Timeweb

Без этого браузер не откроет приложение.

1. Личный кабинет Timeweb → **Облачные серверы** → ваш сервер.
2. Раздел **Сеть** / **Firewall** / **Группы безопасности** (название может отличаться).
3. Добавьте правило **входящее**:
   - Протокол: **TCP**
   - Порт: **8501**
   - Источник: **0.0.0.0/0** (весь интернет) или IP вашего офиса, если хотите ограничить.

Проверка с Mac:

```bash
curl -s -o /dev/null -w "%{http_code}" http://ВАШ_IP:8501/_stcore/health
```

Ответ `200` — приложение живо.

---

## Шаг 8. Проверка в браузере

Откройте:

1. `http://ВАШ_IP:8501/` — вкладки Вакансии, История, Настройки.
2. `http://ВАШ_IP:8501/master` — мастер-зона.
3. `http://ВАШ_IP:8501/client?dept=Маркетинг` — клиентская зона (название из `departments.json`).

В Telegram: убедитесь, что бот **запущен только на этом сервере** (не на MacBook одновременно — иначе конфликт polling).

---

## Шаг 9. Ссылки для руководителей

Подставьте свой IP:

```
Мастер-зона:
http://ВАШ_IP:8501/master

Маркетинг:
http://ВАШ_IP:8501/client?dept=Маркетинг

Продажи:
http://ВАШ_IP:8501/client?dept=Продажи
```

Новый отдел: **Настройки** в приложении → создать подразделение → новая ссылка `/client?dept=НовоеНазвание`.

---

## Обновление приложения после правок на Mac

1. На Mac: правки → проверка → `git push` (по желанию).
2. Синхронизация на сервер:

```bash
cd /Users/aleksandr/Desktop/hr_ai_agent
./deploy/sync-to-server.sh root@ВАШ_IP
scp -i ~/.ssh/timeweb_hr .env root@ВАШ_IP:/opt/hr_ai_agent/.env
```

3. На сервере:

```bash
cd /opt/hr_ai_agent
docker compose up -d --build
```

Только перезапуск без пересборки:

```bash
docker compose restart
```

---

## Резервная копия `data/` (перед обновлением)

На **сервере**:

```bash
cd /opt/hr_ai_agent
tar czf /root/data-backup-$(date +%Y%m%d).tar.gz data/
```

Скачать на Mac:

```bash
scp -i ~/.ssh/timeweb_hr root@ВАШ_IP:/root/data-backup-*.tar.gz ~/Desktop/
```

---

## Полезные команды

| Действие | Команда |
|----------|---------|
| Статус | `docker compose ps` |
| Логи приложения | `docker compose logs -f hr-app` |
| Логи бота | `docker compose logs -f hr-bot` |
| Перезапуск всего | `docker compose restart` |
| Остановка | `docker compose down` |
| Место на диске | `df -h` и `docker system df` |
| RAM | `free -h` |

---

## Частые проблемы

### Страница не открывается (`connection refused`)

- Проверьте `docker compose ps` — контейнер `hr-app` должен быть Up.
- Откройте порт **8501** в firewall Timeweb (шаг 7).
- Логи: `docker compose logs hr-app`.

### `Out of memory` / контейнер падает

- В панели Timeweb увеличьте тариф до **6–8 ГБ RAM**.
- Убедитесь, что бот не запущен второй копией на Mac.

### Бот не отвечает / «Conflict: terminated by other getUpdates»

- Остановите бота на Mac: не запускайте `python bot.py` локально.
- На сервере: `docker compose restart hr-bot`.
- Должен работать **один** экземпляр бота на одну базу `data/`.

### После `sync-to-server` пропали свежие данные

- Скрипт перезаписывает `data/` с Mac. Перед синхронизацией скачайте актуальный `data/` с сервера или делайте бекап (см. выше).

### ИИ / SpeechKit не работает

- Проверьте `.env` на сервере: `ROUTERAI_API_KEY`, `YANDEX_*`.
- После смены `.env`: `docker compose restart`.

### Telegram: `Network is unreachable` или DNS, хотя Google открывается

На Timeweb IPv6 до `api.telegram.org` часто недоступен, IPv4 с **хоста** — работает. Проверка:

```bash
curl -4 -s --connect-timeout 5 -o /dev/null -w "%{http_code}\n" https://api.telegram.org   # с хоста: 200/302
docker compose exec hr-app curl -4 -s --connect-timeout 5 -o /dev/null -w "%{http_code}\n" https://api.telegram.org
```

Если с хоста `302`, а из контейнера `000` — Docker bridge блокируется. В `docker-compose.yml` включён **`network_mode: host`** (контейнеры используют сеть сервера напрямую). После смены:

```bash
cd /opt/hr_ai_agent
docker compose down
docker compose up -d --build
```

В коде также принудительный IPv4 (`network_ipv4.py`).

---

## Следующие шаги (после успешного запуска)

1. **Домен** — `hr.ваша-компания.ru` → A-запись на IP → HTTPS (Caddy/nginx или Cloudflare Tunnel).
2. **Пароль на клиентские зоны** — Cloudflare Access или Basic Auth на reverse proxy.
3. **Автобэкап `data/`** — cron на сервере раз в сутки.

Общая схема и краткая версия: [ИНСТРУКЦИЯ.md](./ИНСТРУКЦИЯ.md).

---

## Чеклист «всё готово»

- [ ] Сервер Timeweb 4 ГБ, Ubuntu 22.04, статус «Активен»
- [ ] SSH вход работает
- [ ] `/opt/hr_ai_agent` с кодом и `data/`
- [ ] `.env` на сервере
- [ ] `docker compose ps` — оба контейнера Up
- [ ] Порт 8501 открыт
- [ ] `http://IP:8501/master` открывается в браузере
- [ ] Бот отвечает в Telegram, второй экземпляр не запущен
- [ ] Ссылки для отделов разосланы руководителям
