# ADR-0045: Full-Landscape Resolute SOTA Layer-Pin Architecture Manifest (`L0`–`L15`: Shelf, Backtest, Strategies, Trading Engine/UI, Orca Harness & Institutional Expansion)

- **Status:** Accepted
- **Date:** 2026-11-20
- **Layer:** Umbrella Full-Landscape Architecture & Tier-0 Layer-Pin Governance (`native-agent-stack`: `scripts/build_full_landscape_layer_manifest.py`, `docs/SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST.{json,md}`, `tests/test_adr0045_full_landscape_layer_pin_manifest.py`)
- **Evidence Grade:** E4 (Deterministic 16-layer `L0–L15` manifest resolving all 18 exact 40-char Git SHAs from `PINS_LOCK.json` / `upstream-map.toml` + verified GitHub SOTA repos across strategy libraries, full-resolution backtest backbone `:8794`, 24/5 Paper trading engine & UI cockpit, Orca 7-runtime harness, and institutional expansion layers `L11–L15`; verified by `scripts/merge_gate.py`, `ruff`, `ty`, `pytest`, `ADR-0023`, `gitleaks 0`)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-upstream-shelf-lock, https://github.com/nautechsystems/nautilus_trader, https://github.com/nkaz001/hftbacktest, https://github.com/stablyai/orca, https://github.com/finos/perspective
- **Revisit Trigger:** Promotion of any institutional expansion layer (`L11–L15`) from `EXPANSION_ROADMAP` to `ACTIVE_FULL_RES_VERIFIED` or update to `PINS_LOCK.json`.

## Context and Problem Statement

With `18` active repositories, `788+` finalized MADR 4.0 ADRs, `18` immutable core upstream pins, `415+` audited SOTA starred repos, `7` agent runtimes, and `14` newly identified institutional capability gaps (`#1–#14`), the owner required a single, machine-verifiable **Full-Landscape Resolute SOTA Layer-Pin Blueprint** binding every operational layer (`L0–L10`) and every planned institutional expansion layer (`L11–L15`) to exact 40-char pinned SOTA upstreams, owning local repositories, full-resolution zero-fallback invariants, and fail-closed verification gates.

## Decision Outcome

1. **Canonical 16-Layer (`L0`–`L15`) Layer-Pin Manifest (`docs/SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST.{json,md}`):**
   - `L0–L10` (`ACTIVE_FULL_RES_VERIFIED` / `ACTIVE_PAPER_LIVE`): Immutable 18-pin Shelf (`L0`), Bitemporal 12-Feed PIT Lake (`L1`), Full-Resolution `NautilusTrader`+`hftbacktest`+`VectorBT` Backtest Engine (`L2`), Pinned Strategy Libraries (`L3`), Adversarial `CPCV`/`DSR`/`HLZ` Falsifier (`L4`), Autonomous `24/5` Paper `P1–P4` Execution Engine (`L5`), Institutional UI Cockpit `Perspective`/`Lightweight Charts`/`OpenBB` (`L6`), RTX 4090 `:8794` GPU Compute (`L7`), Orca & 7-Runtime Harness (`L8`), Red-Team Security & Single-Repo Consolidated ADRs (`L9`), Continuity Vault & Wiki Memory (`L10`).
   - `L11–L15` (`EXPANSION_ROADMAP`, honestly labeled without pretending live status): Cross-Account `skfolio` Risk & Regime Meta-Allocator (`L11`), Adaptive SOR/Live TCA & Double-Entry OMS (`L12`), Time-Machine Replay, Options/GEX & PIT Corporate Actions (`L13`), Sparse Pre-HLZ Alpha Factory & Post-Wall SPRT/CUSUM Gate (`L14`), Semantic Watchdog, Chaos Failover, Order-to-Commit Lineage & `SkillOpt` Eval (`L15`).
2. **Fail-Closed SHA-256 & 40-Char Pin Verification (`tests/test_adr0045_full_landscape_layer_pin_manifest.py`):**
   - Guarantees every core pin resolves to an exact 40-char SHA matching `PINS_LOCK.json`/`upstream-map.toml`, `allow_silent_fallback = False`, `paper_only_firewall = True`, zero leaks, and valid SHA-256 seal.

## Alternatives Considered

1. **Static Unchecked Prose Architecture Doc:** Rejected — drifts immediately as SHAs, ADRs, or repo heads advance.

## Consequences

- **Positive:** Single authoritative, cryptographically sealed full-landscape blueprint uniting every pinned SOTA repo, strategy library, backtest engine, trading UI, Orca harness surface, and institutional expansion layer.
- **Negative / Safeguards:** Re-run `python scripts/build_full_landscape_layer_manifest.py` whenever a core pin or layer status advances.

## Verification Witness

- **Tests & Gates:** `tests/test_adr0045_full_landscape_layer_pin_manifest.py`, `scripts/merge_gate.py` (`ruff`, `ty`, `pytest`, `umbrella --check`, `architecture_catalog --check` `45/45`, `ADR-0023`), `gitleaks 0`.
