# Native Agent Stack (`v3.0.0`)

Canonical upstream-first ecosystem umbrella, **One-Owner-Per-Layer** convergence lock (`ECOSYSTEM_CONVERGENCE_LOCK.json`), and **5-Stage Quantitative Compounding Governance** across Antigravity (`AGY 2.0`), Claude Code (`cc-sota-harness`), OpenAI Codex, DeepSeek Harness (`dsh`), and Orca (`1.4.255+`).

## Two-Tier Organization Architecture (`https://github.com/native-agent-stack`)

### 1. Public Open-Core Tier (`9` Repos — Unlimited Free GitHub Actions CI, `40`-Char SHA Pins)
| Repository | Primary Layer Ownership |
|---|---|
| [`.github`](https://github.com/native-agent-stack/.github) | Org control plane, `ECOSYSTEM_ORG_MANIFEST.json` & reusable SHA-pinned CI gate |
| [`native-agent-stack`](https://github.com/native-agent-stack/native-agent-stack) | Canonical umbrella, single-owner layer bijection & supersession lock (`v3.0.0`) |
| [`sota-upstream-shelf-lock`](https://github.com/native-agent-stack/sota-upstream-shelf-lock) | `18` immutable `40`-char Git SHA upstream library pins |
| [`sota-harness-foundation`](https://github.com/native-agent-stack/sota-harness-foundation) | Open-core multi-runtime foundation & `Hypothesis` stateful fuzzing |
| [`agy-sota-harness`](https://github.com/native-agent-stack/agy-sota-harness) | Antigravity `L0-L12` harness, pre-wall DuckDB/Polars studies (`H02/H04/H06`) & `13/13` probes |
| [`dsh-sota-harness`](https://github.com/native-agent-stack/dsh-sota-harness) | DeepSeek Harness `10`-layer probe suite & cross-peer MCP triad |
| [`sota-multi-model-workflows`](https://github.com/native-agent-stack/sota-multi-model-workflows) | `9` self-bootstrapping multi-model workflows & SQLite WAL peer bus |
| [`sota-compounding-lab`](https://github.com/native-agent-stack/sota-compounding-lab) | 5-stage `Sim -> Pre-Wall -> Paper -> Empirical-Bayes -> SHA-256 Broker Manifest` engine + `sota-org-doctor` |
| [`astrolabe`](https://github.com/native-agent-stack/astrolabe) | Stage-3B IBKR `:4002` (`DU...` paper-only) NautilusTrader execution engine |

### 2. Private Proprietary Execution, Simulation & Vault Tier (`9` Active Repos — `actions_enabled=false`, `0` Paid Quota Burn)
- `sota-mover-ranker` (Stage-3A `3.0s` SIP+BOATS radar + `<= 200 req/min` Alpaca / `3,000 msg/min` IBKR paper auto-trader)
- `sota-dynamic-trail-c` (Stage-5A `24/5` sub-50ms Dual-Tranche trailing guardian on `:8799`)
- `sota-private-vault` (Stage-5B `82`-trial HLZ ledger, `E1-E4` lessons, Empirical-Bayes priors & broker promotion manifest)
- `cc-sota-harness` (`L5` 27-runtime lead harness & `H05` tick microstructure pre-wall study)
- `meridian` (Stage-1 NautilusTrader `v2.0.0rc9` queue-fill parity simulation)
- `canon` (Stage-2 deterministic causal research & evaluation engine)
- `tsl`, `trading-sota`, `dsh-plugin-landscape` (Private PIT strategy lab & upstream plugin references)

### 3. Cold-Archived Superseded Tier (`2` Frozen `PRIVATE` Repos — `archived=true`, `actions_enabled=false`)
- `legacy-agent-stack-202610`: Preserves historical Sep–Oct 2026 WSL/`jcodemunch`/OmniRoute commits & PRs `#1-#1272` in cold storage with zero cron churn and zero `312 MB` packfile bloat in active clones.
- `ecosystem-records`: Static October 2026 continuity archive superseded by `sota-private-vault`.

## Deterministic Verification

```bash
uv sync --locked --extra dev
uv run python scripts/merge_gate.py
```
