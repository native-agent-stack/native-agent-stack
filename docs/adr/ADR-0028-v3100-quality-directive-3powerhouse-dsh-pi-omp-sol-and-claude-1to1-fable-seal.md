# ADR-0028: `v3.10.0` Quality-Directive `3`-Powerhouse + `DSH` + `Pi/OMP` (`gpt-6.2-sol`) Routing & Claude Code `1:1` `claude-fable-5-2` Mix Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Frontier Model Quality Governance, `Pi/OMP` `gpt-6.2-sol` Alignment & Claude Code `1:1` `claude-fable-5-2` Rebalancer (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`413`-Turn `jsonl` Audit, `sota-multi-model-workflows` `ADR-0023`, `cc-sota-harness` `ADR-0035`, `agy-sota-harness` `ADR-0029`, `sota-harness-foundation` `ADR-0036`, `canon` `0185`, `merge_gate.py` & `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-private-vault, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/native-agent-stack/agy-sota-harness, https://github.com/native-agent-stack/sota-harness-foundation
- **Revisit Trigger:** 2026-12-06 (`23/5` SIP cutover) or next frontier model release on `artificialanalysis.ai`

## Context and Problem Statement

Advancing the ecosystem to `v3.10.0` to enforce strict frontier-only model quality across all orchestrated runtimes:
1. **3 Frontier Powerhouses + `DSH` + `Pi/OMP` (`gpt-6.2-sol` `high`):** Prunes low-quality/free/unauthed route fallbacks, focusing active multi-model execution on Anthropic (`claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`), OpenAI (`gpt-6.2-astra` `xhigh`, `gpt-6.2-sol` `high` including `Pi` & `OMP` agent configs), Google Antigravity (`gemini-4-carbon-high`), and DeepSeek Harness (`deepseek-v4-pro`).
2. **Claude Code `~1:1` `claude-fable-5-2` Mix (`0%` `haiku` Sprawl):** Enforces `OMC_MODEL_HIGH=claude-fable-5-2`, `OMC_MODEL_MEDIUM=claude-sonnet-5-5`, `OMC_MODEL_LOW=claude-sonnet-5-5`, explicit `model:` frontmatter in `~/.claude/agents/*.md`, and `sota-cc-hub model-mix` telemetry targeting `50%` `claude-fable-5-2` vs `50%` `opus-5-5`/`sonnet-5-5`.

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.10.0"` (`28` Umbrella ADRs):**
   - Record `v3100QualityDirective3PowerhouseAnd1To1FableMixSeal` aligned 1:1 with `DEFAULT_ECOSYSTEM_SEMVER = "3.10.0"` across all `22` org repositories and `54` 3-surface checkouts.

## Alternatives Considered

1. **Allow `OMC_MODEL_LOW` to default to `haiku` or retain unauthenticated worker routes in active dispatch tables:** Rejected — compromises code/quant verification rigor.

## Verification Witness

- `.venv/bin/python scripts/merge_gate.py` (`architecture_catalog --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
