# Decision: sourced angle records and explicit FINAL checks

## Bounded integrity correction (2026-10-13)

Recorded at 2026-10-13T08:33:29Z, against `8b336b80`. This amendment handles
four FINAL-evidence cases through the existing source, sweep and verdict
pipeline. It does not change scoring, candidate selection or a recorded winner.

For an explicit FINAL claim, a later sweep date alone no longer revokes closure.
The ordinary component-matrix metric still records dated staleness, and the
final-stack builder verifies that matrix before applying FINAL's changed-evidence
rule. A covering sweep must name a supported `reopen` trigger and retained
reference. The referenced file/pointer is read and hash-bound; missing or empty
evidence fails closed. An actual retained change still requires adjudication
before FINAL. A no-change sweep leaves the FINAL projection current.

The builder reconstructs FINAL's cumulative survivor set across all completed
covering sweeps, including older and same-day observations. Later omission or
missing returns/votes cannot settle it. A returned substantive refutation can
settle the candidate; alternatively, the catalog verdict must explicitly select
it or retain its disposition, reason and evidence references. A disposition
cannot settle a newer post-verdict proposal. Any remaining survivor prevents
FINAL with a specific refusal. These lifecycle checks supplement each winner's
existing convergence, complete-pin, E2E and invocation requirements.

Receipt references in entitlement and licence metadata now use the same
read/hash contract as angle receipt references. An absent metadata receipt
prevents generation, and its later edit invalidates `--check` through the source
hash. Licence metadata remains separate from derivation and arm selection.

The review gate and architecture projection now preserve recorded semantics
for the FINAL verdict alias. Review still recomputes status from sealed lane
evidence and checks the selected winner/alternatives/adjudication; a FINAL label
cannot make pending evidence recorded. Architecture maps FINAL to adopted and
keeps the desk's winner projection. The base copy of the review gate remains
the CI trust source, so this compatibility is available after that gate lands.

Before production changes, nine named synthetic controls produced thirteen
assertion/subtest failures and zero errors at `8b336b80`, covering all four
cases. The correction adds missing-return/empty-disposition controls and
retained-change, retained-disposition and substantive-refutation positive
controls. These are fixture tests, not candidate qualification. The final
[check receipt](../../evidence/artifacts/angle-records-20261012/fix3-checks.json)
records bounded verification and source-hash boundaries.

Primary mechanism references at `8b336b80`:

