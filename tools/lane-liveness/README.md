# Lane liveness monitor

`lane_liveness.py` is the command center's lane monitor. The command center's Monitor runs it
(`/usr/bin/python3 -I -u <monitors>/lane_liveness_v2_2.py`). Every 60 s it reads `claude agents --json --all`, the
supported read of session state from outside Claude Code (agent-view docs, line 794), and the state of the matching
systemd user units. It prints one line per meaningful change and stays quiet on live lanes. The Monitor feeds each
line to the session that armed it (tools reference, line 39).

v2.2 is v2.1 (the host-only `lane_liveness_v2_1.py`, sha256 `43b8c9275e5c…`) with its reports unchanged, plus the
`LIMIT-BLOCKED` report described below. One v2.1 edge changed: a client reply that is not a JSON array now counts
as unreadable, like invalid JSON. v2.1 stopped on `null` and reported every session `GONE` on a JSON object. The
script makes no model call and sends nothing to any session.

## What each line means

`<label>` is `<name> kind=<interactive|background> pid=<pid>`; `pid=-` marks a row whose process has exited.
Every line starts with `[lanes]`; all lines except `not on` and the selftest rows carry the UTC time next.

| Line | Meaning |
|---|---|
| `baseline: <n> sessions, <m> units; current client <version>` | The first snapshot, at each start. |
| `not on <version>: <label> client=<other>` | At start, a session runs a client other than `~/.local/bin/claude`. |
| `NEW: <label> client=<c>` / `GONE: <label> client=<c>` | A session with a live process appears or disappears (key: name, kind, pid). |
| `CLIENT: <label> <a> -> <b>` | A session's client binary changed. |
| `NEEDS-INPUT: <label> waiting=<w>` | The same non-null `waitingFor` in 2 consecutive snapshots, once. |
| `CLEARED: <label>` | That `waitingFor` cleared. |
| `UNIT: <unit> <before> -> <after>` | A matching unit appears, disappears or changes ACTIVE/SUB. |
| `LIMIT-BLOCKED: <label> session=<sessionId> reset=<ISO UTC> blocked_for=<s>` | A background session is still `blocked` at least 600 s after the reset its usage-limit stop names. `blocked_for` is the seconds since that reset. Printed once per session and reset instant. |
| `LIMIT-UNPARSED: <label> session=<sessionId> at=<ISO UTC>` | The same stop, but no reset instant can be read from it (no reset clause, an unknown form, no zone, or no timestamp). `at` is the stop's time. Printed once per session and message; such a stop never gives `LIMIT-BLOCKED`. |
| `LIMIT-STATE: <reason>` | The once-only state file could not be locked, read or written. Lines then stay one per reset only within this process. Printed once per process. |
| `selftest: current client <version>`, then indented rows | `--selftest` prints one snapshot of sessions and units and exits; it reads no transcript and no state. |

No line carries message text: a `LIMIT-*` line holds only the label, the session id, the parsed reset instant or the
stop's time, and a number of seconds.

## Why LIMIT-BLOCKED exists

After a claude.ai usage-limit reset, an interactive session continues on its own (interactive-mode docs, lines
711-713). A background session (`claude --bg`) does not: "Claude Code doesn't offer the wait at all" for "Background
sessions and `-p` runs" (lines 756-758). Such a session stays `blocked` until someone replies. The client has no
command that sends a reply (`claude --help` at 2.1.300, lines 265-310: `agents`, `attach`, `logs`, `respawn`, `rm`,
`stop` and others).

The command center measured this on 2026-10-15. The background session d4-bg was still `blocked` 4 minutes after
the 10:20Z reset, while interactive sessions had continued, and a reply at 10:24:10Z started its turn. Its ruling of
that day (d4 Phase 2 P6) is that the lane monitor reports such sessions and that its consumer resumes each of them
once.

## Who acts on it

The command center's Monitor runs the script. Its consumer, the command center's or the co-op's session, sends ONE
resume message for each `LIMIT-BLOCKED` line: a reply to that session asking it to continue (agent-view docs, line
886), through agent view or `claude attach <id|name>` (line 763). It logs each message it sends with the line's
`session` and `reset`. A `LIMIT-UNPARSED` line gets no automatic message: the consumer reads the session first, for
example with `claude logs <id|name>` (line 764).

