# Lane B stage latch, sequencing v3

The seq2 launcher and eight unit touch hooks wrote the operator's host-wide
STOP at every stage end. A flat recover then removed it. This interrupted other
lanes. Recovery now treats BOTH `alpaca-paper/lane-b/STOP` and host STOP as
read-only operator paths. Automatic cleanup owns only a private per-trial
`.stage-hook-latch` in the already-private instance directory.

The deterministic recutter verifies the original strict bundle inventory and
the exact retained launcher/issuer source bytes, copies the frozen runtime and
eight CONFIGs unchanged, and changes only:

- launch.py: operator paths and outstanding private markers block admission;
  stop-mark creates only a private per-trial machine marker,
  repeated hooks retain original ownership, and exact-CONFIG flat recovery
  clears only that private marker with the same trial, inode/device, modification/change
  clocks, size and body hash as the creating hook;
- issue_go.py: both latches block readiness issuance;
- lane_latch.py: ownership and unchanged-file checks shared by the hooks;
- the 22 seq3 unit files: paths/names point at the new bundle and all eight
  redundant shell touch hooks are removed. They are not retargeted, because
  touching an owned lane latch would invalidate its fingerprint;
- the new strict runtime manifest and separate validity-binding envelope.

Existing human lane latches, symlinks, replacements, modifications and failed
recoveries are never cleared. A host STOP arriving during recovery remains
unchanged. There is no host-latch create, touch, chmod or unlink operation in
the new lifecycle hooks. The frozen native engines continue to honor the
operator host STOP; node/order/quote/account recovery behavior is unchanged.

This is a deployment-glue correction, not an alternate engine or account
writer. The selected NautilusTrader 2.0.0rc5 source at
1b0a49d2792a9432a3aca3fcb617ce7a630d905e,
`crates/system/src/config.rs:98-105,61-64`, keeps native shutdown and bounded
cleanup semantics. Native account STOP enforcement is the existing NAS engine
at 8c95a50d10bd2db0b59058c6827275917ce35aa3 (`runner.Controller.stop_requested`,
`safety.DEFAULT_STOP`). The installed host runs systemd 259
(259.5-0ubuntu3.4). Upstream v259 at
9ca433482f2281d71718718705ca8cd3bf562ad6,
`man/systemd.service.xml:416-418,562-585`,
remains the supported path/service and ExecStopPost lifecycle; no
calendar timer or new scheduler is introduced.

The issuer and a sanitized historical launcher are non-executable `.txt`
fixtures. The launcher's historical private predecessor literal is replaced
with a hash of a published SYN byte string; its lifecycle behavior is retained.
Actual recuts verify the private expected manifest digest supplied as an input
and derive the launcher pin from that verified manifest. No digest committing
to non-public packet bytes is hard-coded in the public source. The test
harness redirects every state/latch/config root under `/var/tmp`, stubs native
recover with labelled SYN proof, and tripwires keyed execution and credential
pointer access. The first seven tests failed against the old launcher (three
failures, one error); the reviewed e3974ed9 baseline has 33 passing tests,
including dual-latch issuer refusal,
unit touch removal, preservation of a human symlink target and re-cutting a
predecessor with a read-only units directory. Round-1 regressions add copied-root
relocation, canonical containment, sealed ROOT permissions, bytecode/receipt
isolation, legacy watcher refusal, computed comparison and lane-directory race
coverage. Only NEW root/unit directories become writable for generation;
their permissions are restored read-only before the bundle is returned.
The final adjudicated round adds ten regressions: 43 tests now pass on the
managed 3.12 interpreter; the 33-case number above names the reviewed baseline.

```sh
systemd-run --user --scope -p CPUWeight=idle --quiet -- env TMPDIR=/var/tmp \
  python3 -B -m unittest tests.test_lane_b_stage_latch tests.test_lane_b_recut_boundaries -v
```

Use the sealed units' managed **CPython 3.12** interpreter for the issuer,
recut and replay commands (replace python3 in the example with that executable).
Generated issue_go.build asserts CPython 3.12 before readiness or GO writes;
another interpreter refuses `issuer_python_3_12_required`. The binding request
records this pin. The co-op must verify its issuer service/daemon interpreter
before restart; this tool does not change the service. pending() uses lstat,
treating only FileNotFoundError as absence, so permission errors block admission
even when a newer pathlib would suppress them. The regression runs pending()
on the managed 3.12 interpreter against a real unreadable SYN instance directory.

Re-cut into a NEW directory with `recut.py --source SEALED_SEQ2 --output NEW_SEQ3
--source-commit LANDED_FIX_COMMIT --predecessor-sha256 EXPECTED_PRIVATE_DIGEST`.
The expected digest comes from the sealed private binding; omission refuses.
After copying, every copied inventory row must match the captured predecessor
manifest before any rewrite or new SHA256SUMS. Source checks alone cannot bind
a later read. Derivations use the verified destination copies. The private
RECUT-RECEIPT retains the predecessor binding; CLI stdout omits that digest.
The strict manifest covers runtime inputs AND all five replay sources;
the GO-BINDING-REQUEST is a separate hashed envelope because it binds that
manifest's digest. The record retains predecessor state and config bindings.
No service is installed or started by the recutter; it writes no GO, STOP or
HOLD and makes no broker/credential call.

