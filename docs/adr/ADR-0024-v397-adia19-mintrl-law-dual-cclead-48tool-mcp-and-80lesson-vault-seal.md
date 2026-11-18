# ADR-0024: `v3.9.7` ADIA #19 `MinTRL` Power Law (`Lesson 6dab48d65a104306`), Dual `CC-Lead` `48`-Tool MCP Parity & 80-Lesson Vault Sync

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Quantitative Power Governance (`ADIA #19 MinTRL`), Dual `CC-Lead` MCP Parity & Vault Sync (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`sota-private-vault` `ADR-0019`, `Lesson 6dab48d65a104306`, `Mac` + `Noesis` `CC-Lead` `4/4` MCP `48`-Tool Probe PASS, `merge_gate.py` & `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-private-vault, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/native-agent-stack/sota-multi-model-workflows
- **Revisit Trigger:** 2026-12-06 (`23/5` SIP cutover) or when `postwall_cohort.closed_trades >= 250`

## Context and Problem Statement

Completing `v3.9.7` convergence across all `6` concurrent peer & workstation sessions (`f2693e3b`, `36628699`, `5d873241`, `7ebd8356`, `ad7807ca`, `noesis-agy`, and `acf160e4`):
1. **ADIA Lab #19 `MinTRL` Power Law (`Lesson 6dab48d65a104306`, `E3`):** Across `T = 700` `XNYS` pre-wall sessions (`2.78` years) at `N = 95` (`t*(95) = 4.1858 -> t*(96) = 4.1882`), clearing `ALPHA_STRATEGY_MINOR` requires annualized `SR >= 2.5115` (`MinTRL = 1,972.1` sessions / `7.83` years at `SR = 1.50`), proving Two-Track `PROTECTIVE_FILTER_OR_GOVERNANCE` + forward `200`-RPM Alpaca / `3,000`-MPM IBKR paper cohort accrual (`N >= 250`) is mathematically required for microstructure upgrades such as `H095`'s `+15s` bid-survived `<= 10.0 bps` collar (`+15.305 bps` `1x`, `+9.832 bps` `2x`).
2. **Dual-Workstation `CC-Lead` + `48`-Tool Win32 MCP Resolution:** Both `Mac Sovereign CC-Lead` and `Noesis CC-Lead` (`100.110.115.22`) verified `trading-lanes` / `harness-lanes` readiness (`17/17` fleet, `4/4` stdio MCP servers = `17 + 7 + 7 + 17 = 48` tools after `noesis-agy` placed `~/.agents/bin/python3.exe` ahead of the Win32 `WindowsApps` Store stub), and `sota-private-vault` (`ADR-0019`) hydrated all `95` scrubbed trials and `80` `E1–E4` lessons.

## Decision Outcome

1. **Record `v397AdiaMinTrlDualCcLeadAnd80LessonVaultSeal` (`schemaVersion = "3.9.7"`, `24` Umbrella ADRs):**
   - Preserve exact `schemaVersion = "3.9.7"` alignment with `DEFAULT_ECOSYSTEM_SEMVER` while binding `sotaPrivateVaultAdr0019Sha`, `lessonsCount = 80`, `adialabMinTrlYearsAtSr150 = 7.83`, and `win32McpToolsVerified = 48`.

## Alternatives Considered

1. **Increment `schemaVersion` past `"3.9.7"` for vault wiki sync:** Rejected — keeping `"3.9.7"` preserves 100% SemVer equality with `sota-multi-model-workflows` (`ADR-0019`) and `agy-sota-harness` (`ADR-0026`).

## Verification Witness

- `.venv/bin/python scripts/merge_gate.py` (`architecture_catalog --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
