# FINAL preparation: foundation/git-github-automation

This working draft proposes one run pin for each existing winner, retains a
deterministic masked derivative of real vendor install/smoke captures, and
supplies a five-candidate angle-record draft. It prepares the layer for the
co-op's two-family review. The per-component E2E files and invoke file are
explicitly derived navigation indexes, not native receipts. A FINAL-qualifying
E2E receipt/disposition remains pending; the draft's E2E receipt fields are null.
Every draft verdict re-derives as **INSUFFICIENT**; the layer remains
**NON_TERMINAL**. No active angle record, catalog verdict, portable pin, default
or FINAL admission changes in this PR.

The base is main revision `30542e70560147c19049016d19aa3f264515c92f`.
The coordination input is `final-wave-layer-prep.brief-20261016.md`, cited by
name only. This preparation is SINGLE-FAMILY GPT. Both families' reads are
pending co-op dispatch; no model comparison or adjudication was self-dispatched.

## F1: reconcile the run pins

| Winner | Sealed verdict | Canonical run | Install-plan script | Installed version | Proposed run |
| --- | --- | --- | --- | --- | --- |
| worktrunk | 0.79.0 | 0.80.0 | 0.80.0 | 0.80.0 | **0.80.0** |
| GitHub CLI (`candidate:cli-cli`, run id `gh`) | unpinned | 2.101.0 | 2.102.0 | 2.102.0 | **2.102.0** |
| difftastic | 0.71.0 | 0.71.0 | 0.71.0 | 0.71.0 | **0.71.0** |

[pin-reconciliation.json](pin-reconciliation.json) cites each source on the
base revision by path and line: the final-stack winner and `runs[]` rows, the
clean-install decision's layer row and installed-client citation, the executable
install-plan rows, the underlying stack/portable pin records, and the last
linked pin-specific evidence consumed. [host-versions.json](host-versions.json)
retains the text of read-only version probes. Those probes used text mode and
lack separate original-byte captures: that gap is explicit, and they are not
labelled native-byte receipts. The evidence search is bounded to the linked
records; it does not claim an exhaustive history of every host report or
documentary relabel.

The worktrunk proposal follows the current run, stack, plan and prior 0.80.0
qualification, with fresh lifecycle evidence below. Its sealed 0.79.0 winner
remains a drift requiring adjudication. The gh proposal follows the plan,
installed client and previously committed unchanged-upstream test/build
qualification at 2.102.0. Both portable pin files and final-stack still use
2.101.0; the sealed winner is unpinned. These are explicit unresolved drifts.
Difftastic has no version drift; its version-only run record is supplemented by
the resolved source identity below.

| Component | Proposed release | Resolved upstream source |
| --- | --- | --- |
| worktrunk | v0.80.0 | `b49ca7eea9b03145791a5b94eccaf9c59412ed37` |
| gh | v2.102.0 | `fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd` |
| difftastic | 0.71.0 | `b7d119e90ac9f972f03f69508da765dacd302c0c` |

## E2E and F2: fresh bounded execution

All three tools were downloaded from their vendor's own GitHub release assets,
checked against the release API's published asset digest, and unpacked into
isolated scratch prefixes under `/var/tmp`. Configuration and Git fixtures also
belong to that scratch. No package manager, shell integration, plugin install,
profile edit, service or unit was used. The scratch binaries remain only inside
the scratch. These are Linux x86_64 vendor-binary smokes, without a complete
source build/test suite or another platform's acceptance.

| Derived navigation index | Fresh local behavior | Derived zero-exit install/smoke count | Derived native invoke count |
| --- | --- | --- | --- |
| [worktrunk.e2e.json](worktrunk.e2e.json) | create/list/remove; two disposable worktrees return to one; dirty removal refused; separate preservation-capture gap | 9 | 6 |
| [gh.e2e.json](gh.e2e.json) | native PR-review help and Bash-completion generation; generated completion accepted by `bash -n` | 7 | 2 |
| [difftastic.e2e.json](difftastic.e2e.json) | upstream JavaScript sample pair; same/different exit controls; separate native JSON-gate probe | 6 | 4 |

[native-commands.json](native-commands.json) retains all **29 command
observations**, including installation and fixture setup. There are 26 zero
exits and three expected nonzero outcomes: worktrunk dirty-removal refusal
(`1`), difftastic changed-file detection (`1`), and the documented unstable-JSON
gate without `DFT_UNSTABLE` (`2`). The 27 commands with a declared expected exit
matched it. These counts are derived arithmetic over the captured command
records; [integrity-source-map.json](integrity-source-map.json) gives the
supporting command, exit-code and output lines. Dirty-file preservation was a
private-driver assertion without a separate native filesystem capture. That
missing capture is a named gap, not a passed native preservation test. Full
upstream suite tests executed in this preparation: **0**. No credentialed
GitHub operation was attempted.

