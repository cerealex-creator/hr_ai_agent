#!/usr/bin/env bash
# Статус локального запуска и доступности Telegram API.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=local_run_common.sh
source "$SCRIPT_DIR/local_run_common.sh"

ROOT="$(local_run_project_root)"
RUN_DIR="$ROOT/run"

echo "=== HR Agent (локально) ==="
check_pid() {
    local name="$1"
    local file="$2"
    if [[ -f "$file" ]]; then
        local pid
        pid="$(tr -d '[:space:]' <"$file")"
        if local_run_pid_alive "$pid"; then
            echo "$name: работает (PID $pid)"
        else
            echo "$name: PID-файл есть, процесс не найден ($pid)"
        fi
    else
        echo "$name: не запущен"
    fi
}
check_pid "Streamlit" "$RUN_DIR/streamlit.pid"
check_pid "Бот" "$RUN_DIR/bot.pid"

extra_bots="$(pgrep -f "${ROOT}/.*bot\\.py" 2>/dev/null | wc -l | tr -d ' ')"
if [[ "${extra_bots:-0}" -gt 1 ]]; then
    echo "ВНИМАНИЕ: запущено $extra_bots процессов bot.py — кнопки могут не работать (конфликт polling)."
    pgrep -fl "${ROOT}/.*bot\\.py" 2>/dev/null || true
fi

echo ""
echo "=== Telegram API ==="
if /usr/bin/curl -4 -sf --max-time 8 "https://api.telegram.org/" >/dev/null 2>&1; then
    echo "api.telegram.org: доступен"
else
    echo "api.telegram.org: НЕДОСТУПЕН (таймаут или блокировка сети)"
    echo "  → включите VPN, или запустите бота только на VPS (docker compose restart hr-bot)"
    echo "  → либо задайте TELEGRAM_PROXY в .env (socks5://… или http://…)"
fi

if [[ -f "$RUN_DIR/logs/bot.log" ]]; then
    echo ""
    echo "=== Последние ошибки бота ==="
    grep -E 'ERROR|Conflict|Cannot connect' "$RUN_DIR/logs/bot.log" 2>/dev/null | tail -5 || echo "(нет)"
fi
