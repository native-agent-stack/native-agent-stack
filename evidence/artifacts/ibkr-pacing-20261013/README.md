# IBKR paper Gateway pacing evidence, 2026-10-13 (sanitized projection)

`ibkr-pacing-evidence-20261013.json` (schema `ibkr-pacing-evidence/1`) is the publishable projection of one day of
throughput and order-id measurements on an Interactive Brokers paper Gateway: NautilusTrader's IB adapter at a pinned
develop commit against the official IB Python client. Everything in it is a count, a rate, a latency in
milliseconds, an error-code count, a boolean or a category word. It contains no account code, client id, order id,
order reference, path, host name, address, credential or timestamp (only a date and relative offsets).

Files here: this README, the JSON, `generate_ibkr_pacing_evidence.py` (receipts to JSON), `verify_ibkr_pacing_evidence.py`
(recomputes the headline numbers from the receipts), `AUDIT.txt` (what was searched in the published files) and
`LOCATORS.txt` (sizes and sha256 of the published files, names and sizes of the private inputs).

## What was measured

All orders were 1-share BUY limit orders far below the bid on one liquid ETF, placed and then cancelled; nothing filled in
any ladder or pair test. A "rung" runs one target message rate for 20 seconds; "msgs/s" counts one order placement and one
cancel as two messages.

| group | labels | what |
|---|---|---|
| adapter, phase A | `A-r1`..`A-r6` | smoke steps S1 (a limit order accepted and cancelled), S2 (a filled round trip) and S3A (an order left open across a node restart) |
| adapter, one connection | `B-r2`..`B-r6` | place-and-cancel ladders (r2 window 10 pairs, r3-r5 window 30, r6 window 50), rungs 5..50 msgs/s |
| adapter, two connections | `m1`..`m4` | the same ladder on two order-writing connections of one account (lower and higher client-id partition) |
| official client, one connection | `P-r1` (and `SMOKE`) | the same ladder at 30/40/45/50 msgs/s |
| official client, two connections | `E1`, `E2`, `T1`, `T1b`, `T2`, `T3`, `T4`, `T6`, `T7`, `T8`, `T9a`, `T9b`, `T10` | two probes at 10 msgs/s each, one design variable changed per test (see `design_declared_by_runner`) |

## Fields

- `facts`: pins and counting rules. `message_counting` defines the three rates below. `source_citations_at_the_pin` gives
  file, symbol and line of the cancel path at the pinned commit (blob URL form included) and the counts of open-order requests
  in the adapter sources at the pin and at the develop head.
- `headline_numbers`: the figures to cite, each with its `source` label. `verify_ibkr_pacing_evidence.py` recomputes them.
- `adapter_single_connection_ladders[].rungs[]`: `counted_msgs_per_s_mean` (placeOrder + cancelOrder, what the harness
  reports), `wire_est_refined_msgs_per_s_mean` and `wire_est_upper_bound_msgs_per_s_mean` (add the adapter's hidden
  request, below), `orders_per_min_by_submits` (orders in the rung / seconds x 60, each with its cancel),
  `orders_per_min_by_counted_rate` (counted mean / 2 x 60), accept and cancel latency (`n`, p50, p90, max in ms, nearest
  rank), `peak_open_orders` (adapter orders stop at their first terminal order event in revision 3), `skipped_slots` (slots the window refused), `cancels_before_acceptance`.
- `rate_estimates_whole_run`: for a whole run, the maximum over sliding half-open one-second windows anchored at message timestamps and the best sliding five-second mean, counted /
  refined / upper bound. Revision-2 UTC-aligned results remain in `max_1s_utc_buckets` and `best_5s_mean_utc_buckets`; receipt slot counters remain separate. See [V3-CHANGES section 4](V3-CHANGES.md).
- `adapter_two_connection_pairs`: the lower-partition connection's first refusal (order index within its own run, seconds
  after the other connection's first order) and the combined rates of both connections.