[invokes.json](invokes.json) is a derived index binding 12 task-triggered
component invocations to the real masked capture's commands, pin, timestamps,
exits, output hashes and source lines. It contains no tool output and is not
itself an invoke receipt. These are deliberate qualification invocations of
the scratch binaries. They do not establish organic fresh-session adoption or
an adoption-wide invocation census.

The native receipt is [native-commands.json](native-commands.json), labelled
`masked_derivative_of_native_capture`. Each output hash covers the exact
**published** UTF-8 stdout or stderr field. The literal masking rules in
[mask_receipts.py](mask_receipts.py) replace the scratch root with `<SCRATCH>`
and the disposable Git commit identity with `<FIXTURE_COMMIT>` in commands,
working directories and output. The script first verifies the original private
stream hashes, then computes hashes of the published streams. It never copies
private stream digests into provenance metadata.

The private capture is named `git-github-native-command-capture-20261016`;
its locator was supplied to the co-op privately, without a digest. The co-op's
`MASKED-REPRO CHECK PASS` records byte-identical reproduction (`cmp` exit 0),
seven masking/custody tests OK and zero private-locator scan hits; that private
check is cited by name only. [test_mask_receipts.py](test_mask_receipts.py)
checks deterministic masking, byte preservation, negative exits, tampering and
private-capture reproduction. Its synthetic unit fixtures are explicitly test
data and never presented as E2E or invoke output. The private-capture test
failed against the old projection and passed after regeneration. A separate
public native log of those utility tests was not retained; that capture gap is
recorded in [adjudication.json](adjudication.json).

From this artifact directory, the reproduction commands use marked private
input placeholders:

```sh
python3 mask_receipts.py --raw '<PRIVATE_NATIVE_CAPTURE>' --out native-commands.json
python3 test_mask_receipts.py --raw '<PRIVATE_NATIVE_CAPTURE>' --published native-commands.json
```

No original-stream digest or digest of the unshared fixture commit is published.
The Git inputs were a disposable synthetic fixture; the component outputs are
real native executions against it. Release/source checksums refer to public
upstream bytes. Checksumming an asset against its release API digest is the
recorded integrity check; signature/attestation verification is not claimed.

