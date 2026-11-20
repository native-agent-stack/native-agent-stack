# ADR-0042: `v3.11.1` Post-ANT Whole-Market `DF1..DF12` Merit Ranking & Lossless Consolidation Seal

- **Status:** Accepted
- **Date:** 2026-11-20
- **Layer:** Organization Umbrella (`L1`): sibling-commit pins across `sota-mover-ranker`, `sota-dynamic-trail-c`, `astrolabe`, `sota-multi-model-workflows`, and `sota-compounding-lab`; post-ANT whole-market 6-pillar `DF1..DF12` merit ranking; strict `ADR-0064` strategy-contract parity; fail-closed quote/SEC/regime/TCA gates; and cross-lane `LosslessProtectionKernel` unification
- **Evidence Grade:** E4 (Independent read-only OpenAI Codex `gpt-6.2-astra` `xhigh` `VERDICT: PASS` with `0` P0/P1 findings across all five implementation repositories; `sota-mover-ranker` `ADR-0066` `66/66` ADRs `550 passed` + live reloaded Paper `:8787` scanning `10,973` US symbols & standalone OpenBB `:6900` HTTP 200; `sota-dynamic-trail-c` `ADR-0030` `30/30` ADRs `231 passed` + live reloaded Paper `:8799` HTTP 200; `astrolabe` `ADR-0016` `16/16` ADRs `97 passed` targeted / `2,489` full suite + `pyright 0` errors; `sota-multi-model-workflows` `ADR-0036` `36/36` ADRs `62 passed, 291 subtests passed`; `sota-compounding-lab` `ADR-0028` `28/28` ADRs `290 passed, 4 skipped`; `42/42` umbrella ADRs; `gitleaks 0` leaks across all repos; Live `:8798`/`:8796` untouched)
- **GitHub Evidence:** https://github.com/native-agent-stack/sota-mover-ranker/commit/dd5a65aa4bd99a8b09b808154beb797e5f1280df, https://github.com/native-agent-stack/sota-dynamic-trail-c/commit/cc4348cfd1d2c78749f505a73cbbfd65b5d05cff, https://github.com/native-agent-stack/astrolabe/commit/801efa5a5706c606a60fe0c9577702624056b26e, https://github.com/native-agent-stack/sota-multi-model-workflows/commit/3b08855f9c39a8b77d0ff24d872ef97cd1a66eed, https://github.com/native-agent-stack/sota-compounding-lab/commit/2235a8273060cf2336a0b38d3a11fba9ac89f13a, https://github.com/native-agent-stack/sota-mover-ranker/blob/dd5a65aa4bd99a8b09b808154beb797e5f1280df/docs/SOTA_FULL_LANDSCAPE_MANIFEST.md
- **Revisit Trigger:** `2026-12-06` `21:00 ET` consolidated `23/5` SIP cutover verification, pre-registration of `Trial #105` (`t*(105) = 4.2084`), or explicit owner-gated Stage-5 Live `:8798`/`:8796` reload after human sign-off.

## Context and Problem Statement

Following the completion of the `2026-11-19` `NASDAQ:ANT` IPO debut event, the ecosystem transitioned into the **Post-ANT Era**: any US equity across the ~`11,000`-symbol NMS universe that manifests real `DF1..DF12` institutional market data (live fresh quotes, liquidity/spread compliance, `BJZZ` dark-pool/OFI flow, clean non-dilutive SEC `edgartools` state, regime alignment, and verified TCA execution quality) must dynamically merit into our active target pipeline and bind seamlessly to our uncapped `LosslessProtectionKernel` (`ADR-0022 <= 2.00%` stop cap, `4x` leverage-aware equity cap, `>= 10%` protective exit reserve, monotonic 3-tier Chandelier, zero fixed-TP upside cap).

Remaining pre-IPO `ANT`/`SPCX` hardcoded symbol anchors, cross-lane contract discrepancies (IBKR `P4` `<2x` equity-risk ceiling and default spread assumptions, zero-roundtrip live canary loopholes, unattributed mixed-account promotion, and factory spread-widening regressions on `<3.0 bps` Noise-VWAP) needed deterministic cross-repo closure under independent adversarial audit.

## Decision Outcome

### 1. Pin the Five Landed `v3.11.1` Sibling Commits (Pointer-Only Charter)

