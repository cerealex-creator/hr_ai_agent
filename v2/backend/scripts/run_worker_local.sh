#!/usr/bin/env bash
# Локальный ARQ worker без HTTP-прокси Cursor (иначе RouterAI → 403 Tunnel).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"   # v2/
BACKEND="$ROOT/backend"
cd "$BACKEND"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy \
  SOCKS_PROXY SOCKS5_PROXY socks_proxy socks5_proxy \
  GIT_HTTP_PROXY GIT_HTTPS_PROXY || true
export NO_PROXY='*'
export no_proxy='*'
exec "$BACKEND/.venv/bin/arq" app.workers.settings.WorkerSettings