The collector's initial assertion treated Worktrunk JSON as a bare array.
Native `wt list` itself exited zero. The retained output and pinned
[schema-2 implementation](https://github.com/max-sixty/worktrunk/blob/b49ca7eea9b03145791a5b94eccaf9c59412ed37/src/commands/list/json_v2.rs#L1)
show the `items[].worktree.path` envelope; the resumed smoke used that shape.
The lookup and orchestration corrections are retained in
[adjudication.json](adjudication.json). No upstream defect or production code
fix is claimed.

## Resolution inputs and the five-candidate delta

The recorded verdict is wave `20260922`, with the foundation layer at
`catalogs/landscape/foundation.json:5043`. The latest covering sweep is
`landscape-sweep-20260929` (`catalogs/saturation/ledger.json:7694`, layer at
`:10776`), with its manifest and retained returns. The 20260923 and 20260926
manifest/return evidence is also consumed. The September 23 return has no
retained per-vote return, as the ledger records; its retained survivor artifact
and manifest votes remain the available evidence. September 26 retains a
critic web-search-cap failure. September 29's pin-moved reopen references are
historical sweep observations, not claims about this smoke.

Both cumulative unresolved survivors remain in scope:

- `anthropics/claude-code-action`, retained tag v1.0.233, resolved to
  `8cf3482550831fb35a4fc3fbf7ca139cf8028b4c`;
- `ataraxy-labs/sem`, retained tag v0.25.0, resolved to
  `4cfe1374f79631b01aca5746441d826738a15448`.

[packet-projection.json](packet-projection.json) comes from successful
`tools/sota-convergence/lane_packets.py` runs using manifests 20260929 and
20260923, `--registered-receipts`, `--manifest-newcomers` and
`--withhold-labels`. The latest packet alone omits the earlier action survivor.
The projection carries that row from the older generated packet and retains
only the three winners and these two survivors. Generator candidate keys are
scoped to their manifest; this projection asserts no common blind-comparison
seal. The supported CLI rejected `--gap-receipts` combined with withheld labels
(exit 2); successful generation omitted the winner-bearing gap receipts.

[angle-record.draft.json](angle-record.draft.json) follows the existing
`angle-convergence/2` schema and default weights. Its statement time is the
observed scratch weight-record modification time, preceding the fresh source
reads and scoring. Prior verdicts and source leads were visible: this is
disclosed re-verification. The repository's current validator and derivation
accept the draft and re-derive all five rows as INSUFFICIENT.

| Angle | Evidence in this delta | Disposition |
| --- | --- | --- |
| A1 capability at pin | winner vendor installs/local smokes; source reads at the two survivor pins | three narrowly positive winner scores; survivor screens unverified |
| A2 upstream engineering | native test/CI definitions at each winner's exact source commit | positive process evidence; no fresh full-suite or CI-outcome claim |
| A3 community consensus | no pin-specific independent consensus measurement retained | U |
| A4 net usage | release downloads and qualification invokes are available, without production net-usage accounting | U; downloads are not substituted for usage |
| A5 published evaluations | carried sem vendor self-evaluation: 3 commits, 4 questions, 24 API calls, Claude Sonnet 4.5 versus raw git diff | sem neutral `0`; no demonstrated v0.25.0 binding, independent replication or difftastic arm; other rows U |
| A6 our comparative runs | no new matched challenger run | U; local smokes remain A1 |

The known vendor evaluation is available, so its A5 weight stays at the stated
value; no unavailable-evaluation weight transfer is applied. Its numbers are
published self-report, not measurements made by this preparation. Every angle
value is a source-review judgment or a named unverified gap, not a measured
numeric score; [integrity-source-map.json](integrity-source-map.json) retains
each value's draft line and supporting source. The A2 locators point to the
actual relevant CI source, including worktrunk's nextest-suite comment at
`ci.yaml:107`, gh's command at `go.yml:32` and difftastic's command at
`test.yml:61`.

## Disputed dimensions and named gaps

[adjudication.json](adjudication.json) is the co-op handoff. It names gh's
2.101.0/2.102.0 drift, worktrunk's 0.79.0/0.80.0 verdict drift, sem's stable
machine-readable diff claim against difftastic's reproduced JSON gate, and the
action's unattended PR-review role versus the local CLI smoke scope.

The retained 20-file structural-coverage and agent surfacing comparison rule
remains the next measurement for sem versus difftastic and plain git diff. The
prior returns' 15/20 and 3/4 observations are historical evidence; neither that
fixture nor the survivor arm was rerun here. Sem was not installed, configured,
logged in or invoked. The action was source-reviewed at its carried pin and
was not installed or connected to a live runner. Its credentialed disposable
PR-review comparison remains a named gap.

Full upstream Rust/Go suites, authenticated GitHub PR lifecycle, organic
fresh-session use, cross-host coverage and the remaining A3-A6 evidence require
their own authorized isolated runs or sourced dispositions. Co-op two-family
reads and the closed FINAL admission gate remain prerequisites beyond this
evidence preparation.

## SOTA sources

- [max-sixty/worktrunk v0.80.0](https://github.com/max-sixty/worktrunk/releases/tag/v0.80.0),
  commit `b49ca7eea9b03145791a5b94eccaf9c59412ed37`: `README.md`,
  `dist-workspace.toml`, `.github/workflows/ci.yaml`, and
  `src/commands/list/json_v2.rs`.
- [cli/cli v2.102.0](https://github.com/cli/cli/releases/tag/v2.102.0),
  commit `fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd`: `docs/install_linux.md`,
  `pkg/cmd/completion/completion.go`, `.github/workflows/go.yml`.
- [Wilfred/difftastic 0.71.0](https://github.com/Wilfred/difftastic/releases/tag/0.71.0),
  commit `b7d119e90ac9f972f03f69508da765dacd302c0c`:
  `manual/src/installation.md`, `manual/src/usage.md`, `README.md`,
  `sample_files/simple_1.js`, `sample_files/simple_2.js`,
  `.github/workflows/test.yml`, `src/options.rs`.
- [anthropics/claude-code-action v1.0.233](https://github.com/anthropics/claude-code-action/tree/8cf3482550831fb35a4fc3fbf7ca139cf8028b4c):
  `README.md` and `action.yml`, source review only.
- [ataraxy-labs/sem v0.25.0](https://github.com/Ataraxy-Labs/sem/tree/4cfe1374f79631b01aca5746441d826738a15448):
  `README.md`, source review only; the carried
  [vendor agent evaluation](https://ataraxy-labs.github.io/sem/agents.html)
  has a separate live-page provenance boundary.

[source-reads.json](source-reads.json) retains URL, exact source identity,
read time, selected public source lines and public upstream checksums. It is
source review, not a native HTTP receipt: full original HTTP response bytes
were not retained in this artifact. The integrity changes follow
`final-wave-layer-prep.brief-20261016.addendum-01.md` and
`final-wave-layer-prep.brief-20261016.addendum-02.md`, cited by name only. The
masking utility uses CPython's standard-library JSON and SHA-256 interfaces;
no upstream component behavior or default changes.
Artifact registration uses `scripts/host_receipts.py:register_file`; the PR
records registration and the required `python3 scripts/validate.py` result.
