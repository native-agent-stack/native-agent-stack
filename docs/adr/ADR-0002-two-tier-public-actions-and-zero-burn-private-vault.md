# ADR-0002: Two-Tier Public Unlimited Actions & Zero-Burn Private Vault

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E3

## Context and Problem Statement
GitHub grants unlimited free Actions minutes to public repositories while metering private repositories, whereas proprietary execution signals and empirical ledgers must remain strictly private.

## Decision Outcome
Split `github.com/native-agent-stack` into `9` `PUBLIC` open-core repositories (running `40`-char SHA-pinned GitHub Actions CI) and `PRIVATE` execution/simulation/vault repositories with `actions_enabled=false` (zero paid quota burn, gated locally by `merge_gate.py` and audited live by `sota-org-doctor --live`).
