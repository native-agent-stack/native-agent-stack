# Correction: the background-haiku catalog row follows Haiku 5.5 (2026-10-17)

**Status:** correction record. It amends one row of the model-currency catalog, refreshes the selection records that
repeated the old pick (see the last section) and supersedes the parts of the earlier records listed below. It changes no host configuration and no settings file.
**Base:** `origin/main` at `83dff3b73226289effd49bf65099680369a1da95`.
**Policy:** [zero tolerance for stale models, runtimes and repositories](2026-10-17-zero-tolerance-currency.md) (a stale
catalog record is refreshed at once; a pending review is not an end state).

## What was wrong

`catalogs/foundation/model-currency.json`, row `background-haiku`, pinned `claude-haiku-4-5-20251001` for "Claude Code
2.1.292 background slot", with a 2026-10-15 landscape check that queued a "migration/quality-cost review and authorized
application" of `claude-haiku-5-5`. The installed client (2.1.302) already runs Haiku 5.5 in that slot, so the row, not the
host, was stale. There was nothing to apply.

## Superseded records, cited by hash

The bytes below are read at base `83dff3b7` by tool in the same command that wrote this file; neither file is edited.

| Superseded | sha256 at base |
| --- | --- |
| `docs/decisions/2026-10-15-model-currency-landscape-check.md` (the `background-haiku` table row, the Haiku correction regression receipt and the "Haiku background migration review" section) | `2351ea7da59e6fc93556b4048efeec2be0288fa01bdbe36139c870d9b5a2e6ec` |
| `catalogs/foundation/model-currency.json` as of `83dff3b7` (the old `background-haiku` row and its `landscape_check`) | `3c5a2d3665aefab02aef36770de4dd0f7f191e534b2c83535405894a62d2932a` |
| `tests/test_model_currency.py` as of `83dff3b7` (the receipt test below) | `0d5b98a3894c1d5f39484e0f6be87f8cc48452be3b831501e6b42e4d43651b54` |

The 2026-10-15 record stays unchanged as dated history. Its Haiku statements are superseded as follows:

- "Record it for normal migration/quality-cost review and authorized application; do not silently replace the in-use 4.5
  pin" and the section `#haiku-background-migration-review` (CC-owned paired Haiku 4.5/5.5 check): moot for this slot, because
  the client default already moved to Haiku 5.5 at Claude Code 2.1.293 and no override is set on this host. A paired
  quality check of 4.5 against 5.5 remains available as a measurement, but nothing is gated on it.
- The regression receipt
  `tests.test_model_currency.ModelCurrencyTests.test_background_haiku_records_sourced_successor_and_triggered_review`
  asserted that the 4.5 pin stays `in_use`. It is replaced by
  `tests.test_model_currency.ModelCurrencyTests.test_background_haiku_row_names_haiku_5_5_for_the_client_it_states`, which
  fails on the old row: its consumer names client 2.1.292, below the 2.1.293 cut, and it pins Haiku 4.5.

## The corrected row

Consumer "Claude Code 2.1.302 background slot (follows the haiku alias; ANTHROPIC_DEFAULT_HAIKU_MODEL unset on this host)",
model and revision `claude-haiku-5-5`, release date 2026-10-07 (from the Haiku 5.5 overview page the old row already
cited), `checked_at` 2026-10-17, status `in_use`. The old `landscape_check` block is removed rather than moved: the pin is
now 10 days from release, inside the 42-day window, so no exception block is needed, and a 2026-10-15 block listing Haiku 5.5
as newer than itself would contradict the row and expire on 2026-10-22. The history lives in this record.

**Overturn:** a Claude Code release after 2.1.302 moves the background slot off Haiku 5.5, or Anthropic marks Haiku 5.5
legacy or retired. Watch the Claude Code releases after 2.1.302.

**Gateway exception:** Claude Code 2.1.295 sends background requests behind a Claude apps gateway to Haiku 4.5, falling back
to the session model. That does not apply on this host (direct Anthropic API); re-check if the host ever uses a gateway.

## Sources

