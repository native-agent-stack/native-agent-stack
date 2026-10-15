# Lane B launcher acceptance and recovery timeout

The shared runner start-path r3 is native-agent-stack commit
`cb0e7d348d564520eb0911476d9d4b0f227952ea`, parent
`303baca4cfe45db815366f1f49a0f137b8b9b42b`. It can complete an outstanding
recovery instead of starting a trial and return exit zero with status
`recovery_only`. Lane B must read the actual paper output, reject that status
as trial evidence, and record a separate `recovery-run.json`. A successful
trial accepts the native exit-zero statuses `passed`, `completed_no_signals`
and `held_overnight`; a nonzero native exit remains nonzero. PRE reads
`paper.json`; scheduled stages read `scheduled/paper-output.json`.

The launcher must also leave recovery time after its normal command timeout.
At the r3 pin:

- `runner.py:252-258` arms the recovery stop handler before unblocking TERM;
  `:300-308` blocks TERM/INT before the fresh-process exec.
- `runner.py:3217` and `mover_runner.py:1063` identify recovery-only starts.
- The preflight observers (`runner.py:2715-2719`,
  `mover_runner.py:622-627`) allow at most 50 requests. `transport.py:973` sets
  5-second connect and 5-second read timeouts for each request.
- `recovery.py:94-98` bounds order work by
  `min(cleanup_seconds, limits.cleanup_seconds, 120)`, including port start
  at `:223`; `:329` gives teardown at most 10 seconds.

The resulting minimum recovery grace is **50 × (5 + 5) + 120 + 10 = 630
seconds**, after TERM, before KILL. These are the cited request/order/teardown
bounds; process scheduling and a network peer's incremental read behaviour
are not measured wall-clock guarantees. The child returning zero during this
grace still leaves a timed-out trial refused with exit 124.

Use the existing credential runner unchanged. Its `run_command` forwards TERM
to the native command group and continues waiting for that command;
`tools/credentials/credential_run.py:996-1041` at current-main source commit
`89e89852161d8157e464f4bd07c2b5c747ad4706` records that mechanism. This task
does not load credentials or weaken its process/secret cleanup contract.
The scheduler's Bash leader installs a TERM/INT no-op trap before sourcing
the unchanged script. Bash defers a trap until its foreground command exits
(installed GNU Bash5.3.9 manual, Signals section); this keeps the native relay's
leader alive during recovery instead of triggering group cleanup early. A
test runs the actual credential relay API with empty synthetic environment
and a late-armed child, verifying the recovery survives its 2-second cleanup
threshold. It never calls the credential inventory/loader entry point.

Primary subprocess reference: CPython v3.12.3 commit
`f6650f9ad73359051f3e558c2431a109bc016664`, `Lib/subprocess.py:548-571`
shows that `run(timeout=...)` kills a timed-out child immediately. Its POSIX
`Popen.terminate`, `Popen.kill` and `Popen.wait` provide the supported
TERM/wait/KILL sequence used here. No process supervisor or signal mechanism
is reimplemented.

Fail-first tests execute the launcher fixture: PRE and scheduled recovery-only
exit-zero results were previously accepted; the fake child blocks TERM before
arming its handler and used to be killed before it could finish. A separate
child double verifies the exact 630-second grace and KILL ordering without
waiting ten minutes. All state/output is synthetic and no provider is called.

This is an issuer/daemon change. Both families and the CC read the PR before
installation. It must land before r3 is placed in lane B's frozen runner.
The current-runner rollover start is unaffected. The shared STOP publishers
remain operators and guards; this task adds no STOP publisher or admission
protocol. Existing deployed bundles are immutable and are not changed here.

