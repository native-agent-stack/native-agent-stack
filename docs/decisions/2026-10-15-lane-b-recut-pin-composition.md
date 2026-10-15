# Compose lane B recuts with landed #1113

Date: 2026-10-15. Scope: new packet construction only.

## Defect and decision

At main `e35a6b6dfa2269c354ac526b1dab2bc7255f5bdc`, the lane B
builder still expected #1087's `paper-readiness-seq3/recut.py`, although #1113
had changed that file on main. Its native source guard correctly refused
`landed_latch_source_pin_mismatch` before creating an output. The previous
required-suite test mocked every pin read and concealed this integration drift.

Adopt the already reviewed #1113 implementation rather than duplicate its
authenticated replay parser. Pin all four latch sources to its landed commit
`e1c28c3201d2f152cd8f171e74262270626e1560`; the recutter blob SHA256 is
`9d46880d52506ec38f9b4598c72fa9bb41804e497737e92fcb071a766abb4c1d`.
Use `inventory_rows`, `replay_inventory` and `REPLAY_SOURCES`, alongside the
existing `rewrite_launch`, `rewrite_issuer` and `rewrite_unit` calls. Emit its
pinned `dry_run.py` through the existing r3 replay adapter. Do not call
#1113's `recut()`; #1117 still supplies the intermediate flat-proof builder.

Original sealed packets may have neither replay inventory rows nor a driver.
Accept a separate expected-hash-bound replay record through explicit CLI
arguments, authenticate its landed Git blobs with #1113, reject conflicting
original rows, and add only captured record/replay bytes to the new packet.
Retain the original source seal and installed-generation receipt origin.
Missing or invalid authority refuses before output construction. No private
authority record or its expected digest is published in this change.

Also anchor the four unchanged #1117 helper files at their squash commit
`edf832907676735ca6fa58c598213b544ca7510c`. All four blobs equal the prior
branch pin `1ebb4d25e140dc1c8bce1b7f2e53c8c74ff575d8`; this changes
reachability in a full-main-history checkout, without a helper algorithm edit.

## Sources

- [native-agent-stack #1113](https://github.com/native-agent-stack/native-agent-stack/commit/e1c28c3201d2f152cd8f171e74262270626e1560),
  `blueprints/us-equities/paper-readiness-seq3/{recut.py,dry_run.py,lane_latch.py,seq2_retirement.py}`:
  authenticated inventory/Git capture, replay tripwires and private latch helpers.
- [native-agent-stack #1117](https://github.com/native-agent-stack/native-agent-stack/commit/edf832907676735ca6fa58c598213b544ca7510c),
  `blueprints/us-equities/paper-flat-proof/{recut.py,recover_pre_skip.py,observe_flat.py,README.md}`:
  native flat-proof intermediate and unchanged helper provenance.
- [Git 2.53.0 cat-file](https://github.com/git/git/blob/v2.53.0/Documentation/git-cat-file.adoc):
  supported `cat-file blob <commit>:<path>` interface used by the existing readers.

These pinned in-repository implementations are the upstream sources for this
composition; no replacement parser, transport, runner or dependency is added.

## Regression and validation contract

Required test:
`tests.test_lane_b_r3_replay.RetainedReplay.test_emitted_packet_retained_lifecycle_and_unit_contracts`.
Run it with the test-only change on the base production bytes: it fails with
`landed_latch_source_pin_mismatch`. The fixed composition must pass using
real local Git objects and the exact builder commit, with no mocked pin reader.
The workflow fetches complete history and includes this module in its required
unittest shards. A future stale pin therefore fails the required suite.

The same module exercises missing original replay rows/driver with a clearly
SYN authority record, checks unchanged original inventory, exact emitted Git
blobs/driver/provenance and native strict checksums, and checks refusal for
absent/incomplete/incorrect authority and source conflicts. The small CI
fixture runs three retained lifecycle/unit contracts with inert data modules;
it is not the full retained drill.

The separately attached full recut SYN drill uses authentic frozen runtime
and config inputs, the separate SYN Git record, all 49 retained cases,
credential/process tripwires and native strict checksum verification. Its
receipt must show zero skips, failures, errors, tripwire hits and services
started, with broker execution `NOT_RUN`. `python3 scripts/validate.py` must
return zero. Actual execution receipts belong in the PR record.

## Alternatives and limits

Changing only the stale pin leaves the absent replay inputs unresolved.
Rewriting the original seal falsely asserts historical membership. Rebuilding
the #1113 parser creates a second authority contract. The chosen composition
reuses its exact landed implementation and preserves both input seals.

This does not prove native trading, install units, arm paths, alter account
state or activate a recut. Two-family review precedes a later build on approved
main; the CC then authorizes the full manifest hash and the co-op controls
the boundary changeover. New contradictory Git provenance or a failed native
required-suite/full-SYN result reopens this composition decision.
