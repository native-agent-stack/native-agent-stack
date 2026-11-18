# ADR-0016: `v3.9.0` Dual-Machine Lane Hub v2 (`T1`–`T5` × `H0`–`H7`), `Trial #91` (`H091`) Lit-Queue Law, `18/18` `UPSTREAM.md` Lineage & Pre-Wall Lake SHA Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Dual-Machine Orca Lane Hub v2, Lit-Queue Microstructure Governance & Pre-Wall Lake Provenance (`L0–L13` × `P0–P5` × `T1–T8`)
- **Evidence Grade:** E4 (`18/18` Active Repos with `UPSTREAM.md` + `orca.yaml`, `Trial #91` `H091` `286/435` Lit-Queue Empirical Proof, `prewallLakeSha256` `a253421e8734...`, `14/14` `sota-doctor` & `22/22` `sota-org-doctor` Verified)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-dynamic-trail-c, https://github.com/stablyai/orca, https://github.com/nkaz001/hftbacktest
- **Revisit Trigger:** 2027-01-02

## Context and Problem Statement

Following `ADR-0015` (`v3.8.0` 9-feed PIT ranking `DF1..DF9` and two-track compounding versioning), four final ecosystem-wide closures completed across all `18` active repositories:
1. **Dual-Machine Orca Lane Hub v2 (`sota-dual-machine-lanes.v2` × `sota-orca-lane-hub.v2`):** Unified `T1..T5` Trading Lanes (`8` repos) and `H0..H7` Harness Lanes (`10` repos) across `portable_mac_m5_max`, `stationary_noesis_win32`, and `stationary_noesis_wsl_carbon` (`100.110.115.22`), with deterministic RTH broker-contention shielding (`Mac M5 Max` sole active Paper broker host `:8787`, `:8799`, `:4002`).
2. **Empirical Pre-Wall Lake SHA-256 (`a253421e873441740d5d4b410d993cfa7345fe34b88ec4ab7f4eecd537b3f234`) & `18/18` `UPSTREAM.md` Lineage:** Bound the true cryptographic digest of the `<= 2026-10-15` pre-wall Parquet lake across `sota-version` 4-hash lineage and standardized `UPSTREAM.md` SOTA framework registers across all `18/18` active repositories.
3. **`Trial #91` (`H091`) Lit-Only Round-Lot Queue Depletion & Protective Entry Shield (`ADR-0017` / `ADR-0009` / `Canon 0179`):** Evaluating `hftbacktest::RiskAdverseQueueModel` on strictly lit round-lot prints (`x != 'D'`, non-`'I'`) across `C(6,2) = 15` disjoint split `CPCV` windows (`286 / 435 = 65.75%` lit fill rate, `-23.732 bps` net 1x when relaxing to `<= 12 bps` / `OFI >= 0.15`) proved that `H090`'s tight `<= 10 bps` spread and `OFI >= 0.25` threshold is structurally required to avoid Glosten–Milgrom adverse selection (`N = 91 -> t*(92) = 4.1785`, `65` compiled lessons).
4. **Live RTH Opening Protection, Singleton Daemon Flock & Explicit `waited_gates` (`sota-mover-ranker` `ADR-0016`–`0017`, `sota-dynamic-trail-c` `ADR-0013`–`0014`):** Enforced `09:30 ET` stale off-hours limit purge, breached-stop rescue, full-qty `trailing_stop`, `2s` zlib Win32 Orca watchlist mirror, `fcntl.flock` daemon exclusivity, and machine-readable `waited_gates` on `:8799/api/landscape`.

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.0"` (`16` Umbrella ADRs):**
   - Record `v390DualMachineLaneHubV2AndH091Seal` (`sota-dual-machine-lanes.v2`, `sota-orca-lane-hub.v2`, `prewallLakeSha256 = "a253421e873441740d5d4b410d993cfa7345fe34b88ec4ab7f4eecd537b3f234"`, `18/18` `UPSTREAM.md` + `orca.yaml` parity, `H091` lit-queue empirical boundary, `91` completed HLZ trials, and `65` lessons) and add `UPSTREAM.md`.

## Alternatives Considered

1. **Relax passive-bid limit admission beyond `<= 10 bps` / `OFI >= 0.25`:** Rejected — falsified empirically by `Trial #91` (`H091`, `-23.732 bps` net 1x due to `34.25%` unfilled runaway winners).
2. **Allow heavy `pytest` / Polars / DuckDB sweeps on `Mac M5 Max` during active RTH broker streaming:** Rejected — routed to `Noesis` / `* Noesis-Carbon` (`100.110.115.22`) by the `sota-dual-machine-lanes.v2` RTH contention shield.

## Verification Witness

- `uv run python scripts/merge_gate.py` (`architecture_catalog.py --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
