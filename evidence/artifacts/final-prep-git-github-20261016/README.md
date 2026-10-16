# FINAL preparation: foundation/git-github-automation

This is evidence preparation for one layer. It proposes run pins, retains
bounded native scratch execution and its private custody, and records a
five-candidate angle draft. All five verdicts remain **INSUFFICIENT** and the
layer is **NON_TERMINAL**. Formal E2E and adoption-invoke receipt fields are
null with named gaps. No canonical pin, sealed verdict, default or FINAL
admission is changed.

The base is `30542e70560147c19049016d19aa3f264515c92f`. The correction follows
the CC's `MICRO-full-f62f2e82` ruling on the initial head, cited by name only.
Preparation is SINGLE-FAMILY GPT; the co-op dispatches both families' reads
after the one correction fold. No model comparison was self-dispatched.

## F1: proposed pins and their supporting records

| Winner | Sealed verdict | Canonical run | Executable install plan | Native host-version custody | Proposed run |
| --- | --- | --- | --- | --- | --- |
| worktrunk | 0.79.0 | 0.80.0 | 0.80.0 | GAP | **0.80.0** |
| gh (`candidate:cli-cli`) | unpinned | 2.101.0 | 2.102.0 | GAP | **2.102.0** |
| difftastic | 0.71.0 | 0.71.0 | 0.71.0 | GAP | **0.71.0** |

[pin-reconciliation.json](pin-reconciliation.json) gives each consumed
base-revision source at its actual supporting path and line: final-stack winner
and run rows, the clean-install decision, its executable plan, portable/stack
pins and linked historical qualification. The plan's layer row names the
components and outstanding work; it does not supply all versions.

Worktrunk's proposal follows its run/stack/plan 0.80.0 and linked qualification;
the sealed 0.79.0 verdict remains drift. Gh's proposal follows plan 2.102.0 and
the existing committed upstream qualification; portable and canonical 2.101.0
pins remain drift, and the sealed verdict remains unpinned. Difftastic's
release versions agree. [host-versions.json](host-versions.json) is a named
GAP, with no host stream hash or native receipt: earlier text-mode observations
had no original-byte custody and do not establish installed-host qualification.

| Repository | Release tag | Full source identity |
| --- | --- | --- |
| max-sixty/worktrunk | v0.80.0 | `b49ca7eea9b03145791a5b94eccaf9c59412ed37` |
| cli/cli | v2.102.0 | `fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd` |
| Wilfred/difftastic | 0.71.0 | `b7d119e90ac9f972f03f69508da765dacd302c0c` |

The correction now retains native `git ls-remote --tags` commands and exits for
all three winners and both survivors, including annotated-tag peeling for
claude-code-action. Their exact output locators are in the pin/source records
and [integrity-source-map.json](integrity-source-map.json). These are fresh
resolution observations after the original smoke, not reconstructed historical
API responses.

## Native execution and the scope of the indexes

[native-commands.json](native-commands.json) is a deterministic masked derivative
of real recorder captures. The original component qualification has **29 rows**:
26 zero exits, difftastic changed-file detection exit 1, worktrunk dirty-removal
refusal exit 1, and the difftastic unstable-JSON gate exit 2. Exactly 27 rows had
declared expected exits and matched them. The latter refusal/gate probes had
null expected-exit fields: their nonzero exits were observed, not predeclared
expected outcomes. Dirty-file preservation was asserted by the private driver
without a separate native filesystem capture and remains a named gap.

| Derived index | Zero-exit rows in `commands[]` | Observed nonzero rows in `negative_controls[]` | Native component calls |
| --- | --- | --- | --- |
| [worktrunk.e2e.json](worktrunk.e2e.json) | 9: install/version, create/list/remove | dirty refusal, exit 1 | 6 |
| [gh.e2e.json](gh.e2e.json) | 7: install/version, help/completion and Bash parse | none | 2 |
| [difftastic.e2e.json](difftastic.e2e.json) | 6: install/version, upstream sample diff and same-file check | changed files, exit 1; JSON gate, exit 2 | 4 |

