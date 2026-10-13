# IBKR pacing and request boundaries

Use the selected NautilusTrader **2.0.0rc5** native IBKR adapter at
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`. Its historical client exposes
instrument, bar and tick requests, while IBKR controls historical availability,
pacing, duration, bar size and regular-hours filtering. A successful installation
or historical response does not establish paper-order or recovery acceptance.
Sources: [selected engine and adapter boundary][target],
[pinned native historical client documentation][native-history].

## Identify the request before choosing a budget

IBKR's general TWS API limit applies to requests submitted by a client connection.
A streaming subscription contributes its original request; subsequent streamed
updates do not each become a new request. The published general rate is maximum
market-data lines divided by two per second: the documented default of 100 lines
therefore gives **50 requests per second**. This is a request budget, not 50 orders
or fills per second, and is not proof of any particular subscription entitlement.
Source: [IBKR, pacing introduction][general].

Historical small bars have additional constraints. The following table describes
IBKR's published **30-second-or-smaller bar** rules; do not apply the general
request rate as a replacement for them. Source: [IBKR, small-bar pacing][small-bars].

| Request condition | Published pacing boundary |
| --- | --- |
| Identical historical requests | Repeating within 15 seconds is a violation. |
| Same contract, exchange and tick type | Six or more requests within two seconds is a violation. |
| Historical request count | More than 60 requests within ten minutes is a violation. |
| Historical `BID_ASK` | Each request counts twice. |

The vendor describes historical limits separately from other request types.
Record bar size, duration and request identity with a historical acquisition;
do not claim that fitting the general rate alone clears historical pacing.
Sources: [historical limitations introduction][history-limits],
[pinned adapter's vendor-documentation boundary][native-history].

## Pacing rejection and queueing are different outcomes

IBKR documents two behaviors for the setting named **Reject messages above
maximum allowed message rate vs applying pacing**. When enabled, an over-limit
request produces error 100; breaking the limit three times terminates the API
session. When disabled, TWS automatically paces requests and waits to acknowledge
them in the EReader thread before moving to new requests. A queued or delayed
acknowledgment is therefore different from an accepted order, a fill or a completed
historical response. This page does not change that setting or prescribe a new
client-side limiter. Source: [IBKR, pacing behavior][behavior].

For a bounded paper trial, keep the request-rate and timeout assumptions with
the frozen order/exposure limits and end-of-run disposition. Preserve actual
refusal, failure and inconclusive outcomes, including unobserved broker events;
do not lower frozen criteria after observing results. The native risk/order
state remains deterministic. Source: [paper trial and evidence contract][paper-policy].

## Measured throughput on 2026-10-13

The [approved sanitized projection][measurement] records paper Gateway trials
using the official IB Python client **10.46.01** and NautilusTrader develop
**2.0.0rc7.dev20261012**, commit
`01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25`. These are measurements at those
versions, not acceptance of the selected rc5 engine. The ladders placed and
canceled one-share limit orders far below the bid; none filled. Sources:
projection `/facts/official_client`, `/facts/nautilus_trader_pin`,
`/facts/nautilus_trader_pin_description` and `/scope`.

| Path and run | Observation or calculation | Boundary |
| --- | --- | --- |
| Official client, `P-r1`, target 50 messages/s | 500 orders with cancels in 20 seconds; mean 49.95 messages/s. Order rate: 1,500/minute. Mean message rate: 2,997/minute, approximately 3,000. | A rate from a 20-second rung, not a sustained full-minute result; one connection, no refusal or pacing error in the ladder; not tested above 50 messages/s. |
| Adapter, `B-r6`, target 30 counted messages/s | 900 orders/minute by submit count, 897/minute by the counted mean; refined wire estimate 44.95 messages/s. | Observed rung rates, approximately 45 wire messages/s. Wire estimates are source-derived, not a packet capture. |
| Adapter budget at 50 wire messages/s | `50 × 60 / 3 = 1,000` orders/minute with cancels. | A computed bound assuming one placement, one cancel and one all-open-orders request per accepted order; not the measured rung rate. Other requests consume this budget too. |

Table locators in the projection: `/official_client_ladder`, and
`/headline_numbers` entries whose `id` is
`official_rung50_orders_in_rung`, `official_rung50_seconds`,
`official_rung50_counted_msgs_per_s_mean`,
`official_rung50_orders_per_min_with_cancel`, `official_rung50_msgs_per_min`
or `adapter_r6_rung30`. Counting assumptions are in
`/facts/message_counting`; limitations are in `/caveats`.

Budget **wire messages**, including the adapter's extra request. The harness's
counted rate includes `placeOrder` and `cancelOrder`; the adapter resolves an
accepted order's permanent venue ID through `reqAllOpenOrders` before canceling.
The refined estimate adds this request for accepted-order cancels; the upper
bound adds it for every cancel. At `B-r6` target 40, the refined estimate was
**51.65 messages/s**, about 3% above 50; at target 50 it was **49.35**. The
earlier upper-bound estimates of 57.3 and 56.55 are not refined wire measurements.
Absence of error 100 or disconnection does not establish cap compliance.
Sources: projection `/facts/message_counting`, `/headline_numbers` entries
`adapter_r6_rung40` and `adapter_r6_rung50`, `/caveats`, and
[pinned cancel resolution][cancel-source].

## Error 103 and the order-writing connection

For this trial policy, retain **one order-writing connection per account**.
The adapter's per-cancel `reqAllOpenOrders` interacts with IBKR's order-ID rule:
after requesting all open orders, a subsequent order ID must exceed the IDs
returned. A separated client-ID range alone does not remove that constraint.
The pinned adapter resolves a permanent ID with an all-open-orders request,
while a numeric order-ID selector returns directly. Sources:
[IBKR's order-ID rule][order-ids], [pinned selector][selector-source],
[pinned cancel handler][handler-source], [pinned resolution][cancel-source],
and projection `/facts/source_citations_at_the_pin`.

The projection contains **13** official-client two-connection tests. The lower-ID
connection had error-103 refusals in `T4`, `T7`, `T9a` and `T10` when it polled
`reqAllOpenOrders`; `T1` instead reused client IDs with lower order IDs and
refused every order. No-poll tests, client-scoped polling (`T8`) and higher-ID-only
polling (`T9b`) did not refuse orders in these bounded probes. These diagnostics
support the all-open-orders/order-ID mechanism; they do not establish a supported
multi-writer configuration or a general latency guarantee. Sources: projection
`/official_client_two_connection_tests`, `/official_client_summary`,
`/adapter_two_connection_pairs` (including `L0-m4`/`L1-m4`) and `/caveats`.

## Source boundaries

- The vendor pages below were checked on 2026-10-13. They describe API behavior,
  not a new throughput measurement or an account's observed pacing configuration.
  The [retained captures and hash inventory][publication] preserve the three
  pacing responses separately from today's measurements.
- The native adapter source is pinned to the selected engine. This handbook
  does not replace it, accept another engine version, or infer broker parity.
  Source: [selected destination and broker-specific qualification][target].
- Today's throughput claims cite the approved sanitized projection, retained
  byte-for-byte with its published generator and verifier. This documentation
  change checked its public fields and cited source, without rerunning broker
  trials or the verifier against private receipts. The projection's broker
  reconciliation counts are explicitly transcript-derived; its sealed
  [addendum][measurement-addendum] extends that reconciliation without changing
  the JSON. Neither a source-derived wire estimate nor a marker is a fill witness.
  Sources: [projection scope and field definitions][measurement-guide],
  [authority versus execution evidence][paper-policy].
- Lumibot remains a separate comparator path; this page neither selects a
  replacement engine nor turns a comparator result into Nautilus/IBKR acceptance.
  The [retained alternative record][comparator] documents that separate path;
  the selected destination remains the one in [runtime-target.json][target].

[target]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/runtime-target.json#L30-L75
[native-history]: https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/integrations/interactive_brokers.md#L217-L234
[general]: https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/introduction.md
[small-bars]: https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/pacing-violations-for-small-bars-30-secs-or-less.md
[history-limits]: https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/introduction.md
[behavior]: https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/pacing-behavior.md
[measurement]: ../../evidence/artifacts/ibkr-pacing-20261013/ibkr-pacing-evidence-20261013.json
[measurement-guide]: ../../evidence/artifacts/ibkr-pacing-20261013/README.md
[measurement-addendum]: ../../evidence/artifacts/ibkr-pacing-20261013/ADDENDUM-01.txt
[publication]: ../../evidence/artifacts/ibkr-pacing-20261013/PUBLICATION.md
[order-ids]: https://interactivebrokers.github.io/tws-api/order_submission.html
[selector-source]: https://github.com/nautechsystems/nautilus_trader/blob/01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25/crates/adapters/interactive_brokers/src/execution/core.rs#L381-L394
[handler-source]: https://github.com/nautechsystems/nautilus_trader/blob/01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25/crates/adapters/interactive_brokers/src/execution/core.rs#L2387-L2434
[cancel-source]: https://github.com/nautechsystems/nautilus_trader/blob/01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25/crates/adapters/interactive_brokers/src/execution/core.rs#L2624-L2643
[paper-policy]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L20-L49
[comparator]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/engines-strategies.json#L240-L287
