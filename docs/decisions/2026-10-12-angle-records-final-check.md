# Decision: sourced angle records and explicit FINAL checks

The freeze generator now reads versioned per-layer angle records, re-derives
their verdicts and enforces the protocol's four conditions on explicitly FINAL
layers. Missing records remain visible gaps. No initial layer is declared FINAL.

The change was recorded at 2026-10-12T22:00:03Z against base `703d588c`.
The bounded input gap was consumed from foundation's catalog, its recorded
20260922 verdict wave, and the latest completed foundation sweep
`landscape-sweep-20260929` with its manifest and retained returns. Earlier
covering sweeps remain in the ledger. Unresolved worker and SDK survivors are
retained; adding an angle row does not settle them. Model-routes has no catalog
verdict or sweep at this base, so its new evidence-only row is unswept.

## Rule and implementation

Use `angle-convergence/2`, with defaults A1/A2/A5 0.20, A3/A4 0.15 and A6 0.10.
Four sourced active angles are needed for convergence; positive capability,
two positive community/usage/publication angles and one positive outcome angle
must agree without a negative angle. Hard disqualifiers reject before coverage
is considered. Without a comparative A6, convergence is provisional. Smoke and
install results are A1, including adverse route observations; they are not A6.
The disqualifier enum is limited to missing capability and abandonment.
Licence is retained as an SPDX/source/read-time compliance note and never
changes a score, verdict or arm list. Entitlement/terms conflicts remain
missing capability. This policy is covered by a licence-note-only invariance
control.
The exact ordered rule, schema and receipt contracts are documented in the
[angle README](../../catalogs/landscape/angles/README.md).

V2 followed visible v1 runtime scores. This order is explicitly disclosed;
previous verdicts and signs remain history. Fresh primary-source reads follow
the new weight statement. This is re-verification with a known prior result,
not a blind assessment or retroactive preregistration. When a former claim
cannot be re-established from the bounded current primary sources, the current
angle remains mixed or unverified instead of copying its source label.

JSON Schema draft 2020-12 and the installed python-jsonschema 4.26.0 validator
own structural validation and format checks. Decimal sums enforce the exact
weight invariant. The repository code supplies only the schema, ordered policy
derivation and evidence checks. It does not replace Scorecard, deps.dev,
registry statistics or published evaluations with a new metric.

The final-stack builder validates all records, tracks their source hashes and
includes summaries. An angle-only model-routes row is included without
inventing a catalog verdict. Existing matrix statuses and the W1b API keep
their meanings; the explicit `terminal_state` is separately enforced. For a
FINAL winner the check requires recorded verdict/class/wave/review metadata,
a matching run pin, CONVERGED angles, pinned native upstream install/test
evidence, and invocation in a measured window or a recorded non-invocation
reason. A bare receipt filename, mismatched pin, synthetic execution, smoke
labelled comparative, zero calls or an unordered window cannot satisfy those
checks. Non-FINAL pin/review flags remain report-only.

## Initial findings and boundaries

The twenty runtime inputs map to sixteen native-client roles, two worker roles
(OpenHands SDK and the mini-SWE bash control) and two SDK-native ACP roles
(Deep Agents and Strands). Muse Code adds a seventeenth native-client row,
TRIAL pending its installed pin and independent angle evidence. README source
reads at a refreshed pin are not silently promoted to a full six-requirement
screen. Both OpenCode generations retain separate candidate identities;
the mirror's HEAD/1.x evidence does not screen the 2.x product.

Claude Code and Codex have provisional source-based convergence. Pi's earlier
smoke outcome disappears from A6, so it no longer converges. The deprecated
OpenHands CLI is rejected using its readable public upstream README, with its
UNMIRRORED pin gap retained. No comparative result is asserted. Some formerly
negative quality/community assessments are not reproduced by the bounded
fresh observations and remain mixed; their former verdicts stay in history.

