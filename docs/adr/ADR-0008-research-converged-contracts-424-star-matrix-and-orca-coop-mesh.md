# ADR-0008: Research-Converged Contracts (`Canon` `0169..0176` + `Shelf-Lock` `ADR-0004` + `424`-Star Matrix) & Bidirectional Dual-Workstation `agy` Orca Co-op

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

Across the `22`-repository `native-agent-stack` ecosystem, primary quantitative research contracts (`Canon` `0166..0176`, `sota-upstream-shelf-lock` `ADR-0004`, `sota-compounding-lab` `ADR-0006`, `astrolabe` `ADR-0004`, `meridian` `#224` `424`-row starred/unstarred upstream manifest, and `sota-multi-model-workflows` `ADR-0008..0010`) and live dual-workstation Antigravity (`agy`) instances (`Apple M5 Max` portable lead `<->` `Noesis 64c/128GB/RTX4090` stationary heavy) require a single umbrella reference architecture and co-op coordination protocol.

## Decision Outcome

1. **Unified Research-Converged Contract Matrix (`ECOSYSTEM_CONVERGENCE_LOCK.json` `v3.3.0`):**
   - **Data Snapshot & 4-Contract Seam (`Canon 0169–0170`):** `RFC-8493` BagIt manifests + `https://github.com/golang/mod` (`v0.43.0` `d4f320b92664` `sumdb/dirhash`) `h1:<base64(sha256)>` digests + 7-role date map (`pre-2025-11-04` round-lot quotes refused).
   - **Ex-Ante Statistical Power & Queue Realism (`sota-upstream-shelf-lock ADR-0004` × `Canon 0175`):** `https://github.com/ml4t/diagnostic` (`19e76072`, ADIA Lab `#19` Eq. 11 `MinTRL`/`MDE` requiring `distinct_dates >= 60`) + `https://github.com/nkaz001/hftbacktest` (`5f3ec40b`, `RiskAdverseQueueModel` passive L1 queue-depletion simulation) + `https://github.com/skfolio/skfolio` (`CombinatorialPurgedCV`).
   - **Microstructure & PIT Eligibility (`Canon 0171–0174` × `sota-compounding-lab ADR-0006`):** First-detection-only mover entry (`0171`, `ADR-0022 <= 2.00%` stop cap), `https://github.com/massive-com/client-python` (`v2.10.0` `8c2bd1d8d14d`) counts-only PIT delisted-ticker proof + `alpaca-py` `StockBarsRequest.asof` (`0172`), `https://github.com/QuantConnect/Lean` (`e28820c9c846` `RelativeDailyVolume.cs`) cumulative same-time-of-day `RVOL` (`0173`), `<= 8`-symbol/`<= 8h` isolated `BOATS` bounds ahead of `2026-12-06` `23/5` SIP (`0174`), and `7`-feed PIT + non-repainting Pine v6 strategy templates (`ADR-0006`).
   - **424-Row Starred & Evaluated Upstream Registry (`meridian #224`):** Account for all `404` owner-starred + `20` evaluated repositories across Layers `0–11` (`louislam/uptime-kuma` L6 loopback heartbeat, `stablyai/orca` `1.4.261`, `ComposioHQ/agent-orchestrator`, `DeusData/codebase-memory-mcp`, `gastownhall/beads`, `likec4/likec4`, `Nutlope/hallmark`).
2. **Bidirectional Dual-Workstation `agy` Co-op over SOTA Orca (`sota-workstation coop`):**
   - Provision `~/.agents/bus/peer_bus.db`, `~/.agents/bin/sota-bus`, `~/.agents/bin/sota-workstation`, and `~/.agents/workflows/*` on both `Mac M5 Max` and `Noesis` (`100.110.115.22`).
   - Bridge `Mac agy <-> Noesis agy` via E2EE Orca (`sota-workstation coop send|inbox|sync`), `crossStoreLineage` worktrees (`--parent-environment local`), `orca worktree set --comment`, and `orca reference add`, without ever network-mounting SQLite WAL files.
