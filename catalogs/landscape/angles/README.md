# Layer angle records

One JSON record names one `(catalog, layer_id)`. The filename is
`<catalog>-<layer_id>.json`; `schema.json` uses JSON Schema draft 2020-12.
`scripts/final_stack.py --check` validates every record with the installed
python-jsonschema 4.26.0 validator, re-derives its verdict and includes the
summary in `catalogs/landscape/final-stack.json`.

The four initial records cover native clients, workers, agent SDKs and model
routes. They retain the twenty runtime candidates plus Muse Code and thirteen
model-route rows. A record adds evidence without selecting a catalog winner.
The model-routes row has no catalog verdict or sweep at this base; the generator
shows that initial evidence as an unswept row with no winner. Every other layer
has an explicit missing-record gap.

## Versioned derivation

`angle-convergence/2` is implemented in `scripts/angle_records.py`. Scores are
`+`, `0`, `-`, or `U` (unverified). A scored angle needs a source. Weights must
sum exactly to one, and `weights_stated_at` must strictly precede every angle's
`read_at`. A URL's source read must not follow its assessment.

| Angle | Meaning | Default weight |
| --- | --- | --- |
| A1 | Capability at the pin; installs and smokes belong here | 0.20 |
| A2 | Upstream engineering quality | 0.20 |
| A3 | Community consensus | 0.15 |
| A4 | Net usage | 0.15 |
| A5 | Published evaluations | 0.20 |
| A6 | Comparative measured runs with retained native results and confounds | 0.10 |

Apply these rules in order:

1. A hard disqualifier (`missing_capability`, `abandoned`) yields
   `REJECTED`. An entitlement/terms conflict is `missing_capability`.
2. An unscreened A1 or fewer than four sourced angles with positive weights
   yields `INSUFFICIENT`.
3. Both a positive and a negative sourced angle yield `DISAGREE`; the record
   must name `measure_next`.
4. `CONVERGED` requires A1 positive, A2 not negative, two of A3/A4/A5 positive,
   no negative angle, and at least one of A5/A6 positive. Without comparative
   A6 it is `CONVERGED, provisional (A6 pending)` (`provisional: true`).
5. Otherwise the verdict is `INSUFFICIENT`.

Licence is a separate `licence_note` with `spdx_id` (or null when unknown),
source, UTC `read_at`, and a compliance note. It never changes a score,
derived verdict or arm list. Entitlement/terms conflicts continue to be
missing capability; changing a licence note alone cannot change derivation.

The weighted score and coverage are sums over sourced, active angles. They
remain reported values; this sign rule does not introduce a numerical
acceptance threshold. Usage and popularity cannot admit a candidate alone.
When `published_evaluations_available` is explicitly false, the fixed rule
transfers A5's weight to A6. Null means availability is unverified and keeps
the stated weights. Failure to find a row is not proof that no evaluation
exists. The initial agent-SDK record retains that uncertainty.

V2 followed visible runtime v1 scores. The records disclose that order and
retain the previous verdicts; the public source receipt retains the v1 sign
matrix. Fresh primary reads follow the weight statement. This is disclosed
re-verification, not a blind or preregistered original scoring exercise.
Some former signs cannot be reproduced from the bounded fresh sources and
therefore remain mixed or unverified. Pi's former smoke no longer supplies
an outcome angle, so it is insufficient under v2.

## Sources and measurement boundaries

Sources are one of a repository URL/full commit/path/line, a public URL with
its UTC read time, or a committed receipt path. Repository reads used the
registered exact mirror commits with lazy fetch and optional locks disabled.
UNMIRRORED and unresolved pins remain explicit gaps. Private coordination
inputs, account details and their digests are not publication sources.

A2 retains OpenSSF Scorecard's published result plus GitHub release and CI
snapshots. A missing Scorecard result remains a gap. Its assessed commit can
also differ from the capability pin. A3 uses deps.dev's project fields; a
star/fork snapshot is a weak community proxy, not a measured independent
consensus or trajectory. A4 uses npm's published downloads and OpenRouter's
opt-in app rankings, whose populations differ. A5 keeps the published
Terminal-Bench agent/model/effort/date row and Artificial Analysis's model
row; neither is a controlled comparison on this workload. No candidate
install or model call is performed by the generator.

