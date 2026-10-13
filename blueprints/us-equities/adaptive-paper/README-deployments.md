# Lane B deployments by readiness

This helper composes the existing native paper engine. It adds frozen deployment
metadata, explicit pass order, fresh account readiness and single-use dispatch;
it implements no trading decision, order pricing or risk-limit engine. The co-op
is the operational GO writer. Lane A's frozen code, journals and qualification
records remain separate. Every public receipt is labelled paper_lane=B and
evidence_class=exploratory, with relative artifact ids and hashes.

## Scope and current limitations

This PR admits RTH and POST kinds only. PRE and intentional overnight require
separately reviewed lifecycle work. At the current native producer pin, TIMES
ends at10:00: the proposed16:05 POST mover recipe is REFUSED at build and verify,
not presented as runnable. A reviewed producer capability and producer-to-helper
integration receipt must precede enabling that rule. No earlier data is
restamped. A supported POST kind alone does not establish a supported mover scan.

The first mover recipe is ONE setting at the code's existing ceiling:
mover-max, canonical max-leverage4, gross40,000 USD, order10,000 USD,
entry1,000 USD, five symbols, loss/drawdown100 USD, 100shares/notional.
Every mover config, including custom aliases, must match this setting until
a versioned sizing preset is registered. Native five-slot/exit-headroom10/order
ceiling limits initial entries to at most5,000 USD before liquidity, share and
regime restrictions. Report achieved exposure; no rung comparison is cut.

RTH's rule is10:00|G20|V1000000|any, any_session, X3, end15:55 ET.
The secondary16:05|G20|V1000000|any/end19:55 proposal is documented as unsupported
by this producer, not selected by the historical study or this helper.
Trials last1,200s, units bound runtime1,500s and cleanup900s; admission reserves
runtime plus TWO stop-phase bounds. These are venue/protocol windows, no timers.

## Cut and state

Use the reviewed landed source pin and canonical managed runtime:

    python paper_deployment.py cut --bundle NEW_DIRECTORY --deployment UNIQUE-ID --source-pin LANDED-COMMIT --order mover-max

Git archive preserves native source. The selected pin's helper validates configs.
Every extracted file, including nested SHA256SUMS, enters the root manifest;
ONLY root/SHA256SUMS is excluded from its own preimage. Source/config/unit files
and the root manifest become read-only. Native strict checks and file-inventory
checks detect edits and additional files. Installed digest pinning is a remaining
pre-install hardening item; do not claim this same-user store authenticates an
issuer against a malicious same-user process.

Only the approved canonical account exploratory root is admitted. Existing
symlinks in the root or descendants are refused before reads/writes; bundle
destinations inside the account or qualification roots are refused. New private
directories use0700 and JSON/capability files0600. Unique atomic temporary files
avoid an interrupted fixed-name write wedging a slot. Private account/capability
files NEVER enter a public evidence packet.

Native state remains the same exploratory/account-state journal across
deployments. Raw config_file_sha256 freezes file bytes; native config_sha256
uses exploration.config_digest(resolved,raw_bytes,limits=limits) when that
reviewed API is present. Old native source uses raw hashes. Native config
namespace and recovery bind the effective digest, never a raw/effective alias.
Changing a finished native config requires the reviewed registration capability
and fresh flat/account/cash/fee checks; before it lands changed-config orders
are refused. Never create another DB to bypass continuity.

A custom stage specification maps ids to engine_kind adaptive|mover|t22,
session_kind RTH|POST and relative config file. T22 requires native resolved
_t22, exact factor bytes and declared availability; an old source cannot
silently fall back to baseline. No live-dir is passed. Multi-config deployments
remain unusable at this base until the native rotation API lands.
Factor availability gates only the selected T22 stage's issue/start, never
bundle integrity or recovery. Expired inputs cannot disable cleanup or another
stage. The caller's config-only require_t22_packet=False seam is used for
integrity/recovery when available; admission uses full provenance loading and
validate_stage for duration plus cleanup coverage. Custom T22 configs retain
their own native share quantity. The first T22 cut still requires the reviewed
landed caller, producer/source/receipt closure and a native composition witness;
this branch does not deploy an unpublished caller or producer recipe.