1. `anthropics/claude-code` at tag `v2.1.302`, commit `c017428c8c27e604840435048d5bce6a9a22c040`, `CHANGELOG.md`
   (each line read at that commit with `gh api repos/anthropics/claude-code/contents/CHANGELOG.md?ref=c017428c8c27e604840435048d5bce6a9a22c040`
   and the raw accept header):
   - `CHANGELOG.md:642` (under `## 2.1.293`, header at `:640`): "Added Claude Haiku 5.5 (`claude-haiku-5-5`), now the default Haiku model on the Anthropic API — 1M context, $0.10/$0.50 per Mtok ($0.50/$2.50 for prompts over 100K)".
   - `CHANGELOG.md:594` (under `## 2.1.295`, header at `:489`): "Improved background requests behind a Claude apps gateway to use Haiku 4.5 instead of the session's model, falling back to the session's model where the gateway does not serve Haiku 4.5".
   - `CHANGELOG.md:421` (under `## 2.1.296`, header at `:407`): "Fixed token counts for Haiku 5.5 and other models that take only adaptive thinking, which failed behind some gateways and were counted with budget thinking elsewhere".
   - No entry from 2.1.294 to 2.1.302 moves the slot back to Haiku 4.5.
2. <https://code.claude.com/docs/en/model-config>: from v2.1.293 the `haiku` alias resolves to Haiku 5.5 on the Anthropic API;
   Bedrock, Vertex, Foundry and the AWS platform stay on Haiku 4.5.
3. <https://code.claude.com/docs/en/env-vars>: `ANTHROPIC_DEFAULT_HAIKU_MODEL` is also used for background functionality;
   `ANTHROPIC_SMALL_FAST_MODEL` is deprecated. Neither is set on this host (user settings env, project settings, shell,
   `/etc/claude-code` absent; no `settings.local.json`). `CLAUDE_CODE_SUBAGENT_MODEL` is set but governs subagents, not the
   background slot. Read as key names only.
4. <https://platform.claude.com/docs/en/models/haiku-5-5/overview>: Haiku 5.5 `claude-haiku-5-5`, released 2026-10-07.
5. Observed over 7 days (read 2026-10-17 19:2xZ): 509 of 509 Haiku assistant messages in 2309 transcripts are
   `claude-haiku-5-5`, none Haiku 4.5; the usage report shows `claude-haiku-5-5` on 2026-10-11, 10-12, 10-16 and 10-17 and
   no Haiku 4.5 row.

**Untested boundary:** background-slot calls (titles, safety checks) are not labelled in transcripts, so slot use is inferred
from the client default plus the absent override, not counted directly. The 509 messages are subagent and headless Haiku
runs that resolve the same alias. A direct confirmation needs a request-level log of a title call.

## Selection records refreshed with this correction

Each file below was read at the head of this change, then updated by its own route.

| Record | State at `e54f0697` | Route and result |
| --- | --- | --- |
| `manifests/stack.json` (model entry for the background slot, near `:2469`) | named `claude-haiku-4-5-20251001`, release 2025-10-15, "latest Haiku line retained as the owner's dated exception", overturn "An Anthropic Haiku 5.x model ID becomes available" | hand-kept file, edited: the entry is now `claude-haiku-5-5` (release 2026-10-07, source the Haiku 5.5 overview page), with the overturn and scope of the corrected row; `currency_rows` still `["background-haiku"]`; evidence row re-registered |
| `docs/model-currency.md` (the "Currency follows the newest release" paragraph, `:69-71`) | said the slot "retains Haiku 4.5 as a dated exception" and "A published Haiku 5.x ID reopens that selection" | hand-kept file, edited: the slot follows Haiku 5.5 at Claude Code 2.1.302; evidence row re-registered |
| `docs/active-model-currency.md` (`:164-166`, not named by the verdict) | called the October 7 inventory entry a "Haiku 4.5 observed-use declaration" awaiting reconciliation | hand-kept file, edited to state that the inventory row now follows Haiku 5.5 and cites this record; evidence row re-registered |
| `catalogs/foundation/latest-models.json` | already maps `claude-haiku` to `claude-haiku-5-5` and carries no Haiku 4.5 text (`:8`, `:23`, `:24`) | read, no change needed; the verdict's claim that it describes Haiku 4.5 does not hold at the head |
| `catalogs/landscape/final-stack.json` | generated; its only Haiku entry is `claude-code-claude-haiku-5-5` pinned `claude-haiku-5-5` (`:6576-6577`) and it has no Haiku 4.5 text, but its `sources` block records the `sha256` of `manifests/stack.json`, which this change edits | re-run by its generator, `python3 scripts/final_stack.py --write` (documented option; `--check` reported the `stack.json` hash change first); the only difference is that one recorded hash, and the generator re-registered the file; `--check` is clean afterwards |

Other files that mention `claude-haiku-4-5-20251001` (`manifests/candidates.json`, `catalogs/sota-convergence/manifest-20260923.json`,
the 2026-09-27 and 2026-10-07 decision records, `scripts/angle_records.py`, receipts and fixtures) record what a third-party tool
defaults to or what a dated run observed. They are history, not the background-slot selection, and stay as they are.
