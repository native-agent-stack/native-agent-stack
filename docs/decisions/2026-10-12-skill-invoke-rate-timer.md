# The daily skill-invoke record can run: two halves, the capture's timeout and the clone it needs, 2026-10-12

Status: built from CPA-C-002 of the Claude-family practice audit (`claude-practice-audit-claude-20261012`, finding G3-01), relayed by the command center on 2026-10-12, and measured here. The command center ruled the same day that the daily run is split into two units, one per client, with the limits and schedule below. Installing the units is the command center's act after this lands. Round 2 (Astra's read of 6c4bbd0d, 2026-10-12) added decision 7 (the services are confined to their record directory), the validation of the other half's record and the refresh lock (decision 3), and corrected the systemd source label (below).

## Context

#970 ([2026-10-10-daily-skill-invoke-rate.md](2026-10-10-daily-skill-invoke-rate.md)) added `tools/skill-usage/daily_skill_usage.py` and a user timer that records, once a day, the native `/skill-doctor` lifetime uses for the host with the Codex and Claude lane counts. On 2026-10-12 the host had no timer and no unit, `skill-invoke-rate-latest.json` did not exist, and the newest manual host report (2026-10-11T16:13:49Z) had refused its Claude half: `failed to run claude -p /skill-doctor: TimeoutExpired`, the 30 s default of `skill_usage.py`. The trial's review (2026-10-25) and its prune rule need per-skill Claude uses, and a skill with zero uses cannot be told from one that was not measured.

The audit predicted that the templated unit would fail twice. Both are real, and a third followed from running the unit once:

1. **The timeout.** `daily_skill_usage.py` runs `skill_usage.py --run-skill-doctor` and passes no timeout, so the 30 s default applies.
2. **The clone.** The run exits 2 unless `git branch --show-current` prints `main`. The unit renders `@REPOSITORY@` to the live clone, `~/code/native-agent-stack-live`, which the command center defined as a detached worktree of `origin/main` ([2026-10-09-claude-review-worker.md](2026-10-09-claude-review-worker.md), "The install is the command center's": the worker's unit refreshes it with `git fetch` and `git switch --detach origin/main` before every tick). A detached HEAD has no branch name. Measured 2026-10-12: the unmodified script run from the live clone answered `daily skill usage unavailable` and exit 2 before collecting anything; the clone's `git branch --show-current` printed nothing. Attaching that clone to `main` would not last: the worker's next tick detaches it again.
3. **One unit for two clients.** The single run held three commands at a 1,200 s limit each. Run once as a transient user unit on 2026-10-12 (09:13:47Z to 09:37:44Z), it took 23 min 57 s, 26 min 55 s of CPU and 12.5 GB of peak memory (page cache included), and exited 1, which the run does when any key is unmeasured: the Codex lanes scan alone takes 25 min 47 s (below), past the 1,200 s the run allows each command. One exit status and one record therefore stand for both clients, and a timeout in either marks the whole record.

The output directory of the unit (`~/.local/state/native-agent-stack/coordination/command-center/skills/`) is not inside a git work tree, so `publish()` accepts it; that is another place the unit could have failed and does not.

## Measurement

Claude Code 2.1.296, `claude -p /skill-doctor` with the fences of `SKILL_DOCTOR_ARGV` (0 turns, 0 USD every time), run from a clone of the repository, on the host the audit measured. The account's transcript store held 6,263 files (7.3 GB) in 648 project folders.

| Condition | Runs | Wall seconds |
| --- | --- | --- |
| quiet host (1 minute load 9 to 16 on 64 CPUs), the interactive environment, the unit's environment (HOME, USER, XDG_RUNTIME_DIR and the unit's PATH only), the process pinned to 3 CPUs or to 1 CPU | 13 | 17.2 to 20.1, median 18.5 |
| the same with `--settings '{"disableAllHooks": true}'` | 1 | 16.2 |
| one CPU shared with two busy loops (three runnable threads on it, the capture pinned there) | 2 | 61.9, 57.7 |