The enclosing unit must not expire before its child's grace. A separate
recut/envelope commit overlays only the two canonical launcher methods into
newly authenticated predecessor text and raises the NEW packet unit limits:
PRE 4490+630+30=5150s, RTH1190+630+30=1850s, GET-only pre-skip120+630+30=780s;
trading stop/recovery(720+630)+(120+630)+10+30=2140s covers native recovery
and its possible GET-only fallback. The 30 seconds is an explicit supervisor
margin. Native runner/config bytes and scheduled script stay unchanged.
systemd v259 commit9ca433482f2281d71718718705ca8cd3bf562ad6,
`man/systemd.service.xml` sections RuntimeMaxSec and TimeoutStopSec, defines
the enclosing runtime and stop-command timeouts. A generated root-level
scheduler retains the frozen script's logic/native directory and adds
`--kill-after=670s` to its TERM900 wrapper, leaving the frozen input unchanged.
The two read-only preparatory120s commands gain1s KILL-after bounds, making
their total hard budget242s rather than assuming TERM always ends them.
Wrapper hard1570s >900+630+10; loader hard1820s >242+1570; runtime1850s >
loader1820+teardown10. PRE and recovery envelopes are checked independently.
The ordering test reads actual caller deadlines and loader grace from the
canonical launcher AST, then compares every generated enclosing deadline.

Known rollout window: armed lane B stages in the next session still use the
existing sealed launcher, including its900-second wrapper and absence of this
new grace, under the standing authorization. This PR changes the generators,
templates and NEW recuts only; the window closes at the next approved recut.

## Review fold: native receipts and retained replay

The small `safe_json` reader remains limited to 65536 bytes for GO/control
inputs. Native paper output uses a separate descriptor-bound reader capped at
**1 MiB (1048576 bytes)**. A sizes-only inspection of 98 lane B paper outputs
found 80 above the control-input limit and a maximum of **407527 bytes**;
no output contents were inspected for this measurement. The new cap exceeds
that maximum while retaining ownership/regular-file checks, no-follow open,
and a bounded cap-plus-one read if the file grows. A 136292-byte SYN output
now accepts native success or records recovery_only separately; output above
the documented cap still refuses. The GO/control limit is unchanged.

Native successful CLI statuses come from pinned
`8c95a50d10bd2db0b59058c6827275917ce35aa3`,
`adaptive-paper/runner.py:2273` and `mover_runner.py:1043`. Recovery-only is
still refused as trial evidence. This changes no native return/status producer
or recovery/flat-completion rule. Bounded file I/O follows CPython 3.12.3
`f6650f9ad73359051f3e558c2431a109bc016664`,
`Doc/library/os.rst:865,1056,1227` (fdopen/fstat/open),
`Doc/library/io.rst:563` (read up to size) and `Lib/json/__init__.py:299`
(loads accepts bytes).

New packets retain the archived five replay source files byte-for-byte. A
source-bound `replay_adapter.py` adapts their in-memory SYN keyed double to
emit explicit native paper success and updates the two scheduler-name
expectations and unit envelopes to 5150/1850/2140 seconds. The emitted dry_run
driver invokes this adapter before its existing private-latch adaptations;
its 49-case floor and credential/process tripwires remain unchanged. The
adapter changes no launcher behavior. The narrow CI fixture exercises the
retained lifecycle, pre-skip handoff and unit contracts on a newly sealed SYN
packet; the full 49-case drill uses the authenticated retained deployment
context separately, with no installation or credential/native runner call.

## Follow-ups

- The scheduled shell's no-op TERM/INT trap can swallow a stop between
  foreground commands. A later change must handle that window while preserving
  recovery grace; this fold does not alter the trap.
- Extend ordering verification to materialized units, the actual PRE starting
  envelope and the complete pre-skip/startup chain. Existing synthetic ordering
  coverage and cap checks do not establish deployed-systemd acceptance.
- Exact installed timeout process-group behavior and remaining pinned r3
  sources are separate co-op packet inputs. The installed timeout is uutils
  coreutils 0.10.0, not GNU coreutils; GNU timeout behavior is not host evidence.
