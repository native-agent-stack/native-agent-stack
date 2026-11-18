# ADR-0014: `v3.7.0` Stage-B `Noesis-Carbon` `Z:` Reset (`2.85 TB`), Symmetric `:6770` Orca Mesh, `Trial #90` (`+20.84 bps` 1x) & `09:30` ET Protection Convergence

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

Following `ADR-0013` (`v3.6.0` universal workflow/DataFeed/template/engine and 3-surface workstation convergence), final pre-open coordination across `Mac M5 Max` (`100.93.211.101`), `Noesis` Win32 (`100.110.115.22`), and `* Noesis-Carbon` (`Ubuntu 26.04.1 LTS` `ext4`) closed every remaining infrastructure hold (`Meridian` `0055`/`0056`), seeded the `<= 2026-10-15` pre-wall lake on `Noesis`, executed `Trial #90` (`H090`), and sealed MADR 4.0 ADRs across all `18` active repositories.

## Decision Outcome

1. **Stage-B `Noesis` `Z:` Reset, Symmetric `:6770` Orca Pairing & Pre-Wall Lake Seed (`sota-harness-foundation` `ADR-0028`, `Meridian @ f8483af9`):**
   - Legacy `meridian` WSL2 (`120.21 GB` `tar -tf` verified on `E:`) and `Z:` archives were offloaded (`+871.6 GB` reclaimed -> `2.85 TB` free on `Z:` NVMe), promoting `* Noesis-Carbon` (`Ubuntu 26.04.1` `ext4`, `sextant` untouched) in `dual-workstation-lane-manifest.json` (`v1.1.0`).
   - Bidirectional hardened `orca serve --no-pairing --refuse-public` (`100.93.211.101:6770 <-> 100.110.115.22:6770`) and the `1.57 GB` (`29,500`-file) `<= 2026-10-15` pre-wall Parquet lake on `Z:/sota-data/prewall-lake` (`/mnt/z/sota-data/prewall-lake`) are live while `Mac M5 Max` remains the sole active Paper broker host (`singleActiveBrokerHostOnly = true`).
2. **`Trial #90` (`H090`) Microstructure Synthesis & `09:30` ET Live Protection Readiness (`sota-private-vault` `ADR-0010`, `sota-mover-ranker` `ADR-0013`, `sota-dynamic-trail-c` `ADR-0011`):**
   - `H090` (tight-spread `<= 10 bps` + high-`OFI` `>= 0.25` `RiskAdverseQueueModel` passive bid × fixed `ADR-0022` `2.00%` stop) delivered **`+20.84 bps` net 1x**, **`+15.43 bps` net 2x**, **`+39.06 bps` in 2026**, and **`5/5` `CPCV` positive paths** (`75.81%` `15:54` ET survival; honestly logged `FAILED` at `t = 1.2919 < t*(90) = 4.1735`, advancing `N = 90 -> t*(91) = 4.1760` and `59` compiled lessons).
   - Live `:8787` (`GET /api/live_ready_0930_goal` `HTTP 200`, off-top-pool `50/50 + Wave-2` watches, cold-`SAR` `OFI`/`UCB` gate), `:8799` (`GET /api/live-ready-0930` `HTTP 200`, `5`-preset `[P]/[L]/[M]/[B]/[S]` catalog, Pine v1.0 HUD, zero-broker `arm-watch`), and `:4002` (`astrolabe` `ADR-0006`) are 100% armed under `ADR-0022 <= 2.00%` stops.

## Alternatives Considered

1. **Leave Stage-B holds (`0055`/`0056`) or pre-`09:30` execution commits unindexed at the umbrella layer:** Rejected — `ECOSYSTEM_CONVERGENCE_LOCK.json` (`v3.7.0`) maintains 1:1 parity across all `15` single-owner layers.
2. **Run Paper broker writers on both workstations simultaneously:** Rejected — hard-refused by `singleActiveBrokerHostOnly = true`.

## Verification Witness

- `scripts/architecture_catalog.py --check` (`14/14` MADR 4.0 ADRs valid, `0` drift) & `scripts/merge_gate.py` (`PASS`, `v3.7.0`).
- `9/9` public GitHub Actions `completed / success`, `sota-doctor` `12/12 PASS`, and `sota-org-doctor --live` `22/22 PASS` (`0` violations).
