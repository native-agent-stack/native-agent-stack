# Decision: qualify FINAL evidence while admission remains disabled

FINAL admission stays disabled with `admission under redesign`. This change
separates evidence qualification from admission, repairs retained-history and
consumer checks, and supplies positive and negative controls. A successful
qualification result includes `admission_enabled: false`; it never writes a
FINAL manifest or authorizes adoption.

Activation requires a separate reviewed PR after these checks merge, a
qualification receipt on current main passes positive and negative controls,
and independent reads from two model families finish. The separate A1 identity
correction in #1163 must be present before current candidate qualification is
relied upon. Until it lands, a convergence label still requires a manual check
of the candidate's current repository and pin against its A1 evidence.

## Retained native evidence comes first

At base `e1b5288051292cfdb19e2ca64349e4da35ba0970`, the inactive history
predicates could treat a completed empty V1 row without retained discovery as
unchanged. Projected V2 fields could also appear complete while disagreeing
with retained raw returns. Qualification now calls the existing native
[`saturation_ledger.check_ledger`](https://github.com/native-agent-stack/native-agent-stack/blob/e1b5288051292cfdb19e2ca64349e4da35ba0970/scripts/saturation_ledger.py#L1313-L1317)
before interpreting any projection. The native checker already reconciles
discovery, candidate partitions, raw rounds, failure markers, manifests,
registered bytes and the ledger chain. It is reused without modification.
The [ledger contract at that pin](https://github.com/native-agent-stack/native-agent-stack/blob/e1b5288051292cfdb19e2ca64349e4da35ba0970/catalogs/saturation/README.md#L75-L101)
makes an empty proposal set evidence only through retained discovery.

After integrity succeeds, the consumed manifest identifies exactly one
covering sweep. The qualifier compares every later covering ledger index;
it never filters an event by calendar date, status or cutoff. The explicit
admitted status is `completed`, with both scope hashes unchanged, retained
votes and discovery, no reopen or retained failure, and no material pending
candidate. Missing fields and inconsistent evidence refuse. Survivor replay
retains the existing native V2 substantive-refutation rule and same-or-later
ledger-index disposition binding. Earlier omission or unreturned votes cannot
settle a survivor. Ambiguous or missing consumed anchors refuse.

`qualify_final_requirements` also binds the qualification packet to the current
catalog source, recorded winners and registered wave. It then evaluates the
current run pins and angle records through fresh native inputs, rejecting a
retained packet when either changed. It evaluates the
complete run identity, non-provisional comparative convergence, upstream E2E
receipt and invocation requirements. Ordinary dated matrix projections are
reporting inputs, not evidence for qualifying FINAL history.

The ordering oracle follows the history qualifier and its repository helper
calls, including source reads and native material-pending/refutation helpers.
It tests getter access, aliases, delegated functions, sorted/min/max keys and
missing scope. Native whole-ledger integrity remains an independently tested
validation prerequisite. The oracle does not claim to prove arbitrary Python
program behavior or authenticate remote evidence.

## Refusal, replay and recovery

Production builders retain the common unconditional refusal. A lightweight
claim preflight precedes schema/dependency diagnostics; missing validation
packages still refuse generation. Read-only flags and the actual local-pages
flag adapter load without jsonschema or its optional URI package.

The recorder now refuses an unnamed FINAL row before an append can skip it.
Refusal and retry preserve existing bytes, and a repaired ordinary append
recovers. Restored FINAL snapshots cannot become current through definitive
queries, flag readers, wave-row projection or layer-page construction.
Matrix views leave the alias unreported. Historical narrative text remains a
record, and provides no current admission result.

## Receipt and source boundaries

Every E2E repository URI passes the supported direct RFC 3986 validator,
including additional citations beyond the one binding the winner. This follows
[jsonschema 4.26.0's pinned URI mechanism](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/_format.py#L303-L313)
and the existing native angle validator. The pinned source imports at line
307 and calls at 313; the older call locator is explicitly corrected, without
reconstructing historical captures. The [new source receipt](../../evidence/artifacts/final-evidence-qualification-20261015/source-reads.json)
retains the fresh pin, digest and excerpt.

Invocation windows deliberately retain the UTC-`Z` input contract. Producers
must normalize equivalent offset spellings before qualification; equal or
reversed windows refuse. Repository citations use the existing `source_file`
contract so directories cannot qualify as non-FINAL A1 evidence.

The durable CI schema input includes jsonschema 4.26.0 and the direct
RFC3986-validator 0.1.1 dependency. Native uv 0.12.22 compilation for Python
3.12/Linux, constrained by the current lock, reproduced all seven selected
versions and their distribution hash sets exactly. Calendar and analyzer
selections are unchanged. The new input is explicitly included in OSV's scanned
requirements targets.

## Evidence and remaining research

The [check record](../../evidence/artifacts/final-evidence-qualification-20261015/checks.json)
retains fail-first controls and bounded native checks. Converter, appender,
ledger checker, matrix builder and qualification functions execute in the
synthetic V1/V2 scenarios; these are not real candidate capability runs.
No provider call, broker action, account operation or live admission occurs.

Missing historical response captures and upstream execution artifacts are
not authenticated by syntax or package-source checks. Comparative evidence
for the four-angle selection policy across native clients, agent SDKs,
workers and model routes remains research work. The alternative of restoring
admission from the historical predicates is rejected: passing these fixtures
is one input to the separately reviewed activation, not its authorization.
