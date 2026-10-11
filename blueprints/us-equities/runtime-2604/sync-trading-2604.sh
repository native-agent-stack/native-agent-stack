#!/usr/bin/env bash
# Shared host/CI vector: source this file, then call sync_trading_2604.
# The caller supplies safe (a clean-environment command-prefix array), project
# and runtime_python (the managed interpreter). Failures stop the vector even
# if the caller invokes the function from a shell conditional.
# Reuse commands directly, as validate.yml does with its install-command pins.
# https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md
readonly python_pin=3.12.3
readonly uv_pin=0.12.17

sync_trading_2604() {
    # Direct managed-runtime sync callers must coordinate too. The installer
    # supplies its already-locked descriptor; standalone callers keep a newly
    # opened descriptor only through the sync. CI's isolated project is independent.
    local sync_owned_lock_fd='' sync_lock_fd='' sync_result=0
    if [[ "$project" == "$HOME/projects/us-equities-runtime" ]]; then
        runtime_lock="$HOME/projects/.us-equities-runtime.lock"
        [[ ! -L "$runtime_lock" && ( ! -e "$runtime_lock" ||
            ( -f "$runtime_lock" && -O "$runtime_lock" ) ) ]] || return 73
        if [[ -n ${runtime_lock_fd:-} ]]; then
            sync_lock_fd=$runtime_lock_fd
        else
            exec {sync_owned_lock_fd}>>"$runtime_lock" || return 73
            sync_lock_fd=$sync_owned_lock_fd
        fi
        [[ "$runtime_lock" -ef "/proc/self/fd/$sync_lock_fd" ]] || {
            [[ -z $sync_owned_lock_fd ]] || exec {sync_owned_lock_fd}>&-
            return 73
        }
        flock --exclusive --timeout 1 "$sync_lock_fd" || {
            [[ -z $sync_owned_lock_fd ]] || exec {sync_owned_lock_fd}>&-
            return 69
        }
    fi
    _sync_trading_2604_commands || sync_result=$?
    [[ -z $sync_owned_lock_fd ]] || exec {sync_owned_lock_fd}>&-
    return "$sync_result"
}

_sync_trading_2604_commands() {
    step=lock-check
    "${safe[@]}" uv --no-config lock --check --project "$project" --python "$runtime_python" \
        --no-python-downloads || return "$?"
    step=package-sync
    "${safe[@]}" uv --no-config sync --project "$project" --python "$runtime_python" \
        --no-python-downloads --locked --group dev || return "$?"
    step=dependency-check
    "${safe[@]}" uv --no-config pip check --python "$project/.venv/bin/python" || return "$?"
}
