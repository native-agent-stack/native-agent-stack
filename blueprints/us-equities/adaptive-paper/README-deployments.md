# Lane B deployments by readiness

The deployment helper is glue around the existing paper engine. A deployment
freezes source, configs, stage order and native units. The co-op issuer supplies
fresh observations and writes single-use per-trial GOs when validity holds.
Exploratory lane B needs no per-series authorization artifact; lane A's frozen
qualification path remains unchanged.

Every published receipt carries paper_lane=B and evidence_class=exploratory.
Artifacts use relative ids and hashes, with no account id or private home path.
Native orders remain stocks, LIMIT/DAY on the paper endpoint, through
credential_run inventory alpaca-paper. The helper adds no order implementation.

## Cut and register a session deployment

Use the canonical managed runtime and a reviewed landed source pin. Keep scratch
and test outputs under /var/tmp. These commands prepare artifacts; they do not
install units, start services or write a GO.

    python paper_deployment.py cut --bundle NEW_DIRECTORY --deployment UNIQUE-ID --source-pin LANDED-COMMIT --order mover-max postmover-max

Git archive is the source mechanism. The pin's own helper builds its configs;
all source/config/unit bytes enter SHA256SUMS, verified with
sha256sum --strict -c SHA256SUMS. Preserve the previous deployment and receipts.
Do not patch a sealed packet in place.

The first mover deployment uses ONE setting at the current code ceiling and
reports achieved exposure. No rung trial is cut until the versioned sizing
preset is registered; cut refuses the old rung templates. Their remaining
coverage is synthetic config validation, not a production request.
Built-in mover stages use the canonical leverage schedule, 1,200-second
trials, 1,500-second unit runtime and 900-second cleanup bounds. Native
load_mover_config validates every generated config. RTH uses
10:00|G20|V1000000|any, any_session, X3 and trial end15:55 ET. POST uses
16:05|G20|V1000000|any and trial end19:55 ET. These are venue/protocol admission
boundaries, not calendar timers. Input observations must be fresh at each trial.
PRE is supported through a native-validated custom stage specification.

The request ceilings are conservative: native trial150 REST/minute and
120 submits/minute, readiness-only Ledger50 REST/minute. Their rolling sum is
at most200 REST; at least30 native slots remain outside the submit ceiling.
These are ceilings, never request or fill targets. Other inventory users must
coordinate with the co-op; an external process cannot be accounted for from
this helper's ledger alone.

Current native mover MAX_SYMBOLS5 and EXIT_HEADROOM_FACTOR10, together with
RiskLimits' per-order ceiling10,000 USD, limit each initial entry to at most
1,000 USD. Five entries therefore total at most5,000 USD before the other
liquidity/share/regime caps. Configuring a leverage rung does not prove it was
attained; use the native achievement receipt. No safety ceiling is widened.

Optional --stage-spec names a JSON mapping from custom stage id to:

    {"engine_kind": "t22", "session_kind": "RTH", "config": "relative-config.json"}

The mapping accompanies --order. Its config is frozen and validated by native
load_config/load_mover_config. T22 requires the reviewed caller's resolved _t22
capability, exact factor bytes and t22_dispatch.validate_availability; older
source refuses t22_dispatch_not_available. Relative factors_file bytes are
copied and hash-bound. No old baseline dispatch fallback is accepted.

## Co-op issuer contract

All commands use the sealed source's paper_deployment.py (or its
deployment_issue_go.py writer entrypoint), --bundle PACKET and
--state EXPLORATORY-ROOT. Stage and trial ids are explicit; trials match the
native1–24 character contract.

1. For mover input, call publish-scan --stage STAGE --input-packet PRODUCER_DIR.
   The producer supplies input.json, scan.json, ranked-100.json, commitment.json.
   Commitment fields are paper_lane, evidence_class, config_sha256,
   scan_sha256, ranked_sha256, input_sha256, code_sha256, observed_at
   (original aware UTC ISO) and session_date.
   Full ranked symbols contain exact native rows; scan symbols equal the first
   at most5 rows. Native load_scan checks rule/date/freshness/ranks. The helper
   retains content-addressed input bytes and publishes SCAN-READY.json only
   after all hashes agree. Publishing a scan never writes GO.
