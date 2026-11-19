# ADR-0035: `v3.10.8` Orca SOTA Worker Defaults, 60-Skill Red-Team/SkillEvaluator & 415-Starred Convergence Seal

- **Status:** Accepted
- **Date:** 2026-11-19
- **Layer:** Organization Umbrella, Dual-Machine Orca Runtime Fleet (`1.4.263`), Red-Team Security & 4-Tier SkillEvaluator (`ADR-0043`), `60` Skills, `21` Workflows & `415+8` Starred Convergence (`L0–L13` × `H1–H3`)
- **Evidence Grade:** E4 (`sota-harness-foundation@da6b90a3` `ADR-0043`, `sota-multi-model-workflows@3e60a76c` `ADR-0033`, `sota-upstream-shelf-lock@ce5f5ac6` `ADR-0015`, `agy-sota-harness@ed05b00c` `ADR-0034`, `cc-sota-harness@fa053bfc` `ADR-0041`, `35/35` MADR 4.0 ADRs, `merge_gate.py` + `ruff` + `pytest` + `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/sota-upstream-shelf-lock, https://github.com/native-agent-stack/agy-sota-harness, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/elementalsouls/Claude-BugHunter, https://github.com/NVIDIA/SkillEvaluator, https://github.com/Tencent/LoopForge
- **Revisit Trigger:** Addition of canonical runtime skills beyond `60`, Orca workflow changes beyond `21`, or modification of immutable `18`-pin `40`-char SHAs in `sota-upstream-shelf-lock`.

## Context and Problem Statement

While `ADR-0034` (`v3.10.7`) sealed the 5-layer computer-use stack, cross-runtime skill quality checks lacked a unified 4-tier validator (`NVIDIA/SkillEvaluator`) and adversarial Red-Team firewall gate (`elementalsouls/Claude-BugHunter`, `cloudflare/security-audit-skill`, `NVIDIA/OpenShell`, `morluto/rea`), several dual-machine Orca automations lacked explicit non-stale `--extra-agent-args`, `07-orca-lead-e2e-sota-research-convergence` suffered `workspaceMode=existing` collisions, `parabolic-short-trade-planner` needed fail-closed `paper=True` enforcement, and `415` owner-starred repositories plus `8` beyond-starred frameworks required structured `PHILOSOPHY_ONLY` cataloging.

## Decision Outcome

1. **Red-Team & 4-Tier SkillEvaluator Convergence (`60` Skills, `0` Overlap Warnings):** Converge `sota-redteam-bughunter`, `sota-skill-evaluator`, and `sota-loopforge-convergence` alongside fail-closed `paper=True` hardening in `parabolic-short-trade-planner`, passing `evaluate_skills.py` `60/60` (`overlap_warnings: []`) across all `8` active runtimes (`claude`, `codex`, `antigravity`, `opencode`, `dsh`, `omp`, `pi`, `muse`).
2. **SOTA Orca Worker Defaults, Workflow `#21` & `15` Dual-Machine Automations:** Remove retired `grok` and `goose` across configs, hubs, and manifests; enforce explicit SOTA `--extra-agent-args` (`claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`, `gpt-6.2-astra`, `gemini-4-neon-xhigh`, `deepseek-v4.1-flash`); fix `07-orca-lead-e2e` to `new-per-run`; and add Workflow `#21` (`redteam-skilleval-convergence-loop`) + Automation `#15` (`11-noesis-redteam-skilleval-and-security-audit`).
3. **Preserve `18/18` Immutable Shelf Pins &Seal `415+8` Starred Catalog (`ADR-0015`):** Keep all `18` `40`-char upstream SHAs untouched in `sota-upstream-shelf-lock/PINS_LOCK.json` while publishing `STARRED_CONVERGENCE_CATALOG.json` under `PHILOSOPHY_ONLY` authority and sealing `ECOSYSTEM_CONVERGENCE_LOCK.json` at `v3.10.8`.

## Alternatives Considered

- **Mutate `18`-Pin Core Upstream SHAs During Starred Audit:** Rejected to preserve deterministic `RiskAdverseQueueModel` and pre-wall (`<= 2026-10-15`) reproducibility across downstream trading repos.
- **Leave Automations Without Explicit Model Args or Copy 60 Global Skills Into Repo Trees:** Rejected because implicit defaults risk model drift across hosts and duplicating global skills breaks `UPSTREAM_SKILL_PINS.json` scoping.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`35` MADR 4.0 ADRs valid, `0` drift), `uv run ruff format --check .`, `uv run ruff check .`, `uv run pytest -v`, and `gitleaks git --staged --verbose` (`0` leaks).
