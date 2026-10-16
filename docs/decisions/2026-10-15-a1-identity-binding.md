# Decision: bind A1 capability evidence to the current candidate

A screened candidate could keep a `CONVERGED` label after its repository or
pin changed, because A1 required a sourced score without comparing the
citation identity. At base `51279d4f63d87b2d19de722cad786d7293417ac8`,
changing either field while preserving the citations still passed validation.
The resolved-pin syntax also excluded versioned provider model identifiers.

## Decision and sources

Reuse the complete repository/pin equality already enforced for A6 in
[the native reference implementation](https://github.com/seathatflowsinourveins/native-agent-stack/blob/51279d4f63d87b2d19de722cad786d7293417ac8/scripts/angle_records.py#L178-L187).
A screened A1 must have at least one source naming the candidate's current
repository and complete pin. Repository citations carry this identity today.
URL and receipt citations may now carry the same pair, required together by
the existing JSON Schema draft 2020-12 validator. Validation refuses a stale
or absent binding; derivation independently yields `INSUFFICIENT`.

The source schema uses `dependentRequired` from
[python-jsonschema/jsonschema at a7277432b0f7bcd0551f6e589d30457017125df4](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_keywords.py#L243-L254).
The pinned source was read at 2026-10-15T13:50:29Z and its implementation
matched the installed jsonschema 4.26.0 function exactly. No dependency or
replacement validator is introduced.

A bound URL or receipt may explicitly identify a model pin with
`pin_kind: model`. The initial name grammar at
`0d87fdae8b19fc4825401d8bf03c687a301f9e98` was wrong: it also accepted floating
aliases. It is replaced by exact provider-documented snapshot identities.
The supported roster includes current and historical snapshots from the
pinned provider sources. These are identity-validation inputs, not a model
selection or capability qualification. Currency is separate maintenance: an
older exact snapshot is accepted, including retired snapshots retained as
historical evidence. No age or generation cutoff is applied. Unverified
provider identities remain unscreened until their provider source is admitted;
a name's numeric shape grants no resolution.

The currency separation is recorded by the
[2026-10-16 clarification](2026-10-16-preopening-receipt-ownership-v2-replay.md#snapshot-recognition-and-currency),
attributed to the privately recorded operator decision using the existing
[basis convention at 1b633d86, schema.json:475-478](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/catalogs/landscape/angles/schema.json#L475-L478).
The [2026-09-27 model-currency decision](2026-09-27-model-currency.md) supplies
historical configuration and maintenance background.

The OpenAI identities are present in
[`openai/openai-python` v3.31.0 at 86cae50785fb7b7bf2a5d2383370b214b304acd2, chat_model.py:8-96](https://github.com/openai/openai-python/blob/86cae50785fb7b7bf2a5d2383370b214b304acd2/src/openai/types/shared/chat_model.py#L8-L96)
and the official
[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) and
[Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) snapshot tables.
Additional dated OpenAI snapshots are present in
[`all_models.py:14-28` at the same pin](https://github.com/openai/openai-python/blob/86cae50785fb7b7bf2a5d2383370b214b304acd2/src/openai/types/shared/all_models.py#L14-L28).
The official [GPT-5.4 snapshot table](https://developers.openai.com/api/docs/models/gpt-5.4)
also retains the exact historical `gpt-5.4-2026-03-05` identity. The SDK's alias
literals are excluded; accepting a client spelling does not make it a snapshot.
The current Anthropic identities are present in
[`anthropics/anthropic-sdk-python` v1.15.0 at bcd55fe1d3f0f1240765f8cef04295b67337f55a, model.py:8-27](https://github.com/anthropics/anthropic-sdk-python/blob/bcd55fe1d3f0f1240765f8cef04295b67337f55a/src/anthropic/types/model.py#L8-L27).
Anthropic's [model-versioning contract](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)
identifies its dateless model IDs from generation 4.6 onward as pinned
snapshots; this differs from earlier dateless aliases. Requiring a calendar
suffix would therefore reject a documented current snapshot. The
[provider source record](../../evidence/artifacts/angle-records-a1-20261015/provider-snapshot-sources.json)
retains the SDK pins and official documentation references. Older dated
Anthropic snapshots are retained from
[v0.51.0 at e42451ab3f14443c0ed8076b17032a6d8986b6bf, model.py:11-20](https://github.com/anthropics/anthropic-sdk-python/blob/e42451ab3f14443c0ed8076b17032a6d8986b6bf/src/anthropic/types/model.py#L11-L20)
and
[v0.55.0 at 472c51ebec9fca647df9f39e0da1ca77c221a62f, model.py:14-22](https://github.com/anthropics/anthropic-sdk-python/blob/472c51ebec9fca647df9f39e0da1ca77c221a62f/src/anthropic/types/model.py#L14-L22).
Historical dated IDs remain recognizable when a later SDK omits them.
The pre-opening correction excludes `claude-mythos-preview`: its SDK enum
membership does not establish that it is a pinned snapshot under the cited
versioning contract. The supported roster is 83; the source audit records the
excluded unverified spelling without changing the historical source captures.
`test_documented_historical_snapshots_are_not_refused_for_age` covers old
OpenAI and Anthropic generations, both dated and documented dateless forms.

Model typing cannot fall through to the software commit/release parser.
The exact snapshot still needs a current bound source; changing the model
while retaining the old citation reports the identity-binding error rather
than claiming that the new, documented snapshot is unresolved.
The [old preflight diagnostic at 0d87fdae:133-137](https://github.com/native-agent-stack/native-agent-stack/blob/0d87fdae8b19fc4825401d8bf03c687a301f9e98/scripts/angle_records.py#L133-L137)
conflated those causes; `test_model_pin_change_keeps_the_old_screen_bound_to_the_old_model`
asserts the binding cause explicitly.

A receipt's citation labels alone cannot establish A1 identity. The qualifier
now reads its JSON through the native source loader and compares the receipt's
own repository and full pin, following the existing
[`validate_comparison` receipt equality at 0d87fdae, angle_records.py:203-209](https://github.com/native-agent-stack/native-agent-stack/blob/0d87fdae8b19fc4825401d8bf03c687a301f9e98/scripts/angle_records.py#L203-L209).
A stale, foreign, malformed or unread A1 receipt refuses. The native `derive`
entry point accepts the same optional source loader; without it, receipt-only
A1 evidence yields `INSUFFICIENT`. A correctly labelled repository citation
cannot mask a receipt with another identity.

The [pre-opening receipt/replay decision](2026-10-16-preopening-receipt-ownership-v2-replay.md)
adds own kind/candidate fields to the receipt contract and records the native
expanded-field replay correction. It keeps FINAL admission disabled.

The same source loader is carried into the native generated angle summary,
whose caller is
[`final_stack.build_document` at 0d87fdae:1042](https://github.com/native-agent-stack/native-agent-stack/blob/0d87fdae8b19fc4825401d8bf03c687a301f9e98/scripts/final_stack.py#L1042).
`test_a1_receipt_identity_is_preserved_in_the_native_summary` fails without
that propagation, then checks the accepted summary, retained receipt source
and refusal after the receipt's own pin changes. This is an A1 receipt data
flow change; the separate generation-only import work stays in #1167.

The rejected alternatives are a permissive name grammar and inference from
any nonempty pin. Both can promote mutable aliases. Keeping only dated or
commit/release syntax also rejects current provider snapshots. A future
provider resolver can supersede the exact supported identities only with
pinned provider evidence and regression controls preserving alias refusal.

## Verification and limits

The native `validate_record` and `derive` interfaces are the test boundaries.
The three original software identity controls replace the shared fixture's
A1 URL with a base-compatible repository citation before the mutation. Their
before/after results establish repository/pin binding. The original aggregate
base replay also encountered failures caused by the shared fixture's new URL
fields, which the old schema disallows. Those aggregate failures are fixture
compatibility results and must not be counted as additional causal controls.
Provider-model acceptance separately exercises the new URL identity contract.
The [check record](../../evidence/artifacts/angle-records-a1-20261015/checks.json)
retains the historical results and this distinction; no synthetic provider
name is treated as provider-documented evidence.

The fold's fail-first cases at the frozen head separately reject floating or
unverified model identities, block model-typed software-pin fallback, read
receipt-owned identity, refuse unread receipt derivation, and identify the
correct cause of a stale model binding. The supported current snapshots and
native software identities are positive controls.

All capability examples in the regression module are synthetic. The checks
verify identity binding, including retained receipt contents; they do not
authenticate upstream pages or execute provider capability tests. No existing candidate is newly screened,
selected or qualified, and FINAL admission remains under its separate
redesign. Source-bound A1 remains one necessary input to multi-angle
convergence, never sufficient evidence for adoption by itself.