`dry_run.py --bundle NEW_SEQ3 --receipt SYN_RECEIPT` replays all five retained
wiring modules without changing their files. It adapts only SYN host/lane roots,
removes finish()'s simulation of the deleted shell touch hook, and checks the
new seq3 names/two hooks. Human-stop test actions remain intact. The real
credential-pointer function is replaced before the tests execute. The full
replay also tripwires launch.keyed and subprocess.run/Popen before replay
modules execute. It records keyed/process tripwire hit counts; any hit makes
the drill fail even if a test catches the refusal. The actual keyed loader is
unreachable. The sole process exception preserves native tamper tests:
the exact /usr/bin/sha256sum check may run only over a scratch-contained
inventory with no absolute, escaping or symlinked file targets. These keyless
verification processes are counted separately; no service/credential/order
command is allowed. A first overstrict staged drill blocked these hash checks
and failed; the evaluator was corrected before the final commit.
Normal test-owned SYN stubs still supply fixture recoveries. The full
drill passed 49 invocations, zero failures/errors/skips; this count includes
inherited Wiring cases discovered again by the sequencing module. An initial
drill retained the obsolete simulated touch and failed ownership checks; the
harness was corrected, not the ownership guard. No service or broker call ran.
The evaluator sets dont_write_bytecode before imports, rejects existing caches
or foreign cached bundle modules, and refuses a receipt destination anywhere
inside the bundle after canonicalization. Its simulated retirement check is
SYN only and cannot substitute for the live retirement/CC approval below.
Private marker creation/stat/unlink use O_NOFOLLOW directory descriptors and
dir_fd; a renamed instance directory cannot redirect cleanup to an operator
STOP. No cleanup operation uses a basename named STOP. A replacement/touch at
the final unlink boundary affects only an operator path that cleanup never
deletes. Operators must never write private machine-marker paths.

The copied source can live anywhere: the recutter derives and validates the
common absolute root embedded in the unit bytes, then relocates WorkingDirectory
and native command paths to the canonical NEW destination. Symlink ancestors
and `..` cannot put output inside the immutable source. Only the NEW root and
unit directory become owner-writable during generation; the finished root and
units are restored to 0500. Frozen/config equality is computed before sealing.
The old prepare_units.py is removed, unit tests use the two-hook contract, and
GO-PROCEDURE/DEPLOYMENT are replaced with these current activation prerequisites.

## Required generation changeover

Keep the co-op issuer paused. After the PR lands, pin its commit, re-cut and
strict-check the full bundle, and run complete SYN wiring. Before any seq3
install or enable, prove **zero active trials**: all old services inactive, the
active state directory empty, and no pending ready/<stage>/GO.sha256.

Then stop and **disable --now all 11 seq2 .path units**, never their running
services or another lane. Use the exact stage list record, scan, pre, pre-skip,
sip, lev1, lev2, lev4, edge2, edge8, iex:

```sh
systemctl --user stop paper-ready-{record,scan,pre,pre-skip,sip,lev1,lev2,lev4,edge2,edge8,iex}-8c95a50d-seq2.path
systemctl --user disable --now paper-ready-{record,scan,pre,pre-skip,sip,lev1,lev2,lev4,edge2,edge8,iex}-8c95a50d-seq2.path
systemctl --user show --property=Id,LoadState,ActiveState,UnitFileState paper-ready-{record,scan,pre,pre-skip,sip,lev1,lev2,lev4,edge2,edge8,iex}-8c95a50d-seq2.path
```

Send the retirement output proving every old path disabled/inactive, the empty
active directory/no GO and inactive services to the CC. **WAIT for the CC's
install approval after it reads that proof.** Only then install/verify exactly
22 seq3 files, materialize the operator lane directory at mode 0700 without
creating any STOP, reload, enable/arm the 11 seq3 paths with zero active trials and
no GO, and report states. The co-op then restarts its issuer on the new binding.
The new issuer refuses when any old path is enabled or active or its inventory
is unavailable; one GO must never reach both generations. Recutter/dry-run tools
perform none of these service mutations. STOP/HOLD/writer state are untouched.

PREDECESSOR_BUNDLE binds the immediate predecessor from the supplied private
manifest digest. This preserves genuine same-state/config receipts without
relabeling or resetting them. A non-flat lane B recovery holds the lane latch
and stops its chain; it no longer creates an operator abort for every lane.
A lane file blocks new admission, but the unchanged running native engine still
observes the host STOP; it does not poll the lane file. A hook ownership refusal
fails closed and systemd skips the later recover command, requiring operator recovery.
Runbook: if stop-mark refuses, keep the issuer paused, preserve operator STOPs
and private markers, report the active trial/config and invoke exact-config
native recovery through the owning runtime's documented paper loader. Require
a genuine durable flat proof and CC-authorized repair before resuming; never
clear a marker by hand or treat the missing hook receipt as completed recovery.
Those remaining lifecycle boundaries are explicit Follow-ups, not qualifications.
The acct-sized experiment follows this fix and must use the same scoped latch.

Follow-ups: apply the same lane-scoped lifecycle to the new general deployment
helpers after #1042 lands; capital-transition/account-sized integration stays
in #1086. No paper acceptance claim follows from the SYN tests.
Also tracked as Follow-ups: pin the 42 unpinned protective guards from the
reader's census (coverage remains incomplete); resolve the stop-mark/recover
chaining boundary above; document recovery after marker-before-receipt crash,
uninstalled seq2 watcher inventory, and remaining lifecycle/durability hygiene.
