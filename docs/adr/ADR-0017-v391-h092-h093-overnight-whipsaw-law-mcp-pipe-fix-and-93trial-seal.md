# ADR-0017: `v3.9.1` `H092`+`H093` Overnight Whipsaw Boundary Law (`7,473` Events), MCP Pipe-Deadlock Fix & Live `ADR-0017` E2E Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Pre-Wall Volatility-Scaling Governance & Live RTH Execution Reliability (`L0–L13` × `P0–P5` × `T1–T8`)
- **Evidence Grade:** E4 (`93` Pre-Registered Trials, `7,473`-Event `H092`+`H093` Twin Proof, `sota-mover-ranker @ e8eebd7a0570` `81/81` `pytest` PASS & `69` Compiled Lessons Verified)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-compounding-lab, https://github.com/native-agent-stack/sota-private-vault
- **Revisit Trigger:** 2027-01-02

## Context and Problem Statement

Immediately following `ADR-0016` (`v3.9.0`), peer sessions finalized two critical quantitative and production-reliability closures:
1. **`Trials #92` & `#93` (`H092` + `H093`, `7,473` NYSE/Nasdaq Events `<= 2026-10-15`):** Proved across `5,400` loser events (`t = -5.4145`, `23.06%` stop rate) and `2,073` high-`RVOL` winner events (`t = -4.6903`, `18.81%` stop rate) that holding high-sigma (`>= 2.5%..15%` intraday move) stocks overnight under a fixed `200 bps` extended-hours stop incurs `18.8%–23.1%` thin-liquidity stop whipsaw prior to the `09:30 ET` Opening Auction (`N = 93 -> t*(94) = 4.1834`).
2. **Live `:8787` MCP Pipe-Deadlock Elimination & `ADR-0017` E2E Wiring (`sota-mover-ranker @ e8eebd7a0570`):** Fixed the `64KB` macOS `stderr=PIPE` + blocking `readline` deadlock in `SanctionedAlpacaPaperMcpBridge`, wired `protective_entry_shield` (`<= 10 bps` spread, `OFI >= 0.25`, streak cooldown) + `alloc_mult` into `alpaca_paper_e2e.py`, blocked `1`-share dust orders at `99.9%` BP, and hardened Ubuntu 26.04 headless-Chrome CI probing (`dsh-sota-harness @ 9e4ca13e4e62`, `69` lessons).

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.1"` (`17` Umbrella ADRs):**
   - Record `v391OvernightWhipsawLawAndLiveE2ESeal` (`hlzTrialsCompleted = 93`, `nextHlzTHurdle = 4.1834`, `lessonsCount = 69`, `sotaMoverRankerLiveE2ESha = "e8eebd7a0570"`) across all `22` repositories.

## Alternatives Considered

1. **Leave `ECOSYSTEM_CONVERGENCE_LOCK.json` at `v3.9.0` without recording `H092`–`H093` (`N = 93`) and `e8eebd7a0570`:** Rejected — umbrella lock must reflect live peer-bus multiplicity (`t*(94) = 4.1834`) and active RTH execution commits.

## Verification Witness

- `uv run python scripts/merge_gate.py` -> `PASS` (`17/17` ADRs, `umbrella --check`, `ruff`, `ty`, `pytest`).
- `gitleaks` -> `0` leaks.
