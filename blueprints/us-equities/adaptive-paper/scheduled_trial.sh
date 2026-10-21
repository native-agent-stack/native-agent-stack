#!/usr/bin/env bash
# One bounded adaptive paper trial: ingest a fresh promotion-gate snapshot,
# gate it, then run `runner.py paper` once. Never retries; every step's output
# stays under OUT_DIR. The STOP file kill switch (safety.DEFAULT_STOP) applies.
#
# Required env: TRIAL (runner trial id, [a-z0-9-]{1,24}), ENV_FILE (0600 paper
# credential file outside any Git worktree), STATE_ROOT, OUT_DIR.
# Optional: CONFIG (default config-sip.json), PY, GATE_PY, LIVE_DIR (runner --live-dir:
# live decision/intent stream and NautilusTrader JSON log). Run it from a frozen,
# read-only copy of a published commit (git archive), never from a live worktree.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
data="$(cd "$here/../data" && pwd)"
: "${TRIAL:?}" "${ENV_FILE:?}" "${STATE_ROOT:?}" "${OUT_DIR:?}"
CONFIG="${CONFIG:-$here/config-sip.json}"
PY="${PY:-$HOME/projects/us-equities-runtime/.venv/bin/python}"
GATE_PY="${GATE_PY:-$HOME/.local/share/codex-ecosystem/tools/promotion-gate-20260922/.venv/bin/python3}"
for p in "$PY" "$GATE_PY"; do
  [ -f "$p" ] && [ -x "$p" ] || { echo "refused: interpreter not executable: $p" >&2; exit 2; }
done
# Mirror install-trading-2604.sh and accept-trading-2604.sh's published runtime
# ownership/completion and metadata identity. A failed sync leaves Python
# executable, so executable checks alone cannot establish default readiness.
# Explicit alternate interpreters remain the owning caller's choice.
runtime="$HOME/projects/us-equities-runtime"
runtime=$(realpath --canonicalize-missing -- "$runtime") || {
  echo "refused: canonical runtime directory unavailable" >&2; exit 2;
}
# Lock the managed runtime when either stage uses its interpreter, including
# executable file aliases. Alternate runtimes retain their existing overrides.
if [[ "$PY" == "$runtime/.venv/bin/python" || "$PY" -ef "$runtime/.venv/bin/python" ||
      "$GATE_PY" == "$runtime/.venv/bin/python" || "$GATE_PY" -ef "$runtime/.venv/bin/python" ]]; then
  refuse_runtime() { echo "refused: canonical runtime incomplete or metadata differs" >&2; exit 2; }
  [[ ! -L "$HOME/projects" && ! -L "$runtime" && -d "$runtime" && -O "$runtime" &&
     ! -L "$runtime/.venv" && -d "$runtime/.venv" ]] || refuse_runtime
  # A stable lock beside the runtime also covers a fresh installer. Never
  # unlink/replace it: both scripts must coordinate on the same inode.
  runtime_lock="${runtime%/*}/.us-equities-runtime.lock"
  command -v flock >/dev/null || refuse_runtime
  [[ ! -L "$runtime_lock" && ( ! -e "$runtime_lock" ||
      ( -f "$runtime_lock" && -O "$runtime_lock" ) ) ]] || refuse_runtime
  exec {runtime_lock_fd}>>"$runtime_lock" || refuse_runtime
  flock --shared --nonblock "$runtime_lock_fd" || {
    echo "refused: canonical runtime in use by installer" >&2; exit 2;
  }
  # Keep runtime_lock_fd open through ingestion, gate and runner. Marker and
  # metadata checks occur only after the shared lock has been acquired.
  for marker in .trading-2604-owner .trading-2604-complete; do
    [[ -f "$runtime/$marker" && ! -L "$runtime/$marker" ]] || refuse_runtime
  done
  IFS= read -r recorded_owner < "$runtime/.trading-2604-owner" || refuse_runtime
  [[ "$recorded_owner" == native-stack-trading-2604-v1 ]] || refuse_runtime
  for entry in 'pyproject.toml|aa370e42e29dc2419e586358254ff2e821df48a693aa9a3ee16b65d30036ee0b' \
               'uv.lock|9d8350a6773437a6890808c5b6ae61d98d305021b16ea0a4b4e753dd2f4f6223'; do
    IFS='|' read -r filename expected_hash <<< "$entry"
    [[ -f "$runtime/$filename" && ! -L "$runtime/$filename" ]] || refuse_runtime
    printf '%s  %s\n' "$expected_hash" "$runtime/$filename" | sha256sum --check --status || refuse_runtime
  done
  IFS= read -r recorded_completion < "$runtime/.trading-2604-complete" || refuse_runtime
  [[ "$recorded_completion" == native-stack-trading-2604-no-dvc-r4 ]] || refuse_runtime
fi
mkdir -p "$OUT_DIR"
live=()
if [ -n "${LIVE_DIR:-}" ]; then live=(--live-dir "$LIVE_DIR"); fi
# One run per OUT_DIR: the lock directory is created atomically and never removed.
if ! mkdir "$OUT_DIR/.run-once" 2>/dev/null; then
  echo "refused: $OUT_DIR already holds a run (remove nothing; use a new OUT_DIR and TRIAL)" >&2
  exit 3
fi
exec >>"$OUT_DIR/scheduled-trial.log" 2>&1
echo "start $(date -u +%FT%TZ) trial=$TRIAL config_sha256=$(sha256sum "$CONFIG" | cut -c1-64)"
timeout 120 "$PY" "$data/ingest_snapshot.py" --env-file "$ENV_FILE" --config "$CONFIG" \
  --out "$OUT_DIR/universe-daily.csv" --receipt "$OUT_DIR/ingest-receipt.json"
timeout 120 "$GATE_PY" "$data/promotion_gate.py" --input "$OUT_DIR/universe-daily.csv" \
  --out "$OUT_DIR/gate-result.json" --calendar XNYS
set +e
timeout 900 "$PY" "$here/runner.py" paper --env-file "$ENV_FILE" --config "$CONFIG" \
  --output "$OUT_DIR/paper-output.json" --trial "$TRIAL" --state-root "$STATE_ROOT" \
  --gate-result "$OUT_DIR/gate-result.json" --snapshot "$OUT_DIR/universe-daily.csv" "${live[@]}"
rc=$?
echo "end $(date -u +%FT%TZ) runner_rc=$rc"
exit "$rc"
