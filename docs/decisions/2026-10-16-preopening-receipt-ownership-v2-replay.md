# Decision: bind receipt ownership and replay native expanded V2 members

A1 and A6 evidence must belong to the named candidate, even when a sibling
route uses the same repository and pin. A completed native V2 rediscovery
followed by substantive refutation must also resolve its survivor history.
This pre-opening correction enforces those contracts while FINAL admission
remains disabled. It selects no candidate, invokes no model and changes no
PIN source-proof function.

## Receipt content belongs to its candidate

At base `1b633d861518fa0d299279b1cfaec11d0fb47f82`, native
[`bound_a1_sources`:120-142](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/scripts/angle_records.py#L120-L142)
checked receipt repository/pin, and
[`validate_comparison`:256-274](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/scripts/angle_records.py#L256-L274)
already checked comparative kind and native results. Neither bound a receipt's
own candidate id. Reusing a correctly labelled receipt for a sibling route
could therefore keep capability or comparative evidence accepted.

The supported content contract is now explicit. A1 requires own
`kind: capability`, `candidate_id`, repository and complete pin. A6 retains
`kind: comparative`, native output arms, completion and confounds, and adds
own `candidate_id`. Each id equals `candidate.id`. Generic citation objects
continue to use `kind: receipt` to identify the file; a citation label cannot
replace the content checks. The schema's two receipt definitions document
these producer contracts. Required-field validation reuses
[`jsonschema` 4.26.0 at a7277432b0f7bcd0551f6e589d30457017125df4, _keywords.py:304-309](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_keywords.py#L304-L309).
The fresh [source check](../../evidence/artifacts/angle-records-preopening-20261016/source-checks.json)
confirms that exact function matches the installed package.

Direct derivation also requires a present repository rather than accepting
two missing values as an equality. Model typing uses a citation bound to the
current repository/pin. An unrelated model citation cannot reclassify valid
software evidence. A known model with an old typed citation still reports
the current-identity binding error; an unresolved or untyped model still
reports the resolution error. The schema-pair control validates a complete
positive before deleting either field and checks the nested dependentRequired
error, so reverting the entire source schema cannot pass it accidentally.

## Snapshot recognition and currency

The roster excludes `claude-mythos-preview`. Presence in the pinned Anthropic
client enum alone does not prove snapshot immutability under the already
cited provider versioning contract. The corrected audit covers 83 documented
identities. Current and historical exact snapshots remain accepted, including
dated and documented dateless identities. No age or generation cutoff is added.

Currency separation follows an operator decision, recorded privately, using
the existing [schema basis convention at :475-478](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/catalogs/landscape/angles/schema.json#L475-L478).
The [model-currency decision](2026-09-27-model-currency.md) tracks maintenance
and evaluation gates. This correction changes identity recognition and receipt
ownership; it makes no model-capability or availability claim.

## Replay the member that native discovery actually screened

Native [`v2_expand_field`:266-299](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/scripts/saturation_ledger.py#L266-L299)
joins discovery evidence to frozen members. Rediscovering an existing identity
can add retained raw references without changing that identity. The native
[`check_v2_layer` replay at :1179-1208](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/scripts/saturation_ledger.py#L1179-L1208)
recomputes screens and outcomes from that expanded member.

The FINAL replay helper incorrectly used the original frozen member instead.
Its evidence references then differed from the retained outcome, so it refused
a substantive refutation and left a false unresolved survivor. The correction
reads the retained raw rounds through the native confined source reader and
reuses v2_expand_field before selecting the candidate. Missing or malformed
rounds still refuse. No original-field fallback is introduced.

The public native regression exercises converter, retained appender, ledger
checker and survivor replay, with and without rediscovery. Both histories pass
native integrity and contain no material pending candidate; the rediscovered
case failed before the fix. A separate exact-#1167 qualification reproduction
at `bd0474d3615a18f60d8b881df747a7dcc6a2e997` returned an unresolved-survivor
refusal before the correction. Loading only this corrected helper into an
isolated process makes that unchanged read-only qualifier return qualified
with admission_enabled false. No frozen file, head or policy is modified by
that source-composition check. Final landed composition remains a prerequisite
to the later activation and its second-party current-main receipt.

## Symbolic reopening namespaces come from the native producer

Both namespace citations are explicit: native
[`external_triggers`:1463-1468](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/scripts/saturation_ledger.py#L1463-L1468)
emits `receipt_staleness:`, and
[the same producer at :1483-1493](https://github.com/native-agent-stack/native-agent-stack/blob/1b633d861518fa0d299279b1cfaec11d0fb47f82/scripts/saturation_ledger.py#L1483-L1493)
emits `catalog-freshness:`. These are the qualification correction's two
symbolic namespaces. Other references remain confined file dependencies;
post-anchor symbolic reopening still refuses under native history policy.

## Evidence and activation prerequisite

The [check record](../../evidence/artifacts/angle-records-preopening-20261016/checks.json)
retains fail-first and bounded native results with their limits. Synthetic
controls establish receipt ownership and native replay behavior, not candidate
superiority, remote-source authenticity or real capability. Activation waits
for this follow-up and the qualification/PIN-RULES prerequisites to land, then
for the co-op's current-main receipt and independent reads. Passing these
fixtures alone does not authorize FINAL.
