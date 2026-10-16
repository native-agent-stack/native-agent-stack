# Model-route consistency and model-currency reporting supersession

Status: proposed for review. Base: `5bab63233ef90260bec4a8ee0cec4f5e4431776c`.
Read date: 2026-10-16. This is the separate binding prerequisite for C2 publication; the privacy-only #1177 rebuild remains independent.

The combined review correction incorporates main at `30542e70560147c19049016d19aa3f264515c92f`; the manifest conflict is resolved by re-registering the retained files from both sides.

## Decision

Use the existing `scripts/validate.py` publication command to check explicit references into `catalogs/foundation/model-currency.json`. The new `catalogs/foundation/model-route-bindings.json` maps stable route IDs from the carried angle record and retained family proposals to inventory row IDs.

The check fails for a missing inventory row, absent binding for an observed route, malformed join, duplicate route identity or incomplete C2 proposal coverage. A route model that differs from the referenced inventory model produces a `blocking: false` notice in the successful JSON summary. It does not fail on an older generation, impose a latest-generation adoption gate or perform an invocation.

## Supersession of publication age enforcement

This decision supersedes the publication-failure behavior in [2026-10-07 model-currency enforcement](2026-10-07-model-currency-enforcement.md). It follows the 2026-10-15 23:39 ET direction to keep the north-star work primary and handle model currency as maintenance, recorded in `direction-cc-20261015T1946Z-north-star-new-wsl-takeover.addendum-19.md`, item 4. That private authority is cited by name only and paraphrased here.

The [2026-10-15 rollover incident](2026-10-15-model-currency-landscape-check.md) records nine October 7 landscape exceptions becoming eight days old at UTC rollover. Publication then failed because time had advanced. The corrected publication path reports those due rows with exit 0 in `model_currency_notices` and appends them to the GitHub Actions step summary. This keeps maintenance work visible without using age alone to prevent publication.

The 42-day release and seven-day landscape windows remain the maintenance windows. `model_currency_problems` still computes their due findings. Malformed JSON, structural errors, invalid or future dates, invalid source references and broken joins continue to fail. The publication caller separates structural problems from age findings; it does not remove the inventory rows or silently refresh their dates. No automatic deployment follows a report.

The daily collector uses the same `model_currency_due` projection and persists `models_past_window`, its detail rows and the session notice. An unreadable or structurally invalid inventory is a `model inventory unreadable` coverage gap. The collector retains recoverable prior inventory findings, labels their earlier origin in JSON and text, and writes them alongside current known counts and the gap. Unreadable prior history is marked unavailable; it does not prevent writing current known counts. With no known counts and incomplete coverage, the existing file remains in place. Age findings and this gap keep the existing exit behavior. The timer's existing `freshness_propose.py --model-currency` pre-step supplies refresh proposals; the collector does not add another proposal invocation.

The notice budget cannot stop collection. It tries full gap phrases, compact named gaps and a coverage-gap count with the actual supplied command/pointers. If no real command fits, the bounded notice omits its inline command; the report still contains `details_command` and all coverage fields. This supersedes the earlier `summary_line` path-length failure at `1b62f8e7d501846abb974622c89111f6f794ae9b:scripts/currency_due.py:438-447`. Three simultaneous gaps, long paths, unreadable prior state and retained-origin rendering have fail-first controls. Existing route-kind/identity-shape and PyPI mismatch guards gain explicit negative tests without claiming baseline defects.

For already reviewed inputs, read the carried angle candidates and, when present, #1177's `sweep-manifest.json`. Match their stable IDs through the new mapping; retain their historical bytes and votes. Known `cx/`, `codex/`, `mc/` and `muse-code/` prefixes are removed only for the comparison notice. A non-model placeholder on the rejected Muse foreign-subscription route remains visible as a difference notice; its binding names the Full family for traceability and does not qualify that route.

## C2 publication contract

Alongside `evidence/artifacts/model-routes-sweep-merge-20261015/returns.json`, C2 supplies `route-currency.json`:

```json
{
  "schema_version": 1,
  "routes": [
    {
      "repository": "EXACT discovery.proposed identity",
      "route_id": "stable-route-id",
      "model_id": "selected model ID",
      "model_currency_id": "existing models[].id"
    }
  ],
  "components": [
    {
      "repository": "EXACT component-only discovery.proposed identity",
      "package_currency_id": "existing packages[].id"
    }
  ]
}
```

