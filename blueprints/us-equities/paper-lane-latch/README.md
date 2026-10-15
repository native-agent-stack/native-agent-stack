# Lane B stage latch: a private automatic marker

The installed seq2-flat stage end creates the shared host STOP twice: the
launcher stop-mark opens it, then the unit's shell touch updates it. A normal
stage end therefore stops independent lanes before recovery removes the file.
Removing the touch alone still leaves the launcher write.

This recut adopts the already merged #1087 mechanism. Operator host STOP and
lane-b/STOP remain read-only. Stage end creates a private `.stage-hook-latch`
under the owned mode0700 instance; non-flat recovery retains it. Launcher and
issuer admission see both operator paths and all outstanding private markers.
Only successful native flat recovery can clear the exact hook-owned private
marker. A modified marker remains an admission block. Existing native runtime
still honors the canonical host abort; no runtime or CONFIG byte changes.

## Sources and composition

Reference: native-agent-stack #1087 merged at
`943d5ba27b21aba01df1c2df6f63ef4b7e10fd36`:

- `paper-readiness-seq3/recut.py:31-86` relocates admission to lane/private
  marker checks and replaces stage stop-mark/recover ownership handling.
- `recut.py:89-98` updates issuer admission and retirement proof;
  `:127-138` removes the redundant shell touch from all eight stage services.
- `lane_latch.py:21-48` implements fail-closed pending-marker detection;
  `:79-95` creates and hashes an exact private marker;
  `:98-127` clears only the exact owned marker using descriptor-relative unlink.
- `seq2_retirement.py:8-22` is the native read-only unit inventory checker.
  The local flat_retirement adapter runs the same checker with an isolated
  globals dictionary for the prior seq2-flat names, after checking seq2.
  It never changes the shared module inventory. CPython3.12.3's supported
  `types.FunctionType` supplies that isolated binding.

Flat proof fixes come from #1117 head
`1ebb4d25e140dc1c8bce1b7f2e53c8c74ff575d8`: its existing native recutter,
observer and failed-observation receipts. `seal()` checks all reused source
bytes against those exact published Git blobs and its own source commit.
The original deployment is authenticated by its externally supplied seal.
The currently installed generation is separately authenticated by its seal
and native strict checksum before its runtime/config bytes are compared.
No source seal is rewritten. The new receipt origin is the supplied currently
installed bundle, so same-state-root historical handoffs need no relabeling.

The lane B r3 preparation overlays only the canonical launcher's `keyed` and
`run_stage` methods from `tests/fixtures/seq2-launch.txt`, selected from the
builder's exact source commit. It leaves the authenticated native runner and
CONFIG files unchanged. Trial acceptance reads PRE `paper.json` or scheduled
`paper-output.json`, records recovery-only starts separately and refuses them
as trial evidence. Native paper reads have a separate 1MiB cap (measured
maximum407527B across98 outputs); the64KiB GO/control reader is unchanged.
Native exit-zero statuses passed/completed_no_signals/held_overnight remain
successful. A timeout sends TERM, permits 630 seconds for the cited
recovery bounds, then KILL if still running; timeout remains refusal exit124.
The scheduled Bash leader defers its TERM/INT exiting traps until its
foreground runner ends, then returns143/130 without starting any later command.
The generated root `scheduled_trial_r3.sh` retains the frozen script's logic
and native module directory, adding `--kill-after=670s` to its TERM900 wrapper.
It does not alter the frozen input script. Wrapper hard deadline1570s exceeds
900+630+10; the two read-only120s ingestion/gate commands gain1s KILL-after
bounds, so loader1820s exceeds242s preparatory work plus1570s wrapper.
Those signal/group semantics are uutils/coreutils0.10.0 at28b6856d,
timeout/platform/unix.rs:47-54,64-81,99-119. Its uucore process/unix.rs:119-144
ignores repeated TERM in kill-after without resetting the grace deadline.
The decision record gives full paths/pin and the installed -k3/1 timing probe.

New packets also emit a source-bound replay adapter. It updates retained SYN
paper outputs, scheduler-name assertions and unit-budget expectations only
in memory; all five archived replay files remain byte-identical. Run the new
packet's own dry_run.py: it retains the full49-case minimum and all credential/
process tripwires. A narrow CI contract probe is separate from that full drill.

New-unit envelopes cover that full wait plus 30 seconds: RuntimeMaxSec at least
5150s PRE, 1850s RTH and 780s GET-only pre-skip; TimeoutStopSec at least2140s
for native recovery plus its possible GET-only fallback, including both630s
graces,10s teardown and30s margin. These are new-packet construction values, not changes to any
installed unit. The enclosing native runner's recovery bounds and CPython
subprocess semantics are cited in
`docs/decisions/2026-10-15-lane-b-r3-launcher-contract.md`.

The packet uses canonical `-seq3` unit names. It embeds BOTH old-generation
retirement checks so an enabled/active seq2 or seq2-flat watcher refuses new
issuer admission. The shared seq3 retirement-inventory PR remains separately
required before any later general seq3 recut/changeover. This composition does
not consume #1113's unlanded alternate replay inventory API or claim that
historical replay files belong to their predecessor seal.

## Verification and boundary changeover

1. Fail-first: execute the unchanged installed launcher's stop-mark/recover
   on SYN state. It creates shared host STOP; the new stage end leaves host
   and lane operator paths untouched and creates its private marker instead.
2. Exercise successful flat recovery, non-flat retention, orphan-marker
   issuer refusal, operator STOP identity preservation, modified-marker
   refusal, and every enabled prior path unit. Retain failed runs. Keep the
   #1117 failed-observation/native transport regressions in the named suite.
3. Normal one commit/push and new destination seal, native strict checksum,
   runtime/config comparison and systemd-analyze unit-parser checks. No broker
   or runtime activation is part of this build.
4. Lane B stays HELD today. Astra and CC micro review this exact head/packet.
   Tonight's SESSION BOUNDARY only: the co-op/CC verifies old active trials
   completed/flat, no pending GO, and retires EVERY seq2 and seq2-flat path
   first. Confirm all old services inactive; never run generations together.
5. Obtain the explicit CC authorization naming the new full manifest hash,
   install/verify the 22 new unit files, then arm the 11 new paths. Co-op
   binds its sole issuer to this packet/authorization and repeats its native
   SYN drill. Existing native flat proof/60-second same-boot drain gates remain.

This coding lane performs no real recovery, account/STOP mutation, unit
installation, arming or start. The protected #1117/#1113 heads are unchanged.
Current-new-bundle pre-skip recovery lifecycle and broader deferred #1117
findings remain follow-ups; the inherited canonical host abort is retained.