The child's resource use over two runs: 16.1 and 15.8 user plus 10.3 and 10.8 system CPU seconds in 18.4 and 18.6 s of wall time (1.43 cores); pinned to one CPU, 13.4 plus 5.3 CPU seconds in 19.0 s (0.98 cores) and no slower. So a capture is about one core of work and its wall time grows with the number of runnable threads per CPU: 3.2 times the quiet time at three per CPU. The client's own debug timeline puts start-up and the SessionStart hook at about 2 s of the 18 s; the rest is the command's work, over a transcript store that was not varied here.

The host's load, from the local Prometheus (`node_load1`, 64 CPUs): 175 at the failed capture (2026-10-11T16:13Z, 2.7 per CPU, estimate 50 s), 111 at the 95th percentile of the last seven days (1.7 per CPU, estimate 32 s, already past the old limit) and 201 at their maximum (3.1 per CPU, estimate 58 s). The estimate is the quiet median times the per-CPU load; the two loaded captures agree with it. Not measured: a capture at load 175 itself, and the effect of a larger store.

**Each command of the daily run on its own**, as a transient user unit (`systemd-run --user --wait`, the template's PATH, `StandardOutput=file:`), one command at a time, on 2026-10-12 at a 1 minute load of 12 to 19:

| Half | Command | Wall | CPU | Peak memory (the unit's cgroup, page cache included) |
| --- | --- | --- | --- | --- |
| Claude | `skill_usage.py --run-skill-doctor --claude-timeout 300 --window 7` (no Codex root) | 19.9 s | 30.4 s | 1.5 GB |
| Claude | `child-usage.mjs --lanes-sweep --root ~/.claude/projects` (7 days) | 2 min 17.9 s | 2 min 39.7 s | 1.8 GB (its stdout is 198 MB of JSON; parsing it takes 513 MB resident) |
| Codex | `skill_usage.py --codex-root ~/.codex/sessions --window 7` (no Claude source: 3,234 rollout files) | 1 min 10.5 s | 1 min 5.2 s | 2.8 GB |
| Codex | `skill_usage.py --lanes --codex-root ~/.codex/sessions` | 25 min 47.1 s | 29 min 18.1 s | 1.8 GB |

The host report answers for one client without the other: with no Codex root its Codex part is `measured: false`, with no Claude source its Claude part is. The 12.5 GB peak of the single run was therefore page cache of the read transcripts and rollouts (reclaimable), not a command's resident set: the largest resident figure measured here is 2.8 GB.

**Both halves end to end.** The units rendered by `--render-units` from a detached worktree of `origin/main` carrying this change (the clone test passed), each started as a transient user unit with the rendered `ExecStart` and `TimeoutStartSec`, the three record paths redirected to a scratch directory (the real ones are the command center's to create), one half after the other on 2026-10-12 at a 1 minute load of 17 to 22:

| Half | Wall | CPU | Peak memory | Exit | Record |
| --- | --- | --- | --- | --- | --- |
| Claude (09:30 unit) | 2 min 43.9 s | 3 min 16.0 s | 2.1 GB | 0 | `measured` host and claude true: 30 skills, 443 lanes |
| Codex (10:00 unit) | 28 min 3.6 s | 31 min 33.8 s | 3.4 GB | 0 | `measured` codex true: 30 skills, 3 lanes |

The combined record after the second half is `measured` true for host, codex and claude, carries the stamp of each half in `halves` and the older of the two in `generated_at`, and every record is mode 0600. The Codex half took 28 minutes against its 63-minute limit; the single run it replaces timed out its lanes scan at 1,200 s.

The host's load by UTC hour of day over the last 7 days, from the same Prometheus series (281 five-minute samples: the series is sparse, about 12 samples an hour, so the hour is provisional):

| UTC hour | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 to 21 | 22 to 07 (mean of the hours) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mean load | 15.4 | 19.6 | 12.8 | 19.2 | 7.8 | 14.1 | 25.7 | 51.6 to 91.7 | 10.7 to 36.2 |
| maximum | 21.2 | 26.5 | 18.0 | 24.8 | 13.3 | 37.9 | 93.2 | 98.6 to 184.8 | 16.4 to 61.9 |

The quietest span is 08:00 to 13:00 UTC (04:00 to 09:00 New York); the heavy hours are 14:00 to 21:00 UTC, the US session.

## Decision

1. **The capture may take 300 s** (`skill_usage.py` `DEFAULT_CLAUDE_TIMEOUT`, also the default of `--claude-timeout`): five times the capture at the seven-day load peak and room for the store to double during the trial. `daily_skill_usage.py` takes `--claude-timeout SECONDS` (1 to 3600) and hands it to the capture only when given, so the unit can override it without a code change.
2. **The clone test is "HEAD is a commit of origin/main"** (`git merge-base --is-ancestor HEAD origin/main`), not a branch name. The live clone passes in its defined state; a clone on `main` passes; a feature branch, a commit of the clone's own and a clone with no `origin/main` are refused with a fixed message (the collection and `--render-units` alike, so a unit that would fail every day is never rendered). What it protects is that the scheduled run executes code that was merged: it is stricter than the old test for a local `main` with commits of its own, and, like the old one, it does not look at uncommitted edits.
3. **Two halves, two units, two records.** `daily_skill_usage.py --half claude` runs the capture and the Claude lanes sweep; `--half codex` runs the host report's Codex scan and the lanes report. Each half publishes its own record (`skill-invoke-rate-claude-latest.json`, `skill-invoke-rate-codex-latest.json`) whose `measured` holds only its own keys (Claude: `host`, `claude`; Codex: `codex`), and exits 0 only when its own keys are measured. So a Codex timeout marks only the Codex half unmeasured, and a slow Codex scan cannot delay or hide the Claude half. Each half then refreshes the combined `skill-invoke-rate-latest.json` that the Fleet page reads, merged from its own record and the other half's newest (`--combined-out`, `--other-record`): the older of the two `generated_at` stamps, each half's measured keys, the Claude fields of a skill from the Claude half and the Codex fields from the Codex half; a missing, unreadable or foreign record is an absent half, not a guess. A failed refresh never changes the half's exit status and prints a fixed message. The other half's record is taken only when every field the merge reads has the type it is written with (`measured` a mapping of booleans for that half's keys, `host` and `lanes` null or lists, `generated_at` null or a timestamp, the counts null or non-negative integers); a record of another shape is an absent half, as an unreadable one is, and the merge copies counts and the wiring name only when they have those types. Both timers are `Persistent=true`, so after the host was off both units start at once and their refreshes can overlap: the read of the other record and the publication of the combined one happen under an exclusive `flock` on `skill-invoke-rate-latest.json.lock` in the record directory, after the half has published its own record, so whichever refresh runs second reads what the first half published and writes the last combined record (a refresh waits up to 60 s for the lock and then leaves the combined record as it was; the lock is held for one read and one rename). The Fleet reader is unchanged and a test feeds the merge through it.
4. **Limits per command, from the measurements.** The capture its own limit plus a minute (360 s); the Claude sweep 600 s (4.3 times its wall); the host report's Codex scan 600 s (8.5 times); the Codex lanes scan 3,120 s (52 minutes, twice its 25 min 47 s wall, the command center's rule). A CPU-bound command takes about three times as long at three runnable threads per CPU, which the one-core commands above cover and the Codex lanes scan, at twice its wall, does not: a scan slower than that is the case for the incremental scan under Follow-ups, not for a longer limit. `TimeoutStartSec` of each unit exceeds the sum of its half's limits by a minute (17 min and 63 min); a test pins it. Oneshot units have no start timeout unless one is set (`man/systemd.service.xml` L682-L689, and the installed `systemd.service(5)`: "Defaults to DefaultTimeoutStartSec= ... except when Type=oneshot is used, in which case the timeout is disabled by default"), so a hung scan would otherwise hold the unit indefinitely. Every `man/...` citation of this record is to `systemd/systemd@e846bbad04d87e58ba9c3e30d8a1087141691715`, the mirror's development head (its `meson.version` reads `263~devel`; the mirror has no v259.5 ref, which an earlier version of this record mislabelled), and each behaviour cited was read again in the installed systemd 259.5 manuals (`systemd.service(5)`, `systemd.time(7)`, `systemd.timer(5)`, `systemd.exec(5)`, `/usr/share/man`, "systemd 259.5") on 2026-10-12; no 259.5 source citation is filled in from memory.
5. **Schedule: 09:30 UTC (Claude) and 10:00 UTC (Codex)**, `OnCalendar=*-*-* HH:MM:00 UTC` (`man/systemd.time.xml` L254-L256: the timezone may be the literal `UTC`; `man/systemd.timer.xml` L190), `Persistent=true` (L384) and `RandomizedDelaySec=5m` (L265), `Nice=10` (`man/systemd.exec.xml` L1356): inside the quietest span, staggered so the 3-minute Claude half is over before the 26-minute Codex half starts, which ends by about 10:35 UTC typically and by 11:10 UTC at its limit.
6. **The unit templates are replaced:** `skill-invoke-rate-{claude,codex}.{service,timer}` take the place of the never-installed `skill-invoke-rate.{service,timer}`; the installed copies are the command center's. No `ExecStartPre` refresh is added: the live clone is refreshed by the worker's tick, stale code on `origin/main` is still reviewed code, and a second unit moving the same clone could fail the run on a git lock.

7. **Each service writes only its record directory.** `UMask=0077` fixes the mode of what a service creates, not where it can write, and neither service had a read-only file system or a write allow-list: ordinary Python start-up wrote `__pycache__` into the live clone (Astra's reproduction), and the client the Claude half starts has the account's whole home to write to. Both services now carry `ProtectSystem=strict` (the whole hierarchy read-only, `man/systemd.exec.xml` L1497), `ProtectHome=read-only` (L1526), `ReadWritePaths=%h/.local/state/native-agent-stack/coordination/command-center/skills` (L1809; the one directory written: each half's record, the combined record and its lock, so both units share it), `PrivateTmp=true` (L1919; under `ProtectSystem=strict` it is what keeps `/tmp` writable for the client) and `Environment=PYTHONDONTWRITEBYTECODE=1` (it reaches every interpreter the service starts; `-B` on the parent alone would not). In a user service the file system namespaces need unprivileged user namespaces, which the user manager then enables itself (`man/system-or-user-ns.xml` L11-L14; `systemd.exec(5)` under `ProtectHome=`): where the kernel lacks them the unit fails to start with status 226/NAMESPACE and does not run unconfined. `ReadWritePaths=` has no leading `-`, so a missing directory fails the unit the same way: the record directory is created by the install (`mkdir -m 0700 -p`), which stays the command center's act. Specifiers resolve in `ReadWritePaths=` (checked: `systemd-analyze --user verify` rejects an unknown `%k` there and accepts `%h`).

   Measured on 2026-10-12 on this host (systemd 259.5, Linux 6.18 under WSL2) with `systemd-run --user`: (a) a probe started with the rendered directives is refused writes to the clone, to a sibling directory and to the rest of the home (`EROFS`), writes its record directory, and writes no bytecode, while the same probe without them writes everywhere and creates `__pycache__` in the clone (tests `ServiceSandboxRuntimeTests`); (b) the `/skill-doctor` capture, run under `ProtectSystem=strict`, `ProtectHome=read-only` and `PrivateTmp=true` with only a scratch record directory writable, exited 0 and measured the Claude side (30 skills, empty stderr), so the client's start-up writes to the account's state are not needed for the capture; (c) the rendered units, run end to end from a scratch live clone (a detached worktree whose `origin/main` is the commit under test, the record paths moved to a scratch directory) with their own directives:

   | Half | Wall | CPU | Peak memory | Exit | Record | Clone afterwards |
   | --- | --- | --- | --- | --- | --- | --- |
   | Claude | 3 min 7.5 s | 3 min 44.0 s | 1.9 GB | 0 | `measured` host and claude true: 30 skills, 546 lanes | no change, no `__pycache__` |
   | Codex | 33 min 58.1 s (the host was loaded by other work) | 38 min 20.2 s | 8.8 GB (page cache included) | 0 | `measured` codex true: 30 skills, 3 lanes | no change, no `__pycache__` |

   The records and the lock are mode 0600 and the directory 0700. Not measured: a host without unprivileged user namespaces (the unit's failure there is what the manual documents, not something this host showed), a client release whose start-up needs to write under the home (the capture would then be refused as `not-measured`, never recorded as zero uses), and the install itself.

## Alternatives

- **Attach the live clone to `main`** (the audit's second option): rejected, the worker detaches it on its next tick, and the daily run would fail silently from then on.
- **Raise only `skill_usage.py`'s default, or only add the flag:** each alone fixes the unit; both are kept so a manual capture at a loaded moment (the failed one was manual) also succeeds, and the unit can still override.
- **One unit with a 90-minute timeout:** rejected, it keeps the Claude record hostage to the Codex scan and marks the whole record unmeasured for either timeout.
- **A second clone on `main` for this unit:** rejected, a new clone to keep current for one timer, against the live clone the sibling units already use.
- **Refresh the clone in the unit** (as the worker does): see decision 6.
- **`UMask=0077` alone, or `-B` on the parent interpreter:** the read of 6c4bbd0d showed neither limits where a service writes; both stay (the mode of what is created, and no bytecode from the parent), the file system directives do the confinement.
- **Allow the client's state directory (`~/.claude`) for the Claude half:** not needed, the capture measured without it (decision 7); a directory that the client rewrites (transcripts, credentials) is the wider thing to leave open.
- **The Fleet page reads both records:** it would change a reader and its tests for no gain over a derived file; the combined file keeps the reader as it is.

## What is not covered

- The timers are not installed here. The audit's settling rule stands for the Claude half: two consecutive daily records under the installed unit with `measured.host` true, before 2026-10-25.
- A capture on a host far more loaded than the seven-day peak, or with a much larger store, can still exceed 300 s; it then fails as `not-measured` with the `TimeoutExpired` reason, which this change leaves unchanged (a refused capture is never recorded as zero uses).
- The Codex lanes scan can exceed 52 minutes at three runnable threads per CPU (about 77 minutes by the same ratio); that half is then unmeasured for the day and the Claude half is not.
- The quiet hours rest on a sparse series; they are revised when a week of samples exists.
- Why the capture costs a core of CPU is not attributed here.

## Follow-ups

- A native report with the right `kind` and an inner field of the wrong type still raises in `project_reports` (a traceback names the home path and no record is written); the reports come from this repository's own commands, so the guard added here is on the other half's file, which another process writes. Validating the native reports the same way is a separate change.
- The measurements of this record were taken by the author from transient user units; the receipts that exist are published beside the record (`evidence/artifacts/skill-invoke-rate-timer-20261012/`, with the claims that have none listed in its README).

- An incremental Codex scan, reading only the rollouts newer than the last record, would take the Codex half from 26 minutes to the day's new files (the command center's direction); the 3,120 s limit is then a ceiling, not a working figure.

## Overturn conditions

- A client release that makes `/skill-doctor` cheap or slow: re-measure the capture (the method is the table above) and revise the timeout.
- The command center changes how the live clone is kept (for example attaches it to a branch): the test still passes for a branch that is at a commit of `origin/main`.
- A week of load samples that puts a different span lowest: move the two `OnCalendar` lines.
