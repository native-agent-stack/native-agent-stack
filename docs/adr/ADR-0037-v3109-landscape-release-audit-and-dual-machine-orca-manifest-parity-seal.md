# ADR-0037: `v3.10.9` Upstream Landscape Release Audit & Dual-Machine Orca Manifest Parity Seal

- **Status:** Accepted
- **Date:** 2026-11-19
- **Layer:** Organization Umbrella, `2026-11-19` Upstream Release Audit (`Orca 1.4.263/1.4.264`, `claude 2.1.328`, `agy 1.5.12`), `18/18` Cross-OS `orca.yaml`, `9/9` 3-Surface Folder Lane Hubs & `18/18` `sota-doctor` (`L0–L13` × `H1–H3`)
- **Evidence Grade:** E4 (`sota-harness-foundation@316fa79c`, `sota-multi-model-workflows@156050a6` `ADR-0034`, `sota-upstream-shelf-lock@b82bd522` `ADR-0016`, `sota-private-vault@29cfcb80`, `.github@cbe1ab05`, `37/37` MADR 4.0 ADRs, `merge_gate.py` + `ruff` + `pytest` + `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/sota-upstream-shelf-lock, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/stablyai/orca, https://github.com/anthropics/claude-code
- **Revisit Trigger:** Orca desktop upgrade `1.4.263 -> 1.4.264` completion, release of a new major CLI/orchestrator version, or modification to `18`-repo `orca.yaml` / `9`-hub layout.

## Context and Problem Statement

Deep landscape and dual-machine Orca manifest inspection on `2026-11-19` uncovered concrete drifts despite green CI:
1. Three repository `orca.yaml` recipes were broken on Win32 or referenced missing scripts (`sota-harness-foundation/orca.yaml` referenced non-existent `scripts/doctor.py`; `dot-github/orca.yaml` and `sota-private-vault/orca.yaml` invoked POSIX-only `python3`).
2. `sota-lanes sync-hubs` updated only `~/.agents/orca-lanes`, leaving `C:\sota-workstation\.orca-lanes` (`14` files drifted) and WSL2 `~/sota-workstation/.orca-lanes` stale, while `trading-lanes/LANE_MANIFEST.json` still emitted `activePreCutoverBrokerSplit` pointing Alpaca Paper to `portable_mac_m5_max`, omitted `stationary_noesis_wsl_carbon` (`Noesis-Carbon (WSL)`), and `sota-lanes route` routed broker-bound repos away from Sovereign Noesis under `ADR-0041`.
3. Dual-machine automations `738c2d96`, `234abc3d`, `6542ce7a`, `625c76a7`, `7ca7c6cb` and `430f02d4` (`existing` workspace lock + `dispatch_failed`) needed `new-per-run` / `--setup skip` / SOTA `--extra-agent-args` hardening, while new `2026-11-19` releases (`orca v1.4.264`, `claude-code v2.1.328`, `agy 1.5.12`, `oh-my-pi v19.0.0`, `oh-my-openagent v5.1.79`, `codex rust-v0.170.0`, `oh-my-codex v0.22.11`) needed `PHILOSOPHY_ONLY_AND_HOST_VERSIONS` tracking without breaking `18/18` immutable quantitative pins.

## Decision Outcome

1. **Enforce `18/18` Cross-OS `orca.yaml` Parity & `9/9` 3-Surface Folder Lane Hubs:** Convert `dot-github` and `sota-private-vault` `orca.yaml` to `uv run --no-project python`, fix `sota-harness-foundation/orca.yaml` to valid `architecture_catalog.py --check` + `runtime_fleet.py`, upgrade `sota-multi-model-workflows` `ADR-0034` (`activeSovereignBrokerTopology`, `stationary_noesis_wsl_carbon`, `:8794` CUDA sidecar, `antigravity-neon`), and upgrade `sota-lanes-cli.py` to honor `ADR-0041` sovereign routing and sync both `~/.agents/orca-lanes` and `<workstation>/.orca-lanes` cleanly (`0` byte diffs).
2. **Publish `2026-11-19` Landscape Release Audit (`sota-upstream-shelf-lock` `ADR-0016`) & Seal Umbrella (`ADR-0037`):** Record live vs newly evaluated upstream versions while preserving all `18/18` immutable `40`-char `PINS_LOCK.json` SHAs and ignoring untracked `.omc/` state cleanly.

## Alternatives Considered

- **Mutate `dot-github/ECOSYSTEM_ORG_MANIFEST.json` Before Peer Leases Expire:** Rejected per strict `sota-bus` lease discipline — `dot-github/orca.yaml` landed on non-overlapping paths while `sota-bus msg` notifies active manifest-lease peers of our exact landed SHAs.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`37/37`), `uv run python scripts/merge_gate.py`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pytest -v`, and `gitleaks git --staged --verbose` (`0` leaks).
