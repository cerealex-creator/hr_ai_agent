# Общие функции локального запуска (macOS / Linux).
# Подключается из start_local.sh, stop_local.sh и .app-launcher'ов.

local_run_project_root() {
    if [[ -n "${HR_AI_PROJECT_ROOT:-}" && -d "$HR_AI_PROJECT_ROOT" ]]; then
        printf '%s\n' "$HR_AI_PROJECT_ROOT"
        return 0
    fi
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    printf '%s\n' "$(cd "$script_dir/.." && pwd)"
}

local_run_venv_python() {
    local root="$1"
    if [[ -x "$root/venv/bin/python" ]]; then
        printf '%s\n' "$root/venv/bin/python"
        return 0
    fi
    if [[ -x "$root/.venv/bin/python" ]]; then
        printf '%s\n' "$root/.venv/bin/python"
        return 0
    fi
    return 1
}

local_run_pid_alive() {
    local pid="${1:-}"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

local_run_notify_mac() {
    local title="$1"
    local message="$2"
    if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
        osascript -e "display notification \"$message\" with title \"$title\"" 2>/dev/null || true
    fi
}

local_run_alert_mac() {
    local title="$1"
    local message="$2"
    if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
        osascript -e "display alert \"$title\" message \"$message\"" 2>/dev/null || true
    fi
}
