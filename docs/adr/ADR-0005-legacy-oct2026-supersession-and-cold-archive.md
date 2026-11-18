# ADR-0005: Supersession & Cold-Archival of Sep-Oct 2026 Legacy Repositories

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E3

## Context and Problem Statement
The original September–October 2026 `native-agent-stack` repository carried `312.13 MB` (`13,242` blobs) of superseded WSL recipes, `.jcodemunch.jsonc`, `13.5 KB` `.gitleaksignore` debt, and `23` legacy scheduled workflows, while `ecosystem-records` held a static `2026-10-14` snapshot.

## Decision Outcome
Freeze the legacy repository as `PRIVATE` archived `native-agent-stack/legacy-agent-stack-202610` (`actions_enabled=false`, `archived=true`, preserving PRs `#1-#1272` in cold storage without packfile bloat), archive `ecosystem-records`, and establish this greenfield `<100 KB` `v3.0.0` repository as the clean canonical umbrella.
