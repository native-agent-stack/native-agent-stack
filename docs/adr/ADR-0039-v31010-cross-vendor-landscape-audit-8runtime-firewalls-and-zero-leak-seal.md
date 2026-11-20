# ADR-0039: `v3.10.10` Cross-Vendor Full-Landscape Audit, 8-Runtime Upstream-Native Firewalls & Zero-Leak Seal

- **Status:** Accepted
- **Date:** 2026-11-19
- **Layer:** Organization Umbrella (`L1`), Multi-Runtime Security Firewalls (`L4`/`L9`), Tier-3 Full-Manifest SkillEvaluator (`L8`), Dual-Workstation 3-Surface Parity (`Win32` + `* Noesis-Carbon` WSL2 + `Mac M5 Max`)
- **Evidence Grade:** E4 (`cc-sota-harness@85f54cd1` `ADR-0043` `43/43` ADRs `6/6` doctor on Win32/WSL2/Mac, `sota-harness-foundation@8b2ce535` `ADR-0044` `44/44` ADRs `103/103` pytest, `agy-sota-harness@df8e6b7d` `ADR-0035` `35/35` ADRs `23/23` pytest `13/13` probes, `dsh-sota-harness@ab0e5ff8` `ADR-0016` `16/16` ADRs `10/10` probes, `sota-doctor` `18/18` Win32 & WSL2, `evaluate_skills.py --check-mounts` `60/60` full-manifest parity across `8/8` mounts, OpenAI Codex `gpt-6.2-astra` cross-vendor red-team review closed to `0` P0/P1, `39/39` umbrella ADRs, `gitleaks 0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/native-agent-stack/agy-sota-harness, https://github.com/native-agent-stack/dsh-sota-harness, https://github.com/NVIDIA/SkillEvaluator, https://github.com/anomalyco/opencode, https://github.com/google-gemini/gemini-cli, https://github.com/earendil-works/pi, https://github.com/can1357/oh-my-pi
- **Revisit Trigger:** Addition of a 9th active runtime target, upstream hook/plugin API breaking change across any of the 8 runtimes, or `2026-12-06` `23/5` Consolidated SIP cutover

## Context and Problem Statement

A four-track cross-vendor full-landscape audit (spanning Antigravity, Claude Code, OpenAI Codex `gpt-6.2-astra`, and DeepSeek `dsh` across Stationary `Noesis` Win32, `* Noesis-Carbon` WSL2, and Portable `Apple M5 Max`) uncovered subtle hidden fallbacks, secondary-runtime firewall gaps, and privacy-gate inconsistencies across the open-core and harness tiers:

1. **8-Runtime PreToolUse Firewall Parity (`cc-sota-harness` `ADR-0043`):** Only `Claude Code`, `Antigravity`, and `Codex` had active PreToolUse firewalls while `Gemini CLI`, `OpenCode + OMO`, `DeepSeek Harness`, `Pi`, and `Oh-My-Pi` lacked upstream-native hooks; `Noesis-Carbon` WSL2 was missing `12/18` specialty Claude Code marketplaces (failing `doctor.py --fast` at `5/6`); `trading_harness_guard.py` lacked `PowerShell` coverage and false-positived on uppercase English words like `"PARAMETERS"` in `.gitleaks.toml` / `PA` regexes.
2. **Tier-3 Full-Manifest Skill Mount Parity (`sota-harness-foundation` `ADR-0044`):** `evaluate_skill_corpus()` previously did not parse bundled `*.py` scripts via `ast.parse()`, did not detect broken symlinks, and did not verify full-directory SHA-256 manifest parity (`SKILL.md` + executable `scripts/*.py` + resources) across all `8` mounted runtime skill directories.
3. **Offline Fallback Honesty & 3-OS Privacy Gates (`agy-sota-harness` `ADR-0035`, `dsh-sota-harness` `ADR-0016`):** DAG #10's offline stub previously reported `all_gates_passed: True` and `evidence_grade: "E4"` even when `sota_mmw` was unloaded; `dsh-sota-harness` `check-adr-catalog.mjs` lacked Windows/Linux concrete home-path checks and `UPSTREAM.md` retained a forbidden retired `block/goose` reference.
4. **Independent Cross-Vendor Red-Team Hardening (`Codex gpt-6.2-astra`):** Red-team audit flagged fail-open edge cases in JS/TS wrappers (empty/unknown/`ask` decisions, optional-chaining `setup(ctx)` no-op), relative `cwd` in `is_under_upstream`, unidirectional `_path_overlaps`, `:8798`/`:8796` mutation coverage, `SKILL.md`-only mount hashing, and DAG #10 `all_gates_passed` aggregation — every single P1 finding was resolved and live-verified prior to push.

## Decision Outcome

1. **Lock Cross-Vendor Landscape Audit & 8-Runtime Firewall Seal in `ECOSYSTEM_CONVERGENCE_LOCK.json` (`ADR-0039`):** Record `v31010CrossVendorLandscapeAuditAnd8RuntimeFirewallSeal` pinning exact `origin/main` 40-char SHAs across `cc-sota-harness@85f54cd1b0b9a0bc6686559dd1b693e4a9376c92`, `sota-harness-foundation@8b2ce5352018d377e32b3e234d7106a843d68285`, `agy-sota-harness@df8e6b7dd92c508947cd228243b260a482a80fe8`, and `dsh-sota-harness@ab0e5ff84f3ef6cd79d817bd611653179e8292b2`.
2. **Enforce Affirmative `--explicit-allow` Fail-Closed Policy Across All 8 Runtimes:** Require affirmative `permissionDecision === "allow"` in OpenCode (`setup(ctx)` + `server()`) and Pi/OMP (`tool_call`) extensions, native top-level `{"decision": "deny"}` in Gemini CLI `BeforeTool`, isolated `# >>> sota-safety-firewall >>>` fence in DSH `~/.dsh/cordis.patch.yml`, and `sota-doctor` Check #9 verification across Win32, WSL2, and Mac.
3. **Update Umbrella README & Convergence Tests:** Advance `README.md` ADR counts (`39` umbrella, `36` `.github`, `44` `sota-harness-foundation`, `35` `agy-sota-harness`, `16` `dsh-sota-harness`, `43` `cc-sota-harness`) and assert all `ADR-0039` lock invariants in `tests/test_umbrella_convergence.py`.

## Alternatives Considered

- **Shipping Only Static Regex Audits Without Cross-Vendor Red-Team Execution:** Rejected — independent OpenAI Codex `gpt-6.2-astra` review directly caught 5 concrete P1 fail-open and script-drift edge cases that single-model self-review missed.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`39/39` MADR 4.0 ADRs), `uv run python scripts/merge_gate.py` (`umbrella --check`, `ruff check`, `ruff format --check`, `ty check`, `pytest -q`), and `gitleaks protect --staged --no-banner` (`0` leaks).
