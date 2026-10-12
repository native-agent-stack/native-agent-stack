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

Add this block to the existing paper config, with exactly one symbol:

```json
{
  "t22": {
    "family": "gap_premarket",
    "preset": "aggressive-v1",
    "instance_id": "mover_trial_one",
    "cohort_sha256": "<producer cohort SHA256>",
    "factors_file": "factors.json",
    "factors_sha256": "<SHA256 of exact factors.json bytes>"
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

The exact packet hash is checked during config loading. The native caller
refuses future or expired packets before building a node and checks again at
native delivery. It publishes the snapshot through upstream CustomData, after
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
T22 faults freeze the ledger and end admissions; routine notices use a separate
labelled event sink. Post-cutoff fills refresh account risk synchronously from
the booked ledger before ending admissions. Native halt/resume comes from
the normalized transport status, with no fabricated TRADING event; metadata,
future resumes and older resumes cannot clear a cached halt. Missing/expired
producer halt state suppresses family orders.

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

## Follow-ups

- Supply/record the real ranked mover cohort and factor producer mapping,
  then retain the first bounded lane B broker-paper receipt and flat recovery.
- Complete deployment integration with zoli's helper and reve's generic
  exploratory namespace/label/path boundary; test the combined landed heads.
- Add other T22 families as their actual forward inputs exist; leverage,
  multi-symbol allocation, refits and overnight exits remain separate changes.
- Complete T15's fresh pricing on every latched exit submit/re-send before
  releasing the interim preset exit-age constraint.
