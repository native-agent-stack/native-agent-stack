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
