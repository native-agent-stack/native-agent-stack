#!/bin/sh
# Existing host Node is linked read-only; no host installation or mutation.
# Usage: bootstrap.sh <new isolated scratch root> <existing node executable>
set -eu
arm=$1
node_executable=$2
source_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$arm/bin" "$arm/logs" "$arm/tmp" "$arm/work/home" "$arm/work/codex-home" "$arm/work/invoke-codex-home"
cp "$source_dir/recorder.py" "$source_dir/native_invoke.py" "$source_dir/run_native.sh" "$arm/bin/"
ln -s "$node_executable" "$arm/bin/node"
cat > "$arm/bin/npm" <<'WRAPPER'
#!/bin/sh
set -eu
runtime=$(readlink -f "$(dirname "$0")/node")
exec "$runtime" "$(dirname "$runtime")/../lib/node_modules/npm/bin/npm-cli.js" "$@"
WRAPPER
chmod 0755 "$arm/bin/npm"
exec env -i PATH="$arm/bin:/usr/bin:/bin" HOME="$arm/work/home" \
  TMPDIR="$arm/tmp" CODEX_HOME="$arm/work/codex-home" \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
  npm_config_cache="$arm/tmp/npm" npm_config_userconfig=/dev/null \
  sh "$arm/bin/run_native.sh" "$arm"
