# Paper deployment review corrections

Class: source_review plus the separately classified SYN/local integration
checks. No broker acceptance or production operation is established.
Parent reviewed head: de4e92eb59f515457d7723c8f76d6b0946382f44.

| Correction | Primary implementation/reference | Regression |
| --- | --- | --- |
| Account binding at actual engine lookup | NAS d8f7e205 runner.py:53-54,2357 imports/calls preflight by name; mover_runner.py:672-673,901 imports at call time | Real runner.main and mover_runner.main through native_child, consumed SYN GO/capability, A-bound/B-observed, paper/recover; no entry into B's writer |
| Private-output publication | Repository published-digest rule; portable evidence consists of inspectable published bytes | test_paper_deployment_evidence rejects digest fields committing to unpublished outputs; historical raw-log/output digests and prefixes removed |
| Latest account completion at every issue/start | NAS recovery.recover under account lock and helper account-last durable completion | A-first→B-complete→A-second refuses at issue/start until drain; start with previously issued GO also refuses |
| Refused unactivated pending trial | Existing helper sequence/active/consumed-GO custody | Retire pending only without active/used marker; stage does not advance, no flat completion, issued id cannot be reused |
| Exception order uncertainty | NAS d8f7e205 runner.py:2654-2664 native failed/not_established handling | Unexpected exception has failed/not_established and no invented zero submissions |
| Recovery timer census | Native systemctl service/timer inventories, existing paper-recover-a2 timer family | Pending recovery timer refused; unavailable inventories remain fail-closed |
| Native lineage metadata path | Landed exploration.active_trial_metadata read-only SQLite authority; safety.Ledger.register_exploratory_config | trial.json leaf symlink refused before either branch; actual landed SQL journal readiness leaves DB unchanged |
| Raw/effective config domains | Landed exploration.config_digest(config,raw,limits=limits); native mover.check | Fixture commits distinct frozen-file/effective hashes on the exact live merge; no alias |
| Legacy caller seam | Native capability absent before rotation landing | Test explicitly selects legacy Ledger capability and separately runs landed SQL composition |
| Exact top-five and interim issue timing | UET64f52815 research/ranking/exploratory/scan.py:247-313,320-391 | Shorter committed prefix refused; start margin and original directorymtime checked before SCAN-READY and retained-byte admission |
| Foreign STOP symlink | Native global latch plus exact-config sell-only recovery | Entry refused, symlink/target never cleared; genuine SYN recovery can finish |

The UET issuer writes commitment last, syncs the staging directory, verifies,
renames and syncs its parent. Its directorymtime is last child-entry metadata,
not a completion time. Intraday validity lasts to the earlier of generation or
data cutoff plus300s. Interim start<=expiry-60s and mtime<expiry do not waive
native current freshness or prove post-fsync validity. Producer F2 remains a
separate reviewed/deployed input; no old data is restamped.

Other retained parent mechanisms and vendor references:

- Python standard library at CPython3.12: pathlib.Path.is_symlink/absolute,
  os.open O_NOFOLLOW/O_EXCL, os.fstat/lstat, os.replace, os.fsync and flock via
  fcntl. Official references: https://docs.python.org/3.12/library/os.html,
  https://docs.python.org/3.12/library/fcntl.html,
  https://docs.python.org/3.12/library/pathlib.html. Unique private atomic JSON
  writes and writer inode checks use those interfaces; no custom filesystem API.
- Account commitment/capability use Python hmac/hashlib/secrets:
  https://docs.python.org/3.12/library/hmac.html,
  https://docs.python.org/3.12/library/hashlib.html,
  https://docs.python.org/3.12/library/secrets.html. Secrets protect authorization;
  they do not choose trading numbers. Credential runner forwards stdin at its
  supported Popen boundary; no credential pointer/value is carried in argv.
- systemd e846bbad04d87e58ba9c3e30d8a1087141691715,
  man/systemd.unit.xml:1214-1220 configures start-rate limits;
  man/systemd.service.xml ExecStopPost/RuntimeMaxSec and systemd.path.xml
  PathExists retain native lifecycle/readiness semantics.
- Alpaca SDK cc4cb3b7ba50ae250e621983c2779047fb16bb28,
  alpaca/trading/client.py:get_account/get_all_positions/get_orders provides
  the official read-only preflight; native order/risk/recovery engines remain
  unchanged. Unsupported POST mover rule consults the pinned native
  blueprints/us-equities/mover-early-entry/rules.py TIMES/parser.
- T22 static load uses the caller's require_t22_packet=False seam when exposed;
  full selected-stage provenance/availability remains admission-only. No T22
  deployment exists here; its sizing/provenance closure requires a reviewed
  landed composition before first cut.

Follow-ups retained for the actual deployment before arming:

1. Interrupted GO.sha256.tmp publication and each recovery persistence boundary
   need a supported repair/abort protocol without resetting the account journal.
   This correction repairs refusal-before-active custody only; crash repair is
   not claimed complete.
2. Installed units must bind the trusted bundle manifest digest before the first
   installation; same-user read-only permissions are not issuer authentication.
3. T22 sizing, provenance and source/caller closure require first-cut witnesses;
   no synthetic factors become production inputs.
4. OSV ignore expiration belongs to the existing security-policy owner; no
   allowances/scanner settings change in this PR and inherited failures remain
   reported separately.
5. Historical census counts in the artifact are author-reported at the published
   historical head; private timed outputs are not publicly committed. Fresh
   measurements must use the checked-in harness at the desired pin, and wiring
   regressions remain stronger evidence than a blanket deletion count.
6. Additional original-review changes (inventory expansion, unit bounds/env,
   custom quantities, config domains, SQL lineage and independent producer
   clocks) are explicit in the README/body; they are not silently attributed
   solely to the account-binding finding.

The clean merge at current-main107bcca66133db379e9bf31560ba617519c59bec is
tested with the actual native engine/exploration bytes. That SYN composition
does not arm a unit, observe a real account, issue GO or change STOP/HOLD.
