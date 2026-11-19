# ADR-0036: `v3.10.9` Stationary `Noesis` RTX 4090 GPU-First Compute, Win32 Job-Object MCP Isolation & Workstation SOTA Tune

- **Status:** Accepted
- **Date:** 2026-11-19
- **Layer:** Stationary `Noesis` Workstation Performance, `RTX 4090` CUDA (`13.2`) + RAPIDS `cudf-polars` Offload, Win32 Subprocess Hygiene & Dual-Surface Resource Governance (`L5` × `L6` × `L8` × `L10`)
- **Evidence Grade:** E4 (`sota-mover-ranker@40845ddd` `ADR-0047`, `sota-compounding-lab@a35aa821` `ADR-0022`, `native-agent-stack` `scripts/tune-noesis-os-elevated.ps1`, `36/36` MADR 4.0 ADRs, `noesis_rtx4090_sota_tune_benchmark.json` `sha256=b97abeb35974591f`, `merge_gate.py` + `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-compounding-lab, https://github.com/alpacahq/alpaca-mcp-server
- **Revisit Trigger:** Next planned `Noesis` reboot (activating rebalanced `.wslconfig` & elevated OS settings) or promotion of GPU-scored signals in `sota-mover-ranker` `:8787`

## Context and Problem Statement

Full-stack profiling on Stationary Workstation `Noesis` (`AMD Ryzen Threadripper PRO 5975WX 32c/64t`, `128 GB RAM`, `NVIDIA GeForce RTX 4090 24 GB`, Win32 + `Noesis-Carbon` WSL2) identified four systemic bottlenecks:
1. **Win32 `mise` Shim Orphan Leak & Priority Inversion:** Invoking `alpaca-mcp-server==2.4.1` via `mise\shims\uvx.exe` spawned a 6+ process chain whose descendants leaked on `proc.kill()` or shim exit (`561` stranded processes, `~12.8 GB` RAM, `~15–25%` CPU churn), while Task-Scheduler-launched trading daemons (`:8787`, `:8799`, `:4002`) ran at `BelowNormal` CPU priority behind browsers and Windows Defender.
2. **Idle `RTX 4090` (`0%` CUDA Compute) & 9P Lake Latency:** Pre-wall research (`sota-compounding-lab`) crossed WSL2 9P (`/mnt/z`) on every Parquet scan, trained `C(6,2)=15` CPCV MLP folds sequentially, and lacked Python `3.12` RAPIDS `cudf-polars`, `CuPy`, and `ONNX Runtime GPU` wheels.
3. **Missing Cross-OS Win32 -> WSL2 GPU Inference Bridge:** Win32 `sota-mover-ranker` (`:8787`) had no low-latency loopback path to execute parallel scoring on `Noesis-Carbon`'s RTX 4090.
4. **Unbalanced `.wslconfig` (`104 GB` / `64` vCPUs) & Elevated OS Debt:** WSL2 could starve Win32 live trading memory, while HAGS (`HwSchMode`), Defender path exclusions, and `Error`-state virtual display cleanup required an explicit owner UAC trust-gate script.

## Decision Outcome

1. **Win32 MCP Process-Tree Isolation, Direct Binary & `AboveNormal` Trading Priorities (`sota-mover-ranker@40845ddd`, `ADR-0047`):**
   - Pre-installed `alpaca-mcp-server==2.4.1` directly via `uv tool install`, rewired `resolve_uvx_bin()` / `resolve_alpaca_mcp_command()` to skip `mise` shims while honoring unit-test monkeypatches, and bound all MCP children (`P2`, `P3`, `L5`) to kernel `Win32ProcessTreeJob` (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000`) + `terminate_process_tree()`.
   - Promoted all active trading daemons (`:8787`, `:8799`, `:4002`, `ipo_microstructure_stream`) from `BelowNormal` to `AboveNormal`, reaped dead-parent MCP orphans, and trimmed idle `git fsmonitor--daemon` workers (`52 -> 37`).
2. **Full `Noesis-Carbon` `.venv-gpu-py312` CUDA Stack, `/dev/shm` Lake & `:8794` Mirrored GPU Sidecar (`sota-compounding-lab@a35aa821`, `ADR-0022`):**
   - Provisioned `.venv-gpu-py312` (`Python 3.12.16`, `torch 2.15.0+cu132`, `cudf-polars-cu12 26.10.2`, `cupy-cuda12x 14.2.0`, `onnxruntime-gpu 1.32.0`, `triton 3.9.0`, `xgboost 3.4.1`, `optuna 5.1.0`) while restoring `.venv` `polars==2.1.0`.
   - Synced the pre-wall lake (`1,229.28 MB`, SHA-256 verified) to native `ext4` and `/dev/shm/prewall-lake`, started resident `:8794` RTX 4090 scoring sidecar, and verified empirical gains: `df10` Parquet scan improved `3.20x` (`674.6 ms` 9P -> `210.5 ms` `/dev/shm`), `15`-fold CPCV MLP improved `18.88x` (`4,293.64 ms` CPU serial -> `227.46 ms` RTX 4090 batched `TF32`/`BF16`), and cross-OS Win32 -> `:8794` 500-symbol scoring completed in `2.426 ms` GPU compute (`20.83 ms` loopback RTT), while confirming small `500`-obs bootstraps stay faster on CPU (`15.24 ms` vs `183.82 ms` cold GPU).
3. **Non-Disruptive `.wslconfig` Rebalance & Owner UAC Trust-Gate Script (`scripts/tune-noesis-os-elevated.ps1`):**
   - Rebalanced `.wslconfig` (`memory=72GB`, `processors=52`, `autoMemoryReclaim=gradual`; zero `wsl --shutdown`) so Win32 retains `56 GB` / `12` hardware threads.
   - Shipped `-DryRun`-by-default `scripts/tune-noesis-os-elevated.ps1` (`EXPLICIT_HUMAN_TRUST_GATE`) for one-click elevated Defender exclusions, `HwSchMode=2` HAGS, and `Error`-state virtual display cleanup.

## Alternatives Considered

- **Forcing Every Micro-Operation onto CUDA (`cudf-polars` Cold Single-Pass / Small Bootstraps):** Rejected based on empirical benchmarks (`1,011.49 ms` cold `cudf-polars` vs `210.50 ms` Polars `/dev/shm` CPU; `183.82 ms` vs `15.24 ms` for 500-obs bootstrap); workload routing uses RTX 4090 where batched parallelism yields real speedups (`18.88x` CPCV, `2.4 ms` 500-symbol batch scoring) and 64-thread CPU + `/dev/shm` where low overhead dominates.

## Verification Witness

- `sota-mover-ranker@40845ddd`: `36 passed`, `architecture_catalog.py --check` (`47/47`), `merge_gate.py` (`PASS`), `gitleaks` (`0` leaks), live Win32 -> `:8794` 500-symbol GPU roundtrip (`ok=True`, `device="cuda:0"`).
- `sota-compounding-lab@a35aa821`: `84 passed` (Win32) + `5 passed` (`.venv-gpu-py312` CUDA), `22/22` ADRs, `org_visibility_doctor.py` (`PASS`), `gitleaks` (`0` leaks).
- `native-agent-stack`: `uv run python scripts/merge_gate.py` (`36/36` MADR 4.0 ADRs, `umbrella --check`, `ruff`, `ty`, `pytest`) + `gitleaks git --staged --no-banner` (`0` leaks).
