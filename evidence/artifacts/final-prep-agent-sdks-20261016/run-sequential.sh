#!/bin/sh
set -eu
arm=/var/tmp/ns2604-g5-agent-sdks-run
step=$arm/bin/f1_step.py
python3 "$step" "$arm" clone -- git clone --depth 1 --branch rust-v0.160.0 https://github.com/openai/codex "$arm/work/codex"
python3 "$step" "$arm" verify --cwd "$arm/work/codex" -- git rev-parse HEAD
python3 "$step" "$arm" install -- env -i PATH="$arm/bin:/usr/bin:/bin" HOME="$arm/work/home" npm_config_cache="$arm/tmp/npm" npm_config_userconfig=/dev/null npm install --prefix "$arm/work/tools" @openai/codex@0.160.0 pnpm@10.34.5
python3 "$step" "$arm" install --cwd "$arm/work/codex" -- env -i PATH="$arm/work/tools/node_modules/.bin:$arm/bin:/usr/bin:/bin" HOME="$arm/work/home" TMPDIR="$arm/tmp" npm_config_cache="$arm/tmp/npm" npm_config_userconfig=/dev/null pnpm install --frozen-lockfile --store-dir "$arm/tmp/pnpm-store"
python3 "$step" "$arm" verify -- env -i PATH="$arm/bin:/usr/bin:/bin" HOME="$arm/work/home" CODEX_HOME="$arm/work/codex-home" "$arm/work/tools/node_modules/.bin/codex" --version
python3 "$step" "$arm" test --cwd "$arm/work/codex" -- env -i PATH="$arm/work/tools/node_modules/.bin:$arm/bin:/usr/bin:/bin" HOME="$arm/work/home" TMPDIR="$arm/tmp" CODEX_HOME="$arm/work/codex-home" CODEX_EXEC_PATH="$arm/work/tools/node_modules/.bin/codex" pnpm -r --filter ./sdk/typescript run test
python3 "$step" "$arm" invoke -- python3 "$arm/bin/invoke.py"