These files and [invokes.json](invokes.json) are navigation indexes, not native
receipts or E2E acceptance objects. Their counts are derived from native rows.
The 12 component calls are deliberate scratch qualification; they do not
establish organic-session use or adoption-wide usage. Formal invoke fields
remain null because the command array does not satisfy the separate
`kind: invocation`, matching pin, positive calls and measured-window contract
in `scripts/final_stack.py:944-947,974-976`. Their non-invocation reasons explain
the missing adoption receipt without denying the observed scratch activity.

Every tool was unpacked only into an isolated `/var/tmp` prefix. No global
install, shell/plugin setup, service, credentialed GitHub operation or full
upstream suite was run. Worktrunk's release installer is now the install-path
source: at v0.80.0, `worktrunk-installer.sh:338` extracts the archive and `:561`
selects the Linux archive. The receipt distinguishes the observed direct
scratch extraction from running that installer; it does not claim a literal
vendor installer invocation.

The correction adds fresh native release-API requests and fresh downloads,
followed by post-download `sha256sum` and an actual-versus-published check.
[verify_release_asset.py](verify_release_asset.py) reads the digest from the
captured API response and computes the downloaded file's digest at execution
time. Its native output includes both public values and
`actual_equals_published=true`, with exit 0. This is a local integrity check,
not a signature check, attestation check, upstream suite or replacement for the
earlier command result. Additional source and validator observations are
separate supplemental rows; the source map gives their command/exit/output
lines. Total-row arithmetic does not turn provenance requests into component
invocations.

## Private source custody and public masking

The complete generated Bash completion, PR-help text, source files and release
API bodies stay in a private **horizon custody worktree**. Public records cite
the custody by name only: `git-github-native-command-capture-20261016`,
`git-github-fold-native-capture-20261016` and
`git-github-source-custody-20261016`. No private locator or private raw digest is
a publication source.

[mask_receipts.py](mask_receipts.py) verifies the private stream hashes and then
replaces private paths/fixture identities with marked placeholders. It also
withholds complete generated/help/HTTP output behind
`<UPSTREAM_GENERATED_COMPLETION_WITHHELD>`, `<UPSTREAM_HELP_TEXT_WITHHELD>` or
`<UPSTREAM_HTTP_RESPONSE_WITHHELD>`. Source excerpts become
`<UPSTREAM_SOURCE_TEXT_WITHHELD>`; URL, pin, public-source SHA-256 and original
line citations remain in [source-reads.json](source-reads.json). Hashes attached
to published native streams cover the exact **published derivative bytes**.
Public-source checksums identify openly served upstream material; they are
distinct from forbidden digests of unpublished private input.

The historical source projection is retained privately. Fresh pinned source
reads have separate native commands and timestamps, and match the retained
public-source checksums. They are not passed off as historical HTTP captures.

[test_mask_receipts.py](test_mask_receipts.py) reads the actual committed
derivative in public tests, verifies its stream hashes and enforces withholding
of generated/source text. Its optional private checks reproduce both public
native and source derivatives. Synthetic unit fixtures are labelled test data,
not E2E results. [test_evidence_claims.py](test_evidence_claims.py) guards against
host-gap hashes, unsupported A1/A2 upgrades, incorrect tag/digest claims,
nonzero-control count confusion, invalid formal invoke pointers and the sem
citation error. The regression checks failed before the corrections.

The native utility captures record 11 masking/custody tests, eight evidence
boundary checks, two digest-helper tests and a successful call to the current
angle validator. Their outputs are supplemental native rows, not driver
acceptance flags. A later rerun does not change those captured timestamps.

The old co-op reproduction PASS applied to the initial derivative. The changed
masking rule and supplemental data require a **new private co-op PASS before
the one fold is pushed**. The native validator/test commands and return codes
are retained as supplemental capture rows; the public metadata is not a
stand-in for those commands.

## Resolution inputs and the five-candidate angle draft

