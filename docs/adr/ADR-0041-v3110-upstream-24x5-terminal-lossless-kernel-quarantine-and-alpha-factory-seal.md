# ADR-0041: `v3.11.0` Upstream-First `24/5` OpenBB Terminal, Shared `LosslessProtectionKernel`, Paper Quarantine & Pre-Wall Alpha Factory (`Trial #104`) Seal

- **Status:** Accepted
- **Date:** 2026-11-20
- **Layer:** Organization Umbrella (`L1`): sibling-commit pins across `sota-upstream-shelf-lock`, `sota-compounding-lab`, `sota-dynamic-trail-c`, and `sota-mover-ranker`; shared lossless execution parity; upstream-first terminal retirement of static Pine tables; Paper `P1–P4` strategy quarantine; and honest Pre-Wall `Trial #104` falsification seal
- **Evidence Grade:** E4 (Independent read-only OpenAI Codex `gpt-6.2-astra` `VERDICT: PASS` across all four implementation repositories; `20/20` shelf-lock tests + exact `PINS_LOCK.json` SHA-256 `ed5e461e...`; `289 passed, 4 skipped` compounding-lab tests + live WSL2 `Noesis-Carbon` Pre-Wall `S1`+`S2` `Trial #104` receipt `5e073f98...`; `230 passed` dynamic-trail-c tests incl. `2,000` Hypothesis examples; `419 passed` mover-ranker tests incl. `12,500` Hypothesis examples + real Paper `24/5` `OVERNIGHT_BOATS` `QQQ` fill receipt with `0` `42210000` rejections and `live_touched=false`; `41/41` umbrella ADRs; `gitleaks 0` leaks across all repos; Live `:8798`/`:8796` untouched)
- **GitHub Evidence:** https://github.com/native-agent-stack/sota-upstream-shelf-lock/commit/e3549753294874eaf4d388119ff7053c308794dd, https://github.com/native-agent-stack/sota-compounding-lab/commit/00178c12fbf318dbf4ae5ab9e59a374ba5a3a921, https://github.com/native-agent-stack/sota-dynamic-trail-c/commit/d89ce3acf0ff9c4468b790c2df4fffb8a99c3879, https://github.com/native-agent-stack/sota-mover-ranker/commit/67f786382ad81c0de3a518c23330552d55592530, https://github.com/native-agent-stack/sota-upstream-shelf-lock/blob/e3549753294874eaf4d388119ff7053c308794dd/docs/adr/ADR-0018-qlib-and-openbb-workspace-backend-upstream-pin.md, https://github.com/native-agent-stack/sota-compounding-lab/blob/00178c12fbf318dbf4ae5ab9e59a374ba5a3a921/docs/adr/ADR-0027-prewall-next-session-lake-qlib-alpha158-and-trial104-alpha-factory.md, https://github.com/native-agent-stack/sota-dynamic-trail-c/blob/d89ce3acf0ff9c4468b790c2df4fffb8a99c3879/docs/adr/ADR-0029-shared-lossless-protection-kernel-and-boats-parity.md, https://github.com/native-agent-stack/sota-mover-ranker/blob/67f786382ad81c0de3a518c23330552d55592530/docs/SOTA_FULL_LANDSCAPE_MANIFEST.md
- **Revisit Trigger:** `2026-12-06` `21:00 ET` consolidated `23/5` SIP cutover verification, pre-registration of `Trial #105` (`t*(105) = 4.2084`), or explicit owner-gated Stage-5 Live `:8798`/`:8796` reload after human sign-off.

## Context and Problem Statement

`ADR-0040` (`v3.10.11`) sealed the terminal taxonomy, collar recalibration contract, and Dec 6 `23/5` readiness baseline while deferring the `v3.11.0` architectural wave to four owning repositories:

1. **Overnight `24/5` Execution Gap:** TradingView's Alpaca panel omitted `extended_hours=True` and froze `19:59 ET` quotes during `20:00–04:00 ET` Overnight `BOATS`, queuing orders dormant until `09:30 ET` instead of filling overnight.
2. **Duplicated Protection Math:** Stop quantization (`ADR-0022 <= 2.00%`), `4x` leverage-aware equity cap, `>= 10%` protective exit reserve, and monotonic 3-tier uncapped Chandelier logic needed unification into one shared, Hypothesis-verified kernel across `P1–P4` and Stage-5 Live.
3. **Static Hand-Rolled UI Debt:** Static Pine table generation (`/api/pine/live_ranker`) and ad-hoc HTML cockpits violated our upstream-first terminal policy (`OpenBB Workspace` + `TradingView 24H/BOATS` live charting + canonical `DF1..DF12` feeds).
4. **Paper Hygiene & Pre-Wall Alpha Discipline:** Negative-expectancy/noisy paper strategies diluted `P1–P4` capital allocation, while the `S1`/`S2` Pre-Wall factory (`<= 2026-10-15`) needed canonical `XNYS` `next_session_date` pre-joining and an honest `ADIA Lab #19` + `hftbacktest` + `CPCV` + `DSR` + symmetric `CSCV PBO` evaluation (`Trial #104`).

## Decision Outcome

### 1. Pin the Four Landed `v3.11.0` Sibling Commits (Pointer-Only Charter)

| Repository | Owner Decision | Pinned `origin/main` Commit | ADRs | Verification Witness |
| --- | --- | --- | --- | --- |
| `sota-upstream-shelf-lock` | `ADR-0018` (`microsoft/qlib` `MIT` + `OpenBB-finance/backends-for-openbb` `MIT`; `18` core pins preserved) | `e3549753294874eaf4d388119ff7053c308794dd` | `18` | `20 passed`, `PINS_LOCK.json` SHA-256 `ed5e461e...`, Codex `gpt-6.2-astra` `PASS` |
| `sota-compounding-lab` | `ADR-0027` (`XNYS` `next_session_date` pre-join + `S1`/`S2` `Trial #104` Alpha Factory) | `00178c12fbf318dbf4ae5ab9e59a374ba5a3a921` | `27` | `289 passed, 4 skipped`, WSL2 receipt `5e073f98...`, Codex `gpt-6.2-astra` `PASS` |
| `sota-dynamic-trail-c` | `ADR-0029` (shared `LosslessProtectionKernel` + `DataFeed.BOATS` parity on `:8799` P1) | `d89ce3acf0ff9c4468b790c2df4fffb8a99c3879` | `29` | `230 passed` (incl. `2,000` Hypothesis), Codex `gpt-6.2-astra` `PASS` |
| `sota-mover-ranker` | `ADR-0062..ADR-0065` (`24/5` BOATS, OpenBB backend, `DF1..DF12` targets, kernel, quarantine, landscape manifest) | `67f786382ad81c0de3a518c23330552d55592530` | `65` | `419 passed` (incl. `12,500` Hypothesis), live Paper `QQQ` `BOATS` receipt, Codex `gpt-6.2-astra` `PASS` |

### 2. Upstream-First `24/5` Execution, Shared Kernel & Paper Quarantine Invariants

- **True `24/5` Uncapped Lossless Execution:** All 6 RTH TradingView presets (`[P]`, `[L]`, `[M]`, `[B]`, `[S]`, `[O]`, `TP OFF`) coordinate seamlessly with `auto_adopt_owner_entries=True` -> monotonic 3-tier uncapped Chandelier. Extended and `20:00–04:00 ET` Overnight `BOATS` route through live `DataFeed.BOATS` NBBO (`<= 35 bps` spread cap), sanctioned `OpenBB Workspace` Order-Staging Widget (`:8787/api/openbb/*` & `:6900`), and `IBKR P4 :4002` `OVERNIGHT`/`outsideRth=True` + RTH native `SMART TRAIL LIMIT`. Real Paper `OVERNIGHT_BOATS` `QQQ` round-trip verified empirically with `0` `42210000` rejections and `live_touched = false`.
- **Single Shared `LosslessProtectionKernel`:** Exact `Decimal` Rule-612 `ROUND_FLOOR` stop quantization (`<= 2.00%`), `4x` leverage-aware equity cap, `>= 10%` protective-exit reserve, and monotonic Chandelier verified across `14,500` combined Hypothesis property examples (`12,500` in `sota-mover-ranker` + `2,000` in `sota-dynamic-trail-c`).
- **Upstream-First Terminal & Canonical `DF1..DF12` Target Engine:** `/api/pine/live_ranker` is hard-retired (`HTTP 410 Gone`), `static/index.html` is deprecated, and canonical SHA-256-signed `sota.active-market-targets.v1` (`/api/active_market_targets`, 5 lenses, late-`POST` and 90-day SEC dilution hard retirement) feeds `OpenBB Workspace` natively alongside `SOTA_FULL_LANDSCAPE_MANIFEST` (`fb60d3938eac8576661ec36c4c930d1f93ab52df78a60b2913176bb81271185a`).
- **Paper `P1–P4` Hygiene & Unified Strategy Contract:** `ADR-0064` quarantines `5` negative-expectancy/noisy strategies out of active Paper capital allocation while concentrating `P1–P4` on `6` citation-backed SOTA families under `sota.strategy-contract.v2` and canonical `sota-<slug>-<lane>-<seq>` broker client IDs.

