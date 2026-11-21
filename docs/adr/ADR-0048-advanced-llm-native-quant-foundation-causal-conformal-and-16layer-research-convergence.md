# ADR-0048: Full-Landscape Advanced LLM-Native Quant, Microstructure Foundation Models, Causal/Conformal Risk & License-Firewall Convergence (`v3`)

- **Status:** Accepted
- **Date:** 2026-11-20
- **Evidence Grade:** E4 (`36`-repo live `gh api` 40-char HEAD SHA + SPDX + archive audit on `2026-11-20`; `8`-repo shallow inspect-only source & order-path security audit in `Z:/sota-cache/llm-native-eval-pass2/`; `sota-upstream-shelf-lock@b6eb237` `ADR-0026` PASS; `one_harness_cleanliness_doctor.py` `10/10 PASS`; `7/7` global `.md` `0`-byte drift; `792/792` single-repo finalized ADR parity; `scripts/merge_gate.py PASS`; `gitleaks 0`)
- **Supersedes / Extends:** Extends `ADR-0044`, `ADR-0045`, `ADR-0046`, `ADR-0047`, and pairs with `sota-upstream-shelf-lock` `ADR-0026`

## Context

Following the `ADR-0045` 16-layer SOTA pin blueprint, `ADR-0046` continuous 10-invariant One-Harness Cleanliness Doctor & universal Git hooks, and `ADR-0047` hosted-SOTA-platform mandate, the ecosystem conducted a multi-wave institutional survey and live primary-source verification across `36` LLM-native trading, quant, microstructure foundation-model, causal-inference, conformal-risk, and financial MCP repositories (`2026-11-20`).

Key empirical findings driving this umbrella convergence:
1. **Separating Real Quant SOTA from the LLM "Profit Mirage":** `waylonli/FINSABER` (KDD 2026 Oral, `Apache-2.0`) empirically demonstrated that prompt-only trading agents suffer severe pre-training cutoff memorization unless evaluated with strict post-cutoff timing (`next_open` vs `same_close`), realistic slippage, liquidity caps, and LLM token-cost accounting.
2. **Official Vendor & Rust-Native Alignment (`ADR-0047`):**
   - `nautechsystems/nautilus_agents` (`LGPL-3.0`, `380ae38f35`, pure Rust, `0` order-path code verified) is the official Agents SDK for our pinned `NautilusTrader` core.
   - `anthropics/financial-services` (`Apache-2.0`, `41,423` stars, `3e32c2287d`, `0` order-path code verified) ships official financial analysis & earnings-review plugins wired for Claude MCP.
   - `openbq-org/OpenBB` (`75,607` stars, `f0f1852b96`) + `openbq-org/finos-workspace` (`:1420`) is confirmed as the official active continuation of OpenBB (`OpenBB-finance/agents-for-openbb` is archived).
   - `dgunning/edgartools` (`v6.2.0`, already pinned on our immutable shelf) ships a built-in zero-API-key SEC EDGAR MCP server.
3. **Microstructure, Tabular, Covariate, Causal & Streaming Drift Expansion across `L1`–`L15`:**
   - Generative LOB & impact validation: `microsoft/MarS` (`MIT`, ICLR 2025) & `peernagy/LOBS5` (`MIT`).
   - Local RTX 4090 (`:8794`) foundation models: `shiyu-coder/Kronos` (`MIT`, `48k` stars), `aliyun/qwen-dianjin` (`MIT`, `DianJin-R1` + `Fin-PRM`, `0` order-path code), `The-FinAI/Fino1` (`MIT`), `PriorLabs/TabPFN` (`Apache-2.0`, `8.5k` stars), `amazon-science/chronos-forecasting` (`Apache-2.0`, `Chronos-2`), `SalesforceAIResearch/uni2ts` (`Apache-2.0`, `MOIRAI-2`).
   - Streaming alpha-decay, conformal risk & causal attribution: `online-ml/river` (`BSD-3-Clause`, CUSUM/ADWIN for `L14`), `scikit-learn-contrib/MAPIE` (`BSD-3-Clause`, conformal intervals for `L11`), `py-why/dowhy` (`MIT`, causal refutation for `L4`/`L12`), `FreedomIntelligence/TwinMarket` (`MIT`, NeurIPS/ICLR 2025 Best Paper for `L11`/`L13`).
   - Read-only market/event MCP feeds: `massive-com/mcp_massive` (`MIT`, `0` order-path code) and `BrainDAO/mcp-polymarket` (`MIT`, strictly read-only with zero private key).
