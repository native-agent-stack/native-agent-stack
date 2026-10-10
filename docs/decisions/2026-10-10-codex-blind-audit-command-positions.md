# Codex blind audit: command positions and read operands

Date: 2026-10-10. Base: `9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`.

The tier-1 run quarantined three commands that used forbidden-looking text as data: document-retrieval's
Python `'/'.join(...)` separator, git-github-automation's `rg '(git|diff|...)'` pattern, and mcp-surfaces'
backtick string inside a quoted Python heredoc. The retained command metadata is the regression input;
the collected receipts, session homes and verdicts are not changed by this fix.

The old runner applies `ROOT_PATH` to raw text at [codex_lane.py:396][root], exempts selected slash shapes
in `names_root` at [454–469][names], and emits the flagged command at [513][emission]. The three exact
metadata regressions fail on that runner. An actual `git log`, root read and outside-file read must still
be flagged, so adding more raw-string exceptions would leave the policy dependent on incidental formatting.

The consumed Codex 0.162.1 JSONL does not carry an argv array or file-access events. Upstream converts
`ExecCommandEndEvent` into a `CommandExecutionItem` whose `command` is a display string, alongside output,
exit and status. Lower-level protocol `parsed_cmd` is not retained here, and its read path is itself best
effort. We therefore parse the recorded command display statically. We do not claim to have observed actual
syscalls, runtime branches or resolved symlink targets.

Reuse the repository's existing `child-usage.mjs` exports (`loadShellParser`, `withShellTree`, `wordValue`)
and its verified tree-sitter-bash 0.25.1/web-tree-sitter 0.27.0 install. The small Node adapter records
executable positions, decoded wrapper/shell arguments, redirections, expansions and quoted interpreter input;
it never executes a payload. Python `ast` identifies read operands and subprocess arguments in Python input.
Pattern/filter data is separate from read operands: `rg -f FILE`, `grep -f FILE`, jq filter files and variable
files still read files. Literal subprocess argv is passed back through the same shell/wrapper analyzer with
`shlex.join`. Callable aliases, keyword arguments, chained path methods and unresolved indirect reads remain
subject to the boundary policy. Unsupported grammar, active shell expansion and unresolved Python read or
execution operands refuse the result. Resolution and nesting have finite budgets.

The parent verifies the adapter/helper/pin digests before analysis; those expected hashes are in the runner,
so its existing digest binds the audit dependency set without changing native receipt fields. A pending real
blind lane refuses a missing or modified backend before creating its home or spending a model turn. The
command-only dry run needs no parser. Two CI jobs that run the suite now provision the same existing pin
before their tests. The child isolation arguments, environment and PATH are unchanged.

Evidence is in `tools/sota-convergence/evidence/codex-blind-audit-command-positions-20261010.json`.
The four-test base replay has three failures (the three real quarantines), no errors and exit 1; the root-read
control remains flagged. The new fixtures execute neither their command strings nor an upstream model. Tests
also pair newly clean literal data with real reads/execution and refuse unsupported syntax, missing/tampered
dependencies, nested process execution and bounded resolver overflow. Test results distinguish synthetic
command replay from integration with the actual pinned parser. No result is sealed or promoted by this work.

This choice would be replaced if a maintained Codex JSONL interface supplies structured argv and trustworthy
read events that preserve the same refusal controls. Indirect script/config reads, runtime branch selection
and symlink targets remain outside this static audit's observations.

## SOTA sources

- [Native Agent Stack at the base][base]: the old policy sites above; existing
  `examples/claude-native/workflows/child-usage.mjs:675,685,1071` exports and
  `shell-parser.pin.json`; `tests/test_command_position_oracle.py:9–23` records the static/runtime boundary.
- [openai/codex rust-v0.162.1][codex] (`092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`):
  `codex-rs/exec/src/exec_events.rs:159–166` and `event_processor_with_jsonl_output.rs:162–180` define the
  consumed command event. This is the installed client's version.
- [tree-sitter/tree-sitter-bash v0.25.1][bash] (tag `a06c2e4415e9bc0346c6b86d401879ffb44058f7`, npm
  `801326684a26ffc4e749bb016c50c6c30bdfa345`) and [web-tree-sitter v0.27.0][tree]
  (`6070dbfefd326bd735e5683eb128cc1b57dad0c0`): existing pin records npm integrity, asset hashes and install.
- [CPython v3.13.16][python]: `Lib/ast.py:30–49` (parse without execution) and `Lib/shlex.py:305–318`
  (join argv with shell quoting), matching the installed interpreter.
- Installed [ripgrep 15.1.0][rg] `--help` (`-f PATTERNFILE`), [GNU grep 3.12][grep] `--help`
  (`-f/--file` versus `-E`), and [jq 1.8.1][jq] `--help` (`--from-file`, `--rawfile`, `--slurpfile`)
  are primary sources for the file-option distinction.

[base]: https://github.com/seathatflowsinourveins/native-agent-stack/tree/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff
[root]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/tools/sota-convergence/codex_lane.py#L396
[names]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/tools/sota-convergence/codex_lane.py#L454-L469
[emission]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/tools/sota-convergence/codex_lane.py#L513
[codex]: https://github.com/openai/codex/tree/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d
[bash]: https://github.com/tree-sitter/tree-sitter-bash/tree/a06c2e4415e9bc0346c6b86d401879ffb44058f7
[tree]: https://github.com/tree-sitter/tree-sitter/tree/6070dbfefd326bd735e5683eb128cc1b57dad0c0
[python]: https://github.com/python/cpython/tree/v3.13.16
[rg]: https://github.com/BurntSushi/ripgrep/tree/15.1.0
[grep]: https://www.gnu.org/software/grep/manual/grep.html
[jq]: https://github.com/jqlang/jq/tree/jq-1.8.1
