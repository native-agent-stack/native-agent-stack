# ADR-0004: Five-Stage Sim -> Pre-Wall -> Paper -> Empirical-Bayes -> Broker Lifecycle

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E3

## Context and Problem Statement
Unshielded bar-level alpha decays under real bid-ask spread, adverse selection, and multiple-testing bias (`Trials #1-#82`).

## Decision Outcome
Enforce the 5-stage promotion pipeline across `meridian` (Stage 1 Sim), `canon`/`agy-sota-harness`/`cc-sota-harness` (Stage 2 Pre-Wall `<= 2026-10-15`, HLZ + `CPCV` + `DSR`), `sota-mover-ranker` + `astrolabe` (Stage 3 Paper `PA...` `<= 200 req/min` & `DU...` `:4002` `<= 3,000 msg/min` with `ADR-0022 <= 2.00%` stops), `sota-compounding-lab` (Stage 4 Empirical-Bayes shrinkage), and `sota-dynamic-trail-c` + `sota-private-vault` (Stage 5 `24/5` guardian & SHA-256 broker manifest).
