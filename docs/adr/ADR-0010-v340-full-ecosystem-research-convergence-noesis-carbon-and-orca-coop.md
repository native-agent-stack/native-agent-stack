# ADR-0010: v3.4.0 Full-Ecosystem Research Convergence, Clean `Noesis-Carbon` WSL2 Guest & Lease-Safe Bidirectional Orca Co-op

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

Following `ADR-0009` (`v3.3.0` 7-feed `sota-research-feeds.v2` PIT surface and `85`-trial HLZ ledger), the portable Apple M5 Max (`64 GB`) and stationary `Noesis` Threadripper (`64` logical cores, `128 GB` RAM, RTX 4090 `24 GB`) workstations entered active cooperative execution across all `18` live `native-agent-stack` repositories (`22` total including `4` cold-archived seals). Finalizing `v3.4.0` required:
1. Binding the `424`-entry research-converged catalog (`404` owner-starred + `20` evaluated repositories in `Meridian` `docs/adr/data/ecosystem-manifest.md`) across every tier (`Meridian` `0058`–`0059`, `sota-compounding-lab` `ADR-0007`, `astrolabe` `ADR-0005`, `dsh-plugin-landscape` `ADR-0004`, `sota-harness-foundation` `ADR-0021`/`0024`);
2. Upgrading `sota-workstation` (`v2.0.0`, mirrored onto both Mac M5 Max and `Noesis`) for idle Tailscale UDP tunnel wakeup, `ConPTY`-wrap-proof Base64 co-op messaging (`--inbox`, `--send`, `--sync-refs`), and remote `sota-bus` lease-safe fast-forward synchronization;
3. Resolving the `8` multi-worker (`-n 8`) Linux/WSL2 headless Chromium `requestAnimationFrame` throttling failures on `Meridian` (`PR #9` -> `ce99430fdfa8`) without relaxing any assertion.

## Decision Outcome

1. **Full `424`-Entry Research-Converged ADR Closure (`v3.4.0`):**
   - Lock `Meridian @ ce99430fdfa8` (`56` ADRs, `meridian/research_convergence.py` `ADR-0058` + headless Orca co-op & `-n 8` Chromium unthrottling `ADR-0059`), `sota-compounding-lab @ f252bdb6fdb2` (`7` ADRs, `golang/mod` `dirhash` snapshot locks + `learnharness`/`LoopForge` postmortem distillation + `0` `ty` diagnostics), `astrolabe @ e1023b3e568a` (`5` ADRs, `hftbacktest::RiskAdverseQueueModel` `100x` CTA/UTP round-lot queue parity + `300 msg/min` protective-exit reserve), `dsh-plugin-landscape @ 0703d7504731` (`4` ADRs), and `sota-harness-foundation @ 601f58a4fb70` (explicit Stage B owner cutover guard `stage_b_cutover_authorized`, `PR #6` receipt `#6968908591`).
   - Advance the pre-registered hypothesis ledger to `N >= 88` cumulative trials (`t*(89) >= 4.1709`) and `51` compiled `E1–E4` root-cause lessons.
2. **SOTA Dual-Workstation Orca Co-op Practice (`sota-workstation v2.0.0` + `Noesis-Carbon`):**
   - Enforce hardened headless `orca serve --no-pairing --refuse-public` on stationary `Noesis` alongside clean `Ubuntu 26.04.1` `Noesis-Carbon` WSL2 (`agy 1.5.10`, `uv`, `15` mirrored workflow files) while preserving `sextant`/`D:`/`Z:` Stage A/B boundaries.
   - Wake idle Tailscale direct LAN UDP tunnels via 1-packet ping before WebSocket RPC, exchange `ConPTY`-wrap-proof `@@B64:` co-op payloads between `mac-m5-agy` and `noesis-agy`, and skip `git pull --ff-only` on any locally or remotely leased/dirty repository (`singleActiveBrokerHostOnly: true`).

## Alternatives Considered

1. **Blind `git pull` on remote workstation repositories during active `24/5` guardian leases:** Rejected — risks clobbering in-flight remote worktrees or active `sota-bus` leases (`sota-mover-ranker::agy-noesis-24x5`).
2. **Switch Playwright `wait_for_page` from `requestAnimationFrame` (`polling=None`) to `setTimeout` interval polling in `Meridian`:** Rejected — empirically falsified by `test_a_page_whose_timers_never_fire_fails_the_check` (which stubs `window.setTimeout = () => 0`); solved cleanly via Chromium renderer/timer unthrottling flags and `pytest.mark.xdist_group("chart_browser")` under `--dist loadgroup`.

## Verification Witness

- `Meridian @ ce99430fdfa8`: `56/57` ADRs, `15/15` `-n 8` browser tests (`27.85s`), `220/220` size/tense/tree/manifest checks, `pyright 0/0`, receipt `https://github.com/native-agent-stack/meridian/pull/9#issuecomment-6969139023`.
- `sota-workstation v2.0.0`: `coop --inbox` (`ingestedIntoLocalBus=1`), `sync --repo all` (`18/18` `Noesis` repos synced + `15` workflow files mirrored, `7` locally leased repos safely skipped).
- `scripts/merge_gate.py`: `10/10 MADR 4.0 ADRs, 0 drift, umbrella v3.4.0 PASS`.