- [Layer resolution protocol:50](https://github.com/native-agent-stack/native-agent-stack/blob/8b336b80c345444f073cca74281c725fd5e0d4b9/docs/decisions/2026-10-11-layer-resolution-protocol.md#L50),
  cumulative unresolved survivors, and `:62` / `:74`, changed-evidence
  reopening and terminal dispositions.
- [scripts/saturation_ledger.py:657](https://github.com/native-agent-stack/native-agent-stack/blob/8b336b80c345444f073cca74281c725fd5e0d4b9/scripts/saturation_ledger.py#L657),
  native reference resolver; `:625`, returned merit versus missing vote;
  `:86`, supported reopen triggers. The builder reuses these helpers.
- [scripts/final_stack.py:195](https://github.com/native-agent-stack/native-agent-stack/blob/8b336b80c345444f073cca74281c725fd5e0d4b9/scripts/final_stack.py#L195),
  existing confined read/hash contract;
  [scripts/landscape.py:33](https://github.com/native-agent-stack/native-agent-stack/blob/8b336b80c345444f073cca74281c725fd5e0d4b9/scripts/landscape.py#L33),
  shared recorded-verdict statuses. The existing unittest and JSON Schema
  sources below remain the validation harness; no replacement is introduced.

## Fix round 2: file citations, URI validation and the FINAL alias

Recorded at 2026-10-13T04:14:45Z. This amendment corrects the remaining
source-locator and parser-only claims at `fe640793`. It records validation
and synthetic controls; no candidate is installed, invoked or made FINAL.

An upstream E2E citation must name a safe relative file. The shared path
pattern now requires the entire string to match; the E2E source-file contract
also refuses directory aliases and trailing separators. Repeated dot-only
paths, `src/.`, `src/` and a trailing newline no longer satisfy condition 3.
Ordinary files, including `./README.md` and `.github/workflows/test.yml`, remain
accepted. This verifies locator syntax; it does not establish that a cited
upstream file exists or that a source page is authentic.

`urlsplit` parses URLs and does not validate URI syntax. HTTPS sources now
first pass `rfc3986-validator==0.1.1`, the URI validator used by pinned
jsonschema's supported `format-nongpl` extra. That dependency is pinned
directly with public package hashes in the CI requirements and imported
directly by the record validator. This makes URI validation required even
when optional `FormatChecker` registrations are absent. CPython then checks
the scheme, hostname, userinfo and port. Malformed escapes and backslashes
are refused with a constant error; a valid encoded HTTPS URL still passes.
The earlier parser-only wording below is corrected to describe this path.

The FINAL verdict alias now follows recorded-verdict semantics through the
landscape validator, component-matrix generator, verdict narrative and
final-stack generator. It retains the ordinary verdict contract, sealed
new-wave winner binding, winner factors, reopening and dated review metadata.
FINAL enforcement still checks the terminal conditions separately. The
positive control regenerates its matrix after setting the alias, eliminating
the fixture's previously stale recorded-status matrix.

The two committed neutral route rows are pinned by a data regression test.
An otherwise fully measured synthetic winner with the pool row's metadata
separately exercises `final_eligible: false` and `entitlement: unverified`.
The generic entitlement control covers both pending and unverified status.
Receipt refusals assert their binding or invocation reason and rebuild output
if a guard is absent, so source drift cannot substitute for the intended check.
The route and decision use neutral `unverified` wording.

Before the corresponding production corrections, the new directory/URI
controls failed in nine subtests; the affected mechanisms were unchanged from
`fe640793`. The regenerated alias controls failed at the landscape, matrix and
final-stack boundaries, and its narrative control rendered a pending row.
The [round-2 check receipt](../../evidence/artifacts/angle-records-20261012/fix2-checks.json)
retains the final bounded verification and its limits.

Primary correction sources, read at 2026-10-13T04:08:24Z:

- [python-jsonschema/jsonschema@a7277432b0f7bcd0551f6e589d30457017125df4:jsonschema/_keywords.py:215](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_keywords.py#L215)
  uses `re.search` for schema patterns.
- [python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91:Doc/library/re.rst:826](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/re.rst#L826)
  documents the final-newline behavior of `$`;
  [Doc/library/urllib.parse.rst:416](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/urllib.parse.rst#L416)
  states that the URL parsers do not validate inputs.
- Pinned jsonschema's [jsonschema/_format.py:313](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_format.py#L313)
  calls `validate_rfc3986(..., rule="URI")`; its
  [pyproject.toml:64](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/pyproject.toml#L64)
  names the supported dependency.
- [Public package metadata](https://pypi.org/pypi/rfc3986-validator/0.1.1/json),
  and the retained [read receipt](../../evidence/artifacts/angle-records-20261012/fix2-source-reads.json).
  The package repository is UNMIRRORED; its public wheel's exported validator
  was read at 2026-10-13T04:11:01Z and retained as a readable excerpt. The
  repository's existing validators, registration helper and unittest fixtures
  supply the alias and evidence paths; no replacement pipeline is introduced.

## Fix round 1: exact FINAL identity and measured convergence

Recorded at 2026-10-13T02:59:11Z. The original PR commit was replayed onto
main `c63c83a822f2687c3e7aed2d3b3ede0413119c9b`, where
[the converged-candidates rule](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c63c83a822f2687c3e7aed2d3b3ede0413119c9b/docs/decisions/2026-10-12-converged-candidates-only.md#how-the-rule-applies-every-layer-the-freeze-and-the-north-star)
is now retained. The original decision below records the first head's
behavior. This amendment supersedes its acceptance of provisional FINAL
evidence and its shared-field pin comparison.

FINAL now requires a NON-provisional CONVERGED candidate with comparative A6.
A reopened matrix layer must have its sweep delta adjudicated and leave
reopened before FINAL. All explicit terminal-state inputs are reconciled;
a truthy landscape state cannot hide an angle-record or verdict FINAL claim.
The FINAL verdict alias receives ordinary recorded review metadata.

Winner, angle candidate, final-evidence binding, execution receipts and
upstream citations must agree with the complete run identity. A version-only
run cannot bridge two different commits, and a receipt cannot drop a recorded
commit and rely on a release-name match. Upstream E2E receipts use the native
JSON Schema validator with strict command/source contracts: nonblank command
strings, safe relative source paths and positive integer line numbers.
Malformed list members are rejected before phase counting.

Screened A1 pins use allowed resolved identity forms rather than a sentinel
denylist. UTC timestamps are explicitly checked using CPython's datetime parser.
HTTPS URLs require the pinned upstream RFC 3986 validator before CPython's URL
parser checks their authority; optional checker registrations do not disable
this direct validation. Rejected values are never echoed. The weight statement must strictly precede every
angle, URL, entitlement and compliance read time.

The two neutral trial rows have `trial_permitted: true`, `final_eligible:
false`, and `basis: "operator decision, recorded privately"`. These fields
do not change derivation or the arm list. The Meta foreign-harness subscription
remains REJECTED with an evidenced terms conflict. The OpenAI non-Codex pool
route remains INSUFFICIENT with entitlement `unverified`; no terms conflict
is inferred. Either row's explicit ineligibility, or any unverified entitlement,
prevents FINAL.

The sanitized Muse installation observation retains client 1.4.6-R6000.1,
installer exit 0 and the Full model identifier muse-wonder-full-1.0. It is A1
installation evidence only. Complete screening, Standard-mode confirmation
and successful Full-model invocation remain gaps. No candidate is installed
or invoked by this fix-round lane.

Fresh readable source captures now retain the OpenRouter app page, Muse
overview/configuration/extensions/subscription pages and the deprecation
README. Their current citation times match the retained captures. Non-read
generic README URLs are removed from unverified cells. Every current
URL/read-time pair has a receipt locator. Older API/page receipts remain
extracted snapshots; absent historical raw responses are not reconstructed
or described as independently verified.

The genuine-worktree repository grant proposal at replayed head
`c7dbb078dabe2d1b226eddc409e0133e6c3e7e37` added exactly one selected inventory
path, `scripts/angle_records.py`. That exact path was reviewed and added to
the static architecture-inventory grant. No runtime discovery, receipt role
or user grant was broadened. The existing two inventory controls failed
before the update and the 25-test grant module then passed.

The fix controls reproduce the reported paths before changing production
checks and assert specific refusal reasons. Tests that previously relied on
source drift now fail when each of five targeted guards is removed, including
weight sum, source presence, convergence, E2E receipt and invocation reason.
The updated implementation passed 75 bounded controls before final full
affected-module verification; the final receipt retains the actual counts.

Primary correction references:

- [python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91:Lib/_pydatetime.py:1862](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/_pydatetime.py#L1862),
  v3.13.16, `fromisoformat` and its value-bearing exceptions;
  [Lib/urllib/parse.py:472](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/urllib/parse.py#L472),
  `urlsplit`, hostname, userinfo and port properties. These sources were read
  from their registered exact mirrors with lazy fetching disabled.
- [python-jsonschema/jsonschema@a7277432b0f7bcd0551f6e589d30457017125df4:jsonschema/_format.py:307](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_format.py#L307)
  and `:396` show optional URI/date-time registration; its native
  `Draft202012Validator` owns strict receipt type/required/path validation.
- [Source-capture receipt](../../evidence/artifacts/angle-records-20261012/supplemental-source-reads.json)
  and [sanitized installation receipt](../../evidence/artifacts/angle-records-20261012/muse-install-sanitized.json).
- The repository's existing `local_pages_policy_grants.py` proposal mechanism,
  `host_receipts.register_file` registry helper and synthetic unittest harness
  are reused; this correction introduces no metric or replacement runtime.

### Follow-ups

The evidence behind the four-angle acceptance policy remains a retained
research question. JSON Schema and Scorecard validate the mechanism and
source APIs, not that acceptance policy. It is outside this bounded fix round.
Historical line locators remain bound to their original revisions rather than
being rewritten after registry movement. Pre-existing machine-name text in
the shared evidence registry is not introduced by this change and is retained
for its separate hygiene follow-up. Full raw captures of the initial public
responses remain unavailable; current readable excerpts and field snapshots
are the explicitly bounded evidence.

## Original record

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
own structural validation. Explicit CPython datetime/URL validation supplies
the format checks, independent of optional jsonschema extras, and rejects
invalid values with constant diagnostics. Decimal sums enforce the exact
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
  retain extracted source fields, URLs, pins and read times. These historical
  extracts are not full raw-response captures. No private input digest or
  attribution is published.
- [Layer resolution protocol](2026-10-11-layer-resolution-protocol.md), the
  retained four FINAL conditions and delta-only reopening rule.
