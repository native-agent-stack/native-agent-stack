#!/usr/bin/env bash
set -euo pipefail
mkdir -p /work/qdrant-offline/storage /work/qdrant-offline/snapshots
cd /work/qdrant-offline
QDRANT__STORAGE__STORAGE_PATH=/work/qdrant-offline/storage \
QDRANT__STORAGE__SNAPSHOTS_PATH=/work/qdrant-offline/snapshots \
QDRANT__SERVICE__HTTP_PORT=6333 \
  /work/qdrant/qdrant --disable-telemetry \
  > /work/raw-captures/qdrant-offline.stdout \
  2> /work/raw-captures/qdrant-offline.stderr &
owned_pid=$!
cleanup() {
  kill -TERM "$owned_pid" 2>/dev/null || true
  wait "$owned_pid" || true
}
trap cleanup EXIT
cd /work/socraticode
node -e 'const url="http://127.0.0.1:6333/healthz"; for(let i=0;i<100;i++){try{const r=await fetch(url);if(r.ok)process.exit(0)}catch{}await new Promise(resolve=>setTimeout(resolve,100));}process.exit(1)'
REQUIRE_QDRANT=1 QDRANT_MODE=external \
QDRANT_URL=http://127.0.0.1:6333 QDRANT_HOST=127.0.0.1 QDRANT_PORT=6333 \
  npx --no-install vitest run \
  tests/integration/partial-upsert-skip.test.ts \
  tests/integration/interrupted-resume-recovery.test.ts
