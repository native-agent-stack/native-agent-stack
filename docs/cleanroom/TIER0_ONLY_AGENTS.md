# SOTA Tier-0 Only Agent Instructions (`AGENTS.md` / `GEMINI.md` — Clean-Room `v4.0` Draft)

> **ONE RULE ONLY:** Never self-build ever again. Every single line of code, backtest platform, strategy, trading engine, UI, harness, hook, skill, and ADR MUST **install, integrate, or build thinly upon** a live-verified, SPDX-licensed, SHA-pinned SOTA upstream repository (`<= 5,000` LOC total native glue across the entire ecosystem). Anything self-built outside a hosted upstream platform is rejected fail-closed.

---

## 1. The Single Tier-0 Law (Fail-Closed Across Every Layer)

1. **Upstream-Only & Zero Paper Self-Invention Mandate (`ADR-0023` / `ADR-0047` / `ADR-0049` / `ADR-0050`):**
   - **FORBIDDEN:** Hand-rolled OMS loops, custom fill reconcilers, custom backtesters, empty `BacktestEngine.run()` stubs, custom HTML/JS dashboards, 1-bar strategy proxies, throttle band-aids on negative-expectancy logic, unlicensed (`NONE`) / archived / unverified repos, or self-inventing/hand-coding algorithms, indicators, models, or strategies from scratch "based on papers."
   - **REQUIRED:** Cleanly install and host the real pinned SOTA upstream frameworks, platforms, and official/verified paper reference repositories directly, configured with related installed paper packages and tested end-to-end (E2E) on pre-wall historical data (`<= 2026-10-15`), writing only a thin typed plugin/adapter layer (`upstream-map.toml` + `40`-char SHA in `PINS_LOCK.json` + GitHub-evidenced MADR 4.0 ADR + `scripts/merge_gate.py` + universal `core.hooksPath`).
2. **Full-Resolution, Zero-Fallback Mandate (`ADR-0025` / `ADR-0038`):**
   - `allow_silent_fallback = False`, `0` residual stubs, real `NautilusTrader v2` instruments + data + `Strategy` (`iterations > 0`), real Rust `hftbacktest` `HashMapMarketDepthBacktest` + `RiskAdverseQueueModel`, RTX 4090 `cuda:0` (`require_gpu=True`), and strict pre-wall `<= 2026-10-15` isolation (`post_wall_n == 0`).
3. **Research-Convergence-First Mandate (`S1`–`S8`):**
   - Every trading hypothesis is pre-registered with SHA-256 (`sota-bus preregister`) **before** OOS lookup, clamped strictly to trade date (`date_window` pattern), validated with `Qlib v0.9.8` (`REG_US` `1m`) -> `NautilusTrader` `BacktestNode` -> `hftbacktest` `RiskAdverseQueueModel` -> `skfolio` `C(6,2)=15` CPCV + `ml4t-diagnostic` DSR/MinTRL + `FINSABER` leakage/cost gate + HLZ `t*(N+1)` + `1x/2x` sqrt-impact stress + date-clustered HAC SEs. Zero fabricated passes.
4. **Core Trading Philosophy (Whole-Market Norm-Disruption Early-Entry + Reversal Flip SAR):**
   - Continuously scan the whole US market (`DF1`–`DF12` PIT feeds) for per-symbol statistical norm disruptions (early-window volume/range/OFI/catalyst shocks); enter early with `<= 2.00%` hard stop (`ADR-0022`) and **when reversal confirms, atomically flatten and flip into the inverse direction (long ↔ short SAR)** — implemented strictly as a thin `NautilusTrader` `Strategy` + `VectorBT` (`upon_opposite_entry="reverse"`) + `hftbacktest` queue-verified plugin, never as a self-built loop.

---

## 2. Clean-Room `v4.0` Hosted SOTA Ecosystem (`4` Repos Replacing the Retired `18`-Repo Sprawl)

