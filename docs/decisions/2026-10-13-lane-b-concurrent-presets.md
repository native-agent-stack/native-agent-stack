# Proposal: concurrent lane B presets through one account writer

Status: proposed, offline feasibility measured; no runtime deployment or broker
acceptance. Lane B exploratory only. Prepared from native-agent-stack main
993cc890b3ff3fc95fa7cdba51edd726565f9ace. Today's sealed serial series remains
unchanged. Proposal version: `concurrent-presets-proposal-v2`. NautilusTrader 2.0.0rc5 is the selected engine; the accepted Lumibot
comparison path remains a comparator and supplies no Nautilus/Alpaca parity.

**Recommendation:** represent a concurrent trial as one portfolio experiment
inside one Nautilus LiveNode, with several native Strategy instances, one Alpaca
execution client and one account Controller/Ledger. Reuse upstream strategy
registration, message routing and order attribution. Do not launch several
existing scheduled stages or create a journal/request counter per preset.
Begin with disjoint symbol ownership. Shared-symbol allocation and independent
preset exits need durable ownership evidence before paper acceptance.

## Existing supported path and measured result

Upstream nautechsystems/nautilus_trader v2.0.0rc5,
1b0a49d2792a9432a3aca3fcb617ce7a630d905e already supports this node structure:

- python/nautilus_trader/live/__init__.pyi:1087-1107 exposes LiveNode.build,
  exec_factories and add_strategy/add_strategy_from_config. The proposal adopts
  those interfaces, not another orchestrator or execution client implementation.
- Python registration runs through crates/live/src/python/node.rs:1321-1411
  and crates/system/src/python/registration.rs:192-250,292-317. The prepare
  step checks native strategy identity and order-tag uniqueness before commit;
  each strategy receives its own component clock and shares cache/portfolio.
  crates/system/src/trader.rs:2519-2616 tests the generic Rust route; it is
  supporting evidence, not the Python call path used by this probe.
- crates/risk/src/engine/config.rs:48-63 defines node submission/modification
  rate limits and per-order notional checks. crates/common/src/throttler.rs
  implements the maintained throttler. crates/risk/src/engine/mod.rs:226-299
  supplies a failure handler that denies excess submits rather than buffering
  them; it is not a durable account-wide HTTP
  limiter for broker reads/cancels or other processes.
- crates/execution/src/engine/mod.rs:1678-1764 NETTING reconciliation sums cached
  quantities for the reported account/instrument and warns on split strategy
  ownership. A warning and aggregate reconciliation do not establish a durable
  per-preset economic subledger or authorize one strategy to sell another's lot.

The repository's existing native_adapter.build_node already accepts a list of
strategies, builds ONE `exec_clients={"ALPACA": ExecutionClientConfig()}`, and
registers them through node.add_strategy. AlpacaExecutionClient explicitly uses
OmsType.NETTING (native_adapter.py:339-346). Its order payload carries native
strategy_id/client_order_id (:790). No upstream Nautilus Alpaca adapter exists;
the already accepted repository boundary remains the adapter, with official
alpaca-py 0.44.0 at cc4cb3b7ba50ae250e621983c2779047fb16bb28. Do not create or fork
a second broker adapter for concurrency.

The explicit offline probe uses the installed rc5 node and that existing
adapter with one fixture port. Two fresh processes each registered two native
strategies, produced four unique order ids and two fills per strategy, used one
port start/stop, and ended flat. Duplicate order tags caused upstream refusal
before node execution. These are synthetic fills, not paper trades or tested
concurrent AdaptiveStrategy presets.

Control A now registers two actual AdaptiveStrategy instances and checks the
exact native refusal `Strategy ADAPTIVE-001-A is already registered`. Control B
changes only native identity/tag in a fixture subclass, inheriting the actual
rebalance and native submit path. Both siblings mint
`adp-shared-trial-0000001`; the native cache owner changes from `ADAPTIVE-A1` to
`ADAPTIVE-B2`, and its cached instrument changes to the second order's QQQ.
The node is not run in either control: zero port starts and external submits.
This demonstrates why identity-only repair is insufficient. The successful
roundtrip fixture uses upstream-generated IDs and is a different class.

