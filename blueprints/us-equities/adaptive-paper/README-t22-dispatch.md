# Exploratory T22 mover dispatch

`runner.py paper` accepts an opt-in `t22` config block for one equity from
the exploratory ranked mover cohort. It dispatches the existing
`GapPremarketStrategy` or `MomentumBreakoutStrategy` through the existing
native node and account writer. Lane B only: `paper_lane: "B"` and
`evidence_class: "exploratory"` are required. Absence retains baseline dispatch.

First deployment target is the ranked mover `gap_premarket` family with its
registered `aggressive-v1` hypothesis, using the code-managed limit variant.
The caller does not reconstruct factors, fetch history or manufacture a signal.
Unsealed/unfitted forward data may be supplied with the exploratory label;
development release/cutoff rules and qualification remain separate.

## Frozen input

Add this block to the existing paper config, with exactly one symbol and
`feed: "sip"`. IEX is refused for T22: it supplies no ongoing native halt-status
channel in the qualified transport. SIP entitlement remains a preflight check.

```json
{
  "t22": {
    "family": "gap_premarket",
    "preset": "aggressive-v1",
    "instance_id": "mover_trial_one",
    "cohort_sha256": "<producer cohort SHA256>",
    "factors_file": "factors.json",
    "factors_sha256": "<SHA256 of exact factors.json bytes>",
    "source_file": "source.json",
    "producer_receipt": "producer.json"
  }
}
```

`factors_file` is resolved relative to the config file. Its producer-owned
`FactorSnapshot` JSON contains instrument/cohort/source hashes, decimal-string
values, `ts_event`, `ts_init` (availability), `valid_until_ns`, cohort membership,
explicit halt state, and `evidence_class: "exploratory"`. Required price inputs
are `atr_price` and `entry_trigger`, both positive. Gap inputs are
`overnight_gap`, `premarket_return`, `premarket_activity`; momentum inputs are
`momentum_20`, `range_breakout`, `tight_range_state`. Source hashes and clocks
are recorded facts, not synthesized from a fixture. The ranked list/cohort and
factor mapping are producer inputs; the caller does not select a fixed universe.

All three files use relative JSON paths beneath the config directory, with
symlink escapes refused. The loader binds exact source bytes to
`snapshot.source_sha256`, and a producer receipt binds source, packet and a code
hash in `t22-producers.json`. It verifies that code's retained bytes and import
origin, then reconstructs the packet through that deterministic producer.
The initial `t22-source-normalizer-v1` is reviewed with this caller; it normalizes
a timestamped factor-source export through the existing FactorSnapshot contract.
It does not compute a factor from market observations, select parameters or
prove the source export's empirical quality. A market-data factor producer and
its reviewed code commitment remain inputs to the first real deployment.
The north star in `AGENTS.md` requires deterministic code in numeric/risk/order
state; neither a model-generated number nor a source-hash assertion alone is
an accepted factor-production mechanism.

For the numeric factors, declared availability/expiry interval, membership and
source halt flag, the source export is **operator-attested, provenance unverified**.
The producer guard verifies retained bytes and deterministic normalization;
it does not prove these declarations were computed from market data.

The exact packet hash is checked during config loading. The native caller
refuses future or expired packets and packets not covering the full duration
plus cleanup before building a node and checks again at native delivery.
It publishes the snapshot through upstream CustomData, after
the strategy has started and subscribed. Family thresholds and sizing use
the existing registered T22 preset and frozen account RiskLimits. Both
`conservative-v1` and `aggressive-v1` are admitted; the conservative preset's
existing 300-second confirmation/RTH rule still applies. Quantity is bounded
by both StrategySpec's 100-share ceiling and the existing account governor.

This initial caller admits 1x only, no rotation, overnight exposure or baseline
exit-preset selector. It selects the existing regular-close/after-hours exit
policy according to the session config and always supplies a bounded stage
deadline. `exit_quote_max_age_seconds` must remain at most 10 seconds under
T15 Addendum 01; StrategySpec's entry/exit quote freshness stays at most 3 seconds.
The same bounded cleanup/recovery path runs after residuals or faults.
Preflight checks the producer's current availability/expiry before reporting
ready. Recovery validates the frozen config and limits without reading the
producer packet, source file or receipt; missing/corrupted bytes cannot prevent reaching the
ledger-driven recovery path. Its packet-less dispatch marker refuses paper
execution, so it cannot fall back to baseline behavior.

## Execution and evidence

Use the deployment helpers' `t22`/adaptive engine stage with the existing
`runner.py preflight`, `paper`, and `recover` commands. zoli's sealed bundle and
the co-op issuer provide GO and stage validity; this module writes neither GO
nor STOP. The same account root, ledger, fee window and cash baseline persist;
reve's exploratory config namespace registration/receipt boundary is a deployment
dependency. No lane A trials, state or qualification evidence are used.

Helpers must verify `runner.T22_PAPER_DISPATCH_VERSION == "t22-exploratory-v1"`
and the resolved config's `_t22` dispatch before GO: old runner versions ignore
an unknown `t22` block. `t22_dispatch.validate_availability(dispatch, now_ns)`
checks the producer's declared interval. This caller does not invent a numeric
factor-age ceiling; its expiry provenance belongs to the real producer packet.

