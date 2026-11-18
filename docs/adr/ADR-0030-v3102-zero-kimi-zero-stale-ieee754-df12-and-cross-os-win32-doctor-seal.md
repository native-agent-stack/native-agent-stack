# ADR-0030: `v3.10.2` Zero-Kimi / Zero-Stale Model Seal, IEEE-754 & Bitemporal `DF1..DF12` Hardening, and Cross-OS `Noesis` Win32 Doctor Parity

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Multi-Model Hygiene, Bitemporal `DF1..DF12` Safety & Cross-OS Verification (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`sota-multi-model-workflows` `ADR-0025`+`ADR-0026`, `cc-sota-harness` `ADR-0038`, `sota-harness-foundation` `ADR-0039`, `dsh-sota-harness` `ADR-0015`, `sota-private-vault` `ADR-0025`, `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/native-agent-stack/sota-harness-foundation
- **Revisit Trigger:** `2026-12-06` `23/5` Consolidated SIP cutover or `v4.0.0` promotion

## Context and Problem Statement

Finalizes the `v3.10.2` multi-peer convergence wave across `Apple M5 Max`, `Noesis` Win32, and `* Noesis-Carbon` WSL2: enforcing Owner Directives #1 & #2 (`0` stale models such as `deepseek-v4-pro`, `0` `kimi-*`/`Moonshot AI` models), merging cross-OS `scripts/doctor.py` (`0` errors on `Noesis` Win32 with truthful platform-scoped `goose`/`omniroute`), pinning broker-lane Orca routes executed on `Noesis` to `--on 100.93.211.101`, and remediating all `5` `noesis-cc-lead` `#92` IEEE-754/bitemporal/schema defects in `DF1..DF12` and Workflow `#19`.

## Decision Outcome

1. **Bump `ECOSYSTEM_CONVERGENCE_LOCK.json` to `3.10.2` With Zero Stale or `Kimi` Model Identifiers (`30` Umbrella ADRs):**
   - Seal `claude-fable-5-2` (`~1:1` mix), `claude-opus-5-5`, `claude-sonnet-5-5` (non-GPT `Hephaestus`), `gpt-6.2-astra`, `gpt-6.2-sol`, `gemini-4-carbon-high`, `gemini-4-hydrogen-xhigh`, and `deepseek-v4.1-flash` (`deepseek-flash`) across all `8` runtimes.

## Alternatives Considered

- **Leaving `ECOSYSTEM_CONVERGENCE_LOCK.json` with legacy `5_omo_kimi_...` channel strings:** Rejected — violates zero-Kimi hygiene across umbrella locks.

## Verification Witness

- `python scripts/architecture_catalog.py && python scripts/architecture_catalog.py --check` (`30` ADRs, `0` drift)
- `python -m unittest discover -s tests -v && python scripts/merge_gate.py && gitleaks git --log-opts=HEAD~1..HEAD --no-banner` (`PASS`, `0` leaks)