In a separate real Ledger slice, one durable account counter admitted 200
read/cancel requests at a synthetic timestamp, deferred request 201, preserved that
reservation across reopen, and released it after 61 s. Two independent counters
admitted 201 and failed the account invariant. Two individually valid 100.01 USD
pending buy intents against a 150 USD global gross cap caused the second to fail
aggregate_exposure_cap_exceeded, leaving pending gross 100.01 USD. No HTTP or
account is involved. The node slice and Ledger slice are not represented as
an integrated production writer or actual rate/latency test.

Portable results: [probe-result.json](../../blueprints/us-equities/concurrent-paper-presets/probe-result.json).
Public retained inputs/source pins and full-blob hashes:
[inputs.json](../../blueprints/us-equities/concurrent-paper-presets/inputs.json).
Reproduce with the managed runtime and the work-conserving scope:

```sh
# Run in the selected managed runtime's activated shell; python must be rc5.
systemd-run --user --scope -p CPUWeight=idle --quiet -- env TMPDIR=/var/tmp python -E -s -B blueprints/us-equities/concurrent-paper-presets/probe.py
```

`--duplicate-tags` and `--separate-budgets` are intentional failing controls.
Each now asserts its exact expected reason before returning rc 1; an unrelated
failure does not satisfy the control. A/B are assertions in the successful run.
Every probe uses the existing `tests.adaptive_paper_hermetic` helper to isolate
all imported canonical STOP bindings under a private SYN root and restore them
in finally. Passing a private trial stop_file alone does not isolate the
canonical latch. No host STOP is read, created or cleared by the probe.
The focused native module `tests.integration.concurrent_preset_probe` reproduces
both regressions before the fix: a private stand-in canonical STOP made the
coupling slice refuse, and an unrelated outstanding-order refusal was reported
as aggregate-risk success. The fix preserves the SYN sentinel and requires
exactly `aggregate_exposure_cap_exceeded` before reporting that success.
Absent/wrong Nautilus runtime fails, never skips. Raw logs are private; this
proposal publishes no hash or prefix committing to withheld output bytes.

## One portfolio experiment, several strategy policies

The next implementation should register a portfolio trial with a frozen roster
of preset ids and versions, native strategy ids/order tags, config hashes and symbol leases.
One issuer GO binds the WHOLE roster and account readiness. Preset start/stop
events carry preset/version plus config_sha256 in paper-output.json and all
order, refusal, recovery and restart receipts. They are within that portfolio trial, not separate competing account
GOs or independent writer-lock owners. The node's execution client alone reaches
the paper transport, governed by one Controller and durable account Ledger.

The numerical experiment contract contains:

| Authority | Required rule |
| --- | --- |
| Account envelope | One configured capital, gross, loss/drawdown, quantity, order and request ceiling; no summing whole-account preset limits or fresh balances |
| Preset allocations | Deterministic suballocations whose gross/risk reservations never exceed the account envelope; includes pending buys and fees; no implicit capital multiplication |
| Risk admission | Global Ledger reserve/validate first, optional stricter per-preset bounds second; every callback/transport submit retains the final-wire governor |
| Rate budget | One rolling durable broker-request counter for reads, submits and cancels, counting attempts/failures; native node throttle is an additional guard, not its replacement |
| Attribution | Unique native strategy/order ids plus a durable preset ownership association, not only tags or an in-memory event log |
| Symbol ownership | Disjoint symbol leases for the first pilot; overlaps fail closed until netted attribution and partial-fill/restart exits are accepted |
| Recovery | One account coordinator cancels only owned orders and exits only owned residuals sequentially; preset shutdown does not flatten siblings or reset the account journal |
| Fault boundary | Unknown fill/account state stops entries portfolio-wide and invokes bounded account recovery; strategy faults cannot leave a live sibling silently trading through unknown state |

Use current account limits as ceilings, not throughput targets. The retained
paper throughput receipt observed 200/min but used nonmarketable submit/cancel
probes, not strategy fills or indefinite availability. No Elite 1000/min uplift
is implied. The existing Ledger preserves 20 slots against new submits. Broker
reconciliation, cleanup and observations consume the same account budget; data
provider GET/stream entitlements are tracked separately. Controller currently
exempts `data_read` from this broker budget; do not falsely claim that broker
200/min proves unrestricted data throughput. Coordinate any external observer
or ingestion worker; one process counter cannot cover uncoordinated callers.

