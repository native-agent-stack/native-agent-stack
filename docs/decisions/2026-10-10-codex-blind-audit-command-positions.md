# Codex blind audit: command positions and read operands

Date: 2026-10-10; review correction: 2026-10-11. Initial base: `9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`.
Historical landing base: `c4f4990737c4e2ed8f0452d069e25a460f897bb5`.
Prior bytes-correction landing base: `eb31d233234cdc552fc81672087ac8769e3696e0`.
Current CC-authorized landing base: `65cf2730068429a1c48c8c18fb24aadef8120817`.

The tier-1 run produced four text-match quarantines: document-retrieval's Python `'/'.join(...)` separator,
git-github-automation's `rg '(git|diff|...)'` pattern, mcp-surfaces' backtick string inside a quoted Python
heredoc, and the later workers rerun's `'://'` membership guard. The retained command metadata supplies the
regressions. Exec JSONL alone has no independent cwd records. The corrected blind verdict lane retains native
command history in a fresh scratch home and binds that history to the exec events before audit. Commands
without a unique matching native record remain **UNVERIFIED**. Clean four-command parser fixtures supply
synthetic cwd records; they do not attest raw production streams. The collected receipts, session homes and verdicts are
preserved. The CC's separate acceptance of the four historical quarantines is an adjudication of that run.
The new native-history path is source-reviewed and fixture-tested; live provider execution is **UNMEASURED**.

The workers membership guard skips external evidence references before statting relative files. Its command
is retained byte-for-byte. Bounded static JSON projection resolves the references from a digest-bound approved
packet. The snapshot loader checks a trusted digest or the approved root's `SHA256SUMS`, the flat packet
filename/schema, no-follow directory/file descriptors, a single-link regular file and descriptor/path identity.
Nonblocking leaf opens refuse FIFOs before they can wait. Packet input is capped at 1 MiB and its hash list at
128 KiB; accepted JSON is capped at 20,000 nodes and 64 levels. The restricted domain supports default
`json.loads`, literal subscripts, Name-target list/set comprehensions and `sorted`, with finite work and
collection budgets. It reads the packet and hash list; it never opens evidence references. Unsupported
projection, relevant mutation, callbacks, reflective namespace changes and unresolved reads stay refused.
URI skip guards apply only where their `continue` dominates the read, including reads through path aliases.
Reads earlier in the loop or inside the guard receive no such filter. These data-flow checks still require
an independent cwd binding for the command as a whole.

The CC's 19:56Z landing cue also folds in the supervisor usage-key correction. Native usage rows use `layer`,
while returned verdict objects use `layer_id`; confusing them failed post-processing after a successful child.
Shared `usage_row_belongs_to_layer` and `layer_usage_suffix` helpers provide the native contract for a
supervisor caller. The append-only suffix helper rejects changed prefixes, incomplete/malformed rows and
rows for another layer. Its failing-first fixture is the exact 521-byte native workers row from the rerun.
These helpers perform no model or filesystem call. A stopped run may have an empty suffix.
The retained supervisor is outside this diff: the helpers are **UNCALLED** until it imports and invokes them.
The fixture tests the helper contract, not supervisor integration or a repaired live rerun.

The 20:43Z follow-up also corrects interrupted-run failure persistence. The original [end-only write][failures]
lost already observed layer failures if the next child interrupted the runner. `run_pending` now publishes a
valid snapshot before launch and records each completed failure under a shared lock: exhausted retry,
blind-audit quarantine or evidence-tree change. A flushed sibling temporary file is atomically replaced into
place. Unselected `--layers` failures are retained from the initial snapshot. Exception interruption and
orderly STOP preserve valid partial JSON, including an empty snapshot; a successful run without STOP retains
the prior behavior of removing an empty registry. Mock-only interruption regressions preserve termination
codes and cover the completed-failure, initial-snapshot, selected-rerun and orderly-STOP cases.

The old runner applies `ROOT_PATH` to raw text at [codex_lane.py:396][root], exempts selected slash shapes
in `names_root` at [454–469][names], and emits the flagged command at [513][emission]. The three exact
metadata regressions fail on that runner. An actual `git log`, root read and outside-file read must still
be flagged, so adding more raw-string exceptions would leave the policy dependent on incidental formatting.

