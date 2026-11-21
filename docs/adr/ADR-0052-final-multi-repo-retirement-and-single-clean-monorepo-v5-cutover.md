# ADR-0052: Final Multi-Repo Retirement & Cutover to Disk-`Z:` Single Clean Monorepo (`Noesis-SOTA:~/tier0-quant` & Single Master ADR)

- **Status:** Accepted
- **Date:** 2026-11-21
- **Supersedes:** Formally supersedes BOTH the legacy `18`-repo multi-repo sprawl (`C:\sota-workstation`) AND the intermediate `4`-repo split proposed in `ADR-0049`.
- **Evidence Grade:** E4 (100% Disk-`Z:` topology verified via live WSL `Lxss` registry & Docker probes: `Noesis-SOTA` -> `Z:\WSL\Noesis-SOTA` (`~/tier0-quant`, single consolidated Master ADR `ADR-0001` hosted live via `Zensical` on `:8010`, native `dockerd` `6/6` services `:5000` MLflow 3 / `:3000` Dagster / `:8080` Optuna Dashboard / `:7575` Inspect AI View / `:8010` Zensical + `aideml-sandbox`), `docker-desktop` -> `Z:\sota-cache\docker-wsl\main` (`openbq-org/finos-workspace` `:1420`/`:8000` + `plotly-charts@2.5.0` & `ag-grid@2.3.0`), `Noesis-Carbon` -> `Z:\WSL\Noesis-Carbon` (`native_ext4` lake + `:8794` RTX 4090 CUDA sidecar), `95` hosted upstream repos on `Z:\sota-data\hosted-research-frameworks\` & `Z:\sota-data\upstream\`, all model/package caches on `Z:\sota-cache\`; legacy `18/18` repos preserved clean & synced `0/0` at `one_harness_cleanliness_doctor.py` `10/10 PASS`)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/nautechsystems/nautilus_trader, https://github.com/stablyai/orca, https://github.com/OrchestratorInc/agent-orchestrator, https://github.com/mlflow/mlflow, https://github.com/openbq-org/finos-workspace, https://github.com/zensical/zensical

## Context

Even after converging `18/18` legacy repositories cleanly, maintaining multiple repositories—or placing new clean-room repositories, Docker volumes, model weights, or package caches on Drive `C:`—violates the owner's **Disk-`Z:`-only, single-clean-repo** directive. The active clean-room harness is already hosted natively on Disk `Z:` inside `Noesis-SOTA` (`Z:\WSL\Noesis-SOTA` -> `~/tier0-quant`) alongside `Z:\sota-data\` and `Z:\sota-cache\`.

## Decision

1. **100% Disk-`Z:` Clean-Room Topology (Zero New Repos, Dockers, or Model Caches on Drive `C:`):**
   - **Sole Active Clean-Room Monorepo:** `Noesis-SOTA:~/tier0-quant` (`Z:\WSL\Noesis-SOTA`, with Windows mirror `Z:\tier0-quant` & Mac converged reference `Z:\tier0-quant-mac-converged`), enforcing `<= 5,000` LOC custom production ceiling, Zero Self-Built Frameworks, and Zero Paper Self-Invention (`AGENTS.md` Charter `ba34ef82...`).
   - **Single Consolidated Master ADR (`len(adr_files) == 1`):** `Noesis-SOTA:~/tier0-quant/docs/adr/ADR-0001-tier0-quant-clean-architecture-layers-research-convergence-and-hosted-frameworks.md` covering all `16` layers (`L0–L15`) × `8` Research Convergence stages (`S1–S8`), `18` core shelf pins, and all `95` Disk-`Z:` hosted research/Orca/AO frameworks, hosted live via `Zensical 0.1.3` on `http://127.0.0.1:8010`.
   - **All Docker Engines & Live Research Services on Disk `Z:`:**
     - `Noesis-SOTA` native `dockerd` (`Z:\WSL\Noesis-SOTA`): `MLflow 3` (`:5000`), `Dagster` (`:3000` + daemon), `Optuna Dashboard` (`:8080`), `Inspect AI View` (`:7575`), `Zensical ADR Portal` (`:8010`), plus `aideml-sandbox`.
     - `docker-desktop` (`Z:\sota-cache\docker-wsl\main`): `openbq-org/finos-workspace` (`:1420`/`:8000` with `plotly-charts@2.5.0` & `ag-grid@2.3.0`) connected to `openbq-org/backends-for-openbb` (`:6900`).
     - `Noesis-Carbon` (`Z:\WSL\Noesis-Carbon`): `native_ext4` pre-wall lake & RTX 4090 CUDA sidecar (`:8794`).
     - Pure unmodified upstream tearsheets (`Z:\sota-data\tearsheets` -> `:8793`) & IBKR Paper (`:4002`).
   - **All `95` Hosted Upstream Repos, Models & Multi-Runtime Caches on Disk `Z:`:** `Z:\sota-data\upstream\` (`18` immutable core pins, untouched), `Z:\sota-data\hosted-research-frameworks\` (`95`-repo registry including `Orca`, `OrchestratorInc/agent-orchestrator` AO, `OMC`/`OMX`/`oh-my-pi`/`DSH`, `OpenHands`, `aideml`, `QuantLib`, `Lean`, `Qlib`, `MarS`, `LOBS5`, `TabPFN`, `TimesFM`, `SkillEvaluator`, `OpenShell`, `Claude-BugHunter`), and `Z:\sota-cache\` (`huggingface`, `torch`, `ollama`, `pip`, `uv`, `uv-python`, `npm`, `venvs`, `cargo-target`, `docker-wsl`).
2. **Non-Destructive Archival Closure of `18/18` Legacy Repos:**
   - Seals the legacy `18`-repo `C:\sota-workstation` estate cleanly (`dirty=0`, `0/0` pushed, `10/10` cleanliness doctor, `797/797` verbatim ADR archive in `sota-private-vault/adr_archive/`) as read-only archival provenance. Any temporary duplicate repo on `C:` (`C:\sota-ecosystem`) is permanently removed.

## Consequences

- **Positive:** Every single active component—clean monorepo, Master ADR + Zensical portal, both Docker engines, all `95` hosted upstream repos, multi-runtime toolchains, model weights, and caches—resides exclusively on Disk `Z:` (`3.3 TB` free), leaving Drive `C:` clean and legacy `18/18` repos frozen and archived.
- **Negative / Safeguards:** Protected boundaries (`Z:\WSL\sextant`, `Z:\meridian-data\handoff-2026-11-17\`, `~/Documents/upstream/`, Drive `D:`, Drive `F:`, live broker ports, and `wsl --shutdown`) remain 100% hard-refused.
