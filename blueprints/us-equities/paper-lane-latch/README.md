# Lane B stage latch: a private automatic marker

The installed seq2-flat stage end creates the shared host STOP twice: the
launcher stop-mark opens it, then the unit's shell touch updates it. A normal
stage end therefore stops independent lanes before recovery removes the file.
Removing the touch alone still leaves the launcher write.

This recut adopts the landed #1113 composition of the #1087 mechanism. Operator host STOP and
lane-b/STOP remain read-only. Stage end creates a private `.stage-hook-latch`
under the owned mode0700 instance; non-flat recovery retains it. Launcher and
issuer admission see both operator paths and all outstanding private markers.
Only successful native flat recovery can clear the exact hook-owned private
marker. A modified marker remains an admission block. Existing native runtime
still honors the canonical host abort; no runtime or CONFIG byte changes.

## Sources and composition

Reference: native-agent-stack #1113 merged at
`e1c28c3201d2f152cd8f171e74262270626e1560` (including the #1087 mechanism):

- `paper-readiness-seq3/recut.py`'s `rewrite_launch` relocates admission to lane/private
  marker checks and replaces stage stop-mark/recover ownership handling.
- `rewrite_issuer` updates issuer admission and retirement proof;
  `rewrite_unit` removes the redundant shell touch from all eight stage services.
- `lane_latch.py:21-48` implements fail-closed pending-marker detection;
  `:79-95` creates and hashes an exact private marker;
  `:98-127` clears only the exact owned marker using descriptor-relative unlink.
- `seq2_retirement.py:8-22` is the native read-only unit inventory checker.
  The local flat_retirement adapter runs the same checker with an isolated
  globals dictionary for the prior seq2-flat names, after checking seq2.
  It never changes the shared module inventory. CPython3.12.3's supported
  `types.FunctionType` supplies that isolated binding.

Flat proof fixes come from #1117 landed commit
`edf832907676735ca6fa58c598213b544ca7510c`: its existing native recutter,
observer and failed-observation receipts. Its four consumed helper blobs are
byte-identical to the reviewed branch head `1ebb4d25e140dc1c8bce1b7f2e53c8c74ff575d8`;
the landed pin makes them available in normal full-main-history CI checkouts.
`seal()` checks all reused source
bytes against those exact published Git blobs and its own source commit.
The original deployment is authenticated by its externally supplied seal.
The currently installed generation is separately authenticated by its seal
and native strict checksum before its runtime/config bytes are compared.
No source seal is rewritten. The new receipt origin is the supplied currently
installed bundle, so same-state-root historical handoffs need no relabeling.

The additional #1113 APIs consumed are `inventory_rows(raw)` and
`replay_inventory(path, expected_sha256)`, plus its `REPLAY_SOURCES` contract.
The first parses the original sealed inventory; the second authenticates a
separate authority record and captures its five exact landed Git blobs.
When the original seal lacks replay rows, both `--replay-inventory PATH` and
`--replay-inventory-sha256 EXPECTED` are required. The expected digest comes
from the CC separately, never from discovery beside the source. Existing
inventoried replay rows must agree with the record. Record bytes/provenance
and captured replay blobs enter only the new packet; the original inventory
and its receipt origin stay unchanged. An unlisted physical replay file is
never used. The replay driver comes from #1113's pinned `dry_run.py`, so the
predecessor need not contain a driver. This builder does not call #1113's
`recut()`; the #1117 builder still constructs the flat-proof intermediate.

The lane B preparation overlays the canonical launcher's `keyed` and
`run_stage` and `verify_handoff` methods and its narrow `rest_flat_after_stream_failure` hook from
`tests/fixtures/seq2-launch.txt`, selected from the builder's exact source
commit. The hook is inserted after native recovery, preserving the source
generation's private-latch and handoff code. It leaves the authenticated native runner and
CONFIG files unchanged. Trial acceptance reads PRE `paper.json` or scheduled
`paper-output.json`, records recovery-only starts separately and refuses them
as trial evidence. Native paper reads have a separate 1MiB cap (measured
maximum407527B across98 outputs); the64KiB GO/control reader is unchanged.
Native exit-zero statuses passed/completed_no_signals/held_overnight remain
successful. A timeout sends TERM, permits 630 seconds for the cited
recovery bounds, then KILL if still running; timeout remains refusal exit124.

A persistent stream-readiness failure can occur when a flat stage traded no
symbols. Native zero counts alone remain insufficient to certify flatness.
Only a single native stream-start TransportError, strict integer0/0/0
position/open-order/submission preflight, no local positions/unresolved
orders and no submit/cancel/exit activity may invoke the existing GET-only
`observe_flat.py`. Unknown/non-stream/integrity/teardown errors and nonzero or
missing native counts refuse. The normal handoff validator still requires
observer rc0, passed/flat=true and complete REST0/0 proof. An absent observer
output preserves the native failed receipt and records a refusing handoff.
No native retry or live stream is added. The observer fits the already
reserved120s fallback slot; the enclosing recovery budgets do not change.

RTH qualification uses the public `runner.py recover` mode `adaptive_paper`,
not the inner recovery mode. The mover producer does not emit the required
preflight counters, so that missing evidence keeps PRE stream failures closed;
zero counts are never inferred. The ordinary no-owned-trial fallback remains.
The emitted handoff validator recognizes `stream-flat-probe.json` alongside
the two legacy paths only when its exact hash matches the handoff's existing
`native_recover_sha256`. Bundle/config/trial/flatness/boot/drain checks stay
in force. A stale legacy file cannot override the recorded stream proof, and
a tampered proof cannot admit the next stage. This validator is grafted into
new packets, not just changed in the canonical fixture.

An authenticated PRE `scan_empty`/`not_started` receipt with zero submitted
orders is a clean no-trade stage. The launcher verifies its config and scan
hashes plus the empty selected-symbol list, records `no-trade.json` with an
INFO event and evaluated counts selected_symbols0/orders_submitted0, and
returns0 even when the immutable runner returned its legacy no-start code2.
The native receipt stays unchanged. This creates no trial evidence or flat
proof; the normal recovery hook still runs. Service exit0 avoids OnFailure
for the empty scan itself. The native scan has no evaluated-universe count,
so none is inferred or invented. Other refused, malformed or nonzero-order
outcomes remain refusals.
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
required before any later general seq3 recut/changeover. The separate replay
record establishes first authenticated Git provenance; it does not claim
historical replay files belonged to their predecessor seal.

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
   The required unittest discovery suite includes
   `tests.test_lane_b_r3_replay.RetainedReplay.test_emitted_packet_retained_lifecycle_and_unit_contracts`:
   it uses actual Git pin checks, without a pin-reader mock, and refuses stale
   composition pins with `landed_latch_source_pin_mismatch`. Additional tests
   cover absent replay rows/driver, authenticated capture, retained source
   seal, invalid authority and conflicting inventoried rows.
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
