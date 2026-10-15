# Memory index guard

`memory_index_guard.py` watches two things the Claude Code client does with its auto memory, every 6 hours, as a systemd
`--user` timer (the layer's recorded supervisor, `catalogs/landscape/foundation.json`, `scheduling-supervision`):

- **The index limits.** The client loads the first 200 lines of `MEMORY.md`, or the first 25KB, whichever comes first
  (memory.md:546). The guard reads both caps from the installed client binary, measures every index the way the client
  does, and alerts at 90% of either cap, before anything is cut off.
- **Background consolidation (auto-dream).** On 2026-10-15 at 00:45 ET the command center set `autoDreamEnabled: true` in
  user settings after the owner asked that memories consolidate on their own. The guard reports whether that setting can
  act, and when the client consolidates a memory directory for the first time it keeps a before and after copy of the
  directory and alerts, so a person reads that first run.

It makes no model call, starts no process, and writes nothing outside its own state directory. Sources:
`evidence/artifacts/memory-maintenance-20261015/` (quoted doc and source lines with sha256 and fetch times, the binary
reads with offsets, the measurements).

## What the client does (2.1.300)

- **Caps.** The binary declares them beside the file name: `var Xu="MEMORY.md",S$=200,Yie=25000` (byte 219416424). The
  identifiers change in every build (`iN`/`Roe` in 2.1.296, `qN`/`Yse` in 2.1.299), so the guard binds them in two steps:
  step A takes the two identifiers from the loader's user-visible warning (`lines (limit: ${X})` and
  `(limit: ${F(Y)}) ... index entries are too long`, in the 1,200 bytes before `Only part of it was loaded`); step B takes
  the values from the declaration `="MEMORY.md",X=<int>,Y=<int>`. The caps count only when both steps bind exactly one
  pair; otherwise they are `unknown` and no number is assumed. Both steps gave 200 and 25000 on 2.1.296, 2.1.299 and
  2.1.300, the same as the FACTS script, in 0.23-0.28 s per build (`extract-results.json`).
- **Measure.** `Cft()` trims the text with `String.prototype.trim()`, counts lines as newlines + 1 and size as the string's
  length, which is UTF-16 code units, not UTF-8 bytes (byte 219416424). The write-time check uses the same measure on a
  host without a prompt-index surface cap (`vfe(...)` at byte 225760764), and reminds from 0.8 of a cap
  (`var FPo=0.8`, byte 225621868; the rewrite target 0.7 gives the "under 140 lines" of errors.md:4275). The guard trims
  with the 25 code points that `trim()` removed in Bun 1.4.2 and Node v24.21.0 (`js-trim-set.json`); Python's own
  `strip()` differs. The client strips YAML frontmatter and block-level HTML comments before measuring
  (errors.md:4278); the guard does not, and marks such an index `stripped_parts_present` (its numbers are then an upper
  bound).
