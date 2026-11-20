# Native Agent Stack (`v3.12.0`)

Canonical upstream-first ecosystem umbrella, **One-Owner-Per-Layer** convergence lock (`ECOSYSTEM_CONVERGENCE_LOCK.json`), **Three-Substrate Dual-Workstation Mesh** (`Apple M5 Max` + Windows `Noesis` + `* Noesis-Carbon` WSL2 `ext4`), and **5-Stage Quantitative Compounding Governance** across Claude Code (`cc-lead` + `OMC` v2), Antigravity (`Gemini 4 Neon` / `Carbon`), OpenAI Codex (`OMX` `gpt-6.2-astra`/`sol`), DeepSeek Harness (`dsh` `deepseek-flash`), OpenCode (`OMO` `claude-sonnet-5-5`), Pi/OMP (`@worker`), Muse, and Dual-Machine Orca.

## Two-Tier Organization Architecture (`https://github.com/native-agent-stack` — `22` Repositories)

### 1. Public Open-Core Tier (`9` Repos — Unlimited Free GitHub Actions CI, `40`-Char SHA Pins)
| Repository | Primary Layer Ownership |
|---|---|
| [`.github`](https://github.com/native-agent-stack/.github) | Org control plane, `ECOSYSTEM_ORG_MANIFEST.json` (`22`-repo `v3.12.0` SHA lock) & reusable SHA-pinned CI gate (`39` ADRs) |
| [`native-agent-stack`](https://github.com/native-agent-stack/native-agent-stack) | Canonical umbrella, single-owner layer bijection & supersession lock (`v3.12.0`, `43` ADRs) |
| [`sota-upstream-shelf-lock`](https://github.com/native-agent-stack/sota-upstream-shelf-lock) | `18` immutable `40`-char Git SHA core pins preserved, `QUALITY_AND_SOTA_ONLY_NO_LICENSE_EXCLUSION`, `108` Wave-1/2 elite stars, `39` Nautilus Rust + `29` LWC plugins & `RiskAdverseQueueModel` (`22` ADRs) |
| [`sota-harness-foundation`](https://github.com/native-agent-stack/sota-harness-foundation) | Open-core multi-runtime foundation, `45` MADR 4.0 ADRs, TradingView 14-library/5-layout/1,000 rpm contract, Tier-3 Full-Manifest Red-Team/SkillEvaluator & `Hypothesis` stateful fuzzing |
| [`agy-sota-harness`](https://github.com/native-agent-stack/agy-sota-harness) | Antigravity `L0-L13` harness (`36` ADRs), TV 14-library/5-layout/1,000 rpm red-team verifier, `10` native workflows & `13/13` probes |
| [`dsh-sota-harness`](https://github.com/native-agent-stack/dsh-sota-harness) | DeepSeek Harness `10`-layer probe suite (`16` ADRs), `4`-server MCP parity & DSH `PreToolUse` firewall |
| [`sota-multi-model-workflows`](https://github.com/native-agent-stack/sota-multi-model-workflows) | `21` canonical multi-model workflows, `60` canonical skills, `sota-cc-hub` (`16/16` core binary fleet), Post-ANT `sota.strategy-contract.v2` parity (`36` ADRs) & SQLite WAL peer bus |
| [`sota-compounding-lab`](https://github.com/native-agent-stack/sota-compounding-lab) | 5-stage `Sim -> Pre-Wall -> Paper -> Empirical-Bayes -> SHA-256 Broker Manifest` engine, Hansen SPA/MCS + Conformal PID + `W1..W5` playback manifest + `Trial #104/#105` Pre-Wall empirical receipts (`32` ADRs) & `sota-org-doctor` |
| [`astrolabe`](https://github.com/native-agent-stack/astrolabe) | Stage-3B IBKR `:4002` (`DU...` paper-only, `3,000/min`) NautilusTrader execution engine with Post-ANT `LosslessProtectionKernel` & exact `Fraction` wire parity (`16` ADRs) |

### 2. Private Proprietary Execution, Simulation & Vault Tier (`9` Active Repos — `actions_enabled=false`, `0` Paid Quota Burn)
- `sota-mover-ranker` (Stage-3A/5 `3.0s` SIP+BOATS radar, Post-ANT 6-pillar `DF1..DF12` merit engine, `OpenBB Workspace` `:6900` KeepAlive + 8 widgets & 5-layout seamless import, TV quota lockdown (`00:00 UTC` latch), `1,000 RPM` anti-adverse TTL + Fixed-Share Hedge + Conformal PID + clean `W5` cohort, `IBKR :4002` `4/4` Paper + `IBC v3.24.2`, fail-closed Stage-5 elevated reload guard, `75` ADRs)
- `sota-dynamic-trail-c` (Stage-5A `24/5` sub-50ms Dual-Tranche trailing guardian, Post-ANT dynamic merit hydration, crossed-NBBO/Rule-612 hardening, shared `LosslessProtectionKernel` & `DataFeed.BOATS` parity on `:8799`, `30` ADRs)
- `sota-private-vault` (Stage-5B `105`-trial HLZ ledger `t*(106)=4.2105`, `286+` `E1-E4` lessons, `ADR-0064` quarantine parity & scrubbed promotion vault, `26` ADRs)
- `cc-sota-harness` (`L5` Claude-Lead `43`-ADR harness, `8`-runtime upstream firewalls, `6/6` 3-surface doctor, `sota-workstation` & tick microstructure pre-wall studies)
- `meridian` (Stage-1 NautilusTrader `v2.0.0rc9` queue-fill parity simulation & `62`-ADR host/Stage-B governance)
- `canon` (`161`-ADR deterministic causal research & evaluation engine)
- `tsl`, `trading-sota`, `dsh-plugin-landscape` (Private PIT strategy lab `27` ADRs, `4` canonical strategy templates & upstream plugin references)

### 3. Cold-Archived Superseded Tier (`4` Frozen `PRIVATE` Repos — `archived=true`, `actions_enabled=false`)
- `legacy-agent-stack-202610`: Historical Sep-Oct 2026 WSL/`jcodemunch`/OmniRoute commits & PRs `#1-#1272` in cold storage (`0` cron churn).
- `ecosystem-records`: Static October 2026 continuity archive superseded by `sota-private-vault`.
- `legacy-edge-202611` & `legacy-movers-202611`: Pre-org prototypes harvested into `sota-compounding-lab`, `sota-mover-ranker`, and `sota-dynamic-trail-c`.

## Deterministic Verification

```bash
uv sync --locked --extra dev
uv run python scripts/merge_gate.py
```