4. **Hard License, Archival & Order-Path Firewall:** Live GitHub API + shallow source inspection caught unlicensed (`NONE`) repos (`QuantaAlpha/QuantaAlpha`, `SUFE-AIFLM-Lab/Fin-R1`, `FinStep-AI/Alpha-R1`, `horizon-llm/AlphaQuanter`, `patronus-ai/financebench`, `virattt/dexter`), strong-copyleft (`hansbuehler/deephedging` `GPL-3.0`), archived repos (`OpenBB-finance/agents-for-openbb`, `Polymarket/agents`, `jpmorganchase/abides-jpmc-public`, `hummingbot/mcp`), and live order-routing paths inside `HKUDS/Vibe-Trading`, `BrainDAO/mcp-polymarket`, and `FINSABER`'s vendored `finrl` subpackage.

## Decision

1. **Upgrade `SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST` to `v3` (`scripts/build_full_landscape_layer_manifest.py`):** Bind all `19` live-verified, active, non-archived, SPDX-licensed frontier repos cleanly across `L1`–`L15` while keeping `~/Documents/upstream/` immutable until explicit promotion ADRs pass full verification.
2. **Enforce Cross-Repo Provenance Parity with `sota-upstream-shelf-lock` `ADR-0026`:** Every Beyond-Starred frontier anchor added to `L1`–`L15` must pass SPDX license clearance, non-archived status, and explicit order-path containment (`ADR-0022`); unlicensed, archived, and `GPL-3.0` repos remain strictly quarantined in `LICENSE_AND_ARCHIVE_QUARANTINE_WATCHLIST`.
3. **Propagate Across All `7/7` Global Runtime `.md` Files & Single-Repo Consolidated ADR Archives:** Sync via `sync_tier0_harness_and_master_adrs.py --apply-global-md` and `one_harness_cleanliness_doctor.py --fix-sync --write-receipt` (`10/10 PASS`, `0`-drift parity across `native-agent-stack` public registry and `sota-private-vault/adr_archive/` verbatim private copy).

## Upstream Evidence & Primary Sources (`2026-11-20` Live Verified)

- Official Nautilus Agents SDK: https://github.com/nautechsystems/nautilus_agents (`LGPL-3.0`, `380ae38f35`)
- Official Anthropic Financial Services Plugins: https://github.com/anthropics/financial-services (`Apache-2.0`, `3e32c2287d`)
- FINSABER (KDD 2026): https://github.com/waylonli/FINSABER (`Apache-2.0`, `e72c26206d`)
- Microsoft MarS (ICLR 2025): https://github.com/microsoft/MarS (`MIT`, `f04dd87a4d`)
- LOBS5: https://github.com/peernagy/LOBS5 (`MIT`, `aa36029e9d`)
- FinRobot: https://github.com/AI4Finance-Foundation/FinRobot (`Apache-2.0`, `63e1884a42`)
- HKUDS Vibe-Trading (sandbox ref only): https://github.com/HKUDS/Vibe-Trading (`MIT`, `25c89a0aa2`)
- Alibaba Qwen DianJin: https://github.com/aliyun/qwen-dianjin (`MIT`, `a626b083c1`)
- The-FinAI Fino1 & FinBen: https://github.com/The-FinAI/Fino1 & https://github.com/The-FinAI/FinBen (`MIT`)
- PriorLabs TabPFN: https://github.com/PriorLabs/TabPFN (`Apache-2.0`, `e1a3550654`)
- Amazon Chronos-2: https://github.com/amazon-science/chronos-forecasting (`Apache-2.0`, `1224fafa91`)
- Salesforce MOIRAI-2: https://github.com/SalesforceAIResearch/uni2ts (`Apache-2.0`, `cfd46d4510`)
- Online-ML River (CUSUM/ADWIN): https://github.com/online-ml/river (`BSD-3-Clause`, `5ea2454006`)
- MAPIE Conformal Risk: https://github.com/scikit-learn-contrib/MAPIE (`BSD-3-Clause`, `e4c4f5f7da`)
- PyWhy DoWhy: https://github.com/py-why/dowhy (`MIT`, `45de9a9062`)
- Massive.com Market/Options MCP: https://github.com/massive-com/mcp_massive (`MIT`, `1e161a8c50`)
- BrainDAO Polymarket MCP (read-only): https://github.com/BrainDAO/mcp-polymarket (`MIT`, `5360bef548`)
- FreedomIntelligence TwinMarket: https://github.com/FreedomIntelligence/TwinMarket (`MIT`, `de5f2446fc`)
- Official OpenBB Continuation & Workspace: https://github.com/openbq-org/OpenBB & https://github.com/openbq-org/finos-workspace

## Consequences

- All `16` layers (`L0`–`L15`) now incorporate the complete, live-verified `2026` frontier of LLM-native quant, microstructure foundation models, causal/conformal risk, streaming drift detection, and read-only MCP tooling under strict license, archival, and `ADR-0022` order-path firewalls.
- Zero self-built waste (`ADR-0047`), zero unlicensed vendoring (`shelf-lock ADR-0026`), and `10/10` continuous verification (`ADR-0046`) remain locked end-to-end across all `18` repositories and `7` agent runtimes.
