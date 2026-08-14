#!/bin/bash
# Сервер → локальная Postgres (hr-v2-db) + data/ (перезапись локали).
# Usage:
#   CONFIRM=yes ./deploy/pull-db-from-server.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=db-sync-common.sh
source "${SCRIPT_DIR}/db-sync-common.sh"

require_confirm "перезаписать локальную БД и data/ с сервера ${SERVER}"
load_local_pg_env
require_local_db

TS="$(stamp)"
DUMP_NAME="hr_v2_pull_${TS}.dump"
LOCAL_DUMP="/tmp/${DUMP_NAME}"
LOCAL_BACKUP="/tmp/hr_v2_local_backup_${TS}.dump"

echo "→ Локальный бэкап перед pull…"
docker exec "${LOCAL_DB_CONTAINER}" pg_dump -U "${POSTGRES_USER}" -Fc "${POSTGRES_DB}" > "${LOCAL_BACKUP}"
echo "   ${LOCAL_BACKUP}"

echo "→ Дамп с сервера…"
ssh "${SERVER}" "docker exec ${REMOTE_DB_CONTAINER} pg_dump -U ${POSTGRES_USER} -Fc ${POSTGRES_DB}" > "${LOCAL_DUMP}"

echo "→ Останов локальных api/worker (если запущены)…"
docker stop hr-v2-api hr-v2-worker 2>/dev/null || true

echo "→ Восстановление локальной БД…"
docker cp "${LOCAL_DUMP}" "${LOCAL_DB_CONTAINER}:/tmp/restore.dump"
docker exec "${LOCAL_DB_CONTAINER}" pg_restore \
  --clean --if-exists --no-owner --no-acl \
  -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" /tmp/restore.dump
docker exec "${LOCAL_DB_CONTAINER}" rm -f /tmp/restore.dump
rm -f "${LOCAL_DUMP}"

echo "→ Синхронизация data/ с сервера…"
rsync -avz \
  --exclude '.DS_Store' \
  --exclude 'output/' \
  --exclude 'tmp/' \
  "${SERVER}:${REMOTE_DIR}/data/" "${DATA_DIR}/"

echo "→ Запуск локальных сервисов…"
docker start hr-v2-api hr-v2-worker 2>/dev/null || true

echo "→ Проверка локально…"
docker exec "${LOCAL_DB_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c \
  "SELECT (SELECT count(*) FROM candidates) AS candidates, (SELECT count(*) FROM vacancies) AS vacancies, (SELECT count(*) FROM clients) AS clients;"

echo ""
echo "Готово. Локальная копия совпадает с сервером."
echo "Совет: в v2/.env держите MESSAGING_OUTBOUND_ENABLED=false локально, чтобы не слать в боевой Telegram."
