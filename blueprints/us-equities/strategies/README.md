# T22 deterministic strategy hypotheses

Ten **equity-only** NautilusTrader `2.0.0rc5` Strategy subclasses, three risk
presets and four versioned exit-timing candidates follow the landed
[equities scope decision](https://github.com/seathatflowsinourveins/us-equities-trading/blob/2e0860ccd1d485593d1bd31b8a97c12198ca6b3d/docs/decisions/2026-10-09-equities-intraday-scope.md)
and trading-ecosystem §6. Every rule and parameter remains an untested hypothesis.
The same classes have synthetic
BacktestEngine and adaptive-paper LiveNode checks; neither check uses a broker.
[registry.json](registry.json) freezes the grid, factor coordinates, overrides,
controls and target order plans. [source-review.md](source-review.md) records
the upstream pins, demonstrated implementation gap and reference corrections.

The Strategy constructor takes a frozen `StrategySpec`. It accepts only one
instrument and a hash-bound cohort. `FactorSnapshot` records original event
time, availability time, validity, source/cohort hashes and exact decimal factor
values. Missing, future, mismatched, conflicting or unqualified inputs suppress
entry or latch a fault. Observed halt state also suppresses orders and repricing.
The upstream CustomData wrapper schedules snapshots by availability time.

The signal boundary expects available upstream-derived factor and ATR inputs;
it performs no acquisition or ATR reconstruction. It never reads rank rows,
labels or arm outputs from #16. Development use requires release and horizon
qualification plus family-specific OD3/OD4/OD6 gates. The development cutoff is
2026-10-13. This package has no provider client or forward-data mode.

## Class interface

The directory has a hyphenated ancestor, so use Python's supported importlib
module loading:

```python
import importlib

contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
families = importlib.import_module("blueprints.us-equities.strategies.families")

spec = contracts.StrategySpec(
    instrument_id="SPY.ALPACA",
    cohort_sha256=cohort_hash,
    preset="conservative-v1",
    exit_policy="after-hours-v1",
    instance_id="cohort_trial_1",
    position_cap_usd="1000",
    loss_cap_usd="10",
    cash_cap_usd="1000",
)
strategy = families.GapPremarketStrategy(
    spec, ledger=paper_ledger, fault_sink=session_fail
)
```

Backtests call `engine.add_strategy(strategy)`. Hana's adapter accepts the same
instance in `native_adapter.build_node(port, instruments, [strategy])`. Before
adoption, the paper lane must supply its existing durable ledger, failure sink,
qualified factor/cohort bridge and account limits, then review the PR. It retains
the native risk engine and its independent final-wire governor. This lane provides
no paper command and has placed no broker order. Passing the fake-port LiveNode
check does not qualify the bridge or a paper session.

Native startup requires an `Equity` instrument before subscriptions or orders;
an option whose underlying asset class is equity is still excluded. The option
wheel and gamma-scalping order families stay catalogued as paused under D1 in
the registry, with their references retained and E2E NOT_RUN.
`OptionsFlowStockStrategy` remains an equity family: its orders are stock, and
its option-history inputs retain the separate OD3 development gate.

## Measured exit-timing candidates

`StrategySpec.exit_policy` resolves an immutable parameter in the preset. It
supports four research candidates, each with an explicit two-minute boundary
margin; the margin itself remains an untested hypothesis:

| Version | Target boundary |
| --- | --- |
| `regular-close-v1` | Entry day's regular close, including early closes |
| `after-hours-v1` | Entry day's POST close |
| `overnight-v1` | Next trading day's PRE open, from within the overnight window |
| `next-premarket-v1` | Next trading day's regular open, from within PRE |

The existing session helper and its pinned XNYS calendar supply the boundaries,
holidays, weekend navigation and DST. Exit timing is chosen from qualified
historical evidence; these candidates do not declare a winner. Development
specifications require the explicit policy and `exit_evidence_sha256` from the
external qualified timing study, alongside the existing release/horizon gates.
A hash binds that evidence and does not qualify its contents by itself. No
historical timing study has run here. Intraday entries prioritize the protocol's
09:35 and 10:00 ET snapshots; no frozen protocol, data fence or ranking arm changes.

An explicit policy overrides the old five/twenty-session horizon for every risk
preset, including conservative. The one-hour halt-family risk bound and
options-flow expiry bound still apply. `exit_policy=None` retains the original
v1 synthetic controls and their IDs; it is unavailable for development use.
Instances with an explicit policy use a new identity version bound to both the
policy and evidence digest, preserving restart determinism without collisions.

OVERNIGHT is an admitted, evidence-gated research candidate. Until T15's shared
classifier, adapter and paper acceptance qualify that session, execution holds
and flags the position. Fresh quotes do not authorize an unsupported session;
stale quotes suppress new exits. No candidate metadata authorizes paper orders.

## Execution profiles and R9

`code-managed-limit-v1` is a separately registered simple-order hypothesis. It
uses LIMIT/DAY entries on an observed crossing and reuses adaptive-paper's
existing `exits.py` rule chain for stops, profit, trail and time exits. Position
size is capped by the preset's fractions of frozen notional/loss budgets, whole
shares and available cash. Trail activation, partial profit and per-family hold
overrides are explicit. A measured exit policy supplies the timing boundary.

Every extended-hours exit is a code-managed limit at the same preset's stop
or trail level. A stale execution quote sends no new order and flags the held
position. Valid fresh two-sided size is required. There is no claim that limit
exits guarantee flatness or a maximum loss through a gap. One in-flight order
prevents buy/sell overlap, and repricing waits for native cancel confirmation.
Partially filled buys are never re-sent. Each fill uses its own quantity/price;
duplicates are ignored, inconsistent owned fills fault, and exit budgets are
bounded. The paper lane's governor budgets all actual submits and cancels.

`native-target-v1` fails closed with
`T15_native_order_capability_unqualified`. §6's pre-placed stop-limit, native
bracket/OCO/OTO/trailing and broker-replacement behaviors need T15's separate
order-contract and adapter acceptance. They are recorded as target plans and
are not silently substituted or reported as accepted. T22 edits no adaptive-paper
file. Overnight quote protection remains limited to sessions supported by its
existing XNYS/session helper; closed sessions are flagged for handoff.

## Synthetic acceptance

Use T13's unchanged runtime installed with `uv sync --locked` from
`ee3883699870d972058516192b1ee1c6e3ffb762`. Candidate screeners have their own
separate locked environment. Run suites normally; no small memory/CPU caps or
Windows-gate waits apply. Heavy builds use the standard 10G scope and the
vendor's worker controls.

```sh
"$ENGINE_PYTHON" -m unittest tests.test_us_equities_strategies \
  tests.test_us_equities_strategy_lifecycle -v
"$ENGINE_PYTHON" -m blueprints.us-equities.strategies.simulation \
  --output blueprints/us-equities/strategies/synthetic-receipt.json
python3 scripts/validate.py
```

The matrix uses synthetic FactorSnapshot/QuoteTick data, the upstream
`OneTickSlippageFillModel` with a fixed seed and `StaticLatencyModel`.
Each family/risk-preset/exit-policy has a receipt, with the retained v1 synthetic
controls, non-cohort inverses and independently
registered hash-random, `momentum_20`, relative-volume and no-trade controls.
The short fixture has an explicit accelerated cleanup deadline; it tests engine
mechanics, not the multi-session strategy horizon. The LiveNode check reuses the
existing synthetic FakePort and tests individual partial fills and duplicate
wire deliveries for every family.

[synthetic-receipt.json](synthetic-receipt.json) contains each family/preset and
control result with fixture/trace hashes.
[test-acceptance.json](test-acceptance.json) binds the native checks to their
exact source bytes, including the reused adapter and FakePort.
[runtime-acceptance.json](runtime-acceptance.json) records the bounded unchanged
upstream wheel checks and the corrected type-stub/import-path findings.

[cts-acceptance.json](cts-acceptance.json) records the exact vendor install,
six upstream CI matrix checks, six inverse selections and verbatim skill-tree
hashes. These qualify reference screeners, not strategy efficacy or a numeric
decision-maker in the order path.

Historical Layer 1.5 E2E, same-input LEAN strategy-matrix reconciliation,
chronological evaluation, cost/delay sensitivities, overfitting controls,
T16 Pine parity and paper adoption remain separate gates. No strategy performance
number is cited. `run_analysis=False` suppresses performance statistics in these
acceptance receipts.

The later owner-dispatched vectorbt 1.1.2 Rust candidate is qualified separately
in a shared T13/T22 acceptance run, using exact published wheels and upstream
engine/parity/inverse checks. Its environment and licence override are recorded
apart from the strategy runtime. It may support future development sweeps; every
survivor must return to Nautilus/T13 before any strategy claim.
[vectorbt-acceptance.json](vectorbt-acceptance.json) records the precompiled
install, 41 unchanged vendor engine/parity checks and ten overlapping inverse
checks, with licence/owner override and resource limits.

## Safety, cancels and clock fixtures

A forced time-exit order rests until its configured exit timeout; an already
expired strategy deadline never cancels that same forced exit early. The
deadline can still cancel an entry or a non-forced exit. Replacement waits for
native terminal confirmation. After a cancel request, the pending role's bounded
timeout also bounds acknowledgement waiting. A native cancel rejection or a
missing acknowledgement freezes durably and escalates, preserving the original
order identity and residual rather than guessing that a replacement is safe.

Explicit exit policies also bound entry: no new buy at or after the selected
calendar boundary. A resting buy arms a native alert for its earliest latched
policy boundary, explicit entry/exit deadline or entry timeout. Cancellation is
dispatched at that boundary; a fill matched before cancellation is processed
remains owned, accounted and exited. Post-cutoff execution exclusion is not
claimed. Identity remains pending until a native fill or terminal confirmation.
Holding time and calendar deadlines start from the
first buy fill's native `event.ts_event`, including delayed callback delivery.

Both a halted factor snapshot and native `InstrumentStatus` halt
immediately drive pending-entry cancellation. The native status subscription
uses the upstream rc5 callback and a distinct halt latch. A non-halted snapshot
cannot clear it; only an available, ordered native `TRADING` resumption without
an explicit non-trading flag does. Native resumption likewise cannot clear a
halted snapshot. Quote-only, paused, suspended and unavailable native status
actions, or an explicit non-trading flag, also block trading.

Halting actions take effect at observation even when their event or init
timestamp leads the host clock or regresses. `status_clock_ahead` and
`snapshot_clock_ahead` record leads. The raw event and init stamps remain in
each carrier's ordering fence: an available resumption stamped before an
observed halt cannot clear it. Future factor values remain unavailable even
when their halt signal acts immediately.

The named synthetic halt producer is the instrument-scoped `t22-factors-v1`
custom-data stream. Only explicit `halted=True`/`False` supplies known state;
an omitted/null field defaults to unknown rather than trading. Its
`valid_until_ns` bounds that state. An absent state or one past its validity blocks
every new order, including reduce-only exits and replacements, at both drive
and final submission. Native status halts remain an independent veto. A held
position with an expired producer state is flagged/notified as
`held_halt_state_unknown`. T15 still owns the actual paper producer, freshness
bound and restart reconciliation; this synthetic stream does not qualify them.

The status latch is memory-only and resets on construction; it is not persisted
across a restart. Snapshot halts and durable ledger halts remain separate. Before
the first non-synthetic runner, the owning status producer must qualify fresh
restart status reconciliation or persist/restore the halt through its journal.
A new actor's initial false latch is not evidence that trading has resumed.

The unsupported-session branch holds both enum names `CLOSED` and `OVERNIGHT`
and returns before entry admission or a new exit. It freezes/flags an owned
position with `closed_session_requires_handoff` under the existing durable
handoff. OVERNIGHT is held even when a future session classifier introduces
that enum member; this does not depend on importing an unmerged PR version.

Pending exits intentionally keep their working order and original identity
through a halt or unknown state. The position is flagged `held_halted` for a
halt, and the session sink is notified at observation and every ten minutes
through a native nanosecond alert. The entry cancellation rule does not cancel
exits; elapsed timeouts and deadlines act on the next drive after an accepted
resumption. A held exit's expiry callback flags/notifies and freezes the
instance for handoff before returning.

[F-1's policy](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md)
is settled at `f8c607bc`: hold-and-flag exits, cancel entries, submit nothing
new into a halt or unknown state. T15's seven acceptance assertions remain
separate: venue-driven DAY expiry, partial reopening fills, in-flight exit
outcomes, broker cancel/reconciliation behavior and the named paper producer
are not qualified by these native synthetic/state-machine tests.

An entry whose halt-driven cancel is not processed retains its original ID.
A fill before its own earliest deadline is an ordinary entry. A fill between
that deadline and the cancel-acknowledgement freeze is flagged, synchronously
sunk and force-exited on a permitted drive. A fill after the freeze is flagged
and sunk with the instance still frozen and its residual held for handoff.
The halt-driven cancel time is not an additional F-2 cutoff; that question
belongs to the T14 follow-up. These three outcomes are pinned natively.

F-2 never depends on venue expiry. Its cutoff is the latched earliest pending-
entry deadline: the policy boundary, explicit entry or exit deadline, or entry
timeout. A BUY executed at or after that cutoff is logged and flagged as
`post_cutoff_fill`, while the original fill
remains owned. An injected synchronous
`post_cutoff_fill_sink(strategy, native_order_filled, cutoff_ns)` runs after
fill accounting and before this callback returns or another admission occurs.
The coming T14 follow-up contract is
`risk.caps.post_cutoff_fill(state, snapshot, caps, now) -> AccountState`; this
callable is not implemented or bound by this repository, and the selected
merged UET main pin does not supply it. T14's follow-up may publish it separately;
that publication alone does not bind this strategy. An actual account/rung writer must build
the complete native post-fill account view and install the consumer's returned
state in that same call. The fixture verifies exposure and daily-loss state move
together; neither is inferred from one instrument or logged by this strategy.
An awaitable sink result is refused through the existing callback freeze and
escalation path. Synthetic fixtures without the sink are explicitly flagged
`post_cutoff_risk_sink_unqualified` and do not qualify account risk integration.
Non-synthetic startup refuses without a callable sink, independently of the
durable-ledger requirement; a deferred accounting result freezes at the fill.

The marker forces a time-exit at the next drive permitted by the existing
session rules, including races at an explicit entry/exit deadline or ordinary
entry timeout. When F-1 requires a hold, the residual stays held and flagged.
Paper acceptance must exercise the complete exception-to-accounting-to-exit/hold
path before the first non-synthetic run.
The sink fixture and T14's consumer tests remain separate engineering evidence
until their actual main-to-main binding is qualified. GTD or IOC is an optional
execution-profile capability qualified per broker later, not a dependency.

The synthetic LiveNode fixtures supply a declared native status publisher
through the rc5 data-client boundary and assert receipt of its events. The
shared adaptive-paper AlpacaDataClient still inherits an unimplemented native
status-subscription method; a direct native run with the new subscription
fails closed and requests node shutdown. Its actual status publisher and
subscription require T13-runtime adjudication and qualification before a
non-synthetic run. These fixtures do not qualify that broker capability.

Startup refusals and held-position hazards call the existing Ledger.freeze and
the injected fault_sink independently, following the reused adapter callback
guard's failure handling. Stale quotes, observed halts, unsupported closed
sessions and exhausted exit budgets hold the position and require the existing
paper-lane reconciliation path. A durable halt also blocks a flat restart.
If journal persistence fails, the session stop is still attempted and its error
type is retained; that path does not claim successful durability. Explicit
synthetic fixtures can still use the documented empty local ledger boundary.

Lido's source answer (#85545) leaves residual management unqualified. At #938
`45ebe5c4e996a53fa0627bbfd2087c1e936e86b0`, `families.py:136` attempts the
durable halt and fault sink, while `families.py:259` leaves only the local
`owned_residual_requires_operator_reconciliation` flag on stop. At #940
`8c9357c7e9face151e0da1ccb14816d95a279dd1`, `native_adapter.py:233` stops the
node on failure. The adaptive receipt exposes its wired fault (`runner.py:1628`,
`:1863`), but held-position status uses adaptive-strategy attention fields
(`native_strategy.py:868`, `runner.py:1521`); the T22 local flag has no established
bridge into that status.

The CLI makes a bounded recovery attempt (`runner.py:2496`), subject to fresh
quotes, allowed sessions and budget (`recovery.py:239`). Stale/near-close
refusals can leave a residual; finalization closes the port (`recovery.py:322`)
and reports `native_engine_resumed=False` (`recovery.py:339`). This does not
establish a continuing T22 manager or next-fresh-quote takeover. Native
paper/journal acceptance remains NOT_RUN (`README-exits-session.md:100`).

Under the CC ruling of 2026-10-10T00:08:00Z, that missing join gates T13-runtime
and permits synthetic #938 to land. Before the runtime run, a test-backed T22
follow-up must join fault sink and journal, operator-visible frozen/held-position
run status, and the shared R9 paper exit logic taking over at the next fresh
quote. A stale-tick carry is never evidence-qualified overnight holding.

LiveNode fixtures obtain timestamps from a registered native actor's engine
clock. Their market session is a declared synthetic RTH scenario anchored to
the existing calendar, independently of the wall-clock day. No live clock is
mutated and no weekend case is skipped. Actual calendar boundaries remain
covered separately by the dated early-close/holiday/DST regressions.

The lifecycle regressions reproduce the semantic defects on 93871505. The
consumed-entry case is a coverage correction: a terminal, flat, low-sequence
entry already remains consumed on that baseline. Its new isolating test also
has a distinct-instance positive control, and fails when the consumed-entry
assignment is deliberately removed in an isolated test-only source mutation.
It is not represented as a pre-existing behavioural failure.

## Restart and multiple instances

Each frozen `instance_id` is part of a hash over family, preset, instrument,
execution profile and cohort. The hash supplies both the configured StrategyId's
unique final tag and the order-ID tag. Different presets and named instances can
share a trader; deploying the same identity twice is refused by rc5. Instance
identity is stable across process restarts, and its sequence is restored at
`on_start` from the durable ledger's maximum matching intent suffix. Orders pass
an explicit `ClientOrderId` to upstream `OrderFactory.limit`; the existing paper
governor journals that ID before any broker request.

An unresolved intent or held position for the instrument refuses startup with a
named reconciliation flag. Terminal prior entry attempts also remain consumed
for that instance, preventing a restart from silently creating another entry.
Recovery stays with the existing paper lane. Development specifications require
a durable ledger; synthetic fixtures may use the explicit empty local boundary.

Overnight candidates remain unqualified for paper operation until T15 qualifies
that session. The current helper treats 20:00–04:00
ET as closed and flags the position; it does not provide overnight exits. PRE
and POST retain the existing code-managed limit protections.

Regenerate the behaviour receipt with the repository generator in the unchanged
T13 runtime, then regenerate the companion matrix:

```sh
"$ENGINE_PYTHON" -m blueprints.us-equities.strategies.acceptance \
  --output blueprints/us-equities/strategies/test-acceptance.json
"$ENGINE_PYTHON" -m blueprints.us-equities.strategies.simulation \
  --output blueprints/us-equities/strategies/synthetic-receipt.json
```
