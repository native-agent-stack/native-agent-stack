# ADR-0047: No Self-Built Anti-Tier-0 Waste, Legacy Monolith Freeze & Hosted SOTA Platform Mandate

- **Status:** Accepted
- **Date:** 2026-11-20
- **Evidence Grade:** E4
- **Supersedes / Extends:** Extends `ADR-0044`, `ADR-0045`, `ADR-0046`, and `sota-upstream-shelf-lock` `ADR-0023`/`ADR-0025`

## Context

A full-landscape workstation audit on `2026-11-20` measured `764,013` Python LOC across `18` repositories (`695,593` LOC split across `7` overlapping trading/sim repos), `574` ADR files, `128` manifests, `20.64 GB` (`558,971` files) of dead already-merged Orca worktrees containing duplicate `~940 MB` `.venv` environments, and two `8,300+`-LOC god-files (`alpaca_paper_e2e.py` `8,399` LOC and `stage5_lossless_live_lane.py` `8,324` LOC).

The audit exposed a core Tier-0 failure mode:
1. **Cosmetic Upstream Labels vs. Real Platform Execution:** `upstream-map.toml` verified that files declared `how = "build-on"`, yet `sota-mover-ranker/.venv` (`Python 3.14` Win32) did not even have `nautilus_trader`, `openbb`, `hftbacktest`, `vectorbt`, `quantstats`, or `perspective` installed. Agents therefore hand-rolled custom order managers, fill reconcilers, backtest loops, HTML/JS dashboards, and 1-bar strategy proxies — self-built waste that directly violated Tier-0 in practice.
2. **Throttling Broken Architecture Instead of Fixing Strategies:** Stacking `0.25x` probation and `0.55x` allocation throttles onto strategies whose live implementation used naive 1-bar proxies and choked winners at `+21 bps` (`0.44x` payoff ratio) left `92%` of Paper cash idle without fixing root expectancy (`0/108` HLZ passed).
3. **Worktree & Venv Sprawl:** Completed Orca worktrees were never pruned after landing on `origin/main`, accumulating `20.64 GB` of dead copies.

## Decision

1. **Zero Self-Built Anti-Tier-0 Waste (Hard Law Across All `7/7` Runtimes & `18/18` Repos):**
   - **Prohibited:** Hand-rolling custom OMS loops, fill reconcilers, backtest runners, custom HTML/JS dashboards, or 1-bar strategy proxies disguised behind cosmetic `upstream-map.toml` labels.
   - **Prohibited:** Masking negative-expectancy strategy bugs with stacked sizing throttles instead of fixing structural features, entries, and exits (or retiring the failing strategy).
2. **Host the Actual Pinned SOTA Upstream Platforms Directly:**
   - **Execution & Backtest Runtime:** Host native `NautilusTrader v2` (`BacktestNode` + `TradingNode` + `OrderEmulator` + native `IBKR` adapter + `nautilus-alpaca`) on unified `Python 3.12` so the exact same `Strategy` subclasses execute in Backtest and Paper/Live (`0%` parity drift).
   - **Hosted Terminal & Dashboard:** Host native `FINOS/OpenBB Workspace` (`openbq-org/finos-workspace` `:1420`) + `openbq-org/backends-for-openbb` (`:6900`) + `FINOS Perspective` WASM + `Lightweight Charts` + `QuantStats` tearsheets — zero custom HTML/JS UIs.
   - **L1 Queue Sim, Sweeps & Data:** Execute native Rust `hftbacktest`, `vectorbt`, `Polars`, `DuckDB`, `skfolio`, `ml4t-diagnostic`, and `edgartools` directly over read-only `Z:/sota-data/prewall-lake` (`<= 2026-10-15`) and RTX 4090 CUDA (`:8794`).
   - **Owned Custom Code Ceiling:** Keep owned domain code strictly to a thin (`<= 5k` LOC target for new hosted stack) plugin layer: whole-market `24/5` SIP/BOATS discovery, authentic structural `Strategy` subclasses (`5m ORB`, `14d Noise-Area`, `Stage-2 VCP`, `SMA200 Daily IBS`, `5d Parabolic Exhaustion Short`), and hard risk/broker firewalls (`ADR-0022 <= 2.00%`, Paper-vs-Live isolation).
3. **Legacy Monolith Freeze & Merged Worktree Waste Gate (`scripts/one_harness_cleanliness_doctor.py` Check `#8`):**
   - Freeze all top `7` legacy monoliths (`stage5_lossless_live_lane.py <= 8330`, `alpaca_paper_e2e.py <= 8405`, `tv_watchlist_fast_sync.py <= 3775`, `paper_p3_aggressive_lab.py <= 3120`, `ipo_microstructure_stream.py <= 3035`, `scanner.py <= 2915`, `paper_auto_engine.py <= 2650`) under strict downward-only ratchet caps.
   - Enforce a workstation merged-worktree waste budget (`<= 4.0 GB` of `CLEAN + ahead=0` Orca worktrees) and require pruning merged worktrees immediately after push.
4. **Propagate Permanently Across All `7/7` Global Runtime `.md` Files & `sota-bus` (`E4`):**
   - Record as `E4` hard lesson `30408a2e8c8938e5` in `peer_bus.db` / `~/.agents/wiki/LESSONS.md`.
   - Sync into `TIER0_CANONICAL_BLOCK` across Gemini/AGY, Claude, Codex, OpenCode, DSH, OMP, and `agy-sota-core` via `scripts/sync_tier0_harness_and_master_adrs.py --apply-global-md`.

## Upstream Evidence & Primary Sources

- NautilusTrader (`BacktestNode` / `TradingNode` / `OrderEmulator`): https://github.com/nautechsystems/nautilus_trader
- FINOS / OpenBB Workspace hosted terminal: https://github.com/openbq-org/finos-workspace
- OpenBB hosted backend (`:6900`): https://github.com/openbq-org/backends-for-openbb
- hftbacktest Rust L1 queue simulator: https://github.com/nkaz001/hftbacktest
- FINOS Perspective WebAssembly blotter: https://github.com/finos/perspective
- TradingView Lightweight Charts: https://github.com/tradingview/lightweight-charts
- Polars & DuckDB columnar lake analytics: https://github.com/pola-rs/polars · https://github.com/duckdb/duckdb
- VectorBT & QuantStats tearsheets: https://github.com/polakowo/vectorbt · https://github.com/ranaroussi/quantstats

## Consequences

- Every agent across all `7` runtimes is explicitly blocked from building self-built anti-Tier-0 custom engines, dashboards, or throttled proxy strategies.
- Legacy god-files are frozen against growth and merged Orca worktree bloat is continuously policed by `one_harness_cleanliness_doctor.py --check`.
- All new trading capability lands directly on the hosted SOTA platforms (`NautilusTrader v2` + `OpenBB/FINOS Workspace` + `hftbacktest` + `Polars`/`DuckDB`) with minimal thin-plugin code.