- `official_client_ladder`, `official_client_two_connection_tests`: orders, accepted, cancel-confirmed, `refused_103`,
  `first_refused_order_index`, error-code counts (`202` order cancelled, `103` duplicate order id, `10147` cancel of an
  order not found, `2104/2107/2158` data-farm notices), latencies, stop reason. `cancel_confirmed` counts orders closed:
  cancelled by the venue (`cancelled_by_venue_202`) or reported not found (`closed_as_not_found_10147`, the cancels of
  refused orders). In T10 the first connection's ids fall inside the other connection's range after a re-seed, so its
  `accepted` and `cancel_confirmed` over-count (see the entry's `note`); use its 202 count. A negative
  `first_connection_first_103_after_second_connection_first_order_s` (T1 only) means the refusal came before the other
  connection placed anything: the client ids had been used earlier the same day with higher ids.
- `reqids_probe`: the Gateway's next-valid-id reads across two connections; `transcript-derived` (see below).
- `reconciliation`: journal submits against the broker's completed-order list, by arithmetic.
- `caveats`: read them before citing a number.

## How the figures are derived

- The adapter harness journals every submit and cancel with a time and a reason. Per-rung counted rates are the harness
  receipts' own per-second counters (`per_second_msgs`); whole-run and combined rates are recomputed from the journals'
  submit and cancel events.
- **Wire estimate.** At the pinned commit, cancelling an accepted order resolves its `PERM-<permId>` venue id with
  `client.all_open_orders()`, one `reqAllOpenOrders` per cancel; cancelling an order that was not yet accepted carries no
  venue id and sends no such request. The refined estimate adds one message per cancel of an accepted order, the upper
  bound one per cancel. This is derived from the source and cross-checked against the vendor logs (the number of
  `CancelOrder` commands with a PERM id equals the journal's cancels of accepted orders, per run); it was **not** captured
  on the wire.
- Latencies are nearest-rank percentiles of accept (submit to accepted event) and cancel (cancel command to cancelled
  event) per rung, on one host clock.
- The official-client probes count messages the same way (placeOrder + cancelOrder); the client sends nothing else per
  order, so its wire rate equals its counted rate (`wire_msgs_per_s_mean_equals_counted`).

## What the data shows (observed; no mechanism claim beyond what the tests support)

1. One official-client connection sustained 49.95 msgs/s at rung 50 (500 orders in 20 s, 1,500 orders a minute with
   cancels, 2,997 messages a minute) with flat latency and no refusal.
2. One adapter connection sustained about 900 orders a minute with cancels (rung 30: 897-900, wire estimate about 45 msgs/s)
   with accept p50 0.61 s. At rung 40 its wire estimate was 51.7 (refined) to 57.3 (upper bound) msgs/s and at rung 50
   49.4 to 56.6, the window filled (50 open) and latency rose (accept p50 0.90-0.93 s); three of those four estimates are
   above the 50 cap.
3. Two order-writing adapter connections on one account: the connection with the lower client-id partition is refused with
   `[103] Duplicate order id` within about 0.3-3 s of the other connection's first order (m1, m2, m4).
4. The refusal reproduces with the official client (13 two-connection tests): it appeared in T4, T7, T9a and T10, where
   the lower-id connection polled `reqAllOpenOrders` once a second, and in T1 (client ids reused with order ids below
   their earlier ids). It did not appear in the six no-polling tests (E1, E2, T1b, T2, T3, T6), when only the higher-id
   connection polled (T9b), or when both polled the client-scoped `reqOpenOrders` (T8). After the first refusal in T10,
   `reqIds` returned the other connection's first order id plus one.
5. The adapter issues `reqAllOpenOrders` on every cancel of an accepted order (source at the pin; no client-scoped
   open-order request exists in the adapter sources, at the pin or at the develop head).

These observations are consistent with: the Gateway delivers other clients' open orders to a connection that asks for all
open orders, and then refuses order ids below the highest id it delivered. No IBKR documentation of that cross-client
effect is cited here; treat it as observed behaviour at Gateway server version 225. It is a limit of the adapter's request
pattern interacting with that behaviour, not an IBKR throughput limit.

## What is private and why

The run root (journals with client order references and times, vendor logs with account-shaped tokens and the host name,
receipts with client ids and order-id bases, marker files) stays outside the repository. Its names and sizes are listed
in `LOCATORS.txt`; its digests are not published where a file's bytes contain an account-shaped token, the local user
name, a home path or a host name (a digest of such a file would confirm a guess). The generator and verifier take the run
root as an argument, so the projection can be reproduced by someone holding the receipts.

## Transcript-derived values

Three groups of numbers come from live reads recorded in the session, not from receipt files, and the JSON labels them:
the broker's completed-order counts (6,292 after the harness runs, 8,494 after the official-client runs), the `reqIds`
probe reads, and the one order of that probe. The verifier checks only the arithmetic relations between them and the
file-derived numbers.

## Verify

```
python3 -I -B generate_ibkr_pacing_evidence.py RUN_ROOT > check.json && diff check.json ibkr-pacing-evidence-20261013.json
python3 -I -B verify_ibkr_pacing_evidence.py ibkr-pacing-evidence-20261013.json RUN_ROOT [PINNED_CORE_RS]
```

Both scripts use only the standard library. `PINNED_CORE_RS` is `crates/adapters/interactive_brokers/src/execution/core.rs`
at the pinned commit; with it the verifier also checks the cited line numbers. The counts of open-order requests (11
`all_open_orders()` string occurrences in six files, no `open_orders()`, in the 54 `.rs` files under
`crates/adapters/interactive_brokers/src/` at both commits) were taken by fetching each file at the commit and counting
occurrences; they are not recomputed by the verifier.