Durable Ledger, Controller, endpoint gate, preflight, one account writer lock,
REST/submit budgets, reconciliation and STOP remain in the existing runner.
T22 faults freeze the ledger and call the native session's failure boundary,
ending the run promptly so existing recovery can flatten exposure. Routine notices use a separate
labelled event sink. Post-cutoff fills refresh account risk synchronously from
the booked ledger before ending admissions. Native halt/resume comes from
the normalized transport status, with no fabricated TRADING event; metadata,
future, older and equal-timestamp resumes cannot clear a cached halt. Missing/expired
producer halt state suppresses family orders.
The account controller's independent halt predicate is also supplied to the
family gate. A positive startup seed delivered after its bounded wait can veto
an exit/reprice; only the controller's authoritative expiry/resume changes that
state. A frozen held family still requires the established recovery handoff;
resumption alone does not clear its durable safety freeze.
Entry admission pauses on not-ready transport, seed/reconciliation waits,
STOP or a stage deadline. It does not disable the family's owned exits. Fresh
post-cutoff account marks omit stale and excessively future quotes.

At the existing final SDK HTTP boundary, an optional policy callback executes
on the owner loop and binds the selected packet/instance and current halt state.
The SDK worker then rechecks the returned immutable nanosecond window and fresh
quote/stream state immediately before each HTTP attempt. This covers operation,
budget and worker delays. Buy eligibility is also bounded by the stage's entry
deadline. No native actor is invoked from the SDK thread. Broker order payloads
retain their existing schema; the extra callback is absent for baseline runs.

An integrity gap durably freezes the T22 ledger and retains needs_attention even
if cleanup is flat. Native instrument metadata admits four decimal places for
sub-dollar movers; the existing family price rule retains the cent grid at $1
and above.

The run receipt carries lane B/exploratory, family/preset/instance and cohort/
packet hashes. It never serializes a factor-file path or broker account ID.
The adapter uses a fixed internal paper alias for this caller. Generic CLI
refusal/preflight/recovery labels and exploratory path guards are supplied by
reve's companion change and must be included in the deployment.

Broker-paper acceptance: **NOT_RUN**. Local tests use synthetic factor/port
fixtures against the real native runtime and account governor. They establish
engineering dispatch, not market performance, factor qualification or empirical
preset fits. First paper execution still needs a real factor/cohort packet,
reviewed landing, the deployment helper and issuer GO.

## Primary mechanisms and demonstrated glue gap

- Native engine: `nautechsystems/nautilus_trader`
  `1b0a49d2792a9432a3aca3fcb617ce7a630d905e` (2.0.0rc5),
  `crates/trading/src/python/strategy.rs:1704` exposes `is_running()`;
  `crates/common/src/python/actor.rs:1453` publishes CustomData;
  `crates/common/src/python/actor.rs:3543` tests Python on_data delivery.
- Status subscription/data output: same pin,
  `crates/live/src/python/client/mod.rs:1424` invokes the client's
  `_subscribe_instrument_status`, and `:1773` admits InstrumentStatus.
  The existing local AlpacaDataClient lacked that subscription, reproduced by
  the native fixture's NotImplementedError before this glue was added.
  The implementation consumes the existing transport's normalized status,
  preserving the strategy's independent factor/native halt fences.
- Existing engine source: native-agent-stack
  `d8f7e2051b61bde6361a85b64f41413798015353`, `runner.py:357`, `:660`,
  `:827`, `:2583`; `native_adapter.py:967`; `strategies/families.py:48`,
  `:1159`, `:1194`; `strategies/presets.py:55`. No strategy or adapter fork.
- Final HTTP mechanism: `alpacahq/alpaca-py` 0.44.0,
  `cc4cb3b7ba50ae250e621983c2779047fb16bb28`,
  `alpaca/common/rest.py:176,195` delegates each attempt to its session.
  The existing local `transport.py:GuardedSession.request` performs its budget
  and before_send checks under the HTTP lock before delegating that request;
  the controller callback uses its existing owner-loop RPC path.

## Review regression evidence

The native four-decimal instrument contract is NautilusTrader 2.0.0rc5 at
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`,
`crates/model/src/instruments/equity.rs:115` (price precision equals increment
precision) and `:121` (positive increment). Selected metadata is precision 4 /
increment 0.0001; the fixture checks actual native penny limits against bid/ask.
This cites engine representability; market tick-rule qualification is separate.

At reviewed head 6ba2b620, fail-first witnesses reproduced delayed seeded-halt
SELL, entry sent across packet expiry, IEX admission without a halt channel,
clean integrity-gap status, blocked recovery on missing/corrupt packet, ready
preflight for expired/future packets, and non-marketable penny limits. The
corrective native test module covers those boundaries plus expiry after risk/
budget, an eligibility window expiring as the owner reply returns, and an
explicit resume preserving the frozen-family recovery boundary. The existing
source-manifest scope test also failed before its out-of-scope key was removed;
contracts and family source bindings use the broader evidence registry.
Deletion witnesses also cover source/receipt/code binding, full-stage coverage,
not-ready admission with an owned exit, prompt fault recovery, external-cwd
launch, individual loader refusals, native status delivery and bounded lifecycle
cleanup. These are guard-deletion fixtures, not broker-paper acceptance.

## Follow-ups

- Supply/record the real ranked mover cohort and factor producer mapping,
  then retain the first bounded lane B broker-paper receipt and flat recovery.
- Complete deployment integration with zoli's helper and reve's generic
  exploratory namespace/label/path boundary; test the combined landed heads.
- Add other T22 families as their actual forward inputs exist; leverage,
  multi-symbol allocation, refits and overnight exits remain separate changes.
- Complete T15's fresh pricing on every latched exit submit/re-send before
  releasing the interim preset exit-age constraint.
- Halt while holding ends the native run promptly. Shared recovery currently
  has no halt veto and can attempt a flatten during a halt. Resolve that shared
  recovery policy before claiming halt-safe paper recovery; the family/final
  send veto does not qualify the recovery boundary.
