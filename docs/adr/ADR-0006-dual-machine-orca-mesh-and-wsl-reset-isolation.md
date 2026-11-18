# ADR-0006: Dual-Machine Portable M5 Max & Stationary Noesis Orca Mesh with Shared-VM WSL2 Isolation

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

The `native-agent-stack` ecosystem operates seamlessly across two physical machines paired over Tailscale and Orca:
1. **Portable Lead Workstation (`local`):** Apple M5 Max (`18` CPU cores, `64 GB` unified RAM, `darwin-arm64`, Orca `v1.4.255`) — carried unplugged/roaming while sustaining full autonomous DuckDB/Polars/CPCV research (`14` threads AC / `8` battery / `4` `<35%` low-battery conservation).
2. **Stationary Heavy Workstation (`100.110.115.22` — `Noesis`):** AMD Threadripper (`64` logical cores, `128 GB` RAM, NVIDIA GeForce RTX 4090 `24 GB`, `win32` + WSL2 `3.0.5.0`, Orca `v1.4.261`) — hosting all `18` active `native-agent-stack` repositories under `C:/sota-workstation/*` alongside WSL2 Linux/CUDA lanes (`meridian` and co-resident `sextant`).

## Decision Outcome

1. **Unified Dual-Machine Placement & Failover (`~/.agents/bin/sota-workstation`, `sota-doctor` `L10`):** Route `interactive_lead` and `heavy_prewall_research` locally to the M5 Max (zero degradation when offline/carried) and offload `combinatorial_gpu_batch` (`56` threads + RTX 4090) and lid-closed parked workers (`terminal.paired-parking.v1` + `crossStoreLineage`) to `Noesis` when docked (`<= 1,500 ms` RTT), failing over automatically to the M5 Max when roaming.
2. **Single-Owner Broker Split-Brain Firewall:** Enforce `singleActiveBrokerHostOnly = true` so at most one machine holds active `PA...` (`<= 200` req/min) or `DU... :4002` (`<= 3,000` msg/min) paper broker execution while real-money live accounts and ports (`4001`, `7496`) remain 100% hard-refused across both hosts.
3. **Shared-VM WSL2 Reset & Gateway Non-Interference (`meridian` `ADR-0053`, `ADR-0055`):** Never execute `wsl --shutdown` or modify co-resident `sextant`, drive `D:`, or recovery drive `Z:` during `meridian` WSL2 distro resets; never expose loopback model gateways (`127.0.0.1:20128`) over Tailscale Serve without password, `REQUIRE_API_KEY=true`, and `/v1`-only tag grants; never route Claude subscription OAuth (`CLAUDE_CODE_OAUTH_TOKEN`) behind a custom gateway.
