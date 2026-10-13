# Proposal: concurrent lane B presets through one account writer

Status: proposed, offline feasibility measured; no runtime deployment or broker
acceptance. Lane B exploratory only. Prepared from native-agent-stack main
993cc890b3ff3fc95fa7cdba51edd726565f9ace. Today's sealed serial series remains
unchanged. NautilusTrader2.0.0rc5 is the selected engine; the accepted Lumibot
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
- crates/system/src/trader.rs:545-622 validates strategy/order-id uniqueness,
  registers each strategy against the same trader clock/cache/portfolio, and
  installs its native message handlers through :695. Tests :2519-2616 verify
  unique generated tags and duplicate-tag refusal.
- crates/risk/src/engine/config.rs:48-63 defines node submission/modification
  rate limits and per-order notional checks. crates/common/src/throttler.rs
  implements the maintained throttler; it is not a durable account-wide HTTP
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
alpaca-py0.44.0 at cc4cb3b7ba50ae250e621983c2779047fb16bb28. Do not create or fork
a second broker adapter for concurrency.

The explicit offline probe uses the installed rc5 node and that existing
adapter with one fixture port. Two fresh processes each registered two native
strategies, produced four unique order ids and two fills per strategy, used one
port start/stop, and ended flat. Duplicate order tags caused upstream refusal
before node execution. These are synthetic fills, not paper trades or tested
concurrent AdaptiveStrategy presets.

In a separate real Ledger slice, one durable account counter admitted200
read/cancel requests at a synthetic timestamp, deferred201, preserved that
reservation across reopen, and released it after61s. Two independent counters
admitted201 and failed the account invariant. Two individually valid100.01USD
pending buy intents against a150USD global gross cap caused the second to fail
aggregate_exposure_cap_exceeded, leaving pending gross100.01USD. No HTTP or
account is involved. The node slice and Ledger slice are not represented as
an integrated production writer or actual rate/latency test.

Portable results: [probe-result.json](../../blueprints/us-equities/concurrent-paper-presets/probe-result.json).
Public retained inputs/source pins and full-blob hashes:
[inputs.json](../../blueprints/us-equities/concurrent-paper-presets/inputs.json).
Reproduce with the managed runtime and the work-conserving scope:

```sh
systemd-run --user --scope -p CPUWeight=idle --quiet -- env TMPDIR=/var/tmp PY -E -s -B blueprints/us-equities/concurrent-paper-presets/probe.py
```

`--duplicate-tags` and `--separate-budgets` are intentional failing controls.
Absent/wrong Nautilus runtime fails, never skips. Raw logs are private; this
proposal publishes no hash or prefix committing to withheld output bytes.

## One portfolio experiment, several strategy policies

The next implementation should register a portfolio trial with a frozen roster
of preset ids, native strategy ids/order tags, config hashes and symbol leases.
One issuer GO binds the WHOLE roster and account readiness. Preset start/stop
events are receipts within that portfolio trial, not separate competing account
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
paper throughput receipt observed200/min but used nonmarketable submit/cancel
probes, not strategy fills or indefinite availability. No Elite1000/min uplift
is implied. The existing Ledger preserves20 slots against new submits. Broker
reconciliation, cleanup and observations consume the same account budget; data
provider GET/stream entitlements are tracked separately. Controller currently
exempts `data_read` from this broker budget; do not falsely claim that broker
200/min proves unrestricted data throughput. Coordinate any external observer
or ingestion worker; one process counter cannot cover uncoordinated callers.

Proposed pilot ceilings inherit a reviewed account CONFIG and reserve additional
headroom for recovery and observation. The initial roster should consist of two
baseline presets with deterministic disjoint symbols, zero overnight holds,
stock LIMIT/DAY paper orders, native quote/STOP/exit guards and a bounded runtime
inside the active venue session. Exact allocations and the pilot symbols are
readiness inputs to a later execution record, not model-selected values here.
Changing a preset config cannot reset cash/fee history or erase a loss halt.

## Demonstrated gaps and implementation boundary

One-node registration is already implemented. The remaining gap is the current
single-policy/account-lifecycle contract:

1. runner.Controller.before_submit stores the native strategy in event output
   (runner.py:987-989), but Ledger.reserve_intent does not store a preset/strategy
   owner. Its positions and pending reservations are account/symbol totals.
2. native_strategy.positions reads all ledger positions (:399-402). Adding two
   existing AdaptiveStrategy objects unchanged could make each policy manage
   the other's holdings or spend the same apparent capital. Per-strategy node
   fill attribution does not fix that account view.
3. Account trial metadata, exact config recovery, active namespace and GO
   currently describe one trial/config. A concurrent roster needs one atomic
   portfolio metadata binding and per-preset ownership. Separate stage journals
   would lose the proven global rate/cash/fee continuity.
4. NETTING aggregate broker state cannot reconstruct preset allocation after
   restart on its own. Order/fill lineage must persist first; ambiguous allocation
   is a refusal, never a synthesized preset position.

Only those gaps justify trading glue in a subsequent implementation. Reuse the
engine's upstream native ids/cache/OMS/message bus and the existing adapter,
Ledger, Controller and recovery before adding any new schema. Do not add
independent per-preset broker clients, paper accounts or parallel processes.

## Retained data and evidence

This proposal acquires nothing. It consumes the published SIP/1x configs,
current native source, the September24 throughput index and the retained AAPL
equity-replay receipt at NAS993cc890. Their exact byte hashes are in inputs.json.
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

- At most one broker client/writer/account journal; both preset intents route
  through the same Controller/Ledger/final-wire governor and rolling rate window.
- Every order/fill/cancel/reject retains exactly one durable preset owner; a
  preset cannot sell or cancel another's residual. Disjoint symbol leases reject
  overlap; global pending gross/loss/cash limits remain authoritative.
- Partial fills, one sibling stopping, strategy callback fault, 429/backoff,
  ambiguous submit and process restart retain ownership and request reservations.
  No global cancel-all or account flatten is invoked by a benign single-preset stop.
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
