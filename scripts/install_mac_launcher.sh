#!/usr/bin/env bash
# Ярлыки на рабочий стол (macOS): компилируются через osacompile — работают по двойному клику.
# Использование: ./scripts/install_mac_launcher.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP="$HOME/Desktop"
BUILD_DIR="$SCRIPT_DIR/macos/build"
LOG_DIR="$HOME/Library/Logs/hr-ai-agent"
START_APP="$DESKTOP/Start HR Agent.app"
STOP_APP="$DESKTOP/Stop HR Agent.app"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Этот скрипт только для macOS."
    exit 1
fi

if ! command -v osacompile >/dev/null 2>&1; then
    echo "Не найден osacompile (нужен macOS)."
    exit 1
fi

chmod +x "$SCRIPT_DIR/start_local.sh"
chmod +x "$SCRIPT_DIR/stop_local.sh"
mkdir -p "$BUILD_DIR" "$LOG_DIR"

# Экранирование для вставки в AppleScript-строку
escape_as() {
    printf '%s' "$1" | sed "s/'/'\"'\"'/g"
}
ROOT_ESC="$(escape_as "$ROOT")"
LOG_ESC="$(escape_as "$LOG_DIR")"

cat >"$BUILD_DIR/start.applescript" <<APPLESCRIPT
do shell script "export HR_AI_PROJECT_ROOT='${ROOT_ESC}'; '${ROOT_ESC}/scripts/start_local.sh' >> '${LOG_ESC}/start.log' 2>&1"
APPLESCRIPT

cat >"$BUILD_DIR/stop.applescript" <<APPLESCRIPT
do shell script "export HR_AI_PROJECT_ROOT='${ROOT_ESC}'; '${ROOT_ESC}/scripts/stop_local.sh' >> '${LOG_ESC}/stop.log' 2>&1"
APPLESCRIPT

rm -rf "$START_APP" "$STOP_APP"
osacompile -o "$START_APP" "$BUILD_DIR/start.applescript"
osacompile -o "$STOP_APP" "$BUILD_DIR/stop.applescript"

echo "Готово."
echo "  Запуск:  двойной клик «Start HR Agent» на рабочем столе"
echo "  Стоп:    двойной клик «Stop HR Agent»"
echo "  Логи:    $ROOT/run/logs/  и  $LOG_DIR/"
echo ""
echo "При ошибке macOS покажет диалог; подробности — в логах выше."
echo "Процессы в фоне — терминал можно закрыть."
