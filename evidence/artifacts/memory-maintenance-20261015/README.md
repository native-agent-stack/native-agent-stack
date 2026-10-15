# Memory maintenance: sources and measurements (2026-10-15)

On 2026-10-15 (00:34 ET) the owner told the command center that memories should consolidate on their own and that the
harness should follow current maintenance practice. The command center set `autoDreamEnabled: true` in user settings at
00:45 ET and asked for the native-practice row and a guard. This folder holds the evidence behind
`tools/memory-index-guard/` and the `auto-memory` row of `.claude/skills/claude-native-practice/reference/slots.json`. The
facts come from the cc-native-practice lane's read-only fact-finding (FACTS.md, sha256 `63099f1b…`, in the command
center's private coordination state); every line quoted here was re-read from that run's saved copies, from the client
binary or from the upstream pin, and checked against them.

| File | What it shows | Class |
|---|---|---|
| `sources.json` | Doc lines (memory, errors and settings-reference pages, the CHANGELOG at `94506ff0`) with URL, sha256 and fetch time; the 2.1.300 binary reads with byte offsets; the server flag's `enabled` and `available`; ai-memory 2.6.3 lines at `385b81ea`, its `--help` captures and the listening ports; the repository lines the row cites | primary sources and measured reads; what the minified code does is inference, labelled in each `reading` |
| `extract-results.json` | The caps read from 2.1.296, 2.1.299 and 2.1.300 by the FACTS script and by the guard's port of it: 200 and 25000 each time, identifiers and offsets, wall times | measured |
| `index-measurement.json` | The five `MEMORY.md` indexes on this host as the guard measured them (names masked as `-home-<user>-`; lines, sizes and percents only), next to the FACTS script's earlier numbers | measured |
| `js-trim-set.json`, `probe/js_trim_set.js` | The code points `String.prototype.trim()` removes, in Bun 1.4.2 and Node v24.21.0 (the same 25) | measured |
| `scripts/extract_memory_index_limits.py`, `scripts/memory_index_sizes.py`, `scripts/fetch_docs.py` | The FACTS run's extractor (sha256 `0591a8f6…`), size table and doc fetcher, byte for byte | method |

## What the evidence settles

- The index caps are 200 lines and 25000 UTF-16 code units of the trimmed text in 2.1.300 (memory.md:546 says "the
  first 200 lines ... or the first 25KB"). The write-time reminder uses the same code-unit measure on a host without a
  prompt-index surface cap, which the FACTS run had left open (`sources.json`, `write-time-call`).
- `autoDreamEnabled` is inert on this host while the cached flag `tengu_onyx_plover` has neither `enabled` nor
  `available` true; on 2026-10-15 it had `enabled` false and no `available` key.
- ai-memory 2.6.3 has no `consolidate` command, its `lint` and `forget-sweep` commands are HTTP clients of the running
  server, and its scheduled maintenance is the server's own `[maintenance]` table, so no timer is added for it.
- memory.md:516 and :526 read `autoMemoryDirectory` from every settings scope and honor a project's value once the folder
  is trusted (ignored while `permissions.blockReadsOutsideWorkingDirectories` is on), so the row's rejection of
  repository-tracked auto memory no longer says such a value is inert (item 29 of the command center's 2026-10-15 guide
  screen).

## Fail before, pass after

Run at the base commit `0f4ee075` (the new test modules copied onto it), then on this change:

- `python3 -m unittest tests.test_memory_index_guard`: before, the module cannot load the tool (`FileNotFoundError: [Errno 2]
  No such file or directory: '<checkout>/tools/memory-index-guard/memory_index_guard.py'`, every test); after, 44 tests pass.
- `python3 -m unittest tests.test_native_practice_memory_maintenance`: before, `FAILED (failures=41, errors=1)` over 13
  tests, for example `AssertionError: 'inert' unexpectedly found in 'Repository-tracked auto memory (a
  repository-supplied `autoMemoryDirectory` is inert)'` and `AssertionError: '`autoDreamEnabled: true`' not found in ''`;
  after, 13 tests pass.

Each guard behaviour was also checked against a mutant of the tool, run with the test module: reporting 200 and 25000
without binding (12 failures), Python's own `strip()` (1), UTF-8 bytes in place of code units (1), no alert on a new
consolidation (3), a memory file's digest in the diff (1), a rolling snapshot in the run that sees a consolidation (1), and
the unit without `OnFailure=` (1). Every mutant failed.

## Not measured

A real consolidation (the flag is off; the before and after record has run only on the tests' synthetic locks); the
write-time measure with a team memory mount or a `promptIndexMaxBytes` surface cap; builds before 2.1.268; the live
`config.toml` of the ai-memory server (the `[maintenance]` values are the repository record, docs/memory-landscape-maintenance.md:90-94).