## Account readiness, pass order and dispatch

The co-op invokes the sealed helper with --bundle and --state:
publish-scan; credential_run alpaca-paper observe; check; then issue.
Stage/trial ids are explicit, native trial ids at most24 characters.
--pass-id identifies the pass; when omitted a first trial's unique id is used.
One durable sequence cursor admits only the next stage and latest predecessor.
Issuing records a pending trial under the writer mutex; recovery advances only
after its genuine flat handoff. An old but valid predecessor cannot authorize a
new pass or another successor. Refused/unknown active state is never retried
into a fabricated completion.

Observe makes native GET preflight, acquires the account writer lock and repeats
it. The fingerprint and a random salt remain in0600 private state; only the
salt-keyed account commitment appears in public readiness/GO bindings.
Native child preflight compares the actual account to that private binding,
including recovery, before engine dispatch. Account A's readiness cannot admit
account B, even if B is flat and has an occupied namespace.
Both lookup sites are bound: transport.preflight and runner.preflight, the
name imported by the adaptive/T22 caller. The real runner.main regression
exercises the injected child for paper and recover before account-lock entry,
rather than only calling the account check in isolation.
Readiness is at most30s old, never future. Native startup rechecks positions,
orders, assets, entitlements and quote freshness through its ordinary path.

The native child requires a parent-created, single-use capability tied to the
consumed GO, active trial, account commitment, stage, config, session and expiry.
The random capability crosses the credential runner through inherited stdin,
never argv or environment. The public native spelling without this capability
cannot reach the credential loader or engine. Native paper/recover/flat output
remains private and masked until its labelled safe receipt is written.

Both issue and start check STOP, HOLD, active state, lane A inventory/processes,
config/bundle, session headroom, account and scan bindings, the cursor and replay.
A refused token is retired, retained and not silently reissued. Unit start limits
bound repeated supervisor activation, including validation failure before run.
An unactivated, unconsumed trial also retires its pending cursor relation and
records its refused id; the stage never advances and no flat proof is invented.
A new unique trial requires fresh full readiness; an issued id cannot be reused.
Consumed/active or otherwise unknown state retains its recovery obligation.
STOP is the native safety.DEFAULT_STOP, never an arbitrary state.parent latch.
Only the service's own unchanged STOP may clear AFTER its durable native flat
validation; foreign or changed STOP remains. Recovery retains hook ownership
even for a foreign leaf symlink: it is never followed for content or cleared,
but it does not prevent exact-config sell-only recovery.
on retries and waits boundedly for the writer lock. Unknown/missing output
refuses; only native no_owned_trial_to_recover invokes the GET-only flat proof.
Mover recover argv has no --trial; native engine exceptions produce fixed
failure receipts. Completion timestamps are captured AFTER recovery, and the
60s request drain includes the last account trial across passes/deployments.
Every stage checks that account-wide window, including stages mid-pass.
Unexpected engine exceptions report broker observation not_established, never
an invented zero-order count. Only a proven no-owned-trial refusal claims zero.

The account's native Ledger remains authoritative for orders/budgets. Readiness
uses its own50 REST/min Ledger, native trial150 REST/min and120 submit/min caps;
sum<=200 is conservative arithmetic, not an empirical throughput claim.
Other processes/inventory users require coordination. The helper cannot prove
their request history from its journal alone.

## Scan contract and clocks