The verdict wave is 20260922. The latest covering sweep is 20260929, with its
manifest and retained returns; 20260923 and 20260926 sources preserve the
cumulative unresolved survivors. The missing September 23 per-vote return and
September 26 capped critic search remain historical limitations. The generated
packet projection carries only the three winners and both survivors, using
the older generated packet for the action survivor omitted by the latest one.
Candidate keys remain scoped to their source manifest; no blind-comparison seal
is asserted by the projection.

- claude-code-action v1.0.233 resolves to
  `8cf3482550831fb35a4fc3fbf7ca139cf8028b4c`; no runner trial was performed.
- sem v0.25.0 resolves to `4cfe1374f79631b01aca5746441d826738a15448`;
  no sem install, setup, login or native survivor trial was performed.

[angle-record.draft.json](angle-record.draft.json) uses the existing schema and
default weights, with disclosed prior exposure to the sealed verdict/source
leads. It is re-verification, not a blind or preregistered comparative trial.

| Angle | Current disposition and limit |
| --- | --- |
| A1 capability | Worktrunk/difftastic retain bounded local positives. Gh stays U with its capability screen false: help/completion does not establish PR automation. Survivor screens stay unverified. |
| A2 engineering | U for all winners. A CI definition alone does not establish the documented Scorecard + release + CI basis; Scorecard coverage remains a gap. |
| A3 community consensus | U; no independent pin-specific consensus measurement. |
| A4 net usage | U; download counts and deliberate qualification invokes are not net usage. |
| A5 published evaluation | Sem is neutral `0`; the explicit 3-commit/4-question/24-call vendor self-report is sourced to `catalogs/sota-convergence/manifest-20260926.json:11337` at the base, not the old CSS excerpt. No independent replication, difftastic arm or proven release binding. Other rows stay U. |
| A6 comparative runs | U; no new matched challenger run. Local smokes remain A1. |

Known vendor evaluation availability preserves the stated A5 weight; no
unavailable-evaluation transfer is applied. All five candidate verdicts
re-derive as INSUFFICIENT. Each value and supporting source is indexed at its
actual draft/source line in `integrity-source-map.json`.

[adjudication.json](adjudication.json) retains the disputed pin dimensions,
formal E2E/invoke gaps, host byte-custody and preservation gaps, credentialed PR
lifecycle, full suites, organic-session/cross-host use and survivor comparisons.
The fresh provenance correction does not close those unrelated gaps. No
host-installed version is inferred from a scratch version string.

## SOTA sources

- [max-sixty/worktrunk v0.80.0](https://github.com/max-sixty/worktrunk/tree/b49ca7eea9b03145791a5b94eccaf9c59412ed37):
  `dist-workspace.toml`, `.github/workflows/ci.yaml`,
  `src/commands/list/json_v2.rs` and the vendor release's
  `worktrunk-installer.sh:338,561`.
- [cli/cli v2.102.0](https://github.com/cli/cli/tree/fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd):
  `docs/install_linux.md`, `pkg/cmd/completion/completion.go` and
  `.github/workflows/go.yml`.
- [Wilfred/difftastic 0.71.0](https://github.com/Wilfred/difftastic/tree/b7d119e90ac9f972f03f69508da765dacd302c0c):
  `manual/src/installation.md`, `manual/src/usage.md`, the two upstream
  JavaScript samples, `src/options.rs` and `.github/workflows/test.yml`.
- The carried [action](https://github.com/anthropics/claude-code-action/tree/8cf3482550831fb35a4fc3fbf7ca139cf8028b4c)
  and [sem](https://github.com/Ataraxy-Labs/sem/tree/4cfe1374f79631b01aca5746441d826738a15448)
  source identities above, without a survivor trial.
- GNU coreutils `sha256sum`, Git's `ls-remote --tags`, curl's HTTPS request/
  output path, CPython JSON/SHA-256 and the repository's current
  `scripts/angle_records.py:109` validator are used directly. No new framework
  or upstream fork is introduced.

Artifact registration uses the existing `host_receipts.register_file` helper.
Required repository validation and the one-fold publication remain subject to
the co-op's fresh reproduction check and ruling.