**Pilot rate decision:** accept account-wide coupling, with no independent
per-preset request quota or fairness guarantee. The 200/min ceiling belongs to
the account, not each preset. Both presets consume the same durable window;
either can exhaust the submit allowance and defer both. Controller's shared
`defer_until` advances on `submission_rate_deferred` (runner.py:936-968).
Twenty reserved slots protect cancels/reads from new submits; this is headroom,
not an exit-priority scheduler or an assurance that cleanup always has quota.
An HTTP 429 freezes the one transport as `rate_limited`
(transport.py:1416-1420); Controller.before_submit refuses every preset's buys
while that port is unready (runner.py:970-989). Do not retry through another
client, reset the window or thaw merely on a timer. Reconciliation and bounded
recovery own resumption; an exhausted cleanup budget is an unsuccessful trial.

The added shared-coupling slice exercises the real Controller and transport
freeze methods on a fixture health shell. Both preset submits receive the exact
`submission_rate_deferred` refusal, shared deferral advances, 20 cancels remain
admissible, and a synthetic 429 makes both subsequent buys fail
`admissions_not_ready`. No SDK client is created. This checks available seams
now; it does not integrate the node with the Controller or measure real HTTP.

The node has `shutdown_on_error=True` (native_adapter.py:999-1000), so any
ERROR can stop every sibling (rc5 crates/system/src/config.rs:100-105 explicitly
includes filtered/bypassed error logs). Its throttle denies/drops excess submissions
node-wide; a denied order must release its reservation through the existing
terminal-event path, never be silently reissued. `_cancel_all_orders`
(:812-820) selects by venue/instrument/side without a strategy filter. Thus a
benign preset stop cannot invoke cancel-all, even with disjoint symbol leases;
it must cancel its own durable order IDs. Full portfolio faults use the one
recovery coordinator. Isolating harmless errors or providing rate fairness is
later work, not a pilot claim.

Proposed pilot ceilings inherit a reviewed account CONFIG and reserve additional
headroom for recovery and observation. The initial roster should consist of two
baseline presets with deterministic disjoint symbols, zero overnight holds,
stock LIMIT/DAY paper orders, native quote/STOP/exit guards and a bounded runtime
inside the active venue session. Exact allocations and the pilot symbols are
readiness inputs to a later execution record, not model-selected values here.
Changing a preset config cannot reset cash/fee history or erase a loss halt.

## Demonstrated gaps and implementation boundary

One-node registration exists for compatible native strategies. The actual
single-policy class and account lifecycle have these demonstrated gaps:

1. **Per-preset native identity.** AdaptiveStrategy.__new__ hardcodes
   StrategyId("ADAPTIVE-001") and tag "A" (native_strategy.py:22-24).
   Its second actual instance is refused by Python registration; control A
   measures that refusal. A frozen roster must configure distinct stable
   strategy IDs and order tags, persisting them across restart.
2. **Client order-ID generation and restore.** Ordinary orders (:1117-1118)
   and replacement exits (:1370-1371) use `adp-<trial>-<sequence>`; constructor
   restore (:110-112) scans that same shared Ledger prefix. Native tag changes
   alone do not change those IDs. Control B reproduces the collision through
   inherited production rebalance/submit. At rc5,
   crates/trading/src/strategy/mod.rs:2346-2385 submits with
   `cache.add_order(..., true)`; crates/common/src/cache/mod.rs:4718-4745
   permits replacement and overwrites order-to-strategy ownership. Adopt the
   upstream factory generator with durable counter restore, or put the preset
   tag in BOTH minting paths AND the Ledger restore prefix. Restart, concurrent
   entry and replacement-exit tests must prove uniqueness and stable ownership;
   registration success is insufficient.
3. runner.Controller.before_submit stores the native strategy in event output
   (runner.py:987-989), but Ledger.reserve_intent does not store a preset/strategy
   owner. Its positions and pending reservations are account/symbol totals.