A Monitor watch ends at its deadline, at most 30 minutes, and Claude gets one notice so that it can start the watch
again (tools reference, lines 376-378). Each start runs the check on its first snapshot. The state file is what keeps each `LIMIT-BLOCKED` line to
one across these restarts.

## The LIMIT-BLOCKED rule

- **Row.** `kind` is `background` and `state` is `blocked` (agent-view docs, lines 785-803). The JSON keeps listing
  a blocked background session after its process exits (line 779), so a row without `pid` counts too.
- **Transcript.** The session's transcript is `<config>/projects/*/<sessionId>.jsonl` (sessions docs, line 256).
  `<config>` is `$CLAUDE_CONFIG_DIR` when that variable is set (env-vars docs, line 435; sessions docs, line 264), else
  `~/.claude`. The `sessionId` must be a UUID, and the newest matching file is used. Only its last `--tail-bytes`
  bytes are read (default 1 MiB). In that window, the last assistant record of the main thread (not a sidechain) is
  the one checked.
- **Stop.** The record is the client's own message, not the model's: at 2.1.300 it carries `isApiErrorMessage: true`
  and model `<synthetic>`; either one is accepted. Its text starts with `You've hit your `, the usage-limit messages
  in the errors docs (lines 44, 714-717, 822-826). The warning `You've used 85% of your session limit · resets 3:45pm`
  (line 735) is not a stop.
