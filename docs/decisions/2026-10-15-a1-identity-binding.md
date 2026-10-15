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
`pin_kind: model`. It must use a versioned identifier with a named prefix,
a numeric generation and optional named suffixes. This supports the model
identities already retained in
[the route record](../../catalogs/landscape/angles/foundation-model-routes.json)
without treating an untyped model spelling or an unversioned routing alias
as a resolved commit/release. Identity typing is part of the cited evidence,
so a model change cannot reuse the old source binding.

The rejected alternative was to infer model resolution from any nonempty
pin string. That would also admit `HEAD`, generic aliases and unresolved
route names. Keeping only commit/release syntax would preserve the current
false refusal of documented model identities. An independently retained
provider resolution mechanism could supersede the explicit model-source
contract if it can verify the same identity without promoting aliases.

## Verification and limits

The native `validate_record` and `derive` interfaces are the test boundaries.
Four controls ran against the exact landed base before the correction:
pin mutation, repository mutation, stale-identity derivation and resolved
model identity acceptance. They produced four assertion failures and three
model subtest errors. The affected control names and final commands are
retained in the [check record](../../evidence/artifacts/angle-records-a1-20261015/checks.json).
Additional controls retain valid commit/release identities and reject generic,
partially bound or untyped model sources.

All capability examples in the regression module are synthetic. The checks
verify structural binding; they do not authenticate upstream citations or
execute provider capability tests. No existing candidate is newly screened,
selected or qualified, and FINAL admission remains under its separate
redesign. Source-bound A1 remains one necessary input to multi-angle
convergence, never sufficient evidence for adoption by itself.
