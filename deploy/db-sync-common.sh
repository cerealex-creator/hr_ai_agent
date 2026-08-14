#!/bin/bash
# Shared defaults for deploy/push-db-to-server.sh and deploy/pull-db-from-server.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
V2_DIR="${PROJECT_DIR}/v2"
DATA_DIR="${PROJECT_DIR}/data"

SERVER="${SERVER:-root@201.34.137.208}"
REMOTE_DIR="${REMOTE_DIR:-/opt/hr_ai_agent}"
REMOTE_V2="${REMOTE_DIR}/v2"
REMOTE_BACKUPS="${REMOTE_DIR}/backups/db"

LOCAL_DB_CONTAINER="${LOCAL_DB_CONTAINER:-hr-v2-db}"
REMOTE_DB_CONTAINER="${REMOTE_DB_CONTAINER:-hr-v2-side-db}"
REMOTE_COMPOSE_FILE="${REMOTE_COMPOSE_FILE:-docker-compose.sidecar.yml}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-.env.sidecar}"

POSTGRES_USER="${POSTGRES_USER:-hr_v2}"
POSTGRES_DB="${POSTGRES_DB:-hr_v2}"

load_local_pg_env() {
  if [[ -f "${V2_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a
    source <(grep -E '^(POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB|POSTGRES_PORT)=' "${V2_DIR}/.env" | sed 's/\r$//')
    set +a
  fi
  POSTGRES_USER="${POSTGRES_USER:-hr_v2}"
  POSTGRES_DB="${POSTGRES_DB:-hr_v2}"
}

require_local_db() {
  if ! docker ps --format '{{.Names}}' | grep -qx "${LOCAL_DB_CONTAINER}"; then
    echo "Локальный Postgres не запущен (контейнер ${LOCAL_DB_CONTAINER})."
    echo "  cd v2 && docker compose up -d db"
    exit 1
  fi
}

require_confirm() {
  local action="$1"
  if [[ "${CONFIRM:-}" != "yes" ]]; then
    echo "Операция: ${action}"
    echo "Нужно явное подтверждение: CONFIRM=yes $0"
    exit 1
  fi
}

remote_db_exec() {
  ssh "${SERVER}" "docker exec ${REMOTE_DB_CONTAINER} $*"
}

remote_compose() {
  ssh "${SERVER}" "cd ${REMOTE_V2} && docker compose -f ${REMOTE_COMPOSE_FILE} --env-file ${REMOTE_ENV_FILE} $*"
}

stamp() {
  date +%Y%m%d_%H%M%S
}
