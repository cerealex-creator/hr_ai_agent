#!/usr/bin/env bash
# Останавливает фоновые процессы Streamlit и бота.
# Использование: ./scripts/stop_local.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=local_run_common.sh
source "$SCRIPT_DIR/local_run_common.sh"

ROOT="$(local_run_project_root)"
RUN_DIR="$ROOT/run"
STREAMLIT_PID_FILE="$RUN_DIR/streamlit.pid"
BOT_PID_FILE="$RUN_DIR/bot.pid"

stop_pid_file() {
    local label="$1"
    local pid_file="$2"
    if [[ ! -f "$pid_file" ]]; then
        echo "$label: не запущен (нет $pid_file)"
        return 0
    fi
    local pid
    pid="$(tr -d '[:space:]' <"$pid_file")"
    if local_run_pid_alive "$pid"; then
        kill "$pid" 2>/dev/null || true
        sleep 1
        if local_run_pid_alive "$pid"; then
            kill -9 "$pid" 2>/dev/null || true
        fi
        echo "$label остановлен (PID $pid)"
    else
        echo "$label: процесс уже не работает"
    fi
    rm -f "$pid_file"
}

stop_pid_file "Streamlit" "$STREAMLIT_PID_FILE"
stop_pid_file "Бот" "$BOT_PID_FILE"

# На случай ручного запуска python bot.py в терминале — убрать все копии в проекте
for pid in $(pgrep -f "${ROOT}/.*bot\\.py" 2>/dev/null || true); do
    if local_run_pid_alive "$pid"; then
        kill "$pid" 2>/dev/null || true
        echo "Дополнительный bot.py остановлен (PID $pid)"
    fi
done
rm -f "$RUN_DIR/bot.lock"

local_run_notify_mac "HR Agent" "Приложение остановлено."
