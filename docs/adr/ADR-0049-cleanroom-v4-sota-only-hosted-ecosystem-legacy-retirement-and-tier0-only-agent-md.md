# ADR-0049: Clean-Room `v4.0` SOTA-Only Hosted Ecosystem Blueprint, Legacy `18`-Repo Self-Built Retirement, Inspector Security Corrections & Tier-0-Only `AGENTS.md` / `GEMINI.md` Standard

- **Status:** Accepted
- **Date:** 2026-11-20
- **Evidence Grade:** E4 (Converges BOTH the 7-agent Claude inspect-only audit in `Z:/sota-cache/llm-native-eval/` AND the 36-repo live `gh api` + 8-repo shallow inspect-only security audit in `Z:/sota-cache/llm-native-eval-pass2/`; live pre-wall `Trial #108` `ADR-0068` `NautilusTrader`+`hftbacktest` Norm-Disruption SAR evidence; live Paper `P1–P3` & `P3-SAR :8795` telemetry; `one_harness_cleanliness_doctor.py` `10/10 PASS`; `scripts/merge_gate.py PASS`; `gitleaks 0`)
- **Supersedes / Retires:** Formally marks the legacy `18`-repo self-built sprawl (`162,763`-LOC `sota-mover-ranker` monolith, hand-rolled OMS/fill loops, custom HTML/JS HUDs, fragmented 18-repo ADRs, and bloated multi-hundred-line runtime `.md` files) as **`RETIRING_TO_CLEANROOM_V4`** upon cutover to the 4-repo hosted-SOTA architecture below.

## Context

Two independent, primary-source repository inspections completed on `2026-11-20` converged on the exact same root diagnosis:

1. **Self-Built Anti-Tier-0 Sprawl Must Retire:** Over rapid multi-wave iteration, the legacy `18`-repo stack accumulated `162k+` LOC in `sota-mover-ranker` (`8,399`-line `alpaca_paper_e2e.py`, `8,324`-line `stage5_lossless_live_lane.py`), custom HTML/JS HUDs, bespoke reconcilers, and bloated `36.5 KB` instruction files — violating the core Tier-0 principle that **every single line must install, integrate, or build thinly upon pinned SOTA upstream platforms**.
2. **Primary-Source Inspection Corrections (`Z:/sota-cache/llm-native-eval/` & `llm-native-eval-pass2/`):**
   - **`microsoft/qlib@v0.9.8` (`MIT`, `5435523`):** **USABLE NOW** for `REG_US` `1`-minute bar factor research; zero order-routing code; `tsl` and `trading-sota` already import it. Recommended candidate for promotion to `PINS_LOCK.json` (`19`th core pin) upon owner confirmation.
   - **`alpacahq/alpaca-mcp-server@v2.4.1` (`MIT`):** **CRITICAL SECURITY CORRECTION (`server.py:117`):** Leaving `ALPACA_TOOLSETS` unset exposes all order-placement tools by default, and **any `ALPACA_PAPER_TRADE` value other than `true`, `1`, or `yes` selects the LIVE endpoint**. Safe data-only deployment MUST enforce `ALPACA_PAPER_TRADE=true` AND `ALPACA_TOOLSETS=assets,stock-data,crypto-data,options-data,corporate-actions,news,fixed-income-data`.
   - **`microsoft/RD-Agent@v1.0.0` (`MIT`, `484776c`):** **DO NOT RUN AS SHIPPED:** Defaults to CSI 300 daily bars (`2017–2020`), executes LLM-written code via unsandboxed host shell subprocess (`factor.py:165`), defaults model step to `conda`, and lacks multiple-testing (`HLZ`) accounting. Only its Co-STEER methodology is adopted inside an isolated sandbox + HLZ/CPCV harness.
   - **`TauricResearch/TradingAgents@v0.7.1` (`Apache-2.0`, `c454491`):** Reference only (daily data, non-repeatable LLM outputs); **copy strictly its trade-date clamping pattern (`tradingagents/dataflows/date_window.py:79`)** rather than adopting the LangGraph wrapper.
   - **`virattt/ai-hedge-fund@v2.7.2` (`MIT`, `5c553b5`):** Reference only (tied to paid Financial Datasets API / local mock book).
   - **`openbq-org/OpenBB` (`bbf1ab2` / `f0f1852b96`):** Official active OpenBQ continuation (`75.6k` stars, includes built-in MCP server package); host alongside `openbq-org/finos-workspace` (`:1420`) and `backends-for-openbb` (`:6900`).
   - **`nautechsystems/nautilus_agents@0.2.0` (`LGPL-3.0`, `380ae38`):** Pure Rust SDK (`0` order-path code, `0` API keys), early alpha (`1` proposal type) — **WATCH** for native `NautilusTrader` agent integration.
   - **Pass-2 Source-Verified Frontier Clearances & Quarantines (`shelf-lock ADR-0026` / `ADR-0048`):** Cleared `anthropics/financial-services` (`Apache-2.0`, `0` order code), `waylonli/FINSABER` (`Apache-2.0`, eval-only), `microsoft/MarS` (`MIT`), `peernagy/LOBS5` (`MIT`), `AI4Finance-Foundation/FinRobot` (`Apache-2.0`), `aliyun/qwen-dianjin` (`MIT`, `0` order code), `The-FinAI/Fino1` & `FinBen` (`MIT`), `PriorLabs/TabPFN` (`Apache-2.0`), `Chronos-2` (`Apache-2.0`), `MOIRAI-2` (`Apache-2.0`), `online-ml/river` (`BSD-3-Clause`), `MAPIE` (`BSD-3-Clause`), `py-why/dowhy` (`MIT`), `massive-com/mcp_massive` (`MIT`, `0` order code), `BrainDAO/mcp-polymarket` (`MIT`, read-only zero private key), `FreedomIntelligence/TwinMarket` (`MIT`), `shiyu-coder/Kronos` (`MIT`), and `dgunning/edgartools` built-in zero-key MCP; quarantined all unlicensed (`NONE`), archived, and `GPL-3.0` repos plus broker-routing code in `HKUDS/Vibe-Trading`.