The consumed Codex 0.162.1 JSONL does not carry structured argv, cwd or file-access events. Upstream converts
`ExecCommandEndEvent` into a `CommandExecutionItem` whose `command` is a redacted, shell-quoted display string,
alongside output, exit and status. Its projector omits native cwd and argv and remaps native item IDs. The
initial `codex exec -C` directory cannot fill the gap: `exec_command` accepts a model-chosen workdir.
The pinned client already supports the required native record: non-ephemeral exec requests paginated history,
whose completed `CommandExecutionItem` retains native argv, cwd, `parsed_cmd`, source, status,
`aggregated_output` and exit code. The corrected blind verdict lane uses that supported mode under a fresh
scratch `CODEX_HOME`, with explicit provider configuration. It never copies a real Codex home.

The parent matches each completed exec command to a unique native completed record in its thread by exact
decoded outer argv, status, exit code and output, then binds the exec item identity to that record's absolute
cwd. The existing pinned parser decodes the display; native call IDs and projected exec IDs are not assumed
equal. `events/<layer>.native-cwd.json` retains the complete-events digest, per-attempt native snapshots and
digests, and explicit item/native bindings for retry and resume before the scratch home is removed. Capture
and sidecar input are bounded at 8 MiB. Missing, duplicate, ambiguous or mismatched records, incomplete history,
outside directories and non-local file cwd URIs remain refused. Event `cwd`/`workdir` fields or model assertions
cannot supply the binding. Paginated rollout output is capped at 64 KiB upstream; a truncated native output
that does not match the exec output cannot establish the binding. The default command builder, including
adjudication callers, stays ephemeral. Even a bound cwd supplies no syscall, runtime-branch or resolved
symlink-target observation.
Each command start must have a matching completion in the same thread; a completed start/end pair counts once.
Unfinished starts remain unverified across retries, including when a later attempt finishes cleanly. A present
native `session_id` must match the fresh root exec thread; older metadata without it uses the native `id` fallback.

Reuse the repository's existing `child-usage.mjs` exports (`loadShellParser`, `withShellTree`, `wordValue`)
and its verified tree-sitter-bash 0.25.1/web-tree-sitter 0.27.0 install. The small Node adapter records
executable positions, decoded wrapper/shell arguments, redirections, expansions and quoted interpreter input;
it never executes a payload. Python `ast` identifies read operands and subprocess arguments in Python input.
Pattern/filter data is separate from read operands: `rg -f FILE`, `grep -f FILE`, jq filter files and variable
files still read files. Literal subprocess argv is passed back through the same shell/wrapper analyzer with
`shlex.join`. Callable aliases, keyword arguments, chained path methods and unresolved indirect reads remain
subject to the boundary policy. The review correction fails closed on any Python string literal that the
boundary policy would flag unless static analysis proves it is data. The four retained data cases stay clean;
`linecache.getline`, `sqlite3.connect`, `io.FileIO`, `fileinput.input`, `shutil.copyfile`, `os.path.getsize`,
`pandas.read_json` and `os.walk('/')` do not bypass the boundary through an unlisted call name.
Proven data roles also preserve composed safe read operands, separator formatting in a dormant uncalled
function, and printed comparison/conditional values. CPython executes a function body only on call;
decorators and defaults belong to the separate definition-time context. Unknown or read call sinks stay closed.
Unsupported grammar, active shell expansion and unresolved Python read or
execution operands refuse the result. Commands that change cwd through shell builtins, directory-changing
wrappers, Python `chdir` or subprocess overrides remain unverified. Resolution and nesting have finite budgets.

The parent verifies the adapter/helper/pin digests before analysis; those expected hashes are in the runner,
so its existing digest binds the audit dependency set without changing native receipt fields. A pending real
blind lane refuses a missing or modified backend before creating its home or spending a model turn. The
command-only dry run needs no parser. Two CI jobs that run the suite now provision the same existing pin
before their tests. The new native-history mode changes persistence for the blind verdict lane; the default
builder's isolation arguments, child environment and PATH retain their existing behavior.

Evidence is in `tools/sota-convergence/evidence/codex-blind-audit-command-positions-20261010.json`.
The earlier four-test base replay had three failures (the first three quarantines), no errors and exit 1;
the root-read control remained flagged. That measurement predates the independent-cwd requirement and is
historical evidence, not a current clean-stream attestation. The final four-command fixture helper supplies
caller-owned synthetic cwd records and executes neither the command strings nor an upstream model. Tests
also pair newly clean literal data with real reads/execution and refuse unsupported syntax, missing/tampered
dependencies, nested process execution and bounded resolver overflow. Test results distinguish synthetic
command replay from integration with the actual pinned parser. No result is sealed or promoted by this work.