4. native_strategy.positions reads all ledger positions (:399-402). Even after
   fixing identity and IDs, two AdaptiveStrategy objects could make each policy manage
   the other's holdings or spend the same apparent capital. Per-strategy node
   fill attribution does not fix that account view.
5. Account trial metadata, exact config recovery, active namespace and GO
   currently describe one trial/config. A concurrent roster needs one atomic
   portfolio metadata binding and per-preset ownership. Separate stage journals
   would lose the proven global rate/cash/fee continuity.
6. NETTING aggregate broker state cannot reconstruct preset allocation after
   restart on its own. Order/fill lineage must persist first; ambiguous allocation
   is a refusal, never a synthesized preset position.

Only those gaps justify trading glue in a subsequent implementation. Reuse the
engine's upstream native ids/cache/OMS/message bus and the existing adapter,
Ledger, Controller and recovery before adding any new schema. Do not add
independent per-preset broker clients, paper accounts or parallel processes.

## Retained data and evidence

This proposal acquires nothing. It consumes the published SIP/1x configs,
current native source, the September 24 throughput index and the retained AAPL
equity-replay receipt at NAS 993cc890. Their exact byte hashes are in inputs.json.
The AAPL diagnostic is retrospective and uses synthetic liquidity; it is not a
new holdout or validation of concurrent strategies. No market history is replayed
by the new probe: its quotes/request clocks are explicitly SYN.

The supplied brief says additional "inputs named below", but provides no extra
list. The plan discloses the retained inputs available now; additional assigned
inputs will be incorporated as new evidence rather than guessed or acquired.

## Acceptance and overturn conditions

Proposal complete means source-pinned supported architecture, repeatable native
two-strategy/one-client SYN feasibility, measured shared-budget/aggregate-cap
refusals and explicit remaining ownership/lifecycle work, through paired review.
It does not authorize or qualify a concurrent paper deployment.

Before an implementation can run paper, fail-first integration must demonstrate:

- Two real AdaptiveStrategy presets register with unique stable identity and
  mint disjoint IDs through entry, replacement exits and restart restoration.
  A/B already reproduce the old unsafe behavior; they are not production fixes.
- At most one broker client/writer/account journal; both preset intents route
  through the same Controller/Ledger/final-wire governor and rolling rate window.
- Every order/fill/cancel/reject retains exactly one durable preset owner; a
  preset cannot sell or cancel another's residual. Disjoint symbol leases reject
  overlap; global pending gross/loss/cash limits remain authoritative.
- Partial fills, one sibling stopping, strategy callback fault, 429/backoff,
  ambiguous submit and process restart retain ownership and request reservations.
  No global cancel-all or account flatten is invoked by a benign single-preset stop.
- Rate-coupling acceptance: one preset saturates the shared allowance and both
  defer without loss of pending ownership; real 429 freezes all buys; native
  throttle denial delivers a terminal event and releases reservations; reserved
  cleanup headroom is shared, and exhaustion reports failure. One ERROR stops
  both and bounded account recovery runs. These integrated cases remain NOT_RUN;
  only the Controller/429 slice above is measured now.
- Aggregate cash/fees/PnL reconcile once to broker totals and all bounded trials
  end genuinely flat with zero orders. Synthetic and native paper results stay
  separately labelled B/exploratory.
- Roster/config/source/data/active-session bindings and one GO are frozen in a
  reviewed NEW bundle with strict seal, full dry run, bounded recovery and new
  validity record. Existing sealed serial trials remain untouched.

If upstream supports a durable ownership/allocation seam that satisfies those
specific restart/exit cases, adopt it and remove the proposed extra schema. If
the broker cannot reconcile netting allocations deterministically, keep disjoint
symbols or serial operation. Paper throughput alone, strategy registration alone,
or apparent spare quota does not overturn the accounting requirement.

Follow-ups: concurrent roster/ownership schema and dispatcher; account/preset
allocation tests; lifecycle/restart/recovery acceptance; bounded paper rollout
after source/readiness inputs; independent evaluation of the accepted Lumibot
comparator only if it supplies better measured evidence for the same contract.
No live endpoint, paid service, STOP/HOLD action or other lane state is involved.
