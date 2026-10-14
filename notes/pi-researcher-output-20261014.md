# Pi researcher output budget

The builder-only change in #1104 left the researcher role at8192 tokens.
Fresh Pi researcher profiles on both existing routes now receive32768,
matching builders. Reviewer, auditor and unscoped generated configuration stay
at8192. This changes the native per-message output ceiling; it does not prove
that a task completes within that ceiling or change Pi's exit semantics.

## Primary sources

- earendil-works/pi@04566631c2b51fb688486bc1f040f60d1518c126:
  packages/coding-agent/docs/models.md:67 describes native models/modelOverrides;
  packages/coding-agent/schemas/models.schema.json:107-110,272-275 accepts
  maxTokens; packages/ai/src/api/simple-options.ts:46 selects model.maxTokens
  when no request override is supplied, subject to the context limit;
  packages/ai/src/providers/anthropic-messages.ts:1162 and
  packages/ai/src/providers/openai-responses.ts:340-341 send output limits.
  The docs/schema/simple-options passages were re-read at the mirror pin for
  this follow-up. #1104 retains the provider excerpts in
  notes/pi-builder-output-20261014/sources/pi-max-tokens-source.txt.
- Anthropic official model overview, Compare models:
  https://platform.claude.com/docs/en/about-claude/models/overview.
  #1104's retained source-review fact for claude-opus-5-5 states128K output;
  source record: notes/pi-builder-output-20261014/sources/anthropic-output-limits.json.
  Full vendor-page response custody was not retained.
- The retained keyless OmniRoute /v1/models catalog observation for
  cx/gpt-6.1-sol reports max_output_tokens128000:
  notes/pi-builder-output-20261014/sources/omniroute-model-limit.json.
  This remains a dated catalog observation, not a fresh endpoint measurement.

32768 is below both retained limits. The decision extends the existing vendor
configuration to the truncated role; it introduces no provider or runtime.
New limits or evidence of a role needing a different ceiling would reopen this
choice through a separate reviewed change.

## Regression evidence

The emitted agent/models.json boundary is the regression seam. On main
8c11dac090f71d340abd54abf8c67ffae13fa2d5, the updated test fails on both
researcher routes: expected32768, observed8192 (rc1, two subtest failures).
After the two-line generator change, the three budget tests pass (rc0),
including explicit reviewer/auditor8192 controls. The existing32 runtime-profile
tests also pass (rc0). Installer boundaries are stubbed: this is local
configuration integration evidence, not a native inference measurement.

The change applies through a fresh prepare. No installed profiles were edited,
and no model call or data-layer re-run was performed by this PR. The existing
#1104 native AFTER completion boundary remains OPEN.