| Repository | Owner Decision | Pinned `origin/main` Commit | ADRs | Verification Witness |
| --- | --- | --- | --- | --- |
| `sota-mover-ranker` | `ADR-0066` (Post-ANT 6-pillar `DF1..DF12` whole-market merit engine, fail-closed quote/SEC/regime/TCA gates, strict `ADR-0064` strategy binding & manifest `e9e92588...`) | `dd5a65aa4bd99a8b09b808154beb797e5f1280df` | `66` | `550 passed`, `ruff`/`merge_gate`/`gitleaks 0`, Codex `gpt-6.2-astra` Pass-8 `PASS`, live `:8787` (`10,973` scanned) & `:6900` verified |
| `sota-dynamic-trail-c` | `ADR-0030` (Post-ANT dynamic merit-feed hydration on `:8799`, zero `SPCX` anchors, `LosslessProtectionKernel` parity) | `cc4348cfd1d2c78749f505a73cbbfd65b5d05cff` | `30` | `231 passed`, `ruff`/`merge_gate`/`gitleaks 0`, Codex `gpt-6.2-astra` `PASS`, live `:8799` verified |
| `astrolabe` | `ADR-0016` (IBKR `:4002` `P4` `LosslessProtectionKernel` parity, exact `Fraction` wire check, `[0.01, 4]` leverage guard, Noise-VWAP `<= 0.50%`, VIX allowlist, fail-closed `nbbo_spread_bps=None`) | `801efa5a5706c606a60fe0c9577702624056b26e` | `16` | `97 passed` targeted / `2,489` full suite, `pyright 0`, `gitleaks 0`, Codex `gpt-6.2-astra` `PASS` |
| `sota-multi-model-workflows` | `ADR-0036` (Post-ANT `sota.strategy-contract.v2` parity, zero-roundtrip live canary closed, multi-account `P1 >= 15` & `non-P1 >= 1` full-auto gate, fail-closed promotion defaults) | `3b08855f9c39a8b77d0ff24d872ef97cd1a66eed` | `36` | `62 passed, 291 subtests passed`, `ruff`/`merge_gate`/`gitleaks 0`, Codex `gpt-6.2-astra` `PASS` |
| `sota-compounding-lab` | `ADR-0028` (Post-ANT `ADR-0064` strategy-id & symbol validation in compounding reflections, Noise-VWAP `<3.0 bps` tightening floor preservation) | `2235a8273060cf2336a0b38d3a11fba9ac89f13a` | `28` | `290 passed, 4 skipped`, `ruff`/`gitleaks 0`, Codex `gpt-6.2-astra` `PASS` |

### 2. Governance, Promotion-Track Honesty & Live Firewall Invariants

- **Strict `PROTECTIVE_FILTER_OR_GOVERNANCE` Classification:** `v3.11.1` consolidates whole-market symbol ranking, fail-closed market-data hygiene, and lossless risk parity with `standaloneAlphaClaim: false`. It does **not** consume HLZ `Trial #105` (`hlzTrialsCompleted: 104`, `nextHlzTHurdle: 4.2084`, `trial105Consumed: false`).
- **Updated Landscape Single Source of Truth:** `SOTA_FULL_LANDSCAPE_MANIFEST.{md,json}` regenerated cleanly at SHA-256 `e9e925881cd90e0e29addc23255ca965019ea9f523d5d48a4a102fcc9fd8fdfa` preserving both the live Paper `OVERNIGHT_BOATS` E2E receipt and the honest Pre-Wall `Trial #104` receipt (`5e073f98...`).
- **Live Execution Untouched:** Paper-only daemons (`:8787`, `:8799`, standalone OpenBB `:6900`) were reloaded and verified empirically while Sovereign Noesis Live `:8798` and Live EXT Guardian `:8796` remained `100%` read-only and untouched.

## Alternatives Considered

- **Retaining Static Pre-IPO `ANT`/`SPCX` Seed Anchors:** Rejected because hardcoded legacy symbols bias capital/attention away from whole-market `DF1..DF12` institutional flow in the Post-ANT era.
- **Relaxing Pre-Market Strategy Eligibility To Force Active Tiers At `05:30 ET`:** Rejected under fail-closed `ADR-0064` discipline; thin pre-market quotes without verified RTH/catalyst criteria honestly remain `WATCH_ONLY`.

## Verification Witness

- `uv run ruff check . && uv run ruff format --check .` (`PASS`).
- `uv run python scripts/architecture_catalog.py --check` (`42/42` MADR 4.0 ADRs valid, `0` drift).
- `uv run python scripts/merge_gate.py` (`PASS`).
- `uv run pytest -q` (umbrella lock + Hypothesis + `v3.11.1` Post-ANT seal assertions `PASS`).
- `gitleaks protect --staged --redact --no-banner` (`0` leaks).
