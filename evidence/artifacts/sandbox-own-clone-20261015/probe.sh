#!/bin/bash
# Measurement probe (lead C): is Bash sandboxed with --settings sandbox.enabled true/false/unset on this client?
# Each arm runs one headless turn from its own scratch cwd and asks the model to run one fixed Bash command that
# writes outside the cwd and reports PID 1's command. Under the sandbox the write is denied (bwrap's read-only root
# outside the allowed paths) and PID 1 is bwrap's own init.
set -u
OUT=/var/tmp/ccnp-sbx/out
mkdir -p "$OUT"
for arm in on off unset; do
  cwd=$(mktemp -d /var/tmp/ccnp-sbx/cwd-$arm.XXXXXX)
  target=/var/tmp/ccnp-sbx/written-$arm
  rm -f "$target"
  cmd="touch $target && echo WRITE-OK || echo WRITE-DENIED; tr '\\0' ' ' < /proc/1/cmdline | cut -c1-60; echo"
  case $arm in
    on) settings=(--settings '{"sandbox":{"enabled":true}}');;
    off) settings=(--settings '{"sandbox":{"enabled":false}}');;
    unset) settings=();;
  esac
  ( cd "$cwd" && timeout 300 claude -p --model claude-haiku-5-5 --effort low --max-turns 3 \
      --permission-mode dontAsk --allowedTools "Bash" --tools Bash --strict-mcp-config \
      "${settings[@]}" --output-format json \
      "Run exactly this one Bash command, unchanged, then reply with its raw output only: $cmd" \
      < /dev/null > "$OUT/$arm.json" 2> "$OUT/$arm.err" )
  echo "$arm rc=$? file_written=$([ -e "$target" ] && echo yes || echo no) result=$(jq -r '.result' "$OUT/$arm.json" 2>/dev/null | tr '\n' ' ' | cut -c1-160)"
done
