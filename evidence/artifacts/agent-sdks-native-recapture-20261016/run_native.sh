#!/bin/sh
# Run under the closed environment documented by bootstrap.sh.
set -eu
arm=$1
step=$arm/bin/recorder.py
python3 "$step" "$arm" clone -- git clone --depth 1 --branch rust-v0.160.0 https://github.com/openai/codex "$arm/work/codex"
python3 "$step" "$arm" source-pin --cwd "$arm/work/codex" -- git rev-parse HEAD
python3 "$step" "$arm" install-cli -- npm install --prefix "$arm/work/tools" @openai/codex@0.160.0 pnpm@10.34.5
export PATH="$arm/work/tools/node_modules/.bin:$PATH"
python3 "$step" "$arm" install-sdk --cwd "$arm/work/codex" -- pnpm install --frozen-lockfile --store-dir "$arm/tmp/pnpm-store"
python3 "$step" "$arm" cli-version -- codex --version
python3 "$step" "$arm" npm-lock -- cat "$arm/work/tools/package-lock.json"
python3 "$step" "$arm" binary-hash -- sha256sum "$arm/work/tools/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
python3 "$step" "$arm" source-clean-before --cwd "$arm/work/codex" -- git diff --exit-code HEAD
export CODEX_EXEC_PATH="$arm/work/tools/node_modules/.bin/codex"
python3 "$step" "$arm" test --cwd "$arm/work/codex" -- pnpm -r --filter ./sdk/typescript run test
python3 "$step" "$arm" invoke -- python3 "$arm/bin/native_invoke.py" "$arm"
python3 "$step" "$arm" source-clean-after --cwd "$arm/work/codex" -- git diff --exit-code HEAD
