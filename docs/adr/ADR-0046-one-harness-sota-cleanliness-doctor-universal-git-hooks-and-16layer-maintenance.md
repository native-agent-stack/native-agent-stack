# ADR-0046: Continuous One-Harness SOTA Cleanliness Doctor, Universal Git Hooks, 18/18 Orca Gate Parity & 16-Layer Starred/Beyond Maintenance

- **Status:** Accepted
- **Date:** 2026-11-20
- **Evidence Grade:** E4
- **Supersedes / Extends:** Extends `ADR-0044`, `ADR-0045`, `sota-upstream-shelf-lock` `ADR-0023`/`ADR-0025`, and `sota-private-vault` `ADR-0027`

## Context

After consolidating all 18 repositories under Tier-0 `ADR-0023` (18-pin 40-char Git SHA shelf lock), `ADR-0038` (AST zero-stub full-resolution engine gates), `ADR-0044` (7/7 global runtime `.md` sync + single-repo Master ADR Registry), and `ADR-0045` (16-layer `L0`–`L15` Full-Landscape Resolute SOTA Layer-Pin Manifest), a workstation-wide audit identified five remaining structural drift vectors:

1. Global Git `core.hooksPath` was unset (`1/18` repos had `pre-commit`, `0/18` had `pre-push`), allowing any runtime that forgot to run `scripts/merge_gate.py` manually to commit or push unverified changes.
2. Only `4/18` `orca.yaml` workspace recipes wired a `Tier-0 Merge Gate` (`scripts/merge_gate.py`) tab (`14/18` missing).
3. No single top-level command verified all 16 layers, 18 repos, 7 global runtime `.md` files, `60/60` `SkillEvaluator` corpus, 24-class Red-Team firewall, `415` audited GitHub starred repos + beyond-starred SOTA anchors, `8`-stage Research Convergence Practice (`S1`–`S8`), single-repo ADR archives, downward-ratchet monolith caps, and live Paper/GPU health in one pass.
4. `ADR-0045` needed per-layer explicit separation of `starred_sota_repos` (`415` audited GitHub stars), `beyond_starred_sota_repos`, `research_convergence_stages` (`S1`–`S8`), and `harness_and_agent_md_binding` across every single layer `L0`–`L15`.

## Decision

1. **Universal Cross-OS Git Hooks (`hooks/pre-commit`, `hooks/pre-push`, `hooks/run_sota_git_hook.py`):**
   - Point global `git config --global core.hooksPath` to `native-agent-stack/hooks`.
   - `pre-commit` enforces `@users.noreply.github.com` author email, scans staged additions for broker account IDs, API keys, private keys, and 3-OS home paths, and runs `gitleaks protect --staged --no-banner --redact`.
   - `pre-push` automatically executes each SOTA repository's `scripts/merge_gate.py` fail-closed before any commit leaves the workstation. Non-SOTA repositories outside the ecosystem pass through untouched.
2. **`18/18` `orca.yaml` `Tier-0 Merge Gate` Parity:**
   - Wire `scripts/merge_gate.py` into all remaining `14/18` `orca.yaml` files so every Orca worktree across all `18/18` repositories launches with identical Tier-0 gate ergonomics.
3. **16-Layer Manifest `v2` (`scripts/build_full_landscape_layer_manifest.py`):**
   - Bind EVERY layer `L0`–`L15` explicitly to `pinned_core_shelf` (40-char SHAs from `PINS_LOCK.json`), `starred_sota_repos` (`415` audited GitHub stars), `beyond_starred_sota_repos`, `research_convergence_stages` (`S1`–`S8`), and `harness_and_agent_md_binding` (`.md` rules, canonical skills, MCP/workflow surfaces, enforcement gate).
4. **Single-Command One-Harness SOTA Cleanliness Doctor (`scripts/one_harness_cleanliness_doctor.py`):**
   - Continuously audits all 10 deterministic cleanliness invariants in one pass (`--check`, `--fix-sync`, `--write-receipt`, `--offline`, `--json`) and seals a public-safe SHA-256 Cleanliness Receipt (`docs/SOTA_ONE_HARNESS_CLEANLINESS_RECEIPT.{json,md}`).
   - Enforces a downward-ratchet LOC cap on legacy monoliths (`alpaca_paper_e2e.py`, `stage5_lossless_live_lane.py`) so god-files can only shrink via Strangler decomposition.
   - Re-syncs all `7/7` global runtime `.md` files (`sync_tier0_harness_and_master_adrs.py --check/--apply-global-md`) and verifies `0`-drift parity across both single-repo ADR archives (`native-agent-stack` public registry & `sota-private-vault/adr_archive/` verbatim private copy).

## Upstream Evidence & Primary Sources

- Orca isolated worktrees & `orca.yaml`: https://github.com/stablyai/orca
- NautilusTrader full-resolution engine: https://github.com/nautechsystems/nautilus_trader
- hftbacktest queue-fill parity: https://github.com/nkaz001/hftbacktest
- NVIDIA SkillEvaluator (4-tier 60-skill audit): https://github.com/NVIDIA/SkillEvaluator
- Claude-BugHunter (24-class trading-firewall audit): https://github.com/elementalsouls/Claude-BugHunter
- Microsoft RD-Agent (Co-STEER research convergence): https://github.com/microsoft/RD-Agent
- Microsoft Qlib (Alpha158 PIT factors): https://github.com/microsoft/qlib
- Gitleaks pre-commit zero-secret scanner: https://github.com/gitleaks/gitleaks
- Trail of Bits dimensional & property invariants: https://github.com/trailofbits/skills

## Consequences

- No agent runtime (`Antigravity`, `Claude Code`, `Codex`, `OpenCode`, `DSH`, `Pi/OMP`, `Orca` workers) can commit secrets/paths or push failing Tier-0 `merge_gate.py` code across any of the 18 repositories.
- One command (`uv run python scripts/one_harness_cleanliness_doctor.py --check`) deterministically certifies the entire 16-layer, 18-repo, 7-runtime, 415+ starred/beyond, 8-stage research convergence ecosystem with a verifiable SHA-256 receipt.