3. **Real Pre-Wall Sim & Live Paper Norm-Disruption SAR Evidence (`2026-11-20`):**
   - **Pre-Wall Full-Res Sim (`Trial #108`, `ADR-0068`, `NautilusTrader v2.0.0rc9` + `hftbacktest==2.4.4` `RiskAdverseQueueModel`, `75` XNYS sessions `2026-07-01..2026-10-15`, `24` symbols):** `NT_15M_MAKER_CATALYST_SAR` (1x) produced `857` trades, `148` atomic reversal flips, `48.07%` WR, `+5.971 bps/day` (`ann_sharpe = +0.70`, top symbols: `AAOX` `+54.22 bps/trade` `PF 1.46`, `NBIG` `+51.04 bps` `PF 1.60`, `NBIL` `+48.32 bps` `PF 1.56`, `SNDG` `+34.46 bps` `PF 1.26`, `COHX` `+27.92 bps` `PF 1.31`, `AMD` `+12.53 bps` `PF 1.25`, `NVDA` `+12.05 bps` `PF 1.39`), while `5m` unfiltered arms were negative (`-7.88` to `-13.20 bps/day`) and `hftbacktest` showed `-2.22 bps` maker adverse selection. Overall `HAC t = +0.43` **honestly failed `t*(108) = 4.2148` (`p3_promotion_authorized = False`)**.
   - **Live Paper (`P3-SAR :8795` + `P1–P3`, Snapshot `#14`):** `P3-SAR` scans `10,976` symbols (`14,242` `DF10` causal baselines, `0` `ADR-0022` breaches, IBKR `:4002` connected), `P3 :8797` holds `PF 1.112` (`P3_FRONTIER` `80.0%` WR / `PF 7.76` / `0` breaches), while legacy `P2 :8787` (`PF 0.67`) and `P3-SAR` early live RTs (`n=2`, `-185 bps`) demonstrate why custom loop glue must retire into clean hosted `NautilusTrader` `TradingNode` + `Qlib` + `hftbacktest`.