2. Invoke observe --stage STAGE --trial UNIQUE-TRIAL through the id-based
   credential runner. This runtime-only worker performs native GET preflight,
   acquires the native account writer mutex and repeats the observation.
   It never submits/cancels orders. All requests use the native readiness Ledger.
   It publishes deployments/ID/instances/TRIAL/readiness.json with the lane
   labels, bundle/config/trial/session bindings, observation clock, flat arrays,
   request count and native writer/preflight flags. No account identifier leaves
   the observation. Native startup still rechecks full traded assets and quotes.
3. Call deployment_issue_go.py check --stage STAGE --trial TRIAL
   [--previous PREVIOUS-TRIAL], then issue with the same arguments immediately.
   Account readiness must be no more than30 seconds old, never future. The
   first stage requires a fresh proof too. Every later stage binds the exact
   previous trial's native recovery output and handoff; it cannot use an old
   pass's completed stage file. Its request window must have drained60 seconds.
   The issuer may wait, then acquire a new fresh account proof.
4. The writer validates manifest/config/native ceilings, current session and
   full RuntimeMaxSec+cleanup headroom, fresh inputs, lane A unit/process
   exclusion, no STOP/HOLD/active experiment and no pending/used token.
   It fsyncs payload and audit before publishing GO.sha256 last.
   Only the co-op issuer invokes issue in production; tests use SYN roots.
5. The native path unit consumes the token once, rechecks all bindings and
   calls paper through credential_run. The service's bounded stop hook performs
   exact-config recover. Its own validation receipt is durable before an
   unchanged service-owned STOP clears. Foreign STOP persists. Failed recovery
   or nonflat proof retains the active binding and stops continuation.

GO schema: schema_version, paper_lane, evidence_class, deployment, stage,
trial, bundle_sha256, config_sha256, session_kind, session_date, issued_at,
readiness_sha256, previous_trial, previous_handoff_sha256, scan_binding,
order_sha256. The300-second GO TTL is separate from the30-second account proof
and native quote age3 seconds. SCAN-READY binds schema_version, labels,
deployment/stage/session/config, engine_scan_sha256, commitment_sha256,
ranked_sha256, input_sha256 and original observed_at.

## State and installation

Use the standard account's exploratory root. Native state remains the SAME
exploratory/account-state across deployments. Effective config namespaces are
registered in that native account journal by the reviewed rotation API; never
create a fresh DB to evade cash/fee/request history. Before that API lands, a
same-config trial can run, but changed-config rotation is natively refused.
Recover always uses the engine/config that owned the active trial.

With the co-op issuer stopped and all old trials recovered flat, disarm old
deployment paths, verify no pending GO or active binding, install only the
new sealed unit files, native-verify/reload, then enable and arm only the new
paths. Do not run old and new watchers on the same slot. Retain journals,
receipts, used tokens and writer locks. The co-op restarts its issuer on the
new bundle. No calendar timer, manual GO, manual STOP or manual HOLD change.

Counterbalanced order is a manifest input. A subsequent deployment has a new id,
seal and per-trial ids but retains the native account journal. One account has
one writer; sequential recovery and flat readiness remain mandatory.

## Sources and measured boundary

- native-agent-stack d8f7e2051b61bde6361a85b64f41413798015353:
  runner.py load_config/validate_preflight/main; mover.py load_mover_config,
  load_scan/build_plan; safety.py Ledger/request_budget/account_lock_fingerprint;
  transport.py preflight and its paper-only guarded SDK client. This helper
  composes those mechanisms and does not modify their risk/order implementation.
- alpacahq/alpaca-py cc4cb3b7ba50ae250e621983c2779047fb16bb28:
  alpaca/trading/client.py get_orders107, get_all_positions235, get_account465;
  the native transport remains the adapter to those official APIs.
- systemd/systemd e846bbad04d87e58ba9c3e30d8a1087141691715:
  man/systemd.path.xml PathExists; man/systemd.service.xml RuntimeMaxSec and
  ExecStopPost; man/systemd.resource-control.xml CPUWeight.

The regression seam is tests.test_paper_deployment: SYN filesystem roots,
external native broker/dispatch seam intercepted, actual native config/scan
validators and Ledger exercised. No credential or broker acceptance is claimed.
Focused tests use the idle CPU scope during the paper window; broader suites
also require the co-op suite queue. Source/config validation is distinct from
real entitlement, fresh factor acquisition, fills, slippage and achieved leverage.
