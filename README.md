# Native Agent Stack (`v3.6.0`)

Canonical upstream-first ecosystem umbrella, **One-Owner-Per-Layer** convergence lock (`ECOSYSTEM_CONVERGENCE_LOCK.json`), **Three-Substrate Dual-Workstation Mesh** (`Apple M5 Max` + Windows `Noesis` + `* Noesis-Carbon` WSL2 `ext4`), and **5-Stage Quantitative Compounding Governance** across Claude Code (`cc-lead` + `OMC` v2), Antigravity (`AGY 1.5.10` / `Gemini 4 Carbon`), OpenAI Codex (`OMX`), DeepSeek Harness (`dsh`), OpenCode (`OMO`), and Orca (`1.4.261`).

## Two-Tier Organization Architecture (`https://github.com/native-agent-stack` — `22` Repositories)

### 1. Public Open-Core Tier (`9` Repos — Unlimited Free GitHub Actions CI, `40`-Char SHA Pins)
| Repository | Primary Layer Ownership |
|---|---|
| [`.github`](https://github.com/native-agent-stack/.github) | Org control plane, `ECOSYSTEM_ORG_MANIFEST.json` (`22`-repo SHA lock) & reusable SHA-pinned CI gate |
| [`native-agent-stack`](https://github.com/native-agent-stack/native-agent-stack) | Canonical umbrella, single-owner layer bijection & supersession lock (`v3.6.0`, `13` ADRs) |
| [`sota-upstream-shelf-lock`](https://github.com/native-agent-stack/sota-upstream-shelf-lock) | `18` immutable `40`-char Git SHA upstream library pins & `RiskAdverseQueueModel` L1 parity |
| [`sota-harness-foundation`](https://github.com/native-agent-stack/sota-harness-foundation) | Open-core `28`-runtime foundation, `27` MADR 4.0 ADRs & `Hypothesis` stateful fuzzing |
| [`agy-sota-harness`](https://github.com/native-agent-stack/agy-sota-harness) | Antigravity `L0-L12` harness (`19` ADRs), `5/5` native workflows, pre-wall studies & `13/13` probes |
| [`dsh-sota-harness`](https://github.com/native-agent-stack/dsh-sota-harness) | DeepSeek Harness `10`-layer probe suite & cross-peer MCP triad |
| [`sota-multi-model-workflows`](https://github.com/native-agent-stack/sota-multi-model-workflows) | `14` canonical multi-model workflows, `sota-cc-hub` (`15/15` worker fleet) & SQLite WAL peer bus |
| [`sota-compounding-lab`](https://github.com/native-agent-stack/sota-compounding-lab) | 5-stage `Sim -> Pre-Wall -> Paper -> Empirical-Bayes -> SHA-256 Broker Manifest` engine + `sota-org-doctor` |
| [`astrolabe`](https://github.com/native-agent-stack/astrolabe) | Stage-3B IBKR `:4002` (`DU...` paper-only) NautilusTrader execution engine |

### 2. Private Proprietary Execution, Simulation & Vault Tier (`9` Active Repos — `actions_enabled=false`, `0` Paid Quota Burn)
- `sota-mover-ranker` (Stage-3A `3.0s` SIP+BOATS radar, 50/50 Core+Runner protection & `<= 200 req/min` Alpaca paper auto-trader on `:8787`)
- `sota-dynamic-trail-c` (Stage-5A `24/5` sub-50ms Dual-Tranche trailing guardian & closed-bar Pine v6 webhook bridge on `:8799`)
- `sota-private-vault` (Stage-5B `89`-trial HLZ ledger `t*(90)=4.1735`, `52` `E1-E4` lessons, Empirical-Bayes priors & Stage-B `2.85 TB` receipts)
- `cc-sota-harness` (`L5` Claude-Lead `25`-ADR harness, `sota-workstation v2.1.0` & tick microstructure pre-wall studies)
- `meridian` (Stage-1 NautilusTrader `v2.0.0rc9` queue-fill parity simulation & `56`-ADR host/Stage-B governance)
- `canon` (`150`-ADR deterministic causal research & evaluation engine)
- `tsl`, `trading-sota`, `dsh-plugin-landscape` (Private PIT strategy lab, `4` canonical strategy templates & upstream plugin references)

### 3. Cold-Archived Superseded Tier (`4` Frozen `PRIVATE` Repos — `archived=true`, `actions_enabled=false`)
- `legacy-agent-stack-202610`: Historical Sep-Oct 2026 WSL/`jcodemunch`/OmniRoute commits & PRs `#1-#1272` in cold storage (`0` cron churn).
- `ecosystem-records`: Static October 2026 continuity archive superseded by `sota-private-vault`.
- `legacy-edge-202611` & `legacy-movers-202611`: Pre-org prototypes harvested into `sota-compounding-lab`, `sota-mover-ranker`, and `sota-dynamic-trail-c`.

## Deterministic Verification

```bash
uv sync --locked --extra dev
uv run python scripts/merge_gate.py
```