At the historical pre-review runner source
`e0cc01afa277c820b5235e665ad0d5dda6948adc91559ef6c65c81461e8e32a3`, a compatibility-adapted five-case
command replay paired the four retained commands with a real root-read control: its original-base result
was four failures, no errors and exit 1; its fixed result was no failures/errors and exit 0. That harness
dropped an unsupported cwd keyword and supplied fixture-side preflight compatibility. It did **not** run the
new test classes unmodified on the original base. The CC's class replay reported API errors, including
missing `audit_analysis_issue`; the earlier four-failures/zero-errors claim applies only to the adapted
command selection and cannot describe those new-contract classes.
The fresh narrow replay makes the distinction explicit: the four unadapted retained-command methods produce
four API errors on `9d4c00cd`; the compatibility-adapted selection produces four assertion failures with no
errors, while a separate actual-root control passes. The broader CC class replay remains a reported result,
not a claim that this narrow four-method selection reproduces its error count.

At intermediate corrected runner
`7710b726fafaa4bfa7e7076cc452a6e4fb9a822c7d164db2c36410eb1133e8fc`, the six native-capture methods
produce eight failed subtests and no errors against unchanged `9ffdbff7`, then pass with no failures, errors
or skips after the correction. They exercise a local Codex fixture with native paginated history fields;
they make no live provider or model call. The fail-closed literal class separately reproduces eleven failed
subtests on `9ffdbff7`: seven missed interfaces and four laundering or mutation cases. `os.walk('/')` and
the rebound-`print` control already pass on that baseline; their coverage does not establish a new baseline failure.
The intermediate full Codex module then records 144 tests with four failures and no errors: three preserved
literal-precision cases and one fixture thread-ID assertion. A separate three-test focused replay also fails
on unfinished command starts and mismatched session identity. These intermediate results remain separate
from the final source and required-suite measurements; the six-method native pass alone is insufficient.

At final frozen runner `e08169635a1a60f5765d7cc6bf71e170da6c52a6ee107690b779d212264efebd`, the
expanded eight-method native class produces ten failed subtests and no errors on `9ffdbff7`, then passes
with no failures, errors or skips on the correction. The three preserved precision methods separately fail
on intermediate `9fdfa92c` and pass on this final source. A 19-test safety run of the literal-boundary and
quarantine classes also passes on the same unchanged source and tests. All use synthetic command/native
metadata or local fixtures; live provider behavior remains unmeasured.

The historical required four-module bundle passed 313 tests with no failures/errors and three skips. Both schema skips
were then covered by an isolated `jsonschema==4.25.1` rerun with no skips; the remaining runtime tripwire
requires GitHub Actions. The module counts are Codex lane 135, parser CI 38, lane packets 126 and vendoring 14.
Those results predate this review correction and are retained as historical evidence. Corrected replay,
native-capture and final required-suite measurements are recorded separately in the evidence file.

Final qualification covers 592 tests across the six required modules by combining two scoped runs. The
immutable-candidate six-module run (`ece42fc108b8b57e36526e0bdff0ec98bd6bfb4f`) ran 591 tests with one failure,
no errors and four skips. Its five unchanged modules passed 553 tests with three skips. The sole failure was
the parser-CI test helper still forbidding the CC-required full-mode condition. Correcting that helper requires
the exact `env.VALIDATE_MACOS_MODE == 'full'` condition on parser install and suite steps only in `validate-macos`;
all other jobs remain unconditional. An added test method checks four incorrect condition mutations. The
corrected parser module passes 39 tests with no failures/errors and its one GitHub Actions-only skip.
The 592-test figure is the qualified rollup, not a single all-green bundle. Its four unique skips are the
two jsonschema guards, the GitHub Actions-only parser tripwire and an empty hash-frozen workflow set.

The dated monitoring snapshot uses unchanged `GitTree`, `derive_ci_protected` and `advisory_gate_reads` on
immutable candidate `9d2ab50af8e8a2d5939abee26c0ff20fc84d992d`: 424 unclassified sites, 101 shape locations and
139 Codex-runner sites, with zero unresolved reads. The old 330-site snapshot is retained. The runtime-workers
lane ACK is dated `2026-10-11T01:04:17Z`; enforcement classifications are unchanged. The 125 push-gate tests
pass in the later six-module candidate run. This record covers candidate qualification; the lane records
the subsequent repository-wide validation and published-HEAD check separately.