A6 additionally validates a comparative receipt with `kind: comparative`,
`evidence_class: native_proven`, `completed: true`, `harness` of `Harbor`,
`promptfoo` or `paired`, the candidate's exact `repository` and `pin`, and
nonempty `confounds`. Its `arms` must include at least two distinct `id`
values with nonempty committed `native_output` artifacts. The generator
records those artifacts' hashes; it does not reproduce an upstream metric.
A comparative flag over a smoke receipt fails the check. No initial record
claims this comparative evidence.

## FINAL is an explicit, separately checked state

The existing component-matrix `current` and `converged` statuses remain
distinct from the protocol's `FINAL`. A landscape row or its angle record
can explicitly carry `terminal_state: FINAL`; a landscape `verdict_status:
FINAL` is also recognized. An explicit marker cannot bypass verification.

For every FINAL winner the generator requires:

1. A recorded verdict, evidence class, retained and hash-bound verdict wave,
   and `next_review`.
2. A matching winner/run pin in `runs[]`.
3. Exactly one CONVERGED angle candidate at that repository and run pin, with
   a bound `final_evidence` entry and an upstream E2E receipt.
4. A bound invocation receipt with positive calls in a measured window, or
   a nonempty recorded reason for non-invocation.

`final_evidence` names `candidate_id`, `run_pin`, `e2e_receipt`,
`invoke_receipt`, and `not_invoked_reason`. The E2E JSON receipt must have
`kind: upstream_e2e`, `evidence_class: native_proven`, `success: true`, a
matching repository/pin, pinned upstream source citations, and successful
`install` and `test` command phases. The invocation JSON receipt must have
`kind: invocation`, native evidence at the matching repository/pin, positive
integer `calls`, and ordered `window_start`/`window_end` timestamps.
Installation is not invocation. Fixture receipts exercise these checks but
are not published candidate qualification.

No initial layer is marked FINAL. Claude Code and Codex have provisional
source-based angle convergence; exact catalog-winner/run/angle pin alignment
and bound E2E/invoke receipts remain gaps. The model routes document vendor
entitlement mechanisms without certifying any deployed account or pool.
The Muse subscription outside Muse Code is rejected by the vendor's explicit
terms. Its separately entitled API arms are NOT ADOPTED in the
subscription-oriented foundation; Muse Code with Muse Wonder Full remains
TRIAL. Report-only pin-drift and review-age flags stay report-only on other
layers.

## Refresh and validation

Use the existing evidence registration helper for changed records, sources,
schema, documentation and checks, then regenerate the final-stack file:

```sh
python3 scripts/final_stack.py --write
python3 scripts/validate.py
python3 -m unittest tests.test_angle_records tests.test_final_stack tests.test_resolution_protocol_docs
python3 scripts/final_stack.py --check
python3 scripts/final_stack.py --check --today "$(date -u +%F)"
```

The last two commands are the final-stack shard-0 steps. The named modules
are bounded verification; they do not authorize a full-suite run or a
candidate comparison. Publication still requires the staged-diff gitleaks
check, the privacy scans and independent review.

## Primary references

- [python-jsonschema/jsonschema@a7277432b0f7bcd0551f6e589d30457017125df4](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L307)
  (v4.26.0), `check_schema`, `iter_errors` at line 349 and `Draft202012Validator`
  at line 812; [_format.py:21](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_format.py#L21),
  `FormatChecker`.
- [JSON Schema draft 2020-12 validation](https://json-schema.org/draft/2020-12/json-schema-validation),
  read at 2026-10-12T21:34:46Z; object constraints and format validation.
- [ossf/scorecard@c395761df6afe1a69e476bc60a013a94bcbc153f:README.md:188](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/README.md#L188),
  the supported public REST API, assessed-commit limits and data licence.
- [deps.dev public API v3](https://docs.deps.dev/api/v3/), `GetProject`, read
  at 2026-10-12T21:34:46Z. Each scored API/page URL and read time is retained
  in the layer record or its public source receipt.
- [Public runtime source fields](../../../evidence/artifacts/angle-records-20261012/public-source-reads.json)
  and [vendor source fields](../../../evidence/artifacts/angle-records-20261012/vendor-source-reads.json).
- [Layer resolution protocol](../../../docs/decisions/2026-10-11-layer-resolution-protocol.md)
  and [implementation decision](../../../docs/decisions/2026-10-12-angle-records-final-check.md).
