# Lane B stage latch, sequencing v3

The seq2 launcher and eight unit touch hooks wrote the operator's host-wide
STOP at every stage end. A flat recover then removed it. This interrupted other
lanes. Sequencing v3 owns only `alpaca-paper/lane-b/STOP`; the host-wide file
remains a read-only operator abort.

The deterministic recutter verifies the original strict bundle inventory and
the exact retained launcher/issuer source bytes, copies the frozen runtime and
eight CONFIGs unchanged, and changes only:

- launch.py: both latches block admission, stop-mark creates only the lane file,
  repeated hooks retain original ownership, and exact-CONFIG flat recovery
  clears only a file with the same trial, inode/device, modification/change
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
`safety.DEFAULT_STOP`). Systemd v260 at
54b24a3855de37e5e19235c44acd113eb6ce6830, `man/systemd.service.xml:585-606`,
remains the supported path/service and ExecStopPost lifecycle; no
calendar timer or new scheduler is introduced.

The old launcher and issuer are retained as non-executable `.txt` test fixtures
so their pinned byte hashes and failing behavior are inspectable. The test
harness redirects every state/latch/config root under `/var/tmp`, stubs native
recover with labelled SYN proof, and tripwires keyed execution and credential
pointer access. The first seven tests failed against the old launcher (three
failures, one error); eleven now pass, including dual-latch issuer refusal,
unit touch removal, preservation of a human symlink target and re-cutting a
predecessor with a read-only units directory. Round-1 regressions add copied-root
relocation, canonical containment, sealed ROOT permissions, bytecode/receipt
isolation, legacy watcher refusal, computed comparison and lane-directory race
coverage. Only NEW root/unit directories become writable for generation;
their permissions are restored read-only before the bundle is returned.

```sh
systemd-run --user --scope -p CPUWeight=idle --quiet -- env TMPDIR=/var/tmp \
  python3 -B -m unittest tests.test_lane_b_stage_latch -v
```

Re-cut into a NEW directory with `recut.py --source SEALED_SEQ2 --output NEW_SEQ3
--source-commit LANDED_FIX_COMMIT`. The strict manifest covers runtime inputs;
the GO-BINDING-REQUEST is a separate hashed envelope because it binds that
manifest's digest. The record retains predecessor state and config bindings.
No service is installed or started by the recutter; it writes no GO, STOP or
HOLD and makes no broker/credential call.

`dry_run.py --bundle NEW_SEQ3 --receipt SYN_RECEIPT` replays all five retained
wiring modules without changing their files. It adapts only SYN host/lane roots,
removes finish()'s simulation of the deleted shell touch hook, and checks the
new seq3 names/two hooks. Human-stop test actions remain intact. The real
credential-pointer function is replaced before the tests execute. The full
drill passed 49 invocations, zero failures/errors/skips; this count includes
inherited Wiring cases discovered again by the sequencing module. An initial
drill retained the obsolete simulated touch and failed ownership checks; the
harness was corrected, not the ownership guard. No service or broker call ran.
The evaluator sets dont_write_bytecode before imports, rejects existing caches
or foreign cached bundle modules, and refuses a receipt destination anywhere
inside the bundle after canonicalization. Its simulated retirement check is
SYN only and cannot substitute for the live retirement/CC approval below.
Lane latch creation/stat/unlink use O_NOFOLLOW directory descriptors and dir_fd;
a renamed lane directory cannot redirect a stage hook to a different STOP.

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
22 seq3 files, reload, enable/arm the 11 seq3 paths with zero active trials and
no GO, and report states. The co-op then restarts its issuer on the new binding.
The new issuer refuses when any old path is enabled or active or its inventory
is unavailable; one GO must never reach both generations. Recutter/dry-run tools
perform none of these service mutations. STOP/HOLD/writer state are untouched.

PREDECESSOR_BUNDLE now binds d268be92 (actual seq2), replacing c738f143 as the
immediate predecessor. This preserves genuine same-state/config receipts without
relabeling or resetting them. A non-flat lane B recovery holds the lane latch
and stops its chain; it no longer creates an operator abort for every lane.
A lane file blocks new admission, but the unchanged running native engine still
observes the host STOP; it does not poll the lane file. A hook ownership refusal
fails closed and may skip the later recover command, requiring operator recovery.
Those remaining lifecycle boundaries are explicit Follow-ups, not qualifications.
The acct-sized experiment follows this fix and must use the same scoped latch.

Follow-ups: apply the same lane-scoped lifecycle to the new general deployment
helpers after #1042 lands; capital-transition/account-sized integration stays
in #1086. No paper acceptance claim follows from the SYN tests.