This static display audit would be replaced if a maintained Codex interface supplies trustworthy read events
with the same refusal controls. The existing pinned native command history supplies argv and cwd for the
separate binding step; it does not supply file-access observations.
Indirect script/config reads, runtime branch selection and symlink targets remain outside this static audit's
observations.

## SOTA sources

- [Native Agent Stack at the base][base]: the old policy sites above; existing
  `examples/claude-native/workflows/child-usage.mjs:675,685,1071` exports and
  `shell-parser.pin.json`; `tests/test_command_position_oracle.py:9–23` records the static/runtime boundary;
  `tools/sota-convergence/codex_lane.py:1538–1556` is the original end-only failure write.
- [openai/codex rust-v0.162.1][codex] (`092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`):
  `codex-rs/app-server-protocol/src/protocol/item_builders.rs:56–60,96–142` constructs the redacted display and item;
  `codex-rs/shell-command/src/parse_command.rs:10–13` joins argv; `codex-rs/exec/src/exec_events.rs:161–166`
  omits cwd from the consumed item; `codex-rs/core/src/tools/handlers/shell_spec.rs:40–45` accepts workdir.
  `codex-rs/exec/src/event_processor_with_jsonl_output.rs:162–180,327–365` omits cwd and remaps native item IDs
  into exec item IDs; the capture therefore requires a unique exact command/result binding within a thread.
  `codex-rs/protocol/src/items.rs:244–281` defines native argv, cwd, parsed command, source and result fields;
  `codex-rs/protocol/src/protocol.rs:3159–3161,3288–3293` defines root-thread session identity and supplies
  the native `id` fallback only when legacy metadata lacks `session_id`;
  `codex-rs/exec/src/lib.rs:1459–1462` selects paginated history when non-ephemeral;
  `codex-rs/rollout/src/policy.rs:17–19,227–280` retains completed command items with a 64 KiB output bound;
  `codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs:192–204` resolves the model's workdir.
  This is the installed client's version.
- [tree-sitter/tree-sitter-bash v0.25.1][bash] (tag `a06c2e4415e9bc0346c6b86d401879ffb44058f7`, npm
  `801326684a26ffc4e749bb016c50c6c30bdfa345`) and [web-tree-sitter v0.27.0][tree]
  (`6070dbfefd326bd735e5683eb128cc1b57dad0c0`): existing pin records npm integrity, asset hashes and install.
- [CPython v3.13.16][python]: `Lib/ast.py:30–49` (parse without execution) and `Lib/shlex.py:305–318`
  (join argv with shell quoting), `Lib/json/__init__.py:339–365` (default inert decoding),
  `Modules/posixmodule.c:11159–11170` (descriptor-relative opens), `Python/bltinmodule.c:1585–1604`
  (namespace setters) and `Doc/library/os.rst:2755–2760` (atomic replacement), matching the installed
  interpreter. `Doc/library/json.rst:716–727` distinguishes input size from accepted node/depth bounds.
  `Parser/Python.asdl:11–16,65,114–115` defines function bodies, decorator/default expressions and conditional
  expressions; `Doc/reference/compound_stmts.rst:1246–1247,1250–1266,1298–1301` distinguishes function-body
  execution on call from decorators/defaults evaluated at definition.
- [Linux v6.12][linux]: `fs/open.c:1316–1326` defines directory/no-follow flags, and
  `fs/pipe.c:1145–1164` defines the FIFO wait avoided by nonblocking packet/checksum opens.
- Installed [ripgrep 15.1.0][rg] `--help` (`-f PATTERNFILE`), GNU grep 3.12 `--help`
  (`-f/--file` versus `-E`), and [jq 1.8.1][jq] `--help` (`--from-file`, `--rawfile`, `--slurpfile`)
  are primary sources for the file-option distinction.

[base]: https://github.com/seathatflowsinourveins/native-agent-stack/tree/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff
[root]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/tools/sota-convergence/codex_lane.py#L396
[names]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/tools/sota-convergence/codex_lane.py#L454-L469
[emission]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/tools/sota-convergence/codex_lane.py#L513
[failures]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/tools/sota-convergence/codex_lane.py#L1538-L1556
[codex]: https://github.com/openai/codex/tree/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d
[bash]: https://github.com/tree-sitter/tree-sitter-bash/tree/a06c2e4415e9bc0346c6b86d401879ffb44058f7
[tree]: https://github.com/tree-sitter/tree-sitter/tree/6070dbfefd326bd735e5683eb128cc1b57dad0c0
[python]: https://github.com/python/cpython/tree/v3.13.16
[linux]: https://github.com/torvalds/linux/tree/v6.12
[rg]: https://github.com/BurntSushi/ripgrep/tree/15.1.0
[jq]: https://github.com/jqlang/jq/tree/jq-1.8.1

