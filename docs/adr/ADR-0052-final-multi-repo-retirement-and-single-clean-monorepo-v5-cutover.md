# ADR-0052: Final Multi-Repo Retirement & Cutover to Single Clean Monorepo `v5.0` (`sota-ecosystem`, `10` Clean Consolidated ADRs)

- **Status:** Accepted
- **Date:** 2026-11-21
- **Supersedes:** Formally supersedes BOTH the legacy `18`-repo multi-repo sprawl (`C:\sota-workstation`) AND the intermediate `4`-repo split proposed in `ADR-0049`.
- **Evidence Grade:** E4 (Single clean monorepo initialized & verified at `C:\sota-ecosystem` with `<= 5,000` LOC ceiling enforced fail-closed, `10/10` clean consolidated MADR 4.0 ADRs covering `L0–L15` × `S1–S8` & `95` Disk-`Z:` hosted upstream repos, `merge_gate.py PASS`, `pytest` + Hypothesis PASS, `ruff` 0, `gitleaks` 0; legacy `18/18` repos preserved clean & synced `0/0` at `one_harness_cleanliness_doctor.py` `10/10 PASS`)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/nautechsystems/nautilus_trader, https://github.com/stablyai/orca, https://github.com/OrchestratorInc/agent-orchestrator, https://github.com/mlflow/mlflow, https://github.com/openbq-org/finos-workspace

## Context

Even after converging `18/18` legacy repositories (`796+` ADRs) cleanly, maintaining multiple repositories—whether `18` legacy repos or the `4`-repo split originally drafted in `ADR-0049`—imposes unnecessary multi-repo synchronization, cross-repo ADR drift, and duplicated merge-gate boilerplate. The owner explicitly directed: **"no more multi-repo; the new ecosystem will live in one clean repository with clean ADRs"** covering every detail and layer (`L0–L15`) via Research Convergence (`S1–S8`) alongside local hosting of all advanced research framework repositories, Orca, and Multi-Model AO.

## Decision

1. **Zero Multi-Repo Sprawl — Single Clean Monorepo `v5.0` (`C:\sota-ecosystem`):**
   - Establishes `sota-ecosystem` (`C:\sota-ecosystem`) as the **sole active clean-room repository** replacing all multi-repo topologies (`18`-repo legacy AND `4`-repo `ADR-0049` split).
   - Enforces a hard custom production code ceiling of **`<= 5,000` LOC** via single-repo `scripts/merge_gate.py`, with secrets/credentials strictly excluded from Git (`.gitignore` + `gitleaks` + universal `core.hooksPath`).
2. **One Clean Consolidated `10`-ADR MADR 4.0 Canon (`C:\sota-ecosystem\docs\adr\ADR-0001..ADR-0010`):**
   - Replaces `797` fragmented legacy ADRs with `10` clean, zero-cruft, GitHub-evidenced MADR 4.0 ADRs covering every layer (`L0–L15`), all `8` Research Convergence stages (`S1–S8`), Zero Paper Self-Invention (`AGENTS.md`), single-engine `NautilusTrader v2` + `hftbacktest` + `QuantLib` parity, `MLflow 3.18.0` (`:5050`), `FINOS Workspace` (`:1420` + `plotly-charts@2.5.0` & `ag-grid@2.3.0`) + `OpenBB` (`:6900`) + pure upstream tearsheets (`:8793`), RTX 4090 GPU compute (`:8794`) + `95` hosted Disk-`Z:` upstream repos, `Orca` (`1.4.264`) + `OrchestratorInc/agent-orchestrator` (8-slot Multi-Model AO) + Docker-sandboxed `OpenHands`/`aideml`, and fail-closed risk (`<= 2.00%` Reg-NMS stop, `-1.50%` daily breaker, `>= 10%` API exit reserve, `singleActiveBrokerHostOnly = true`).
3. **Non-Destructive Archival Closure of `18/18` Legacy Repos:**
   - Seals the legacy `18`-repo estate cleanly (`dirty=0`, `0/0` pushed, `10/10` cleanliness doctor, `797/797` verbatim ADR archive in `sota-private-vault/adr_archive/`) as read-only historical provenance while all new development proceeds strictly inside the single clean monorepo `sota-ecosystem`.

## Consequences

- **Positive:** Permanently eliminates multi-repo overhead, cross-repo ADR drift, and boilerplate duplication while preserving `100%` of the legacy audit trail non-destructively.
- **Negative / Safeguards:** Creating a single GitHub remote for `sota-ecosystem` (private vs. public) remains gated on explicit owner confirmation.
