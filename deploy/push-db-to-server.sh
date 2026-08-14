#!/bin/bash
# Локальная Postgres (hr-v2-db) + data/ → сервер (перезапись).
# Usage:
#   CONFIRM=yes ./deploy/push-db-to-server.sh
#   CONFIRM=yes SERVER=root@IP ./deploy/push-db-to-server.sh
#   CONFIRM=yes SYNC_MESSAGING_ENV=yes ./deploy/push-db-to-server.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=db-sync-common.sh
source "${SCRIPT_DIR}/db-sync-common.sh"

require_confirm "перезаписать БД и data/ на сервере ${SERVER}"
load_local_pg_env
require_local_db

TS="$(stamp)"
DUMP_NAME="hr_v2_push_${TS}.dump"
LOCAL_DUMP="/tmp/${DUMP_NAME}"
REMOTE_DUMP="/tmp/${DUMP_NAME}"
REMOTE_BACKUP="hr_v2_server_backup_${TS}.dump"

echo "→ Локальный дамп (${LOCAL_DB_CONTAINER})…"
docker exec "${LOCAL_DB_CONTAINER}" pg_dump -U "${POSTGRES_USER}" -Fc "${POSTGRES_DB}" > "${LOCAL_DUMP}"
LOCAL_BYTES="$(wc -c < "${LOCAL_DUMP}" | tr -d ' ')"
echo "   ${LOCAL_DUMP} (${LOCAL_BYTES} bytes)"

echo "→ Бэкап текущей серверной БД…"
ssh "${SERVER}" "mkdir -p ${REMOTE_BACKUPS}"
ssh "${SERVER}" "docker exec ${REMOTE_DB_CONTAINER} pg_dump -U ${POSTGRES_USER} -Fc ${POSTGRES_DB}" \
  > "/tmp/${REMOTE_BACKUP}"
scp "/tmp/${REMOTE_BACKUP}" "${SERVER}:${REMOTE_BACKUPS}/${REMOTE_BACKUP}"
rm -f "/tmp/${REMOTE_BACKUP}"
echo "   ${SERVER}:${REMOTE_BACKUPS}/${REMOTE_BACKUP}"

echo "→ Копирование дампа на сервер…"
scp "${LOCAL_DUMP}" "${SERVER}:${REMOTE_DUMP}"

echo "→ Останов api/worker на сервере…"
remote_compose stop api worker 2>/dev/null || true

echo "→ Восстановление БД на сервере…"
ssh "${SERVER}" bash -s <<EOF
set -euo pipefail
docker cp "${REMOTE_DUMP}" ${REMOTE_DB_CONTAINER}:/tmp/restore.dump
docker exec ${REMOTE_DB_CONTAINER} pg_restore \
  --clean --if-exists --no-owner --no-acl \
  -U ${POSTGRES_USER} -d ${POSTGRES_DB} /tmp/restore.dump || true
docker exec ${REMOTE_DB_CONTAINER} rm -f /tmp/restore.dump
rm -f "${REMOTE_DUMP}"
# Локальная схема может быть новее alembic_version — иначе API падает на upgrade.
cd ${REMOTE_V2}
docker compose -f ${REMOTE_COMPOSE_FILE} --env-file ${REMOTE_ENV_FILE} run --rm api alembic stamp head
EOF
rm -f "${LOCAL_DUMP}"

echo "→ Синхронизация data/ (app_settings, токены, …)…"
rsync -avz \
  --exclude '.DS_Store' \
  --exclude 'output/' \
  --exclude 'tmp/' \
  "${DATA_DIR}/" "${SERVER}:${REMOTE_DIR}/data/"

if [[ "${SYNC_MESSAGING_ENV:-yes}" == "yes" && -f "${V2_DIR}/.env" ]]; then
  echo "→ Обновление messaging/PUBLIC_APP_URL в ${REMOTE_ENV_FILE} на сервере…"
  # shellcheck disable=SC1090
  source <(grep -E '^(TELEGRAM_BOT_TOKEN|TELEGRAM_HR_USER_ID|TELEGRAM_REMINDER_TZ|MESSAGING_OUTBOUND_ENABLED|MESSAGING_INBOUND_ENABLED|MESSAGING_POLL_ENABLED)=' "${V2_DIR}/.env" | sed 's/\r$//')
  ssh "${SERVER}" bash -s <<REMOTE
set -euo pipefail
ENV_FILE="${REMOTE_V2}/${REMOTE_ENV_FILE}"
touch "\$ENV_FILE"
upsert() {
  local key="\$1" val="\$2"
  if grep -q "^\${key}=" "\$ENV_FILE"; then
    sed -i.bak "s|^\${key}=.*|\${key}=\${val}|" "\$ENV_FILE"
  else
    printf '%s=%s\n' "\$key" "\$val" >> "\$ENV_FILE"
  fi
}
upsert PUBLIC_APP_URL "https://hr-toolbox.ru"
upsert MESSAGING_OUTBOUND_ENABLED "${MESSAGING_OUTBOUND_ENABLED:-true}"
upsert MESSAGING_INBOUND_ENABLED "${MESSAGING_INBOUND_ENABLED:-true}"
upsert MESSAGING_POLL_ENABLED "${MESSAGING_POLL_ENABLED:-true}"
upsert TELEGRAM_BOT_TOKEN "${TELEGRAM_BOT_TOKEN:-}"
upsert TELEGRAM_HR_USER_ID "${TELEGRAM_HR_USER_ID:-}"
upsert TELEGRAM_REMINDER_TZ "${TELEGRAM_REMINDER_TZ:-Europe/Moscow}"
rm -f "\${ENV_FILE}.bak"
REMOTE
fi

echo "→ Запуск api/worker и проверка…"
ssh "${SERVER}" bash -s <<EOF
set -euo pipefail
cd ${REMOTE_V2}
docker compose -f ${REMOTE_COMPOSE_FILE} --env-file ${REMOTE_ENV_FILE} up -d api worker
docker exec ${REMOTE_DB_CONTAINER} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \
  "SELECT (SELECT count(*) FROM candidates) AS candidates, (SELECT count(*) FROM vacancies) AS vacancies, (SELECT count(*) FROM clients) AS clients;"
EOF

echo ""
echo "Готово. Основная база теперь на ${SERVER} (https://hr-toolbox.ru)."
echo "Локальный pull: CONFIRM=yes ./deploy/pull-db-from-server.sh"