| Clean-Room Repo | Replaces (Retired Legacy) | Hosted Upstream SOTA Platforms (Installed / Integrated — NEVER Self-Built) |
| :--- | :--- | :--- |
| **`sota-shelf-and-harness`** | `native-agent-stack`, `sota-upstream-shelf-lock`, `sota-harness-foundation`, `sota-multi-model-workflows`, `agy/cc/dsh` harnesses, `dot-github` | `stablyai/orca` (worktrees + automations), `oh-my-claudecode`, `oh-my-codex`, `oh-my-openagent`, `deepseek-harness`, `hcom`, `beads`, `NVIDIA/SkillEvaluator`, `Claude-BugHunter`, `gitleaks`, `microsoft/SkillOpt`, `stanfordnlp/dspy`, `anthropics/financial-services` · **Single consolidated `docs/adr/`** + `19`-pin `PINS_LOCK.json` |
| **`sota-research-engine`** | `sota-compounding-lab`, `meridian`, `canon`, `tsl`, `trading-sota` | **Data:** `polars`, `duckdb`, `pandera`, `edgartools` (built-in zero-key MCP), `exchange_calendars`, `databento` PIT · **Research:** `microsoft/qlib@v0.9.8` (`MIT`, `REG_US` `1m`), `vectorbt`, `PriorLabs/TabPFN`, `shiyu-coder/Kronos`, `aliyun/qwen-dianjin`, `Chronos-2`, `MOIRAI-2` · **Sim:** `nautilus_trader` `BacktestNode`, `hftbacktest` `RiskAdverseQueueModel`, `microsoft/MarS`, `peernagy/LOBS5` · **Falsification:** `skfolio`, `ml4t-diagnostic`, `FINSABER` (eval-only), `statsmodels`, `arch`, `dowhy`, `river` (CUSUM), `MAPIE`, `quantstats` |
| **`sota-trading-node`** | `sota-mover-ranker` (`162k` LOC monolith), `sota-dynamic-trail-c`, `astrolabe` | **Engine:** `nautilus_trader` `TradingNode` + `nautilus-alpaca` + `ib_async` (`:4002`) + hardened `alpaca-mcp-server` (`ALPACA_PAPER_TRADE=true` & data-only `ALPACA_TOOLSETS`) + watch `nautechsystems/nautilus_agents` (`380ae38`) · **UI:** `openbq-org/finos-workspace` (`:1420`) + `openbq-org/OpenBB` + `backends-for-openbb` (`:6900`) + `finos/perspective` + `lightweight-charts` |
| **`sota-private-vault`** | *(Retained, private, `actions_enabled=false`)* | Verbatim single-repo ADR archive, pre-registered HLZ ledger, `REAL_BROKER_ONLY` `kappa=40` Empirical-Bayes priors, `sota-bus` continuity (`0` secrets, `0` USD balances) |

---

## 3. Hard Non-Negotiable Safety & Workstation Firewalls

- **Paper-Only & Broker Firewall (`ADR-0005` / `ADR-0022`):** Live endpoints (`api.alpaca.markets`, IBKR `:4001`/`:7496`, `:8798`, `:8796`) are 100% hard-refused. `alpaca-mcp-server` MUST set `ALPACA_PAPER_TRADE=true` AND data-only `ALPACA_TOOLSETS=assets,stock-data,crypto-data,options-data,corporate-actions,news,fixed-income-data` (`server.py:117` live-fallback hazard!). Hard initial stop `<= 2.00%`; `singleActiveBrokerHostOnly = true` (Noesis primary, M5 Max failover).
- **Quarantined Upstream Hazards (NEVER Run Unsandboxed or Vendor):** `RD-Agent v1.0.0` runs unsandboxed host shell (`factor.py:165`) with zero multiplicity control — do not run as shipped; `Vibe-Trading`, `mcp-polymarket` (`place-order.ts`), and `FINSABER` vendored `finrl` must NEVER receive broker keys; unlicensed (`NONE`), archived, and `GPL-3.0` repos are quarantined.
- **Host & Storage Boundaries:** `Noesis` RTX 4090 CUDA (`:8794`) + `Noesis-Carbon` `native_ext4` (`~/sota-data-ext4/prewall-lake`) + Disk `Z:` caches (`UV_LINK_MODE=hardlink`). NEVER run `wsl --shutdown`, NEVER touch `sextant`, Drive `D:`/`F:`, `Z:/meridian-data/handoff-2026-11-17/`, `.env`/secrets, or mutate `~/Documents/upstream/` without an explicit shelf-pin ADR.
- **Zero-Bypass Verification:** Commit as `seathatflowsinourveins <234074349+seathatflowsinourveins@users.noreply.github.com>`; universal `core.hooksPath` enforces `gitleaks` + 3-OS zero-leak + `scripts/merge_gate.py`; `one_harness_cleanliness_doctor.py --check` (`10/10 PASS`) certifies the ecosystem. Active models only: `claude-fable-5-2` / `opus-5-5` / `sonnet-5-5`, `gpt-6.2-astra` / `sol`, `gemini-4-neon/carbon/hydrogen/argon`, `deepseek-flash` (zero retired/stale/`kimi` models).
