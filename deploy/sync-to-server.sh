#!/bin/bash
# Копирование проекта и данных с Mac на сервер (запускать на Mac)
# Использование: ./deploy/sync-to-server.sh user@123.45.67.89
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Использование: ./deploy/sync-to-server.sh user@IP_СЕРВЕРА"
  echo "Пример:       ./deploy/sync-to-server.sh root@185.123.45.67"
  exit 1
fi

SERVER="$1"
REMOTE_DIR="/opt/hr_ai_agent"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "→ Синхронизация проекта на ${SERVER}:${REMOTE_DIR}"

rsync -avz --delete \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '.git/' \
  --exclude 'backups/' \
  --exclude 'Downloads/' \
  --exclude '.DS_Store' \
  "${PROJECT_DIR}/" "${SERVER}:${REMOTE_DIR}/"

echo ""
echo "Готово. На сервере выполните:"
echo "  cd ${REMOTE_DIR} && docker compose up -d --build"