## 2026-10-11 bytes-path correction

The CC's micro at `078aeb6d` reproduced a remaining P1: the final boundary-literal pass inspected
only `str` constants, although the filesystem APIs also accept `bytes`. The same exact old runner
produces seven assertion failures and zero errors in the two new offline tests: four named read
interfaces, reversed mixed `copyfile` arguments, and two unsupported wrapper controls. No command
payload is executed. Benign printed bytes, bytes separator data, decode/hex formatting and bytes
comparisons are separate positive controls.

The pass now presents both literal types to the same boundary policy through `os.fsdecode`, retaining
the original AST type for data-flow analysis. Bytes formatting follows the verified data-sink rule;
`decode` is restricted to argument-free calls on strict-UTF-8-decodable literals, as corrected below.
This preserves expression type semantics; mixed bytes
and strings are not coerced into a valid concatenation or join.

The installed interpreter is CPython 3.13.16, official pin
[`cbc944f4bc59639a444dd971c737788ba2283a91`](https://github.com/python/cpython/tree/cbc944f4bc59639a444dd971c737788ba2283a91).
`Lib/os.py:840-866` uses the filesystem encoding and error handler; `Doc/library/os.rst`'s
`fsdecode` section and `Doc/library/sys.rst:781-795` specify that contract. The synthetic API probe
confirms UTF-8/surrogateescape here: an invalid filename byte round-trips to the same inode.
`Modules/_io/fileio.c:302-305`, `Objects/unicodeobject.c:4030-4038`,
`Modules/_sqlite/connection.c:247-268`, `Lib/genericpath.py:84-86`,
`Modules/posixmodule.c:1303-1329` and `Lib/shutil.py:260-262` confirm str/bytes paths.
All four named APIs reject direct `bytearray` and `memoryview` arguments with TypeError in the
installed interpreter. Those types have no AST literal syntax: their constructor forms still
contain the bytes constant, which the audit conservatively scans. API refusal and conservative
audit refusal are distinct results.

The first bytes-correction landing rebase targeted `eb31d233234cdc552fc81672087ac8769e3696e0`.
The only conflict was `manifests/evidence.json`: main's copy was taken and all owned files were
re-registered through `host_receipts.register_file`. The ACKed monitoring snapshot remains
byte-exact SHA256 `b8ff44c24b73981c63edcc0e956c9b8e59bf0b6f199d97ee1baa7e7b3389d9d6`;
the native rebased-head qualifier confirms 424 sites, 139 runner sites and 101 shape locations.
Final-head FULL validation and the target's eight native shards are recorded separately in the
coordination results and PR body; historical qualification above remains scoped to its original tree.

### Why the full scratch rollouts are retained

Dropping `--ephemeral` intentionally preserves native rollouts in the newly created run-specific
`CODEX_HOME`, whose mode is 0700. This follows the existing `isolated_codex_home` forensic contract
at [main `65cf2730`, codex_lane.py:658-665](https://github.com/seathatflowsinourveins/native-agent-stack/blob/65cf2730068429a1c48c8c18fb24aadef8120817/tools/sota-convergence/codex_lane.py#L658-L665): sessions and logs
remain available for inspection. The original native bytes permit comparison with captured rollout
digests and diagnosis of incomplete or ambiguous history. The minimal captured evidence is retained
separately; original rollouts are not copied into published verdicts or evidence manifests.

The existing `release_codex_home` lifecycle (same main pin, `:695-703`) stops children, removes the authentication
symlink and releases the lock. Retention remains local to that owner-only scratch home; capture and
retention read no real Codex home contents and copy no real Codex home. Native setup retains its
existing authentication-path metadata checks and symlink. This correction documents forensic retention rather than
adding a cleanup operation that would discard its source evidence.

## Landing rebase after the binding correction

The CC's 2026-10-11T03:23Z cue authorizes one further landing rebase after the separate adjudication
binding fix. Main at start was `65cf2730068429a1c48c8c18fb24aadef8120817`. Main's
[`bd59f5561` / #957](https://github.com/seathatflowsinourveins/native-agent-stack/commit/bd59f5561)
retired adoption macOS CI. The rebase preserves that workflow and its hardening tests byte-for-byte,
retains catalog-freshness parser provisioning and removes the obsolete macOS-only parser exception
and mutation control. The runtime source and Codex test bytes remain identical to `fd86ad20`.
Evidence manifests were taken from pinned main and regenerated through native registration.

The native advisory API for the source retained at `7a7ff0675c65f9cc555ca29d622ab3375defc8b4` measures
432 unclassified sites, 139 Codex sites, 102 shape locations and zero unresolved. The only normalized
delta from the prior ACKed 424/139/101 snapshot is `scripts/component_matrix.py`: sites 6 to 14 and
shapes 1 to 2, matching main's [#982 shared closeout loader](https://github.com/seathatflowsinourveins/native-agent-stack/commit/878f2891a).
The CC independently compared and ACKed these exact candidate bytes at 04:01Z. The snapshot is
retained as `unclassified-gate-reads-20261011-pr990-landing.json`, SHA256
`2bdc389b35857c74a680f14a8aea676213acc93d83e7971eace218e3d909b2a6` in the published `7071510b`
tree. The 06:24Z citation correction changes only its source metadata to the published head;
the current digest is in the evidence record and the existing native baseline test still selects it.
The later authorized rebase onto main `9b3a39c4` binds this metadata to reachable PR ancestor
`7a7ff0675c65f9cc555ca29d622ab3375defc8b4`; the counter/shapes payload remains unchanged.
The previous b8ff snapshot remains byte-exact historical evidence; worker
enforcement classifications are unchanged.

Both verbatim change-ids, the range-diff, per-hunk resolution notes and final committed-head checks
are retained in the landing artifacts and PR body. Historical test and baseline results above stay
scoped to their original trees. No live provider/model call or additional rebase is part of this cue.

## 2026-10-11 codec and comparison callback correction

The 06:24Z review found that treating arbitrary bytes `decode` calls as builtin formatting was
incorrect. Three synthetic codec/error callbacks actually read a temporary sibling packet; reflected
string/bytes equality and containment callbacks do the same. The two new tests fail at `7071510b`
with six assertion failures and zero errors after verifying each real fixture read. The callbacks live
in a synthetic imported helper so the test exercises the literal transfer across the interface, rather
than an independently detectable open call in the command's source.

Follow `decode` only with no positional/keyword arguments and a literal that decodes as strict UTF-8.
Unknown comparison operands receive a boundary literal conservatively; non-path URI separators
such as `://` retain the existing classification-data behavior. The original printed/decode controls
and the historical separator/regex residual test remain clean. These are static policy checks with
six real local fixture reads, not model/provider calls.

Pinned CPython v3.13.16 primary mechanisms:

- [bytesobject.c:2454-2459](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/bytesobject.c#L2454-L2459)
  forwards bytes decoding to the Unicode decoder. [unicodeobject.c:3572-3576](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/unicodeobject.c#L3572-L3576)
  delegates non-standard codecs; [codecs.c:178-184](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Python/codecs.c#L178-L184)
  invokes registered search callbacks.
- [codecs.c:622-636](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Python/codecs.c#L622-L636)
  looks up named error callbacks, including `strict`; [unicodeobject.c:4408-4411](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/unicodeobject.c#L4408-L4411)
  and [5072-5105](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/unicodeobject.c#L5072-L5105)
  dispatch invalid UTF-8 through that callback registry. A valid literal needs no error callback.
- [object.c:1015-1019](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/object.c#L1015-L1019)
  invokes reflected rich comparison; [abstract.c:2272-2280](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/abstract.c#L2272-L2280)
  passes the tested value into containment.

The three intermediate runner hashes were referenced only by synthetic correction evidence and
registry rows in this repository, with no retained production return found. The authorized correction
removes their eligibility rows and registers the corrected source; their historical test evidence remains.
Off-branch implementation citations now use published main/head pins. The monitoring snapshot's
source metadata also uses the published head; its measured counters retain the earlier accepted scope.

### Combined landing fixture compatibility

Rebasing onto landed adjudication exposed a fixture-only boundary: the new fake Codex journal helper
prepended a thread UUID to ephemeral callers' canned stdout. The unchanged adjudication native-byte
control fails four assertions on this combined source. Restrict journal fixture enrichment to
non-ephemeral attempts; ephemeral test calls preserve the supplied stream byte-for-byte. This follows
[openai/codex at the recorded pin, exec/src/lib.rs:1459-1461](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/exec/src/lib.rs#L1459-L1461),
which requests paginated history only for non-ephemeral exec. The existing raw-byte control and the
whole 130-test adjudication module then pass. Production adjudication and its separate native-cwd
integration are unchanged by this fixture correction.

## 2026-10-11 completion-read corrections

The completion review reproduced five additional gaps on the published source and combined tree.
Neutral `outside-marker.txt` fixtures contain only `OUTSIDE_MARKER`. The initial corrected harness
has 12 tests and 19 assertion failures with zero errors before the fixes, spanning independent audit
and runner-promotion checks. The same 12 tests pass after the first integration. Supplemental controls
then exercise supported/unsupported URL forms, sed source constructs and clean promotion cleanup.
Real dummy reads and simulated native-journal promotion are reported separately.
The final extended 16-test suite also runs against verbatim `7071510b` source compiled in memory:
23 assertion failures, zero errors. Both review families' callback reproductions use only the neutral
`outside-marker.txt` / `OUTSIDE_MARKER` fixture; the two Claude tests separately fail six assertions
on that exact source and the corrected eight-test literal/separator bundle passes.

1. `io.FileIO` now uses the modeled-reader unresolved-operand refusal. Other potentially effectful
   imported calls require a modeled contract; absence of a boundary-looking individual constant no
   longer establishes their purity. Existing verified primitive/packet transformations retain bounded
   handling. Computed `bytes.fromhex` and `chr` operands fail closed, as does a synthetic imported reader.
2. The modeled URL reader accepts bounded local `file:` URLs, converts the pathname with CPython's
   `url2pathname`, and checks the decoded/resolved filesystem target. Remote authorities, malformed
   percent escapes, queries/fragments, NULs, relative paths and unsupported local schemes are refused.
   Encoded absolute outside paths and encoded parent traversal cannot pass promotion.
3. Sed source is interpreted through a bounded allowlist: numeric preview addresses with `p`/`q`/`d`
   and explicit `r`/`R` filename reads. The actual read filename is checked, consuming the rest of its
   source line as GNU sed does. Separate/attached `-f` and `--file` operands are reads whose unmodeled
   script contents are refused. Unsupported source, option forms and execution commands remain refused.
   This uses upstream command semantics without introducing another full sed parser.
4. Every displayed filesystem read is checked against its resolved target, including links under
   the packets root. Blind launches apply the existing export tree invariant to the packets root as
   well as the repository. The established bounded no-follow packet JSON loader remains in place.
   Preexisting outside packet links fail before launching; repository link refusal remains covered.
5. The durable failure snapshot now records all pending layers before child execution. A successful
   audited promotion clears its unfinished entry; terminal failures replace it. Exceptions retain
   their exception type without copying potentially private exception text, remove any return and
   re-raise. The actual consumer reports an interrupted layer as failed rather than missing. Selected
   reruns still preserve failures outside their selection.

Tests run in an OS-enforced local sandbox: no network namespace access, read-only repository/toolchains,
empty explicitly allowlisted environment, scratch-local homes/caches/temp files and a 256 MiB scratch
tmpfs; systemd limits memory to 2 GiB, tasks to 256 and CPU to two cores, with per-process CPU/file-size
limits and a bounded wall clock. The host user's home, configuration and credentials are not mounted.
No external provider or live survivor adjudication is part of these measurements.

### Pinned mechanism sources

- [CPython v3.13.16 `cbc944f4`, Modules/_io/fileio.c:294-305](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Modules/_io/fileio.c#L294-L305)
  converts FileIO's path through the filesystem converter. Model its operand explicitly rather than
  infer safety from constituent strings. Imported modules execute arbitrary module code;
  [Doc/reference/import.rst:429-441](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/reference/import.rst#L429-L441)
  describes that mechanism; the caller must supply a verified pure/read contract.
- [Lib/urllib/request.py:1486-1508](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/urllib/request.py#L1486-L1508)
  opens the pathname returned by `url2pathname`; [1685-1691](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/urllib/request.py#L1685-L1691)
  percent-decodes using filesystem encoding/errors on POSIX. Reuse that conversion, then confinement.
- [GNU sed v4.9 `7e2e575a`, sed/compile.c:360-383](https://github.com/mirror/sed/blob/7e2e575a36bc88c0f3f3d6d8083c5f5b0ed44009/sed/compile.c#L360-L383)
  reads a filename to newline, including semicolons. [1194-1218](https://github.com/mirror/sed/blob/7e2e575a36bc88c0f3f3d6d8083c5f5b0ed44009/sed/compile.c#L1194-L1218)
  compiles `r`/`R`, and [execute.c:1510-1542](https://github.com/mirror/sed/blob/7e2e575a36bc88c0f3f3d6d8083c5f5b0ed44009/sed/execute.c#L1510-L1542)
  reads the named file. Unsupported source is refused instead of copied into an invented parser.
- [CPython pathlib resolve implementation at the same pin:664-672](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/pathlib/_local.py#L664-L672)
  resolves filesystem targets; [os.path.realpath:388-412](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/posixpath.py#L388-L412)
  supplies the POSIX link semantics. These checks are post-run policy, not prevention of a race or syscall attestation.
- [Existing failure snapshot at published `7071510b`, codex_lane.py:2787-2842](https://github.com/seathatflowsinourveins/native-agent-stack/blob/7071510b79a457afd1567142b344919ff27e9631/tools/sota-convergence/codex_lane.py#L2787-L2842)
  uses the atomic native snapshot writer. Extend it to pending/in-flight state;
  [record_verdicts at landed `9b3a39c4`, missing_outcome](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b3a39c43363f32ac61e74c674e4ba069593fe08/tools/sota-convergence/record_verdicts.py#L1059-L1065)
  classifies absent returns through the recorded reason.

### Adjacent state and call-site checks

The changed operand functions' callers in shell analysis and nested Python execution were checked,
as were shared blind-audit consumers at verdict resume/promotion/retry and adjudication counting/
promotion/summary. Controls cover FileIO/import aliases, both sed `r` and `R`, URL conversion,
confined packet reads, native retry/resume/unfinished commands, selective reruns, stop with concurrent
jobs, and exceptions during audit and snapshot clearing after promotion. Thirty focused controls pass.

A wider preexecution-stop test found a stale-return transition next to the durable failure fix: queued
pending layers retained old outputs when STOP preceded process(). A neutral two-layer test fails two
assertions before correction. All pending stale outputs are now invalidated immediately after the durable
unfinished snapshot, before launching or checking STOP; all five incremental-failure controls pass.
Pinned source for this transition is the earlier pending/stale-return lifecycle at
[7071510b codex_lane.py:2822-2863](https://github.com/seathatflowsinourveins/native-agent-stack/blob/7071510b79a457afd1567142b344919ff27e9631/tools/sota-convergence/codex_lane.py#L2822-L2863).

Unmodified cited sources/captures and the call-site/transition ledger are retained in the hashed read
attachment directory named in FIX-PUSHED. A missing historical capture remains an explicit verification
gap until recovered; new measurements never replace or authenticate earlier missing bytes.

The permitted JSON transform call sites were checked one step further into optional callbacks.
`json.loads(object_hook=imported_reader)` and `json.dumps(default=imported_reader)` each read the
neutral scratch marker while the audit passed; one regression fails two assertions before correction.
Decoder override/callback keywords and encoder default/cls are refused. Standard inert literal
formatting remains covered by the passing eight-test literal/control bundle. At CPython `cbc944f4`,
[decoder.py:157-161](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/json/decoder.py#L157-L161)
and [214-218](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/json/decoder.py#L214-L218)
invoke object hooks; [encoder.py:159-161](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/json/encoder.py#L159-L161)
sets the default and [440-443](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/json/encoder.py#L440-L443)
invokes it. Full pinned blobs are retained with the attachment manifest.

### Final baseline ACK and landing

The final landing uses main `1d1164e8c34df8250973a5c632e9747a1ef79533`; the rebased equivalent of
the reviewed head is `89f0915634275f9d308223f3592ab4e8b37aea46`. The CC accepted the exact final
monitoring-only snapshot on 2026-10-11T09:24Z: 436 sites / 143 Codex sites / 102 shapes / zero unresolved,
29,287 bytes, SHA256 `fc481c58f7300e5e3dcc4fe698669b0d6042b07777ab32304bc27f0587e1fe21`.
It supersedes the uncopied 434 candidate. Native derivation at the final source regenerates these bytes;
metadata retains the accepted source ancestor `7a7ff067`, and no classification policy changes.
All 139 previous Codex sites map to unchanged source lines; only namespace extraction at 882-883 and
JSON callback guards at 1642/1644 are added. All other per-file counts and shapes stay equal.
The seven historical missing captures remain explicit gaps in the attachment ledger.