- **Reset text.** The text is split on ` · `. The first part that reads `resets <when>` or `your <window> resets
  <when>` (errors docs, line 831) names the reset; trailing parts such as ` · progress saved` are ignored. `<when>`
  is one of:
  - `6:20am (America/New_York)`: a time, with minutes when they are not zero;
  - `Oct 20, 10am (America/New_York)` or `Jan 3, 2027, 6:30am (<zone>)`: a date and a time;
  - `Mon 12:00am (<zone>)`: a weekday and a time (the errors docs' form, line 715).

  The zone is required, because a wall time without one has no single instant. The 2.1.300 client always writes
  it; the errors docs' examples omit it, and such text gives `LIMIT-UNPARSED`.
- **Reset instant.** The first occurrence of that wall time in that IANA zone (Python `zoneinfo`) at or after the
  stop record's `timestamp`, compared at the timestamp's minute because the text has no seconds. A stated date is
  used, and without a year the first such date at or after the stop counts. A wall time that occurs twice (the
  November change) resolves to its first occurrence at or after the stop. A wall time the zone skips resolves to the
  next day on which it occurs.
- **Due.** The line is printed when the snapshot's time is at least the reset instant plus `--limit-grace` seconds
  (default 600). With the 60 s interval it comes at 600-660 s past the reset.
- **Once.** The key is the session id and the reset instant (`LIMIT-UNPARSED`: the session id and the record's
  `uuid`). A new limit stop with a later reset gives a new line.

## State file

`$XDG_STATE_HOME/native-agent-stack/lane-liveness/limits.json` holds the state, with `~/.local/state` used when
`XDG_STATE_HOME` is unset or not absolute. The directory is set to mode 0700 on every write and the file is 0600.
Each write goes to a temporary file in the same directory, which is fsynced and then renamed over the old file, and
the directory is fsynced after it. An exclusive `flock` on `limits.lock` serializes two monitors; a monitor that
finds the lock held leaves the decision to its next snapshot. Records older than 30 days are dropped on each write.

The line is printed and flushed before its record is saved. A crash between the two can repeat that line once after
a restart, but it cannot lose one. If the file cannot be read or written, a `LIMIT-STATE` line says so and the record
lasts only for the life of the process.

## Install (the command center's act; nothing here is applied)

The running v2.1 is `lane_liveness_v2_1.py` (mode 0555) in the command center's monitors directory. Install v2.2
next to it under a new name, then re-arm the Monitor:

```bash
M=/var/tmp/cc-cc-work/monitors        # the command center's monitors directory
cp tools/lane-liveness/lane_liveness.py "$M/lane_liveness_v2_2.py" && chmod 0555 "$M/lane_liveness_v2_2.py"
/usr/bin/python3 -I -u "$M/lane_liveness_v2_2.py" --selftest   # one snapshot, exit 0
```

To re-arm, the command center stops the Monitor that runs `lane_liveness_v2_1.py` (`TaskStop` with its task id,
tools reference, line 58, or by asking for it, line 380). It then starts a Monitor with
`/usr/bin/python3 -I -u /var/tmp/cc-cc-work/monitors/lane_liveness_v2_2.py`. The first line is the `baseline`. A
session that is limit-blocked past its reset plus 600 s at that moment gets its `LIMIT-BLOCKED` line in the same
snapshot.

Inverse: stop the v2.2 Monitor, start the Monitor again on `lane_liveness_v2_1.py`, which stays in place, and
`rm "$M/lane_liveness_v2_2.py"`. The state directory `~/.local/state/native-agent-stack/lane-liveness/` is inert
without v2.2; remove it to start from nothing. A later v2.2 would then print once more for any session still blocked
past a known reset.

## Limits

- **Transcript format.** "The entry format is internal to Claude Code and changes between versions" (sessions docs,
  line 258). A changed record shape most likely makes the report go silent, because a line needs every check above
  to pass. The tests pin the 2.1.300 shape, so re-measure after a client update. The docs' supported push signal is
  a `StopFailure` hook matched on `rate_limit`, which receives `session_id` and the rendered error text (hooks docs,
  lines 2797-2823). It is not used here because it needs a hook install; it is the candidate if the transcript shape
  changes.
- **Tail size.** A stop followed by more than `--tail-bytes` of other records is not seen. Measured 2026-10-15 over
  the 298 stops in this host's transcripts modified in the previous 3 days: from a stop's first byte to the next
  user or assistant record took a median of 2,844.5 bytes and a maximum of 327,035 bytes. The 1 MiB default is about 3 times that
  maximum.
- **Parser check.** Measured 2026-10-15 over this host's top-level transcripts (`~/.claude/projects/*/*.jsonl`):
  all 419 client-written stops parse to the same instant as the record's own `quotaLimits.resetsAt`. That field is
  undocumented and is used only for this check. Another 26 assistant records contained the phrase (model text or
  tool calls), and none was taken for a stop.

## Sources

Docs pages fetched 2026-10-15 as Markdown from `https://code.claude.com/docs/en/<page>.md`; the lines cited are
lines of these copies.

| Page | sha256 | Lines used |
|---|---|---|
| `errors` | `d28fbfce1925693bcca6448782bdb106b618e7a62f1352cb64d40bc3834bbc03` | 44, 707-720, 722, 735, 819-831 |
| `interactive-mode` | `9c45cebdde1c3a9e4698e0b2dab53c1a5382066efce6005e3cbf3fb9efde2b35` | 711-713, 756-758 |
| `agent-view` | `c8e2b81092b94b4b3ded2c86b40b8329e73b8f39b36acb3288bd56385bc83266` | 763-764, 779, 785-803, 886 |
| `sessions` | `1906cee77bc74796f7e26258793f2840841c08c421b37c503f72f13f0d690919` | 256, 258, 264 |
| `env-vars` | `54351937e4d1a8b7b79d43fc9784709be4fd0a2c5d2423c5388fa2ff88550b3a` | 435 |
| `hooks` | `f5957ad68ec47adaed8c2462a0cb9fb04ccc979e066b3eec96f5342ec51728cc` | 2797-2823 |
| `tools-reference` | `320420019ef6584aa61d1b3e30c91f07885c9dc90b5a184f68f1f0ca13c59b50` | 39, 58, 376-380 |

The installed client 2.1.300 (`claude --version`):

- `claude --help`, lines 265-310, lists the subcommands.
- In its binary, the stop composer writes `You've hit your <limit><suffix>` with an optional ` · progress saved`.
- The reset formatter it calls for these stops writes the time alone when the reset is within 24 hours, else
  `Mon D[, YYYY], H[:MM]am`, and appends ` (<zone>)`.

Both were read with `grep -a` on the binary on 2026-10-15.

## Tests

`python3 -m unittest tests.test_lane_liveness`. It uses fixtures only: a stand-in for `claude agents --json --all`,
temporary transcripts under a temporary `CLAUDE_CONFIG_DIR`, a temporary `XDG_STATE_HOME` and an injected clock.