Producer files: input.json, scan.json, ranked-100.json, commitment.json.
Commitment carries labels, raw config_file_sha256 (file-compatible config_sha256
is accepted), effective_config_sha256, scan_sha256, ranked_sha256,
input_sha256, code_sha256, observed_at=data cutoff,
source_observed_at=acquisition and session_date. Original scan_time is preserved.
input.source declares intraday mode, signal_cutoff_utc and observed_at acquisition.
An omitted source uses the native fixed rule cutoff (09:30 maps09:28).
Cutoff<=acquisition<=now and cutoff<=scan_time; scan_time need not precede
acquisition. Both data and generation must be fresh. Morning protocol issuance
is outside this RTH/POST helper's scope.

Each artifact is read ONCE into bounded bytes, then hashed, parsed and retained.
Mover stages consume the exact first5 rows of the issued top100 (or all rows
when fewer than5 were issued), through native load_scan with real freshness.
A shorter committed prefix is refused rather than silently dropping ranked
picks. The merged producer is uet64f52815, research/ranking/exploratory/scan.py;
its original scan/rank bytes and hashes remain bound before dispatch.
SCAN-READY publishes only after native schema/rule/rank/date/freshness and
commitment checks. Every admission independently checks the RETAINED commitment
against the retained bytes; startup copies the already-verified bytes, never
an unchecked path reread. Publishing a scan writes no GO.
Source closure/code provenance remains distinct from data freshness.
Until the producer's F2 publication recheck is reviewed and deployed, the
consumer enforces the CC interim issue margin: started_at must be at least60s
before issuance expiry, and the ORIGINAL issue-directory st_mtime_ns must be
strictly before that expiry. For this intraday consumer expiry is the earlier
of scan_time+300s and source-data-cutoff+300s, per uet64f52815. The already
observed source cutoff is not an issuance deadline. The physical directory
identity/mtime is checked for change during reads, then retained in a timing
proof bound to commitment bytes and SCAN-READY/GO; copied directory metadata
never substitutes for that observation. No mtime lower bound or clock tolerance
is invented. Directorymtime does not prove final parent-fsync completion;
native current-data freshness remains mandatory at publication and admission.

## Installation and follow-ups

No installation or operation from an unreviewed branch. Stop the issuer, recover
the old writer flat, disarm old paths, verify no pending token/active binding,
install the exact sealed units, native-verify/reload and arm only the new paths.
Retain every old journal, receipt, token and lock. The co-op restarts its issuer
on the new deployment. No manual GO, STOP or HOLD action.

Remaining P3 triggers are recorded in the PR Follow-ups: installed digest pin and
portable source/evidence captures; authenticated issuer custody if required;
additional producer capabilities and live-view portability; migration of legacy
unmarked journals; crash projection/retry integration with the reviewed rotation
API; empirical broker entitlement, rate, slippage and attained exposure evidence.
No native engine or safety ceiling is changed by this helper.

## Sources and verification

- Native engine atd8f7e2051b61bde6361a85b64f41413798015353:
  runner.load_config/validate_preflight/main, mover.load_mover_config/load_scan,
  safety.Ledger/account_lock_fingerprint, transport.preflight.
- alpaca-py cc4cb3b7ba50ae250e621983c2779047fb16bb28:
  alpaca/trading/client.py get_orders107/get_all_positions235/get_account465.
- systemd e846bbad04d87e58ba9c3e30d8a1087141691715:
  systemd.path.xml PathExists, systemd.service.xml ExecStopPost/RuntimeMaxSec,
  systemd.unit.xml:1214-1220 StartLimitIntervalSec/StartLimitBurst,
  systemd.resource-control.xml CPUWeight; unit commands reject unsupported path
  characters rather than silently misparse whitespace or percent specifiers.

Named regression modules use SYN roots, external native broker/dispatch seams
intercepted, and actual native config/scan/parser/Ledger validation. The guard
census mutates only in-memory copies and records each killed/surviving guard and
the exact negative test, not a blanket coverage claim. Managed SDK runtime tests
and archive-environment dependency skips are separate evidence. No new broker
acceptance or strategy-performance claim is made.