## Decision

1. **Codify Clean-Room `v4.0` 4-Repo Hosted-SOTA Architecture (`<= 5,000` LOC Total Native Glue):**
   - `sota-shelf-and-harness` (upstream harnesses + single consolidated `docs/adr/` + `19`-pin `PINS_LOCK.json` + universal Git hooks + `one_harness_cleanliness_doctor.py`),
   - `sota-research-engine` (`Qlib v0.9.8` `REG_US` `1m` + `NautilusTrader` `BacktestNode` + `hftbacktest` `RiskAdverseQueueModel` + `VectorBT` + `Polars`/`DuckDB`/`Pandera`/`edgartools` MCP + `skfolio`/`ml4t-diagnostic`/`FINSABER` eval/`DoWhy`/`river`/`MAPIE`/`QuantStats` + RTX 4090 `Kronos`/`DianJin-R1`/`TabPFN`/`Chronos-2`/`MOIRAI-2`),
   - `sota-trading-node` (`NautilusTrader` `TradingNode` + `nautilus-alpaca` + `ib_async :4002` + hardened `alpaca-mcp-server` + `openbq-org/finos-workspace :1420` + `openbq-org/OpenBB` + `backends-for-openbb :6900` + `Perspective` + `Lightweight Charts`),
   - `sota-private-vault` (private continuity, verbatim ADR archive, HLZ ledger, `actions_enabled=false`).
2. **Publish Canonical Tier-0-Only `AGENTS.md` / `GEMINI.md` Draft (`docs/cleanroom/TIER0_ONLY_AGENTS.md`):** Minimal (~60-line) single-rule instruction file containing ONLY the Tier-0 Upstream-Install/Integrate/Build-Upon law, Research-Convergence-First Norm-Disruption SAR mandate, Clean-Room 4-Repo hosted platform map, and non-negotiable safety/license firewalls — staged for explicit owner review prior to overwriting live `7/7` global runtime `.md` files.
3. **Freeze & Retire Legacy `18`-Repo Sprawl Non-Destructively:** Freeze all legacy monoliths (`ADR-0047` ratchet), prohibit new self-built features in legacy repos, and cut over cleanly into the 4-repo Clean-Room `v4.0` org once the owner approves `TIER0_ONLY_AGENTS.md` and `Qlib v0.9.8` shelf pinning.

## Upstream Evidence & Primary Sources

- NautilusTrader v2 & Nautilus Agents SDK: https://github.com/nautechsystems/nautilus_trader & https://github.com/nautechsystems/nautilus_agents (`380ae38`)
- Microsoft Qlib v0.9.8 (`REG_US` 1m): https://github.com/microsoft/qlib (`5435523`)
- hftbacktest (`RiskAdverseQueueModel`): https://github.com/nkaz001/hftbacktest (`5f3ec40b`)
- Alpaca MCP Server (hardened data-only `ALPACA_TOOLSETS` + `ALPACA_PAPER_TRADE=true`): https://github.com/alpacahq/alpaca-mcp-server
- OpenBB Official Continuation & FINOS Workspace: https://github.com/openbq-org/OpenBB (`bbf1ab2`) & https://github.com/openbq-org/finos-workspace
- FINSABER (KDD 2026 leakage/cost gate): https://github.com/waylonli/FINSABER (`e72c2620`)
- TradingAgents (`date_window.py:79` trade-date clamp reference): https://github.com/TauricResearch/TradingAgents (`c454491`)
- Orca Multi-Runtime Harness: https://github.com/stablyai/orca

## Consequences

- The ecosystem now has a single, unambiguous, primary-source-verified Clean-Room `v4.0` cutover specification (`4` hosted-SOTA repos, `<= 5,000` LOC native glue), a security-hardened `alpaca-mcp-server` / `RD-Agent` containment rule, and an ultra-lean Tier-0-Only `AGENTS.md` / `GEMINI.md` draft ready for 1-click owner approval.
- Zero existing repositories, running Paper services, or `~/Documents/upstream/` pins were destructively deleted prior to explicit owner approval.
