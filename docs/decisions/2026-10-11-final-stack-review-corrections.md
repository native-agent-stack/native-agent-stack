# Final-stack review corrections

The final-stack generator's first review at
`4d6cee1582f024d27319ee005117da5f15ebe269` found missing boundary assertions,
an order-dependent precedence implementation, incomplete unknown-drift reports,
an overbroad lock-root selector and an unintended Architecture projection.
On 2026-10-11 the CC, acting as plan owner, directed a combined correction after
the second review. They retained the foundation lane and assigned the derived
manifest to the Landscape page. This record describes the first review's local
corrections and the second review's privacy/reuse corrections below. Designated
acceptance of the combined commit remains separate.

The existing native generator, source policy and standard-library unittest
harness cover these boundaries. No package, parser, runner or integration is
added. Search-first selected those maintained implementations for this repair.

Primary sources, reviewed at their exact pins:

- [Native status and run-pin contract](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/scripts/final_stack.py#L125):
  `DEFINITIONS`, `run_records`, `build_runs`, `layer_status`, `is_definitive`,
  `flags` and the supported `--write`/`--check` commands. Rank is the precedence
  contract; the implementation now stably sorts by it.
- [Native comparable pins](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/scripts/host_receipts.py#L204):
  `normalize_pin` and `pin_matches` require a digit for comparable pin text.
  Numeric 40-hex fixture commits exercise equality through that implementation.
- [uv 0.12.17 workspace packages](https://github.com/astral-sh/uv/blob/635500036e1705961315e86447f0fab0a8ddb309/crates/uv-lock/src/lock/mod.rs#L3600):
  lines 3600-3607 accept the empty workspace-relative editable/virtual path as
  the root. The lockfile representation is `"."`; an editable child is not
  another root. The exact commit and returned source were checked through the
  upstream API. Both root forms and both child forms are exercised.
- [PEP 503 normalized names](https://peps.python.org/pep-0503/#normalized-names):
  the existing package-name normalization is covered with a positive mixed
  separator case; its implementation is unchanged.
- [Native Architecture exclusions](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/tools/local-pages/source_policy.py):
  the existing exclusion skips a file before content access. The derived
  `final-stack.json` is excluded with provenance; `planned-layers.json` stays
  granted. Source-layer exclusions and this deliberate duplicate-view exclusion
  have separate exact checks, because the derived manifest does contain layers.

The public W1b query now distinguishes an unknown identifier (`untracked`) from
one tracked in other layers (`not-winner`, naming those layers). Unknown drift
remains unknown: reporting now names the layer, component, verdict pin and run
pin, without guessing an unparsed pin's meaning. UNREPORTED intake source paths
are explicitly future integration paths, excluded from the read-source hashes.
Evidence-contribution and hot-file guides refresh and check final-stack after
its inputs change.

Fail-before observations used the existing unittest runner. Correct behavior
that was only missing coverage was checked against a temporary, single-rule
production mutation; every mutation was restored. These are synthetic and
repository integration checks, not upstream acceptance or new host/model runs.

| Finding | Check in `tests/test_final_stack.py` unless noted | Before correction or under named mutation | After restoration/correction |
| --- | --- | --- | --- |
| P3-1 | `StatusTests.test_reviewed_no_selection_and_empty_recorded_winners_keep_the_review_date` | Narrowing `layer_status` to pending lanes produced 2 failures, rc 1 | Both no-selection and recorded-empty cases pass with next review 2026-10-22 |
| P3-2 | `PinTests.test_identical_commit_pins_compare_equal_through_native_normalization` | Alphabetic fixture commit normalized to None: 1 failure, rc 1 | Numeric commit fixture and all 4 pin tests pass |
| P3-2 | `RunTests.test_same_lock_and_verdict_version_has_no_drift`; existing unequal-lock case | Self-comparison mutant: 1 expected failure in 16 tests, rc 1 | Restored 16 tests pass, rc 0 |
| P3-4 | `RunTests.test_run_precedence_uses_rank_even_when_records_arrive_out_of_order` | Reversed input chose stack 1.0.0 over lock 2.0.0: 1 failure, rc 1 | Stable rank sort chooses lock 2.0.0 and lists stack conflict, rc 0 |
| P3-5 | `RunTests.test_unknown_drift_report_names_the_layer_component_and_both_pins` | Count-only CLI output: 1 failure, rc 1 | CLI names all four requested fields, rc 0 |
| P3-6 | `RunTests.test_a_subpath_editable_or_virtual_package_is_not_the_lock_root`; `test_the_lock_root_accepts_dot_and_ignores_an_editable_child` | Child accepted as root; actual root plus child rejected: 2 failures and 2 errors, rc 1 | Both source kinds pass both controls, rc 0 |
| P3-7 | `RunTests.test_unreported_intake_names_future_paths_without_reading_them` | Future-path explanation absent for both entries: 2 failures, rc 1 | Explanations and no-read source hashes pass, rc 0 |
| P3-8 | `RepositoryTests.test_evidence_contribution_and_hot_file_guides_refresh_and_check_final_stack` | Both guides omitted the commands: 2 failures, rc 1 | Contribution and hot-file write/check instructions pass, rc 0 |
| P3-10 | `tests/test_local_pages_architecture_landscape_exclusions.py::CommittedLandscapeSetTests.test_derived_final_stack_is_excluded_but_planned_layers_are_granted` | Derived manifest not excluded: 1 failure, rc 1 | All 8 exclusion-module tests pass, including skipped-before-read control, rc 0 |
| P3-11(b) | `DefinitiveTests.test_the_layer_argument_narrows_the_question` | Known winner in another layer returned untracked: 1 failure, rc 1 | All 5 definitive-query tests pass, rc 0 |
| P3-3 | Positive trialled funnel, lifecycle coverage, wave document, repository-less join, PEP 503 and duplicate research-row controls | Each single-rule mutant returned rc 1 with the intended assertion failure; wave-document mutation caused 2 subcase failures, the others 1 each, zero errors | All mutations restored; covered in the focused integration gate |

The intake test also checks the positive seed total, layer mapping and date;
the measured-evidence fixture checks distinct trialled and adopted counts.
The remaining optional P3-3 mutation classes are outside this bounded pass.
The original review's P3-9 description refresh is due at the landing head; this
committed table supplies an actual source for the correction checks.

The second review at the same starting head established a publication-boundary
P2 and an imported-reuse P3. All four new controls failed on the prepared first
family before these corrections: two privacy refusal tests, shared serializer
identity and a policy-change propagation test (4 tests, 4 failures, rc 1). The
same four controls then returned rc 0 (4 tests in 0.081s, zero skips).

- **Privacy P2:** the shared `component_matrix.assert_no_private_content` accepts
  optional private identifiers and strict email validation. The CLI supplies
  identity context through the existing
  [host-name collector](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/scripts/host_name_scan.py#L43).
  Its existing environment override supplies synthetic identities in tests.
  The in-memory email and literal checks follow the established
  [Architecture source pattern](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/tools/local-pages/architecture_sources.py#L29)
  and [private-literal rule](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/tools/local-pages/architecture_manifest.py#L103).
  Strict context is enabled for final-stack publication without changing the
  historical static checks for other callers or requiring an optional scanner
  binary in CI. The pure builder still reads only repository inputs. Tests use
  synthetic email/account payloads and publication I/O spies, proving refusal
  before output write or registration, unchanged existing output/registry and
  value-free diagnostics. Path/token protections remain enabled.
  This describes the initial correction at `f5bd15dd`; the micro correction
  below supersedes its literal matcher and its host-dependent check path.
- **Reuse P3:** `final_stack.serialize` is now the imported
  [component-matrix callable](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/scripts/component_matrix.py#L1099),
  with callable-identity and literal byte checks. The existing cadence from
  [currency_due.py:156](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/scripts/currency_due.py#L156)
  moves to the side-effect-free `scripts/sweep_policy.py` module.
  Both consumers import the one definition; a temporary policy value of 45
  propagates to both after reload, while the normal value remains 30. No new
  runtime or host read is added. The existing inventory selector requires an
  exact repository grant for this new script; it adds only `sweep_policy.py`,
  taking this branch's reviewed count from 91 to 92. The native committed-grants
  test failed first on the missing path and passes after the grant.

One repair attempt placed the shared value in `saturation_ledger.py`. The
combined 452-test command returned rc 1 with six currency-notice failures:
that suite's isolated checkout replaces the saturation-ledger executable with a
fixture, and importing it returned fixture report data rather than the notice.
The constant therefore lives in a separate pure module and the isolated
checkout copies that source explicitly. This failed attempt is retained here;
its result is not acceptance. The value and cadence remain unchanged.

The native CLI check with actual private identity context returned rc 0, retaining
34 layers and the original status counts. No identity values were printed or
stored. The upstream uv commit and the reviewed first-party commit were also
independently resolved through their native GitHub API objects. These checks
do not turn the earlier review's unavailable archive dependencies or historical
references into new passes.

Final local module gates for the combined correction:

- `python3 -B -m unittest tests.test_final_stack tests.test_component_matrix
  tests.test_currency_due tests.test_host_name_scan tests.test_validate
  tests.test_runtime_worker_openhands_push_gate`: rc 0, 452 tests in 97.722s,
  zero skips. This includes the full native push-gate read-closure suite.
- Two subsequently added privacy-context failure/pure-builder controls: rc 0,
  2 tests in 0.016s. The final generator/policy command below reruns them.
- `python3 -B -m unittest tests.test_final_stack
  tests.test_local_pages_policy_grants` plus all 15
  `tests.test_local_pages_architecture_*` modules: rc 0, 257 tests in 17.752s,
  zero skips. Overlapping executions are not summed as distinct coverage.

The native Git merge-tree of the reviewed starting head against cued current
main `0d822e91c95d0f3cb24a76270daff67840b4da06` returned rc 0 before edits.
The combined committed head must also remain merge-clean before push; this
preparation check does not assert the final merge result.

Completeness critic: the report-only drift path, missing/extra lock roots,
cross-layer query semantics, source exclusions, generated-file maintenance and
positive counter cases were separate dependencies of the original generator.
The graph's current index excludes scripts/tools/docs; exact source reads were
used for those paths, and graph coverage is not claimed for them. The tests have
best-effort indexed coverage. No claim of exhaustive mutation coverage is made.
Hosted checks at the combined head, each family's designated micro and CC landing
remain separate gates. Provider-token usage is unknown; this repair starts no
model run.

## Micro correction at f5bd15dd

The micro found one CI failure and incomplete privacy coverage. The existing
`tests.test_upstream_surface_watch` reproduced the moved citation error:
114 tests, one failure, six existing optional skips, rc 1. The two catalog
references now name `docs/contributing-evidence.md:416`; the same unchanged
module returned rc 0 (114 tests in 1.903s, six existing optional skips).
This module is part of the local acceptance closure from this correction onward.

The native publication scanner replaces the handwritten private-name matcher.
At `--write` only, the CLI collects native private-name context, stages the
serialized bytes in a private temporary directory and invokes the existing
`host_name_scan.scan_paths` before the final output write or registration. The
temporary directory is removed on success or refusal. Static path/token/email
validation remains in both modes; `--check` performs no host-name collection
and requires no scanner. Failures return value-free refusal messages and leave
the existing output and registry intact.

Primary sources for this correction:

- [First-party arbitrary-artifact scan](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f5bd15dd5b100fd00d2aed9beca4941d0f6976d9/scripts/validate.py#L705)
  and [native scanner integration](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d6cee1582f024d27319ee005117da5f15ebe269/scripts/host_name_scan.py#L157):
  native rules, decoded findings, original locations and sanitized failures.
- [Betterleaks 1.9.0 decoder](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/codec/decoder.go)
  and [rule filters](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/docs/config.md):
  use the existing scanner and boundary filters rather than build another
  decoder or substring matcher. Native executable and exact tag commit agree.
- [Reviewed generator starting point](https://github.com/seathatflowsinourveins/native-agent-stack/blob/f5bd15dd5b100fd00d2aed9beca4941d0f6976d9/scripts/final_stack.py):
  native write/check transition, static validation and unchanged data builder.

| Control | Before correction / mutation | Corrected observation |
| --- | --- | --- |
| Native percent, literal Unicode escapes, base64 and hex private-account plants; check does not read host context | Two tests returned rc 1 with five failures: four accepted encoded plants plus host read on check | Native refusal/root-check gate returns rc 0; four tests in 1.969s, zero skips |
| Uppercase and non-ASCII account plants | Supplied micro established missing branch coverage; the native scanner plants now exercise both rather than retain those local matcher branches | Included in actual native write plant test |
| Completed sweep covering a planned layer | Dropping `state is None` caused current instead of no-winner: one failure, rc 1 | Mutation restored; no-winner, empty winner list and no verdict are asserted |
| Scanner unavailable / context unavailable | Value-free fail-closed branch exercised | No final write, registration or existing-byte change |
| Publication ordering | Native scan I/O spy examines the serialized candidate | Exact event order scan, write, register |
| Native boundaries | Alphanumeric wrapper around a synthetic private name | Successful write, preserving native neighbor rules |

The complete generator module returned rc 0: 60 tests in 2.684s, zero skips,
including actual native plants. Hosts without Betterleaks explicitly skip the
the native plant/control tests; ordinary pure builder/check fixtures replace
only the scanner I/O boundary. Those skips are not native scanner acceptance.

The expanded micro gate returned rc 0: 651 tests in 82.848s, six existing
optional upstream-surface fixture skips. Its exact module command is:

```sh
python3 -B -m unittest tests.test_final_stack tests.test_component_matrix tests.test_host_name_scan tests.test_validate tests.test_upstream_surface_watch tests.test_local_pages_policy_grants tests.test_local_pages_architecture_landscape_exclusions tests.test_runtime_worker_openhands_push_gate tests.test_runtime_worker_openhands_resolver
```

All native scanner plants ran on this host; the six skips come from the existing
upstream-surface module, whose stale locator now passes. Overlapping earlier
test executions are not summed as additional coverage. Local FULL validation
and native evidence checks pass at 70 components, 11,478 hashed files, four
profiles and 239 receipts. This is preparation evidence; acceptance at a later
combined committed head remains a separate check.

Adjacent-state/call-site review: shared static validation callers in
component-matrix main keep their existing no-context contract; final-stack check
never invokes host context or the scanner. Write success, finding refusal,
scanner error and context error all preserve their intended ordering. The
planned-layer no-sweep and completed-sweep states have separate assertions.
The native scanner's existing punctuation, Unicode-neighbor, encoded-line and
error tests are included in the scoped gate. Current numeric citations affected
by the earlier document insertions are checked one dependency wider; live
resolver comments and the count-test base comment are corrected. Anti-pattern
rows are reordered without adding lines to that document.

Unmodified primary captures are retained in the lane's hashed attachment packet
`grand-generator-fix/captures`, with `MANIFEST.sha256` and `sources.json`. Official
HTML pages are stored as base64 original bytes; the source manifest records
both original and stored hashes. Pinned Git blobs and upstream sources retain
their original bytes. The co-op receives this directory with the next FIX-PUSHED
handoff; captures support source verification and are not execution acceptance.

The Astra micro at `f5bd15dd` independently confirmed the same locator,
encoded-account and host-context defects. Its explicit encoded-email requirement
adds an opt-in generated-email rule to the existing native scanner configuration;
the rule uses Betterleaks' supported inline rules and decoder depth, with no
new decoder. Other `scan_paths` and history callers retain account-only defaults.
The final-stack writer opts in. Synthetic email plants whose local part does
not match any supplied account cover `%40`, full percent, literal Unicode
escapes and base64. Before that integration, two tests returned rc 1 with four
refusal failures and one missing-API error; after it, four policy/ordering/check
controls returned rc 0 in 2.454s. Static email/path/token checks remain active.

A native scanner-bypass mutation caused six account-plant failures, including
uppercase and non-ASCII, then was restored. The final committed-manifest check
is exercised with root, ubuntu, node and dev, with host/scanner calls forbidden.
The final expanded command above returned rc 0: 654 tests in 91.947s, with the
same six existing optional upstream-surface skips; all native plants ran.

The historical instruction-reference citation is resolved from its actual
`56fced82727921f2de0d99790148acec0bdd11ca` source: the intended rule is at
`docs/harness-defaults.md:208` there. Current line 210 is unrelated. The resolver
comment now explicitly pins the historical guide/distro locators; the original
source blobs are attached, rather than shifting their line numbers by inference.

One step wider, the native actual-host scanner examined all 23 written and
registered PR paths, including unchanged portions: zero findings. A private
supplementary comparison for bare case-folded, percent, Unicode escapes, HTML
entities, base64, hex and zero-width account spellings returned zero in each
class. No private identifier or payload was printed. A context-mode metadata
context produced generic hits during a preliminary attempt; that attempt is not
claimed as host acceptance and was resolved by reproducing in the native shell
context. No leak is inferred from that wrapper-dependent observation.

The attachment closure now includes all 17 input files, the cited verdict wave,
historical derived manifest, upstream tag/commit API objects and the original
approved plan/design. The original plan was located through its maintained page
generator's PLAN declaration; its design table confirms the two planned layers.
The source manifest records every original byte count/hash. These captures
close missing-source packet gaps, not historical model execution gaps.

## Framing micro and Codex threads at 7ceedc64

Historical round at `e5b7d884`: its whole-line bound was rejected by the CC's
native per-entry adjudication and the confirmation micro. The terminal
correction below supersedes that publication mechanism and its size contract;
the source-binding and lower-pin corrections remain accepted.

The relaunched correction closes Astra's one privacy P2 and the four Codex
threads on `7ceedc64f38a0aa1fb4c48c6fb00ed62799d7141`. Search-first quick mode
selected the installed Betterleaks 1.9.0 native command and the reviewed
first-party adapters. The maintained upstream release API still identifies
`v1.9.0` as latest, and its tag resolves to
`81aff7a638638aae3a659845d089043e1d8fe9ac`; the native binary reports 1.9.0.
No scanner, decoder, page renderer, package or test runner is reimplemented.

Primary sources, retained unmodified in the review capture packet:

- [Native file reader](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/file.go)
  and [safe-boundary helper](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/common.go):
  100,000-byte reads, followed by at most 25,000 bytes to a double newline.
- [Native stdin route](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/stdin.go),
  [decoder](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/codec/decoder.go)
  and [encoding recognition](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/codec/encodings.go):
  the supported scanner owns recognition and nested decoding.
- [Reviewed first-party joins and loader](https://github.com/seathatflowsinourveins/native-agent-stack/blob/7ceedc64f38a0aa1fb4c48c6fb00ed62799d7141/scripts/final_stack.py)
  and [pin comparator](https://github.com/seathatflowsinourveins/native-agent-stack/blob/7ceedc64f38a0aa1fb4c48c6fb00ed62799d7141/scripts/host_receipts.py):
  reuse the native safe-file/hash loader and three-valued pin comparison.
- The approved plan's retained original is 55,018 bytes, SHA256
  `fb4a95b19a00335c5831bce913cbf177f90d5bd2c17819013b6021d2dc585e5c`.
  Its Design: ten layers table, lines 386-387, independently supports the
  two projected requirements. The checked-in
  [source-review supplement](2026-10-11-planned-layers-source-review.json)
  preserves the reviewed projection, source identity, original hash and row
  locators. It records no new trading selection or measured strategy result.

| Finding | Failing-before observation | Corrected behavior |
| --- | --- | --- |
| Astra framing P2 / Codex 4241125956 | Complete synthetic writer controls with 3,900-space prefix: long fully percent-encoded email and twice-percent-encoded account both fail with `SystemExit not raised` at the exact reviewed scanner; the oversized-line control fails too. The actual native writer and registration run on temporary fixtures without publication spies. | Whole original serialized lines are kept intact; a line over 24,000 UTF-8 bytes refuses. Native depth-5 decoding and the original boundary filters decide matches. Refusal preserves both existing output and registry bytes. |
| Codex 4241125957, planned-source binding | Two tests / five failing subcases: the committed binding was absent; missing reference, changed requirement, changed review bytes and an authentication-path reference all went unchecked. | Nonempty planned rows require the fixed checked-in review path, exact source SHA256 and equal reviewed rows. The new source is recorded in generated `sources`; the private plan path is never read by the generator. |
| Codex 4241125963, lower commit conflict | One test fails: equal lock/stack/runtime versions with different lower commits returned an empty conflict list. The equal-commit control passes. | Existing precedence is preserved. Fields absent from the chosen pin are compared between lower sources through the unchanged native comparator; both disagreeing sources remain visible. A first broad pairwise attempt also flagged an agreeing stack in a macOS version-drift fixture; the retained failed condition led to narrowing comparisons to absent fields. All 14 run tests then pass. |
| Codex 4241125959, Landscape consumer | The CC's author/plan-owner P3-10 ruling explicitly assigns the consumer to W4 PR 4 and forbids duplicate Architecture dated views. This is the staged generator contract, not evidence that the future page already exists. | Keep the authorized exclusion and planned-layer grant. Correct its reason to say the page is planned and is not shipped by W4 PR 2; no new page or consumer acceptance is claimed. |

The original six-control red run reports six failures and zero errors; a
follow-up using the exact unmodified reviewed scanner with the three complete
writer controls reports three failures and zero errors. The initial combined
focused check exceeded its 10-second tool timeout and is not acceptance.
After the bounded fix and the two Codex corrections, both full modules return
rc 0: 104 tests in 16.344s, zero skips. Earlier current-manifest assertions
correctly failed until the supported `final_stack.py --write` refreshed the
new plan binding and definition. The native refresh changes only `sources`
and `definitions`; layers, runs, summary and indexes are byte-equivalent as
parsed data to the reviewed manifest.

Unchanged upstream harness: `GOMAXPROCS=2 mise exec go@1.25.12 -- go test
./sources ./detect/codec` at the exact Betterleaks tag returns rc 0, both
packages pass (0.532s and 0.006s). The first bare `go test` attempt refused
because the mise shim had no selected Go version; it is not a test pass.
The supported per-command mise selection resolved that condition without
changing client configuration. These upstream tests are distinct from the
repository's synthetic integration controls.

One step wider: all callers of `_scan_entries` and `scan_paths` were checked
through the indexed graph, coverage check and exact call sites. Only final-stack
publication opts into email mode. General validation and author/history scans
retain their prior contracts. The publication controls span offsets 0, 3,900,
3,980, 4,090, 4,110 and 8,000; long percent/Unicode/base64 email, one through five
percent decode levels, decoded alphanumeric neighbors, native chunk crossings,
exact UTF-8 line limits, scanner/context errors and unchanged-output refusal.
The new source loader checks containment through the native loader and refuses
the wrong path before opening it. Equal/differing lower commits and existing
platform/version precedence have separate controls.

Completeness critic: single-encoded literals cannot bound every depth-5 token;
publication therefore bounds the entire serialized line and refuses oversized
inputs rather than estimating token length. Literal string newlines are JSON
escapes; this is a bounded serialized-publication contract, not a new guarantee
for every multiline encoding in general repository/history scans. The original
plan is retained for independent review while only its sanitized source-review
projection is checked in. The future page remains separate W4 work. Expanded
gates, registered evidence and exact-head publication are recorded in the final
handoff; no model run or hosted-green result is inferred from these local checks.

## Terminal native per-entry correction

Historical correction at `bdb4231a`: the adapter scanned native input per file,
but its caller still passed the whole report as one file. The NEW P1 correction
below supersedes this input contract; its earlier unlimited-record claim is
not current acceptance.

The complete 22,476-byte GPT confirmation verdict at `e5b7d884` has SHA256
`2f7cdbfad9a7ba43dc0ec74a1e9109b113e51c105d704bd1a80b1f3f41c4b247`.
Its one blocker reproduces the defect introduced by the prior repair: a
native-clean title of 24,001 ordinary `x` characters was refused by the local
line-size bound. The CC had selected the supported native per-entry route,
not that framing amendment. This correction implements the selected route
without reopening candidate selection or expanding the fix scope.

Primary source is Betterleaks 1.9.0 at
`81aff7a638638aae3a659845d089043e1d8fe9ac`:
[cmd/stdin.go:47-49](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/cmd/stdin.go#L47)
and [sources/stdin.go:18-25](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/stdin.go#L18).
Their original bytes are already in the retained capture packet. Publication
now invokes that native command separately for each entry with its original
text, unframed native rules and no repository input-size limit. It shares the
existing redacted report validation and subprocess isolation with the general
scanner; no decoder or boundary matcher is added. Vendor input fragmentation
remains the vendor's behavior, rather than another local overlap contract.

The native-clean reader regression is ported into the existing CheckTests
fixture and verifies actual output plus registration. It was red on `e5b7d884`
before the production edit. The two existing complete-writer plants are
retained; the exact `7ceedc64` scanner produces four failing subcases (three
email encodings and twice-percent-encoded account), while the corrected native
route refuses them and preserves output/registry bytes. Native adapter tests
also observe a separate stdin invocation for each original entry, unchanged
control characters/text, unframed configuration, native-clean large inputs and
decoded alphanumeric neighbors. Both complete modules pass 105 tests in
41.100s with zero skips on this host.

The reader's standalone script could not start because its local cached packet
lacks `tree/tests/test_final_stack.py`; that missing-fixture attempt is retained
as an error, not a regression result. The equivalent regression runs through
the repository's existing fixture and unittest harness. An earlier aggregate
48-entry scanner fixture also failed under native reader fragmentation; it was
reconciled to separate original entries, as the adjudicated contract requires,
without changing the vendor or introducing framing. Failed attempts remain
distinct from passing results.

Scope-locked P3 follow-ups, carried in the hosted PR body: output/registry
recovery on registration failure; retain complete release-response and raw
vendor-harness execution evidence; correct the pre-existing CI-interpreter
workflow locator through its source. General account/history nested-token and
multiline coverage remains in the secrets/security research queue. None is
folded into this terminal blocker correction unless expressly adjudicated below.

The co-op relayed the CC's final release at 15:52:46Z. The pinned local mirror
now resolves to `81aff7a638638aae3a659845d089043e1d8fe9ac`; its original
`cmd/stdin.go` and `sources/stdin.go` were read with `GIT_NO_LAZY_FETCH=1` and
`GIT_OPTIONAL_LOCKS=0` and agree with the retained sources. This is the selected
native route, not a new scanner selection or a new upstream Go-harness run.

The release permits Codex thread 4241892054 to become a follow-up if the
platform predicate predates `7ceedc64`. It does: the `platforms` assignment is
identical at initial generator `6fbd22d5` (lines 404-406), `f5bd15dd` (409-411),
`7ceedc64` (410-412) and `e5b7d884` (423-425), normalized AST SHA256
`a0cd56fb8ff0d3a9c8f0cde3a705b20861b6f64628128cb5c0a8ef33339e67e4`.
Executing the original `build_runs` bodies at the first two pins with synthetic
equal-version/different-commit platform records reproduces both platform names
and a macOS conflict. This is source review plus a synthetic function probe,
not a new upstream test. It is explicitly routed to the PR-body follow-up
under the CC exception; the pin-selection code is unchanged in this correction.

The cheap CI-interpreter comment is corrected in one line to the explicit
historical provisioning statement at
[0d822e91 `.github/workflows/validate.yml:201-202`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d822e91c95d0f3cb24a76270daff67840b4da06/.github/workflows/validate.yml#L201).
Its original source is retained; no interpreter or fixture behavior changes.
Atomic registration recovery and complete upstream-execution/latest-release
evidence remain the requested P3 follow-ups.

Required local gates pass: 105 tests/zero skips in both owned worktrees;
FULL validate/evidence/final-stack pass 11,479 files on the held-head preparation
and 11,489 files on main `1e6a49ff` plus the full prepared PR applied with native
`git apply --3way --index`. That genuine merged worktree has no conflicts or
synthetic registry repair. The direct validation-caller module also passes 84
tests/zero skips. An optional nine-module expansion hit its 240-second tool
timeout without a complete count and is not acceptance. Original privacy
controls are red at `7ceedc64`; the benign native-clean control is red at
`e5b7d884` (one failure, zero errors). All are green on the selected native route.
The final released commit and exact lease are recorded in the co-op handoff;
no further fix round is authorized except a new P1.

## NEW P1: actual publication records and source-pin fidelity

The CC's 17:27Z adjudication (`adjudication-pr1007-bdb4231a-20261011.md`, 3,013
bytes, SHA256 `14460c5bcc37647d35559b5aa466991da035c929ffbcb86938f166fef6c7975f`)
authorizes ONE correction after a mechanical rebase onto main `bcf55c45`.
Its new evidence shows that the whole 300 KB file was still one stdin entry;
the pinned vendor's nonoverlapping fragments can cut private tokens. This
correction follows the adjudicated native mechanism and input contract.

Primary source: the local Betterleaks mirror at
`81aff7a638638aae3a659845d089043e1d8fe9ac`, read with no lazy fetch/optional
locks. `sources/file.go:283` reads up to 100,000 bytes but permits a short
read; `sources/common.go:72-141` adds at most 25,000 lookahead bytes. Therefore
the nominal buffer size alone is not a safe per-record bound. A JSON record
strictly below 25,000 serialized UTF-8 bytes reaches EOF within the first
read plus lookahead. A record at or above that bound fails closed; there is
no repository byte splitting, overlap, sentinel or synthetic newline framing.

The writer now enumerates actual layer and run objects, individual normalized
repository/component index mappings, and the remaining report metadata entries.
Each is serialized as a JSON object and scanned in its own native stdin call.
The scanner verifies `{` at byte zero, a parsed JSON object, and the strict
byte bound before invoking native detection. All report string values and keys
are retained in these records. Whole oversized records refuse rather than
splitting their tokens. Native depth-5 decoding and Expr boundaries are unchanged.
The old benign-title regression now uses a 23,000-character title whose entire
record fits the new contract; a separate oversized-layer test proves refusal
and byte preservation. This is the new explicit guard from the P1 ruling.

Failing-first evidence on rebased, otherwise unchanged `bdb4231a` code:

- The full native writer has 20 small layers padded so each of a bare account,
  the original percent-encoded email and the original twice-percent account
  crosses byte 90,536. The exact output offset is asserted. One test reports
  three failures, zero errors (`SystemExit not raised`); all three published.
  After actual-record scanning, the same controls refuse and preserve both
  existing output and registry bytes.
- Native adapter prefix/size controls report three failures before guards:
  an oversized JSON object and PDF/RTF prefix inputs were accepted. The guards
  now refuse them; below/equal/above 25,000-byte cases distinguish the bound.
- One real-data test reports four failing subcases: restic/dagu tags and
  PostgreSQL/Poppler artifact SHA256 source pins were absent from their runs.
  `record_pin` now retains raw noncommit `source_pin` and `source_pin_kind`
  (`tag` or `sha256`) without inventing a Git commit. The four real rows pass.
  The canonical meaning is defined in `docs/foundation-layer-map-20261008.md:34-36`.
  The old unit assertion that discarded a tag is reconciled to this corrected
  contract; version/commit parsing and precedence remain unchanged.

Rebase evidence: earlier five substantive patches compare `=` with native
range-diff after explicitly excluding mechanical evidence/count files and the
append-only table plus main-updated exclusion-fixture context. Full range-diff
is retained too; it displays `!` for those mechanical/context changes and is
not relabeled as literal `=`. All 281 anti-pattern rows from the old branch and
all 281 rows from main were individually verified present byte-unchanged before
the new row above. The authorized CC recomputation tool handles supported hash
pairs/counts but refuses insertion-shaped registry conflicts or no-count-conflict
stages. Those stages preserve the current merged registry and recompute owned
bindings through the existing `host_receipts.register_file` hot-file protocol.
An initial shell sequence continued after the helper failed; that entire rebase
was aborted and restarted from the preserved reviewed head, with each subsequent
step checked. No failed attempt was pushed or counted as acceptance.

The first post-fix full generator run reports 71 tests with one stale expected
tag-discard assertion; new privacy and real-pin controls pass. The initial
scanner run reports one oversized aggregate-neighbor fixture; it now supplies
individual JSON entries under the same contract. These failed intermediate
conditions remain distinct from the final gates. The cheap stale email-rule
comment is corrected. Scope-locked follow-ups remain the old conflicting-
platform predicate, non-atomic registration, upstream-execution evidence and
framed non-publication callers. Only another NEW P1 can reopen this correction.
