# Model-route consistency and model-currency reporting supersession

Status: proposed for review. Base: `5bab63233ef90260bec4a8ee0cec4f5e4431776c`.
Read date: 2026-10-16. This is the separate binding prerequisite for C2 publication; the privacy-only #1177 rebuild remains independent.

## Decision

Use the existing `scripts/validate.py` publication command to check explicit references into `catalogs/foundation/model-currency.json`. The new `catalogs/foundation/model-route-bindings.json` maps stable route IDs from the carried angle record and retained family proposals to inventory row IDs.

The check fails for a missing inventory row, absent binding for an observed route, malformed join, duplicate route identity or incomplete C2 proposal coverage. A route model that differs from the referenced inventory model produces a `blocking: false` notice in the successful JSON summary. It does not fail on an older generation, impose a latest-generation adoption gate or perform an invocation.

## Supersession of publication age enforcement

This decision supersedes the publication-failure behavior in [2026-10-07 model-currency enforcement](2026-10-07-model-currency-enforcement.md). It follows the 2026-10-15 23:39 ET direction to keep the north-star work primary and handle model currency as maintenance, recorded in `direction-cc-20261015T1946Z-north-star-new-wsl-takeover.addendum-19.md`, item 4. That private authority is cited by name only and paraphrased here.

The [2026-10-15 rollover incident](2026-10-15-model-currency-landscape-check.md) records nine October 7 landscape exceptions becoming eight days old at UTC rollover. Publication then failed because time had advanced. The corrected publication path reports those due rows with exit 0 in `model_currency_notices` and appends them to the GitHub Actions step summary. This keeps maintenance work visible without using age alone to prevent publication.

The 42-day release and seven-day landscape windows remain the maintenance windows. `model_currency_problems` still computes their due findings. Malformed JSON, structural errors, invalid or future dates, invalid source references and broken joins continue to fail. The publication caller separates structural problems from age findings; it does not remove the inventory rows or silently refresh their dates. No automatic deployment follows a report.

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

The union of route and component identities must equal the retained `discovery["model-routes"].proposed` set, without duplicates. Component-only proposals such as the gateway reference an existing package row and must match its canonical GitHub repository or PyPI project identity. A model route cannot bypass its model-row reference by being mislabeled as an unrelated component. Every model route references an existing model row. Missing fields fail consistency; an older selected model still passes with a notice. The table must also be registered as published evidence under the normal ledger/manifest rules.

## Inventory refresh proposal

Add held entries for GPT-6 Luna, Claude Haiku 5.5, Muse Wonder, Muse Wonder Full and hosted Muse Spark 1.3. The [source record](../../evidence/artifacts/model-route-currency-consistency-20261016/sources.json) retains the provider model pins, dated launch sources and bounded public excerpts.

The earlier background-Haiku successor record asked for comparison and migration review; it contained no measured reason to retain Haiku 4.5. Supersede that temporary staging row with a **held Haiku 5.5 proposal for normal refresh**. No retention exception is asserted and no runtime configuration changes here. The earlier record remains in Git history and the dated landscape decision; application and native invoke evidence remain separate work.

The exact Wonder Full identifier is supported by the published Muse 1.4.7 reader receipt, while the vendor announcement names the product and launch date. It remains held, with the Muse fence and route-approval restrictions intact.

## Verification and limitations

The missing-reference check failed first because the old CLI accepted a nonexistent row. Additional fail-first checks cover an omitted C2 join, missing proposal coverage, ignored GPT route data, binding removal and the background proposal. A stale-generation fixture succeeds and emits a notice. The stale-inventory CLI case failed first with exit 1; after the change it returns 0 and keeps the due row visible in the JSON output and step summary, appending to existing summary content. Malformed JSON, structural, date-format, source and future-date controls still fail. The existing model-currency suite and publication fixture command are reused; no new script or dependency is introduced.

Tests exercise the publication boundary with synthetic documents. They establish join behavior, not provider capability, live model currency, account access, deployment or quality. New model-source changes belong to normal maintenance and reported refresh.

## Sources

- Existing validator and tests at `5bab63233ef90260bec4a8ee0cec4f5e4431776c`: `scripts/validate.py`, `tests/test_model_currency.py`, `tests/test_validate.py`.
- [python/cpython v3.13.16, Lib/unittest/case.py](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py): the installed test harness and assertions.
- [GitHub Actions job-summary protocol](https://docs.github.com/en/actions/reference/workflow-commands-for-github-actions#adding-a-job-summary), read 2026-10-16: append Markdown to the runner-provided `GITHUB_STEP_SUMMARY` file.
- The superseded [October 7 enforcement](2026-10-07-model-currency-enforcement.md), [October 15 rollover incident](2026-10-15-model-currency-landscape-check.md), and the name-only addendum-19 item 4 citation above establish the policy change.
- [OpenAI API changelog](https://developers.openai.com/api/docs/changelog#september-2026): GPT-6 Luna launch on September 22, 2026; [current Luna page](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [Anthropic October 7 release](https://platform.claude.com/docs/en/release-notes/overview#october-7-2026): Haiku 5.5; [current Haiku page](https://platform.claude.com/docs/en/models/haiku-5-5/overview).
- [Meta Wonder and Full announcement](https://dev.meta.ai/resources/blog/build-with-muse-wonder): October 12, 2026; [current models](https://dev.meta.ai/docs/models).
- [Meta Spark 1.3 announcement](https://research.meta.ai/blog/introducing-muse-spark-1-3): September 2, 2026; current hosted Spark entry on the models page.
- [Published Muse fence record at the base](https://github.com/native-agent-stack/native-agent-stack/blob/5bab63233ef90260bec4a8ee0cec4f5e4431776c/docs/decisions/2026-10-14-muse-file-fence.md#L123): the native Full identifier and historical execution boundary.

Replace this reference contract if the C2 output schema changes through a reviewed amendment. Newer vendor models update maintenance notices and inventory proposals through normal refresh; no stale-model failure gate is introduced.
