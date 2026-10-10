# Codex blind audit: command positions and read operands

Date: 2026-10-10. Initial base: `9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`.
One authorized landing rebase: `c4f4990737c4e2ed8f0452d069e25a460f897bb5`.

The tier-1 run produced four text-match quarantines: document-retrieval's Python `'/'.join(...)` separator,
git-github-automation's `rg '(git|diff|...)'` pattern, mcp-surfaces' backtick string inside a quoted Python
heredoc, and the later workers rerun's `'://'` membership guard. The retained command metadata supplies the
regressions. The current production exec JSONL has no independent cwd records, so its commands are explicitly
**UNVERIFIED** under the new contract. Clean four-command parser fixtures supply caller-owned synthetic cwd
records; they do not attest raw production streams. The collected receipts, session homes and verdicts are
preserved. The CC's separate acceptance of the four historical quarantines is an adjudication of that run.

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
Shared `usage_row_belongs_to_layer` and `layer_usage_suffix` helpers now supply the native contract to the
retained supervisor. The append-only suffix helper rejects changed prefixes, incomplete/malformed rows and
rows for another layer. Its failing-first fixture is the exact 521-byte native workers row from the rerun.
These helpers perform no model or filesystem call. A stopped run may have an empty suffix.

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
alongside output, exit and status. Lower-level protocol `parsed_cmd` is not retained here, and its read path
is itself best effort. The initial `codex exec -C` directory cannot fill the gap: `exec_command` accepts a
model-chosen workdir. We therefore parse the display statically and require a separate caller-owned native
record that binds the event item identity, exact display and absolute cwd inside the approved roots. Event
`cwd`/`workdir` fields or model assertions are not independent records. Missing, duplicate or mismatched
identities and outside directories remain flagged. The upstream projector remaps native call IDs into JSONL
item IDs, so a future native capture must retain that mapping. This runner does not provide such capture;
current native raw streams remain unverified. Even a bound cwd supplies no syscall, runtime-branch or resolved
symlink-target observation.

Reuse the repository's existing `child-usage.mjs` exports (`loadShellParser`, `withShellTree`, `wordValue`)
and its verified tree-sitter-bash 0.25.1/web-tree-sitter 0.27.0 install. The small Node adapter records
executable positions, decoded wrapper/shell arguments, redirections, expansions and quoted interpreter input;
it never executes a payload. Python `ast` identifies read operands and subprocess arguments in Python input.
Pattern/filter data is separate from read operands: `rg -f FILE`, `grep -f FILE`, jq filter files and variable
files still read files. Literal subprocess argv is passed back through the same shell/wrapper analyzer with
`shlex.join`. Callable aliases, keyword arguments, chained path methods and unresolved indirect reads remain
subject to the boundary policy. Unsupported grammar, active shell expansion and unresolved Python read or
execution operands refuse the result. Commands that change cwd through shell builtins, directory-changing
wrappers, Python `chdir` or subprocess overrides remain unverified. Resolution and nesting have finite budgets.

The parent verifies the adapter/helper/pin digests before analysis; those expected hashes are in the runner,
so its existing digest binds the audit dependency set without changing native receipt fields. A pending real
blind lane refuses a missing or modified backend before creating its home or spending a model turn. The
command-only dry run needs no parser. Two CI jobs that run the suite now provision the same existing pin
before their tests. The child isolation arguments, environment and PATH are unchanged.

Evidence is in `tools/sota-convergence/evidence/codex-blind-audit-command-positions-20261010.json`.
The earlier four-test base replay had three failures (the first three quarantines), no errors and exit 1;
the root-read control remained flagged. That measurement predates the independent-cwd requirement and is
historical evidence, not a current clean-stream attestation. The final four-command fixture helper supplies
caller-owned synthetic cwd records and executes neither the command strings nor an upstream model. Tests
also pair newly clean literal data with real reads/execution and refuse unsupported syntax, missing/tampered
dependencies, nested process execution and bounded resolver overflow. Test results distinguish synthetic
command replay from integration with the actual pinned parser. No result is sealed or promoted by this work.

At the final runner source `e0cc01afa277c820b5235e665ad0d5dda6948adc91559ef6c65c81461e8e32a3`, the same
five-case replay pairs the four retained commands with a real root-read control: before the fix, five tests
produce four failures, no errors and exit 1; after the fix, five tests produce no failures/errors and exit 0.
The required four-module bundle passes 313 tests with no failures/errors and three skips. Both schema skips
were then covered by an isolated `jsonschema==4.25.1` rerun with no skips; the remaining runtime tripwire
requires GitHub Actions. The module counts are Codex lane 135, parser CI 38, lane packets 126 and vendoring 14.
These fixture results preserve the production-unverified boundary described above.

This choice would be replaced if a maintained Codex interface supplies structured argv, independently recorded
cwd with a preserved identity mapping, and trustworthy read events that preserve the same refusal controls.
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
  `codex-rs/exec/src/event_processor_with_jsonl_output.rs:327–365` remaps native call IDs into exec item IDs;
  the mapping must accompany a native capture. This is the installed client's version.
- [tree-sitter/tree-sitter-bash v0.25.1][bash] (tag `a06c2e4415e9bc0346c6b86d401879ffb44058f7`, npm
  `801326684a26ffc4e749bb016c50c6c30bdfa345`) and [web-tree-sitter v0.27.0][tree]
  (`6070dbfefd326bd735e5683eb128cc1b57dad0c0`): existing pin records npm integrity, asset hashes and install.
- [CPython v3.13.16][python]: `Lib/ast.py:30–49` (parse without execution) and `Lib/shlex.py:305–318`
  (join argv with shell quoting), `Lib/json/__init__.py:339–365` (default inert decoding),
  `Modules/posixmodule.c:11159–11170` (descriptor-relative opens), `Python/bltinmodule.c:1585–1604`
  (namespace setters) and `Doc/library/os.rst:2755–2760` (atomic replacement), matching the installed
  interpreter. `Doc/library/json.rst:716–727` distinguishes input size from accepted node/depth bounds.
- [Linux v6.12][linux]: `fs/open.c:1316–1326` defines directory/no-follow flags, and
  `fs/pipe.c:1145–1164` defines the FIFO wait avoided by nonblocking packet/checksum opens.
- Installed [ripgrep 15.1.0][rg] `--help` (`-f PATTERNFILE`), [GNU grep 3.12][grep] `--help`
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
[grep]: https://www.gnu.org/software/grep/manual/grep.html
[jq]: https://github.com/jqlang/jq/tree/jq-1.8.1
