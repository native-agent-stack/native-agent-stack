# Pi builder output budgets

Pi builder scopes on the existing Claude Console and GPT OmniRoute routes use
32,768 output tokens. Other role scopes and the interactive profile retain 8,192.
The generator writes the native `models.json` field; it does not change tools,
skills, MCP, hooks, memory, telemetry, isolation, authentication or model routing.
Existing installed profiles remain untouched. Prepare a fresh profile root from
the reviewed generator to obtain the new budget; each builder uses its own
`roles/builder/agent/models.json` through `PI_CODING_AGENT_DIR`.

The old 8,192 budget can terminate an assistant message with native
`stopReason: length` while Pi exits 0. Thinking shares the request budget with
visible output; process exit alone does not establish task completion. The new
32K value adds bounded room below both documented ceilings, rather than choosing
the largest possible output by default. It is a per-message limit, not a promise
that a task completes or a dollar spending limit. A model refusal or abbreviated
fixture remains a failed measurement even if its stop reason is `stop`.

Primary mechanism is earendil-works/pi at
`04566631c2b51fb688486bc1f040f60d1518c126` (installed 1.1.0):

- `packages/coding-agent/docs/models.md:67` defines modelOverrides for built-in
  models and models entries for compatible endpoints.
- `packages/coding-agent/schemas/models.schema.json:107-110,272-275` admits
  positive maxTokens in those two native surfaces.
- `packages/coding-agent/src/core/provider-composer.ts:198` applies the override.
- `packages/ai/src/api/simple-options.ts:46` passes model.maxTokens unless
  explicitly overridden, clamped to remaining context.
- `packages/ai/src/api/anthropic-messages.ts:1162` sends max_tokens;
  `:948-975` shows adaptive effort and budgeted-thinking paths.
- `packages/ai/src/api/openai-responses.ts:340-341` sends max_output_tokens when
  the endpoint compatibility admits it. Source metadata alone does not prove
  the endpoint's wire behavior; the native probe tests the configured route.

Claude Opus 5.5's official [model overview](https://platform.claude.com/docs/en/about-claude/models/overview),
Compare models, documents 128K maximum output for `claude-opus-5-5` (read
2026-10-14). The [derived source fact](sources/anthropic-output-limits.json)
records that observation; full HTTP response custody is not claimed. The
keyless local OmniRoute `/v1/models` catalog reports `max_output_tokens: 128000`
for exact route `cx/gpt-6.1-sol`, retained as a [sanitized catalog row](sources/omniroute-model-limit.json).
Both selected 32,768 budgets are below those limits. The model family and
gateway endpoint are unchanged; no /api/settings or authentication store is read.

Acceptance separates generated-config regression tests from bounded native
measurement probes. Public tests exercise both pi_models() and render() at the
system boundary, with installer processes stubbed and no model traffic. A
native no-tool message probe uses a fresh agent/session directory, the runtime's
own provider configuration and documented credential loader. It is explicitly
`measurement_probe`, not full-layer worker qualification. Usage/cost and length
versus completion are retained; failed, refused and abbreviated attempts remain
part of the evidence. Native transcript text and identifiers stay private;
only derived numeric facts and public synthetic configuration are published.

Native AFTER completion is **UNVERIFIED**. [All attempts](measurements.json)
are retained, including native length at 8,192, short task refusals, a platform
refusal, and an incomplete GPT stream. No accepted after-run proves full fixture
completion, and the incomplete stream has unknown final cost. A final marker
mentioned in a refusal does not count as fixture completion. The platform-refused
probe is stopped; it is not retried to evade the block. The one separately
approved builder-shaped AFTER task ended `length` at32,768 output tokens, exit0,
with native cost estimate$0.669461. It fails the CC's required stop/toolUse
completion criterion. Under the explicit option(c) disposition, stop further
calls and retain AFTER completion as an OPEN measurement follow-up while
delivering the source-level budget change plus native BEFORE length evidence.
No statement that the builder task completed is made. Known native estimates
across all attempts total$0.8688136; the terminated GPT stream's final cost
remains unknown. Generation tests/source ceilings do not close that gap.

The two capacity follow-ups from #1082 remain later-PR work: a package-qualified
LaggedExecutor import and an unreachable place_only journal condition. They are
not edited in this output-budget change. Muse profiles follow this PR's readiness
and use their separately approved TRIAL route.
