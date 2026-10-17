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

The next qualification correction uses the existing native current-row and
frozen-wave contracts at `f33b1cb40d1479baeaa4edc6c8973ddfa3e303e9`.
[`landscape_rows`:249-269](https://github.com/native-agent-stack/native-agent-stack/blob/f33b1cb40d1479baeaa4edc6c8973ddfa3e303e9/scripts/final_stack.py#L249-L269)
enumerates the canonical catalogs and rejects duplicate layer keys before a
packet's source pointer can select one. Winner evidence class comes from that
current row; verdict date, wave and next review are recomputed through native
[`build_verdict`:545-561](https://github.com/native-agent-stack/native-agent-stack/blob/f33b1cb40d1479baeaa4edc6c8973ddfa3e303e9/scripts/final_stack.py#L545-L561).
`test_qualification_rejects_duplicate_current_rows_before_following_the_pointer`
and `test_qualification_uses_current_verdict_metadata_instead_of_packet_fields`
fail before these bindings. A matching registered path/hash is also required
to identify a complete tuple. After checking the retained bytes, the existing
[`check_frozen_rows`:476-495](https://github.com/native-agent-stack/native-agent-stack/blob/f33b1cb40d1479baeaa4edc6c8973ddfa3e303e9/tools/sota-convergence/build_verdicts.py#L476-L495)
reconciles the wave with this current layer and winner.
`test_hash_correct_registered_wave_must_contain_this_layer_and_winner` rehashes
both registry and packet before testing unrelated, missing and changed rows.
The positive fixture now builds the wave through the supported native builder.

Consumed reopening metadata must also be an explicit list of valid native
markers with nonempty stripped references. This follows the native
[`check_layer` contract at :1091-1094](https://github.com/native-agent-stack/native-agent-stack/blob/f33b1cb40d1479baeaa4edc6c8973ddfa3e303e9/scripts/saturation_ledger.py#L1091-L1094),
even where the V2 checker at that pin permits null or whitespace metadata.
`test_v2_null_anchor_reopen_refuses_with_a_domain_error` and
`test_whitespace_anchor_reopening_reference_refuses_even_if_file_exists`
reach this boundary after native integrity succeeds. The latter retains a
file named with spaces, so a missing-file error cannot hide the metadata gap.
The qualifier also restricts symbolic references to the two namespaces emitted
by native [`external_triggers`:1463-1493](https://github.com/native-agent-stack/native-agent-stack/blob/f33b1cb40d1479baeaa4edc6c8973ddfa3e303e9/scripts/saturation_ledger.py#L1463-L1493):
`receipt_staleness:` and `catalog-freshness:`. All other references use the
confined file reader; `test_missing_file_shaped_reopening_reference_is_not_symbolic`
fails before that distinction. General V2 checker parity remains a follow-up;
this bounded change only strengthens evidence qualification.

The qualification fold corrects three defects in the implementation at
`425c4367a4db640b0bc4074f48e3990663416bee`. Native reopening identifiers are
not uniformly file references: the native
[`external_triggers` producer](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/scripts/saturation_ledger.py#L1463-L1468)
emits symbolic `receipt_staleness:` identifiers, and the
[`check_layer` contract](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/scripts/saturation_ledger.py#L1091-L1094)
accepts nonempty reopening references. The qualifier retains confined files
when an identifier actually names a file, while leaving symbolic events to
the native history contract. The fail-first control is
`test_symbolic_reopening_identifier_is_not_a_file_dependency`.

Native integrity can faithfully retain failed discovery. Its
[`check_v2_layer` failure reconciliation](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/scripts/saturation_ledger.py#L1171-L1178)
requires the matching failure marker; it does not assert successful discovery.
A consumed baseline with a retained discovery failure now refuses unless a
later covering sweep repairs it. That sweep must independently satisfy the
existing completed, retained, unchanged-scope, no-reopen and no-material-pending
requirements. `test_unrepaired_consumed_discovery_failure_refuses_qualification`
fails before this guard and covers successful recovery through the native
later sweep.

Each qualification call now uses a new native `Sources(root)` reader. The
[memoization at 425c4367:222-231](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/scripts/final_stack.py#L222-L231)
is useful within one read, but a caller can retain that object after the files
change. Reusing it as the current-evidence authority was incorrect. Both
qualification entry points now follow the existing
[`build_document` fresh-reader pattern at 425c4367:1087-1092](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/scripts/final_stack.py#L1087-L1092).
They retain successful source fingerprints for the caller without trusting
its parsed JSON cache. The same-reader regressions change angle evidence,
run pins, the recorded catalog, wave registration, an E2E receipt and a native
ledger, assert refusal, then restore the files and qualify again. These are
current-input and recovery controls, not currency checks.

The symbolic-reference controls cover a consumed anchor, an unrelated layer,
and a later covering reopening. The later event still refuses by native
history policy; its symbolic identifier is not interpreted as a missing file.
The reference contract is the same native check_layer/external_triggers
contract cited above.

Fresh runs alone do not authenticate a retained winner's run association.
Qualification now recomputes that association through the existing
[`build_winner` repository/ID join](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/scripts/final_stack.py#L564-L594).
`test_current_run_with_another_repository_cannot_qualify_a_retained_winner`
fails before this correction even with freshly rebuilt runs and unchanged
ID/pin. `test_current_run_without_a_repository_retains_the_native_id_join`
preserves the native same-ID fallback. These controls qualify synthetic
evidence only; production admission remains disabled.

The bounded ordering oracle now also rejects `list.sort` with a date key.
Its [prior call-shape boundary at 425c4367:88-93](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/tests/test_final_history_ordering.py#L88-L93)
recognized sorted/min/max while missing that mutation. Direct native V1
controls cover winner and alternative dispositions with missing, unknown,
earlier, same and later ledger bindings; the last clean sweep's omission does
not settle an earlier survivor. Direct V2 controls refuse six refutation
identity/vote mutations through the native integrity prerequisite. These
exercise qualification rather than relying only on the disabled CLI.

Historical FINAL aliases retain their recorded text and host-E2E fields in
the matrix and desk, while their layer and winner display statuses remain
unreported. The existing
[`layer_status` rule at 425c4367:58-60](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/tools/local-pages/architecture_manifest.py#L58-L60)
already makes that distinction; the
[matrix and desk call sites at :142 and :277](https://github.com/native-agent-stack/native-agent-stack/blob/425c4367a4db640b0bc4074f48e3990663416bee/tools/local-pages/architecture_manifest.py#L142)
now preserve it for the winners and visible verdict item too. The regression
restores explicit desk assertions. The current/converged page-state admission
item remains assigned to the separate activation change; this fold does not
enable that path.

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
