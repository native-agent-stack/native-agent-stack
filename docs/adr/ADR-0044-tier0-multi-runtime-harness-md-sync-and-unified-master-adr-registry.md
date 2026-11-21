# ADR-0044: Tier-0 Multi-Runtime Harness `.md` Convergence & Unified Single-Repo Master Finalized ADR Registry

- **Status:** Accepted
- **Date:** 2026-11-20
- **Layer:** Umbrella Governance, Multi-Runtime Rules & Consolidated ADR Registry (`native-agent-stack`: `scripts/sync_tier0_harness_and_master_adrs.py`, `scripts/merge_gate.py`, `docs/adr/ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.{md,json}`, `tests/test_adr0044_tier0_harness_and_master_adr_registry.py`)
- **Evidence Grade:** E4 (`7/7` global runtime instruction `.md` files converged on Tier-0 `ADR-0023` + `ADR-0038`; `18/18` repos indexed into single-repo public-safe Master ADR Registry paired with `sota-private-vault/adr_archive/` verbatim archive `ADR-0027`; `18/18` local `scripts/merge_gate.py` enforcing `ADR-0023`; `4/4` quant engines enforcing `ADR-0038` AST zero-stub checks; `ruff`, `ty`, `pytest`, `umbrella --check`, `architecture_catalog --check`, `gitleaks 0`)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-private-vault, https://github.com/native-agent-stack/sota-upstream-shelf-lock, https://github.com/stablyai/orca
- **Revisit Trigger:** Any new Tier-0 ecosystem invariant, additional agent runtime surface, or major ADR wave across the 18 active repositories.

## Context and Problem Statement

A live workstation audit on `2026-11-20` revealed two governance gaps across the 18-repository ecosystem:
1. Only `1/7` global runtime instruction `.md` files (`agy-sota-core/rules/AGENTS.md`) carried the Tier-0 Full-Resolution Zero-Fallback (`ADR-0025/0038/0034`) directive, and `0/7` explicitly embedded the Tier-0 Hard SOTA-Source-Only (`ADR-0023` / `upstream-map.toml`) mandate inside their synced rule block.
2. While all `785+` finalized MADR 4.0 ADRs passed per-repo evidence checks (`18/18`), there was no single-repo consolidated registry for auditing the full finalized ADR set in one place while respecting the Two-Tier Public vs Private boundary (`ADR-0001`).

## Decision Outcome

1. **Canonical `7/7` Multi-Runtime Tier-0 Harness `.md` Sync (`scripts/sync_tier0_harness_and_master_adrs.py`):**
   - Deterministically upserts the canonical `TIER0-SOTA-RULES` block (`ADR-0023` SOTA-Source-Only + `ADR-0025/0038/0034/0095` Full-Resolution Zero-Fallback + single-repo ADR registry references) inside `<!-- BEGIN SOTA-ECOSYSTEM-SYNC --> ... <!-- END SOTA-ECOSYSTEM-SYNC -->` across all 6 synced runtimes (`GEMINI.md`, `CLAUDE.md`, `codex/AGENTS.md`, `opencode/AGENTS.md`, `dsh/AGENTS.md`, `omp/agent/AGENTS.md`) without disturbing OMX/OMC sections, plus updates `agy-sota-core/rules/AGENTS.md` (`7/7` parity).
2. **Unified Single-Repo Master Finalized ADR Registry (`docs/adr/ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.{md,json}`):**
   - Aggregates public-safe metadata (`repo`, `tier`, `title`, `status`, `date`, `evidence_grade`, `github_urls`, `file_sha256`) for every finalized ADR across all 18 repositories into `native-agent-stack`, paired with the verbatim privacy-scrubbed full-text archive in `sota-private-vault/adr_archive/` (`ADR-0027`).
3. **Self-Enforcing `ADR-0023` Merge Gate (`scripts/merge_gate.py`):**
   - Wired `shelf_lock.hard_upstream_rule` locally (with stdlib `tomllib` schema verification in hosted Public GitHub Actions CI) so all `18/18` repositories' `scripts/merge_gate.py` self-enforce `ADR-0023`.

## Alternatives Considered

1. **Full Greenfield Ecosystem Rebuild:** Rejected — strangler consolidation preserves `2,500+` passing production regression tests and live paper safety firewalls while closing 100% of Tier-0 rule and ADR consolidation gaps immediately.

## Consequences

- **Positive:** All 7 runtimes, all 18 `merge_gate.py` scripts, all 4 quant-engine AST gates, and both single-repo finalized ADR views (public-safe master registry + private verbatim archive) are now 100% converged.
- **Negative / Safeguards:** Re-run `python scripts/sync_tier0_harness_and_master_adrs.py --apply-global-md` whenever Tier-0 rules or ADR catalogs advance.

## Verification Witness

- **Tests & Gates:** `tests/test_adr0044_tier0_harness_and_master_adr_registry.py`, `scripts/merge_gate.py` (`ruff`, `ty`, `pytest`, `umbrella --check`, `architecture_catalog --check`, `ADR-0023`, zero-leak), `gitleaks 0`.
