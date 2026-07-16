#!/usr/bin/env bash
# Запускает Streamlit и бота в фоне (не привязаны к окну терминала).
# Использование: ./scripts/start_local.sh
# Без бота: HR_LOCAL_SKIP_BOT=1 ./scripts/start_local.sh

set -euo pipefail

# Finder/AppleScript запускает приложение с урезанным PATH без Homebrew.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=local_run_common.sh
source "$SCRIPT_DIR/local_run_common.sh"

ROOT="$(local_run_project_root)"
RUN_DIR="$ROOT/run"
LOG_DIR="$RUN_DIR/logs"
STREAMLIT_PID_FILE="$RUN_DIR/streamlit.pid"
BOT_PID_FILE="$RUN_DIR/bot.pid"
STREAMLIT_PORT="${HR_LOCAL_STREAMLIT_PORT:-8501}"
STREAMLIT_URL="http://127.0.0.1:${STREAMLIT_PORT}/"

mkdir -p "$LOG_DIR"
cd "$ROOT"

if ! PY="$(local_run_venv_python "$ROOT")"; then
    local_run_alert_mac "HR Agent" "Не найден venv. В папке проекта выполните: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
    local_run_alert_mac "HR Agent" "Нет файла .env в папке проекта. Скопируйте .env.example в .env и заполните токены."
    exit 1
fi

start_streamlit() {
    if [[ -f "$STREAMLIT_PID_FILE" ]]; then
        local old_pid
        old_pid="$(tr -d '[:space:]' <"$STREAMLIT_PID_FILE")"
        if local_run_pid_alive "$old_pid"; then
            echo "Streamlit уже запущен (PID $old_pid)"
            return 0
        fi
        rm -f "$STREAMLIT_PID_FILE"
    fi

    local -a streamlit_cmd
    if [[ -x "$(dirname "$PY")/streamlit" ]]; then
        streamlit_cmd=("$(dirname "$PY")/streamlit")
    else
        streamlit_cmd=("$PY" -m streamlit)
    fi

    nohup "${streamlit_cmd[@]}" run hri_full_v1.py \
        --server.port="$STREAMLIT_PORT" \
        --server.address=127.0.0.1 \
        --server.headless=true \
        --browser.gatherUsageStats=false \
        >>"$LOG_DIR/streamlit.log" 2>&1 &
    echo $! >"$STREAMLIT_PID_FILE"
    echo "Streamlit запущен (PID $(cat "$STREAMLIT_PID_FILE")), лог: $LOG_DIR/streamlit.log"
}

start_bot() {
    if [[ "${HR_LOCAL_SKIP_BOT:-0}" == "1" ]]; then
        echo "Бот пропущен (HR_LOCAL_SKIP_BOT=1)"
        return 0
    fi

    if [[ -f "$BOT_PID_FILE" ]]; then
        local old_pid
        old_pid="$(tr -d '[:space:]' <"$BOT_PID_FILE")"
        if local_run_pid_alive "$old_pid"; then
            echo "Бот уже запущен (PID $old_pid)"
            return 0
        fi
        rm -f "$BOT_PID_FILE"
    fi

    nohup "$PY" bot.py >>"$LOG_DIR/bot.log" 2>&1 &
    echo $! >"$BOT_PID_FILE"
    echo "Бот запущен (PID $(cat "$BOT_PID_FILE")), лог: $LOG_DIR/bot.log"
}

wait_for_streamlit() {
    local curl_bin="/usr/bin/curl"
    [[ -x "$curl_bin" ]] || curl_bin="curl"
    local i
    for i in $(seq 1 45); do
        if "$curl_bin" -sf "${STREAMLIT_URL}_stcore/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

start_streamlit
start_bot

if wait_for_streamlit; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
        /usr/bin/open "$STREAMLIT_URL" 2>/dev/null || open "$STREAMLIT_URL"
    fi
    local_run_notify_mac "HR Agent" "Приложение запущено. Браузер открыт на порту ${STREAMLIT_PORT}."
else
    local_run_alert_mac "HR Agent" "Streamlit стартует дольше обычного. Откройте вручную: ${STREAMLIT_URL} Лог: ${LOG_DIR}/streamlit.log"
fi
