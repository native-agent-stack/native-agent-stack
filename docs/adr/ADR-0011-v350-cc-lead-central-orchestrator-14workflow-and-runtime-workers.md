# ADR-0011: v3.5.0 Claude Code (`cc-lead`) Central Multi-Session Orchestrator, 14-Workflow Hub & 5-Channel Runtime Worker Convergence

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

Following `ADR-0010` (`v3.4.0` `424`-entry research convergence, `Noesis-Carbon` WSL2 guest, and lease-safe bidirectional Orca v2.0 co-op), commanding multi-session, multi-model runtime workers (`omc`, `codex`/`omx`, `orca`, `agy`/`gemini`, `opencode`/`oh-my-openagent`, `dsh`, `pi`/`omp`, `goose`, `hcom`) across the `22`-repository `native-agent-stack` organization needed a single deterministic central orchestrator workflow so Claude Code (`cc-lead`, `claude-fable-5-2` `xhigh`) directs every runtime worker while preserving Anthropic prompt-cache stability (`oneModelPerConversation = true`), `Hephaestus` non-GPT routing (`kimi-k3.1-pro`), isolated git worktrees, and `sota-bus` lease disjointness.

## Decision Outcome

1. **Standardize `cc-lead` Sovereign Central Orchestrator & `sota-cc-hub` (`v3.5.0`):**
   - Lock `sota-multi-model-workflows @ 3312afa5aa92` (`14` self-bootstrapping workflows, `12` MADR 4.0 ADRs, `src/sota_mmw/cc_lead_hub.py`, and Workflow `#14` `cc_lead_multi_runtime_workers_workflow.py`), `sota-harness-foundation @ 069e47db8824` (`26` ADRs, `28` validated runtimes in `config/multi-model-routing.json v1.1.0`), `cc-sota-harness @ d7fe7d3d2fff` (`25` ADRs), and `sota-private-vault @ 0ad8a059d063` (`9` ADRs, `89` pre-registered trials `t*(90) = 4.1735`, `51` `E1–E4` lessons).
   - Route `cc-lead` worker execution through five coordinated channels: (1) `omc ultragoal create-goals` + `/goal` Stop-hook, (2) `OMC_RUNTIME_V2=1 OMC_TEAM_WORKTREE_MODE=branch omc team` + `Claude OMC <-> Codex OMX` split-pane interop, (3) `omc ask <codex|antigravity|muse|grok>` + `omx exec` (`>= 3` concrete frontier vendors `anthropic`, `openai`, `google`), (4) `orca orchestration worker-start --worktree new-child --repo id:<uuid>` across `Mac M5 Max` (`local`) and `Noesis` (`100.110.115.22`, reactive `worker_done`, `0` polling), and (5) `OMO` `kimi-k3.1-pro` non-GPT `Hephaestus` + `DSH` `deepseek-v4-pro` pre-wall (`<= 2026-10-15`) + `hcom` + comma/glob-aware `sota-bus` lease guards.
2. **Enforce Cross-Harness L11 Health Probe (`sota-doctor` `12/12 PASS`):**
   - Add `L11` (`cc-lead-multi-runtime-hub`) to `sota-doctor`, verifying all `15` core runtime binaries, `14/14` workflows, and dual-mesh `Mac M5 Max <-> Noesis` readiness on every Turn-0 preflight.

## Alternatives Considered

1. **Switch models mid-conversation inside Claude Code instead of spawning isolated runtime workers:** Rejected — invalidates Anthropic prompt-cache prefixes and mixes vendor reasoning chains (`oneModelPerConversation = true`).
2. **Dispatch mutating `omc team` or `orca` workers into shared primary checkouts:** Rejected — violates isolated worktree and `sota-bus` path-lease invariants.

## Verification Witness

- Live `run_workflow` on `cc_lead_multi_runtime_workers_workflow.py` (`plan_sha256 = 678fc0cf289b00fd85f7e23a7b5c300b1284fbd1f60c0abe62a9280a0524a5d7`, `15/15` hub binaries, `3` canonical vendors + `moonshot` `Hephaestus`).
- `sota-multi-model-workflows` GitHub Actions Run `44240198191` `SUCCESS`, `sota-harness-foundation` `55/55 pytest PASS` (`26` ADRs, `28` runtimes), `sota-doctor` `12/12 PASS`, and `scripts/merge_gate.py` `11/11 MADR 4.0 ADRs, 0 drift, umbrella v3.5.0 PASS`.