- **Auto-dream gate.** `autoDreamEnabled` is in the settings schema ("Enable background memory consolidation
  (auto-dream). When set, overrides the server-side default.") but on no docs page. The binary reads it only when the
  cached server flag `tengu_onyx_plover` has `enabled` or `available` true (byte 233150543). On 2026-10-15 the flag had
  `enabled` false and no `available` key, so the setting is inert until the flag changes.
- **Consolidation time.** The client keeps `lastConsolidatedAt` as the mtime of `.consolidate-lock` in the memory
  directory (`var g=".consolidate-lock"`, the literal at byte 232910521; `(await p(c(e))).mtimeMs`, 0 without a lock).
  A run writes its PID into the lock; a failed run writes the previous time back with `utimes`, so a lock can move back.

## Decision rules

| Status of an index | When |
|---|---|
| `ok` | below 80% of both caps |
| `warn` | at or above 80% of either cap (where the client's own reminder starts) |
| `alert` | at or above 90% of either cap |
| `unknown` | the caps are unknown (no binary, an empty file, or a template or declaration that does not bind) |

Indexes: every `~/.claude/projects/*/memory/MEMORY.md`, and `MEMORY.md` in the directory that user settings name in
`autoMemoryDirectory` (an absolute or `~/` path, memory.md:516-528), measured once even when both name the same
directory.

The guard reads one key from each private file: `autoDreamEnabled` and `autoMemoryDirectory` from
`~/.claude/settings.json`, and `enabled` and `available` of `cachedGrowthBookFeatures.tengu_onyx_plover` from
`~/.claude.json`, in-process. A field that is not a boolean is reported as `non-boolean`, never echoed.

A **new consolidation** is a `.consolidate-lock` mtime newer than the one recorded for that directory. A directory seen
for the first time has the recorded value 0 (the client's own value for no lock), so a lock that is already there counts
as new. A lock that moved back is reported under `locks_moved_back` and is not an alert.

| Exit | When | Effect |
|---|---|---|
| 0 | no index at alert and no new consolidation, also when the caps or the flag are unknown (reported, never an alert) | none |
| 1 | an index at alert, or a new consolidation | the unit fails; `OnFailure=stack-alert@%n.service` runs the command center's alert handler |
| 2 | the guard's own state cannot be read or written | the same alert: the guard itself needs a look |

A run that finds another run holding `guard.lock` (`fcntl.flock`) does nothing and exits 0.

## State directory

`~/.local/state/native-agent-stack/memory-index-guard/` (mode 0700, narrowed on every run):

| Path | Mode | Holds |
|---|---|---|
| `state.json` | 0600 | the last lock mtime per memory directory, the first consolidation ever seen, the snapshot manifests (per file: lines, bytes, sha256) and every consolidation seen |
| `report.json` | 0600 | the last run's report, the same JSON as stdout |
| `snapshots/<directory>.tar` | 0400 | the memory directory's files, rewritten only when they changed and only in a run that sees no new consolidation; directories without files get none |
| `dreams/<directory>/<lock mtime>/` | 0700 | `before.tar` (the last snapshot, a hard link that outlives the next snapshot), `after.tar` (the directory when the guard saw the consolidation) and `diff.json` (files added, removed and changed with line and byte counts; no content), each 0400 |

The tars hold memory content and stay in this directory for the command center's paired check of the first
consolidation; the report and `diff.json` carry names and counts only. A directory over 64 MiB is not tarred, and the
report says so.

## Install (the command center's act; nothing here is applied)

```bash
T=~/.local/share/native-agent-stack/memory-index-guard
install -D -m 0644 tools/memory-index-guard/memory_index_guard.py "$T/memory_index_guard.py"
install -m 0644 tools/memory-index-guard/units/memory-index-guard.service tools/memory-index-guard/units/memory-index-guard.timer \
  ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user show stack-alert@memory-index-guard.service.service --property=LoadState   # the alert handler: loaded
systemctl --user enable --now memory-index-guard.timer
```

Check: `systemctl --user start memory-index-guard.service`, then
`/usr/bin/python3 -I -m json.tool ~/.local/state/native-agent-stack/memory-index-guard/report.json` shows the indexes and
`limits.status` `ok`.

Inverse: `systemctl --user disable --now memory-index-guard.timer`, remove the two unit files, run
`systemctl --user daemon-reload`, and remove `$T`. The state directory holds the snapshots; remove it only after the
paired check no longer needs them.

## Not covered

- **A real consolidation.** The flag is off on this host, so the before and after record has run only on the tests'
  synthetic locks. The first real run is the one the guard alerts on.
- **Other surfaces.** Team memory mounts and a configured prompt-index surface cap (`promptIndexMaxBytes`) change the
  write-time measure; this host has neither, and the guard measures the auto-memory index only.
- **Older builds.** The extraction rests on warning phrases reworded in 2.1.268; on an older or reworded build the caps
  are `unknown` (reported, no alert), and the guard needs a new reading.
- **Durable memory.** ai-memory's own maintenance runs in its server's `[maintenance]` scheduler; this guard does not
  touch it (the auto-memory row of `.claude/skills/claude-native-practice/reference/slots.json` records why no timer is
  added for it).

## Tests

`python3 -m unittest tests.test_memory_index_guard`: synthetic binaries (the template and the declaration with caps
other than 200 and 25000, other identifiers with a same-named value elsewhere, a mismatched declaration, an empty file, a
computed or zero cap, two bindings), fake memory directories, settings and `.claude.json`, the read-only check and
`systemd-analyze --user verify` of the units.
