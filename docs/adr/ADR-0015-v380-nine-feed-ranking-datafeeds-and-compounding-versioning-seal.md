# ADR-0015: `v3.8.0` Nine-Feed PIT Ranking DataFeeds (`DF1`–`DF9`), Two-Track Compounding Versioning & Cross-Repo `orca.yaml` Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

Following `ADR-0014` (`v3.7.0` Stage-B `Noesis-Carbon` `Z:` reset, symmetric `:6770` Orca mesh, and `Trial #90`), the ecosystem converged whole-market PIT ranking feeds (`DF1`–`DF9`), Vega/Tetlock catalyst surprise scoring (`sota-mover-ranker`), deterministic `sota-version` 4-hash compounding versioning, and cross-OS `orca.yaml` workspace recipes across all Trading Lane and Harness Lane repositories.

## Decision Outcome

1. **Nine-Feed Point-in-Time Ranking Contract (`sota-ranking-datafeeds.v3.8`, `Meridian` `ADR 0060`, `Canon` `0178`, `sota-mover-ranker` `17`-Tool MCP):**
   - Unite the 7 `sota-research-feeds.v2` streams with `DF4_xnys_tod_rvol_bucket_normalizer` (`Canon 0173`, `QuantConnect/Lean@e28820c9c846` trailing `20`-session `XNYS` clock-bucket `RVOL_tod` with `None` cold-start sentinel) and `DF8_finra_rule4560_settled_short_interest_t8` (FINRA Rule 4560 `T+8` `XNYS` backward `asof` settled short interest alongside `DF7` `CNMSshvol` `T-1`), plus Vega (2006) / Tetlock (2007) PIT news surprise (`sota-mover-ranker @ e0375c51`).
2. **`v3.8.0` 4-Hash Monotonic Compounding Versioning & Two-Track Promotion (`sota-version`):**
   - Require strict `prev_version < next_version` (`>= 3.8.0`), non-zero 4-hash SHA-256 provenance (`input_lake_sha256`, `upstream_18_pins_sha256`, `ranking_9feeds_sha256`, `adr_id`), `N = 90` HLZ trial ledger (`t*(91) = 4.1760`, `62` E1–E4 root-cause lessons), `16` canonical + `6` native `agy` workflows, and two-track promotion separating `ALPHA_STRATEGY_MINOR` (`DSR >= 0.95`, `>= 5` positive `CPCV` paths, `Stage-3 >= 30` closed roundtrips) from `PROTECTIVE_FILTER_OR_GOVERNANCE` (`H090` `+20.84 bps` 1x / `+15.43 bps` 2x / `5/5` positive `CPCV` passive-bid protection, `standalone_alpha_claim = False`).
3. **Cross-OS `orca.yaml` Workspace Parity:**
   - Provide zero-secret, zero-local-path `orca.yaml` recipes across `native-agent-stack`, `.github`, and unlocked Trading/Harness Lane repositories for `Mac M5 Max`, `Noesis` Win32, and `* Noesis-Carbon` (`WSL2 ext4`).

## Alternatives Considered

1. **Retain 7-feed `sota-research-feeds.v2` without explicit `DF4` (`RVOL_tod`) and `DF8` (`T+8` Rule 4560 SI) lineage:** Rejected — leaves intraday auction distortion and bi-monthly SI publication lag implicit.
2. **Use a single promotion track that conflates protective queue filters (`H090`) with standalone minor alpha releases:** Rejected — two-track promotion preserves `DSR >= 0.95` statistical rigor while landing verified execution protections.

## Verification Witness

- `scripts/architecture_catalog.py --check` (`15/15` MADR 4.0 ADRs valid, `0` drift) & `scripts/merge_gate.py` (`PASS`, `v3.8.0`).
- `Meridian @ e2153da7` (`57` ADRs, `557` passed), `Canon @ 1a6bd8b6` (`152` ADRs, `canon: lint clean`), and `sota-mover-ranker @ e0375c51` (`72/72` passed).