The union of route and component identities must equal the retained `discovery["model-routes"].proposed` set, without duplicates. Every C2 route ID must already be registered in `model-route-bindings.json`, and its inline `model_currency_id` must agree with that registry. Each binding now declares `kind: "route"` and its exact retained `repositories` aliases. The C2 repository must match that route identity; a gateway proposal cannot borrow a valid model route ID to omit its package row. New route IDs therefore require a registry entry with their retained identities before publication. An inline inventory ID cannot bypass this join.

Component-only proposals such as the gateway reference an existing package row. A component-only table may omit `routes`. GitHub identity comparisons reuse `scripts/host_receipts.py`'s `normalize_repository()`; this accepts case and equivalent URL forms while retaining the exact proposal spelling for coverage. PyPI project names use the existing `scripts/starred_protected.py::package_name()` PEP 503 normalizer: lowercase and collapse runs of `.`, `_`, and `-` to `-`. Scheme, host and project-path shape are still checked, and exact retained proposal spelling remains the separate coverage key. A model route cannot be relabeled as an unrelated component to bypass its row reference. Missing fields fail consistency; an older selected model still passes with a notice. The table also follows the ordinary evidence-registration rules.

That normalizer dependency is declared in the verdict gate's `TRUST_PATHS`. The
native advisory observation is appended under the existing
[dated-delta contract](../../blueprints/runtime-workers/openhands/evidence/advisory-gate-deltas.md),
using `GitTree` and `derive_ci_protected` at published commit
`cc308901f327b04cdd47c356d0726b00c88f0f07`. It derives 354 entries, including
one new conservative entry at `scripts/starred_protected.py:71`. This is static
accounting for the imported module's path-shape helper, not a claim that the
normalizer executes it or reads a filesystem path. Earlier baselines/deltas
remain unchanged, and the advisory grants no execution permission. Both existing
inventory checks failed before these registrations and passed after them.

## Inventory refresh proposal

Add held entries for GPT-6 Luna, Claude Haiku 5.5, Muse Wonder, Muse Wonder Full and hosted Muse Spark 1.3. The [source record](../../evidence/artifacts/model-route-currency-consistency-20261016/sources.json) retains the provider model pins, dated launch sources and bounded public excerpts.

The earlier background-Haiku successor record asked for comparison and migration review; it contained no measured reason to retain Haiku 4.5. Supersede that temporary staging row with a **held Haiku 5.5 proposal for normal refresh**. No retention exception is asserted and no runtime configuration changes here. The earlier record remains in Git history and the dated landscape decision; application and native invoke evidence remain separate work.

The exact Wonder Full identifier is supported by the published Muse 1.4.7 reader receipt, while the vendor announcement names the product and launch date. It remains held, with the Muse fence and route-approval restrictions intact.

## Verification and limitations

The missing-reference check failed first because the old CLI accepted a nonexistent row. Additional fail-first checks cover an omitted C2 join, missing proposal coverage, ignored GPT route data, binding removal and the background proposal. A stale-generation fixture succeeds and emits a notice. The stale-inventory CLI case failed first with exit 1; after the change it returns 0 and keeps the due row visible in the JSON output and step summary, appending to existing summary content. Malformed JSON, structural, date-format, source and future-date controls still fail. The existing model-currency suite and publication fixture command are reused; no new script or dependency is introduced.

Tests exercise the publication boundary with synthetic documents. They establish join behavior, not provider capability, live model currency, account access, deployment or quality. New model-source changes belong to normal maintenance and reported refresh.

The review correction adds fail-first checks for equivalent GitHub repository spelling, component-only C2 proposals, unregistered C2 route IDs, the daily inventory-age feed, unreadable/invalid inventory gaps, the current guide and private citations. Duplicate binding/source/repository, malformed row and GPT-layer-count guards already worked; isolated guard-removal controls establish that the new tests detect their removal. They are not claimed as baseline failures.

Main integration also exposed a custody-test optimization that treated HEAD blobs as unchanged checkout files. The retained final-stack input still exactly matches the published run pin, but a pending merge changes the checkout before HEAD advances. The existing helper in `tests/test_provenance_digest_custody.py` at the base is corrected to fetch pinned blobs for modified paths. A synthetic case failed before this correction; the unchanged-file optimization has a passing control. The accepted public pin and digest rules are unchanged.

