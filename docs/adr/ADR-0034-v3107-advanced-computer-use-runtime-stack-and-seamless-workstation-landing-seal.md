# ADR-0034: `v3.10.7` Advanced 5-Layer Computer-Use Runtime Stack & Seamless Workstation Change Landing Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Hybrid 5-Layer Computer-Use Stack (`L1–L4`), Tiered Zero-Friction Permission Governance & Full Dual-Workstation Handoff (`L0–L13` × `H1–H3`)
- **Evidence Grade:** E4 (`sota-harness-foundation@52ce4c73` `ADR-0042` `computer_use_contract.py`, `cc-sota-harness@4590c995` `ADR-0040`, `agy-sota-harness@2f56eadf` `ADR-0033`, `sota-multi-model-workflows@2eebb676` `ADR-0032`, `34/34` MADR 4.0 ADRs, `merge_gate.py` + `ty` + `ruff` + `pytest` + `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/native-agent-stack/agy-sota-harness, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/stablyai/orca, https://github.com/mediar-ai/terminator, https://github.com/steipete/peekaboo, https://github.com/vercel-labs/agent-browser, https://github.com/microsoft/playwright-mcp, https://github.com/HKUDS/CLI-Anything, https://github.com/simular-ai/Agent-S, https://github.com/trycua/cua, https://github.com/microsoft/UFO
- **Revisit Trigger:** `2026-12-06` `23/5` Consolidated SIP cutover or completion of Noesis Win32/WSL2 `terminator` + `@playwright/cli` rollout

## Context and Problem Statement

While `sota-harness-foundation@52ce4c73` (`ADR-0042`), `cc-sota-harness@4590c995` (`ADR-0040`), `agy-sota-harness@2f56eadf` (`ADR-0033`), and `sota-multi-model-workflows@2eebb676` (`ADR-0032`) codified the executable 5-layer computer-use contract and tiered permission model, live workstation telemetry showed that Stationary `Noesis` (`100.110.115.22`) currently runs only Orca's foreground Win32 UIA provider (`orca-computer-use-windows` with `input.background=false`), `:8792` Zero-Terminal RPC, and Orca's built-in browser — without background Win32 UIA (`mediar-ai/terminator`) or cross-surface CLI/browser helpers installed on disk.

## Decision Outcome

1. **Seal the Ecosystem-Wide `v3.10.7` 5-Layer Computer-Use Stack (`ECOSYSTEM_CONVERGENCE_LOCK.json`):**
   - **L1 (CLI / `:8792` RPC / MCP / `HKUDS/CLI-Anything`):** Default zero-pixel-tax control plane across Mac and `Noesis`.
   - **L2 (Semantic OS Accessibility / Background):** `mediar-ai/terminator` (`terminator-mcp-agent`) for background non-focus-stealing Win32 UIA on `Noesis` paired with `orca-computer-use-windows`, `steipete/peekaboo` paired with background `orca-computer-use-macos` on Mac, plus `trycua/cua` / `microsoft/UFO` (`UFO²`/`UFO³`) patterns.
   - **L3 (Compact Browser Refs):** `vercel-labs/agent-browser`, `@playwright/cli` (`microsoft/playwright-mcp`), and Orca Browser (`orca snapshot`).
   - **L4 (`Agent-S` S4 Distillation & VLM Fallback):** Distill recurring manual/GUI sequences into idempotent CLI/config scripts (`sync-all-8-runtimes.py`, `sync_runtime_hygiene.py`), keeping visual VLM fallback limited to unexposed UIs.
2. **Full Workstation Rollout Handoff & Fail-Closed Permission Preservation:**
   - Execute a full Orca handoff (`sota-workstation handoff`) to Stationary `Noesis` (`cc-sota-harness`) to install, wire, and verify the concrete Win32/WSL2 runtime stack for frictionless change landing (`OWNER_ZERO_FRICTION_SEAMLESS`), while preserving `FAIL_CLOSED_HARD_INVARIANT` (live-capital `:8798`/`:4001`/`:7496`, credentials/Keychain/`.env`, immutable `~/Documents/upstream/` & closed repos, `singleActiveBrokerHostOnly=true`, `ADR-0022 <= 2.00%`, untouched `sextant`) and `EXPLICIT_HUMAN_TRUST_GATE` (`97bd1f5e` / `6d7eba60` hook trust clicks).

## Alternatives Considered

- **Leaving `ADR-0042` Strictly Conceptual Without Workstation Rollout Handoff:** Rejected — Win32 `input.background=false` friction persists unless `mediar-ai/terminator`, compact browser tooling, and S4 CLI distillation scripts are installed and verified on Stationary `Noesis`.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`34/34` MADR 4.0 ADRs valid, `0` drift).
- `uv run python scripts/merge_gate.py && gitleaks git --no-banner` (`PASS`, `0` leaks).
