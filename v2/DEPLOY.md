# Deploy v2 на Timeweb (пилот)

Один публичный домен → **nginx (TLS)** → **Next.js** → rewrite `/api/v1/*` → **FastAPI**.  
Так работают httpOnly cookies и SSE (как в D4). Postgres/Redis/API **не** торчат в интернет.

Каналы заказчика: **Bitrix + Web Client Zone**. Telegram outbound/inbound/poll — **off**.

## Что нужно заранее

1. VPS Timeweb (Docker + Docker Compose).
2. Домен / поддомен (A-запись на IP сервера), например `hr.example.com`.
3. TLS-сертификат: Let's Encrypt или сертификат из панели Timeweb.
4. Секреты: пароль Postgres, `JWT_SECRET` (≥32 символов), пароль owner.

## Sidecar (рядом с LexForge, пока нет домена)

Если на том же VPS уже крутится другой продукт (например LexForge на `:80`/`:3000`/`:8000`):

```bash
cd /opt/hr_ai_agent/v2
cp .env.sidecar.example .env.sidecar   # пароли + JWT
docker compose -f docker-compose.sidecar.yml --env-file .env.sidecar up -d --build
```

- UI: `http://SERVER_IP:8080` (порт задаётся `HTTP_PORT`)
- Postgres/Redis/API **не** публикуются на хост — конфликта с LexForge нет
- `APP_ENV=pilot` + `AUTH_COOKIE_SECURE=false` — только для HTTP-smoke до появления HTTPS
- Когда будет домен и TLS → `docker-compose.prod.yml` + `DEPLOY.md` (и выключить sidecar)


```bash
cd v2
cp .env.production.example .env.prod
# отредактируйте .env.prod: PUBLIC_HOST, пароли, JWT_SECRET, AUTH_BOOTSTRAP_*, CORS_ORIGINS

# TLS-файлы
# deploy/certs/fullchain.pem
# deploy/certs/privkey.pem
# см. deploy/certs/README.md

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Данные: **пустая БД**. Owner создаётся из `AUTH_BOOTSTRAP_EMAIL` / `AUTH_BOOTSTRAP_PASSWORD` при старте API (если пользователя ещё нет). Импорт тестового `data/` **не** делайте на пилоте для внешних клиентов.

Доп. пользователи:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec api \
  python -m app.scripts.create_user \
  --email hr2@example.com --password '…' --role platform_owner
```

## Сервисы

| Сервис | Роль |
|--------|------|
| `nginx` | :80 → HTTPS redirect, :443 TLS → `web` |
| `web` | Next.js UI + rewrite `/api/v1` → `api` |
| `api` | FastAPI (`APP_ENV=production`, fail-fast JWT/cookies) |
| `worker` | ARQ (jobs: HH, demo, STT, …) |
| `db` / `redis` | только во внутренней сети compose |

Telegram-poller в prod-compose **нет** (намеренно).

## Hardening (включено)

- При `APP_ENV=production` API **не стартует**, если `JWT_SECRET` слабый/короткий или `AUTH_COOKIE_SECURE` не `true`.
- Compose выставляет `AUTH_COOKIE_SECURE=true`, messaging flags off по умолчанию.
- `alembic upgrade head` при старте контейнера `api`.

## Nginx / TLS

Конфиг: [`deploy/nginx.conf`](./deploy/nginx.conf).

- HTTP → HTTPS.
- Отдельный `location` для `/api/v1/events/` с `proxy_buffering off` (SSE).
- Серты в `deploy/certs/` (в git не коммитятся).

Let's Encrypt (пример на хосте):

```bash
# после выпуска сертификата:
sudo cp /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem v2/deploy/certs/fullchain.pem
sudo cp /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem v2/deploy/certs/privkey.pem
sudo chown "$USER" v2/deploy/certs/*.pem
chmod 600 v2/deploy/certs/privkey.pem
docker compose -f docker-compose.prod.yml --env-file .env.prod restart nginx
```

## Bitrix (после первого входа)

1. Войти как owner → **Настройки → Каналы / Bitrix**.
2. Включить Bitrix, webhook URL, `public_api_base` = `https://YOUR_DOMAIN` (или URL API, если decide идёт напрямую — для same-origin обычно `https://YOUR_DOMAIN`).
3. Ответственный, сохранить → «Отправить тестовую задачу».
4. Каналы уведомления: `bitrix` + `web`.

Decide-ссылки и client zone `/c/{token}` должны открываться по HTTPS того же хоста.

## Smoke checklist

- [ ] `https://YOUR_DOMAIN` → страница входа
- [ ] Логин owner (bootstrap)
- [ ] `GET https://YOUR_DOMAIN/api/v1/health` → ok (через rewrite)
- [ ] `/jobs` → «Запустить демо» → badge в topbar + toast
- [ ] Компания → client zone token → `/c/…` открывается без логина HR
- [ ] Bitrix test-task (если настроили)
- [ ] В Network нет запросов на отдельный API-порт; cookies на том же домене

## Типичные проблемы

| Симптом | Что проверить |
|---------|----------------|
| API контейнер рестартится | `docker logs hr-v2-prod-api` — слабый `JWT_SECRET` или `AUTH_COOKIE_SECURE` |
| Не логинится / сразу выкидывает | HTTPS, `AUTH_COOKIE_SECURE=true`, часы сервера, `CORS_ORIGINS` |
| SSE / badge молчит | nginx `events` location, worker запущен, логин выполнен |
| 502 от nginx | `web`/`api` healthy: `docker compose … ps` |
| Demo висит в очереди | контейнер `worker` |

## Локальная отладка prod-конфига

Без настоящего TLS можно временно подставить self-signed в `deploy/certs/` (браузер будет ругаться).  
Для повседневной разработки используйте обычный [`docker-compose.yml`](./docker-compose.yml) / `npm run dev` + uvicorn.

## Откат

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod down
# том БД: hr_v2_prod_pgdata — удалять только осознанно
# docker volume rm hr_v2_prod_pgdata
```