The model-route record includes Muse Code/Muse Wonder Full, five separately
entitled Meta API arms that are NOT ADOPTED, the withdrawn subscription outside
Muse Code, three GPT routes and three Claude routes. Meta's readable vendor
terms section 3.2 establishes the coding-harness-only credential restriction,
which rejects the withdrawn route as missing capability. The Full variant is
not inferred from max effort on the API model or from the Artificial Analysis
Muse Wonder row. Native Claude Pro/Max and Codex subscription mechanisms are
documented. OpenAI's supported gateway guide is per-user ChatGPT sign-in;
entitlement of a specific pool configuration remains unverified. These reads
do not inspect credentials or run models.

Thirty-one layers still have no angle record. The source-review convergence
of a runtime candidate does not fill exact winner/run/angle pin alignment or
the FINAL E2E and invoke gaps. No state is promoted on that basis.

## Alternatives and overturn

Keep the previous generator as a reporting join: it cannot reject a forged
FINAL marker, missing receipt or unsupported convergence assertion. Reject
every missing angle record immediately: that would incorrectly treat initial
coverage gaps as already enforced terminal states. Use smoke outcomes as A6:
that would admit Pi without a published or comparative outcome. Treat unknown
publication availability as no publication: that would silently move weights
without establishing the rule's premise.

The selected change makes each boundary explicit and checks FINAL only where
it is claimed. Replace this rule through a reviewed supersession if a retained
upstream comparison shows the sign/coverage rule admits a materially weaker
candidate or rejects the measured workload winner. Reopen individual scores
only on new primary evidence or a recorded landscape change.

## Validation and sources

The initial eleven-control regression class ran against the previous builder
at 2026-10-12T21:36:08Z: nine failure-class controls failed and the missing-angle
summary errored (`Ran 11 tests`, `FAILED (failures=9, errors=1)`, exit 1).
The successful-receipt control passed. After the initial implementation, the
class passed before the 2026-10-12T21:41:48Z clock read (`Ran 11 tests`, `OK`,
exit 0). That first green run has no separate end-time receipt. Additional
controls cover provisional convergence, terms rejection, unknown publication
availability, comparative receipt binding, false smoke labels, pin/class and
invoke-window mismatches. These are synthetic policy tests, not runtime
qualification. Final named-module and publication checks are recorded in the
PR and verification receipt.

The two licence-policy controls were also run against the pre-correction
staged schema/rule at 2026-10-12T22:23:22Z: `Ran 2 tests`,
`FAILED (failures=1, errors=3)`, exit 1. That schema lacked the compliance-note
field and accepted an otherwise self-consistent licence disqualifier. The
current schema accepts the separate note, rejects that disqualifier and the
derivation/arm-list invariance control covers differing SPDX identifiers and
an unknown identifier. Licence does not influence any candidate's scores.

Primary implementation references:

- [python-jsonschema/jsonschema@a7277432b0f7bcd0551f6e589d30457017125df4:jsonschema/validators.py:307](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L307),
  v4.26.0: `check_schema`, `iter_errors` (349), `Draft202012Validator` (812);
  [_format.py:21](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_format.py#L21)
  `FormatChecker`.
- [JSON Schema draft 2020-12 validation](https://json-schema.org/draft/2020-12/json-schema-validation),
  read at 2026-10-12T21:34:46Z, object/numeric/format contracts.
- [ossf/scorecard@c395761df6afe1a69e476bc60a013a94bcbc153f:README.md:188](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/README.md#L188),
  public REST result API; [deps.dev v3 GetProject](https://docs.deps.dev/api/v3/),
  read at 2026-10-12T21:34:46Z.
- [Retained public runtime fields](../../evidence/artifacts/angle-records-20261012/public-source-reads.json)
  and [vendor fields](../../evidence/artifacts/angle-records-20261012/vendor-source-reads.json)
  bind the actual source URLs, pins and read times. No private input digest or
  attribution is published.
- [Layer resolution protocol](2026-10-11-layer-resolution-protocol.md), the
  retained four FINAL conditions and delta-only reopening rule.