### 3. Honest Pre-Wall `Trial #104` Outcome (`PROTECTIVE_FILTER_OR_GOVERNANCE`, Zero Hype)

- **Canonical `XNYS` Pre-Join:** `derived/df10_daily_20d_baselines_next_session.parquet` materialized on `Noesis-Carbon` ext4 from canonical `universe/{2024,2025,2026}/daily_split.csv.gz` (`7,039,270` rows, `680` sessions `<= 2026-10-15`, `679` verified 1-step pairs, `0` mismatches, `0` post-wall breaches, SHA-256 `793ecc1e9bab14f8f704e25552f6e4f9e02974d1d2deb0849878ac2cf9f56cc2`).
- **Live WSL2 `S1` + `S2` Empirical Receipt (`5e073f98...`):**
  - `ADIA Lab #19` power gate approved (`t*(104) = 4.2063`, `MinTRL = 496` days, `MDE = 13.711 bps`).
  - `S2` (`hftbacktest 2.4.2 RiskAdverseQueueModel`, `700` pre-wall SIP date directories, `0` post-wall): `2/11` passive GTX fills (`18.18%` fill rate), calibrated `4.0 bps` 1x / `8.0 bps` 2x floor propagated into `S1`.
  - `S1` (18-feature `Qlib Alpha158`-inspired LightGBM, `skfolio` `C(6,2)=15` `CombinatorialPurgedCV(purge=20, embargo=20)`): `1x = -19.2405 bps` (`t = -12.0161`), `2x = -44.5154 bps` (`t = -27.7820`), `DSR = 0.0`, `CPCV_pos = 0.0`, symmetric Bailey (2014) `C(6,3)=20` CSCV `PBO = 0.60`.
- **Disposition:** **`FAILED`** -> classified strictly as `PROTECTIVE_FILTER_OR_GOVERNANCE` (`standaloneAlphaClaim: false`, zero standalone alpha promoted). HLZ ledger advances from `103` to `104`; next candidate (`Trial #105`) faces `t*(105) = 4.2084`.

### 4. Live Firewall Preservation

- Running Sovereign Noesis Live `:8798` and Live EXT Guardian `:8796` remained `100%` read-only and untouched throughout `v3.11.0` rollout; any Stage-5 Live daemon reload remains strictly behind an explicit human trust gate.

## Alternatives Considered

- **Claiming `ALPHA_STRATEGY_MINOR` on `v3.11.0` Despite `Trial #104` Failing:** Rejected unconditionally under `ADR-0040` and `sota-quant-research-protocol`; `v3.11.0` is a minor architectural architecture/terminal/kernel/quarantine/alpha-factory release with `trial104StandaloneAlphaClaim = false`.
- **Maintaining Parallel Hand-Rolled Static Pine Tables Alongside OpenBB Workspace:** Rejected under upstream-first zero-reinvention discipline; `/api/pine/live_ranker` is retired with `HTTP 410 Gone`.

## Verification Witness

- `uv run ruff check . && uv run ruff format --check .` (`PASS`).
- `uv run python scripts/architecture_catalog.py --check` (`41/41` MADR 4.0 ADRs valid, `0` drift).
- `uv run python scripts/merge_gate.py` (`PASS`).
- `uv run pytest -q` (umbrella lock + Hypothesis + `v3.11.0` seal assertions `PASS`).
- `gitleaks protect --staged --redact --no-banner` (`0` leaks).