The edited October 7 decision and the two touched evidence records (`fill-source-review.json` and `j826-checks.json`) now cite private source packets and proposals by name. The command-output digests in `j826-checks.json` were omitted while its summaries remain. This is a bounded cleanup: the untouched `handbook-projection.json` (lines 40 and 47) and `fill-checks.json` (line 59) still contain pre-existing digest residue, retained as history under addendum-22. Those records are not changed by this PR. The privacy regression first failed on the two citation paragraphs and touched field locations, then passed; failure output contains counts/locators only. Git history is unchanged.

The [primary capture index](../../evidence/artifacts/model-route-currency-consistency-20261016/UPSTREAM-PINS-20261016.json) separates dated vendor excerpts from our findings. The co-op receives the named public base-validator copy for independent review; the Full capture includes only the already-public native receipt lines. No private record or unretained response is hashed.

### Follow-up: active-model coverage

The timer prerequisite is satisfied by `stack-currency-timer-receipt-20261016.md`, cited by name only. Its persisted `active_models: unknown` is a real coverage gap. The [bounded diagnosis](../../evidence/artifacts/model-route-currency-consistency-20261016/active-model-coverage-followup.json) verifies the versioned catalog under the lane and timer interpreters and checks the deployed source. The collector discards the diagnostic subtype, so the retained receipt cannot distinguish timeout from another process/report failure. The service duration is consistent with a timeout but does not prove one.

The host owner should retain a sanitized failure category and duration on the next approved collector run. A full host-selector rerun would scan protected private roots outside this lane. This remains a nonblocking Follow-up; no timeout, timer or host settings are changed speculatively.

## Sources

- Existing validator and tests at `5bab63233ef90260bec4a8ee0cec4f5e4431776c`: `scripts/validate.py`, `tests/test_model_currency.py`, `tests/test_validate.py`.
- Existing repository equivalence at that pin: `scripts/host_receipts.py:547`, `normalize_repository()`, reused through a lazy import to preserve both CLI and package import paths.
- [PEP 503, Normalized Names](https://peps.python.org/pep-0503/#normalized-names), read 2026-10-16; existing implementation `scripts/starred_protected.py:48` at `94b4ba5515da5159c3b50d8b7edef40b7c4bbbc2`. Both public retained family identity maps supply the new route aliases named in the binding registry's `identity_sources`.
- Existing custody helper at that pin: `tests/test_provenance_digest_custody.py`, `pin_blob_digests()`. Its public-pin lookup is retained; the optimization now distinguishes modified checkout files from unchanged HEAD bytes, with a fail-first synthetic regression.
- OmniRoute v3.8.51, commit `c1e30b7676975feb298b49eff6ff58923c04b89e`: [Codex registry](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/config/providers/registry/codex/index.ts) declares `codex`/`cx`; [Muse registry](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/config/providers/registry/muse-code/index.ts) declares `muse-code`/`mc`. Read 2026-10-16; prefix removal is a comparison convenience, not route availability evidence.
- [python/cpython v3.13.16, Lib/unittest/case.py](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py): the installed test harness and assertions.
- [GitHub Actions job-summary protocol](https://docs.github.com/en/actions/reference/workflow-commands-for-github-actions#adding-a-job-summary), read 2026-10-16: append Markdown to the runner-provided `GITHUB_STEP_SUMMARY` file.
- The superseded [October 7 enforcement](2026-10-07-model-currency-enforcement.md), [October 15 rollover incident](2026-10-15-model-currency-landscape-check.md), and the name-only addendum-19 item 4 citation above establish the policy change.
- [OpenAI API changelog](https://developers.openai.com/api/docs/changelog#september-2026): GPT-6 Luna launch on September 22, 2026; [current Luna page](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [Anthropic October 7 release](https://platform.claude.com/docs/en/release-notes/overview#october-7-2026): Haiku 5.5; [current Haiku page](https://platform.claude.com/docs/en/models/haiku-5-5/overview).
- [Meta Wonder and Full announcement](https://dev.meta.ai/resources/blog/build-with-muse-wonder): October 12, 2026; [current models](https://dev.meta.ai/docs/models).
- [Meta Spark 1.3 announcement](https://research.meta.ai/blog/introducing-muse-spark-1-3): September 2, 2026; current hosted Spark entry on the models page.
- [Published Muse fence record at the base](https://github.com/native-agent-stack/native-agent-stack/blob/5bab63233ef90260bec4a8ee0cec4f5e4431776c/docs/decisions/2026-10-14-muse-file-fence.md#L123): the native Full identifier and historical execution boundary.

Replace this reference contract if the C2 output schema changes through a reviewed amendment. Newer vendor models update maintenance notices and inventory proposals through normal refresh; no stale-model failure gate is introduced.
