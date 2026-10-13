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

The [approved sanitized revision 3 projection][measurement] records paper Gateway trials
using the official IB Python client **10.46.01** and NautilusTrader develop
**2.0.0rc7.dev20261012**, commit
`01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25`. These are measurements at those
versions, not acceptance of the selected rc5 engine. The ladders placed and
canceled one-share limit orders far below the bid; none filled. Sources:
projection `/facts/official_client`, `/facts/nautilus_trader_pin`,
`/facts/nautilus_trader_pin_description` and `/scope`.

| Path and run | Observation or calculation | Boundary |
| --- | --- | --- |
| Official client, `P-r1`, target 50 messages/s | 500 orders with cancels in 20 seconds; mean 49.95 messages/s. Order rate: 1,500/minute. Mean message rate: 2,997/minute, approximately 3,000. | A rate from a 20-second rung, not a sustained full-minute result; one connection, no refusal or pacing error in the ladder; highest tested target 50 messages/s. |
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

## Revision 3: sliding maxima and receipt counters

Revision 3 computes whole-run `max_1s` in **sliding one-second windows** and
`best_5s_mean` in sliding five-second windows. Each window starts at a message
timestamp and is half-open: the start is included and the end excluded. Integer
microseconds avoid floating-point boundary comparisons. Historical UTC-aligned
results remain in `max_1s_utc_buckets` and `best_5s_mean_utc_buckets`. The
20-second rung means above are unchanged. Sources: projection
`/facts/rate_window_conventions` and [V3-CHANGES, sections 2 and 4][v3-changes].

The producer's section 4 corrects the earlier maximum-rate claims:

| Combined adapter pair | Sliding 1 s refined wire estimate | Sliding 1 s upper bound |
| --- | --- | --- |
| m1 | 52 | 53 |
| m2 | 47 | 47 |
| m3 | 40 | 40 |
| m4 | 47 | 52 |

Thus m1 and m4 exceed 50 in the upper-bound series. The previous claim that
every pair stayed at or below 50, and the broader ceiling of 45, do not hold
under the sliding definition. Source: [V3-CHANGES section 4, items 1 and 3][v3-changes],
projection `/headline_numbers` entry `adapter_two_connection_combined_rate_estimates`.

| Whole run | Counted sliding 1 s maximum | Refined wire maximum | Upper-bound wire maximum |
| --- | --- | --- | --- |
| B-r5 | 46 (previous UTC bucket: 37) | 69 (57) | 69 (57) |
| B-r6 | 53 (48) | 78 (66) | 83 (71) |

B-r5's best sliding five-second wire mean is **51.2 messages/s** (refined and
upper bound); the earlier 49.8 bucket mean cannot support a ceiling of 50.
B-r6's refined best five-second mean is **56.6**, replacing 53.8. Sources:
[V3-CHANGES section 4, items 2 and 5][v3-changes], projection `/headline_numbers`
entry `adapter_whole_run_rate_estimates`.

The B-r5 rung-50 value **38** is a receipt slot counter, not a sliding peak rate.
The largest sliding one-second window within that rung contains **46 counted
messages (69 wire)**. B-r6 rung-30's mean remains approximately 45 wire
messages/s, while its in-rung sliding maximum is **63 refined / 64 upper-bound**
wire messages. The official client's rung-50 slot maximum is 51; no per-message
times were retained for recomputing its sliding maximum, which is therefore at
least 51. Sources: [V3-CHANGES section 4, items 4, 8 and 10][v3-changes] and
projection `/facts/rate_window_conventions`.

No pacing text, code 100 or disconnect occurred in the retained adapter runs.
**Whether a sliding 1 s window above 50 wire messages is above the cap depends
on how the Gateway counts, which this evidence does not establish.** Hidden
requests remain source-derived estimates stamped at the cancel-row time, not
wire captures. Sources: [V3-CHANGES section 4, item 11 and final boundary][v3-changes],
projection `/facts/message_counting` and `/facts/rate_window_conventions`.

Adapter `peak_open_orders` now closes an order at its **first terminal order
event**, including rejection or fill; a rejected cancel is not a terminal order
event. The official-client peak field remains its separate runtime counter:
a 103-refused order stays in that counter until its stale cancel is answered.
Neither counter alone establishes broker-confirmed accepted exposure. Sources:
projection `/facts/peak_open_orders_definition` and [V3-CHANGES sections 2 and 6][v3-changes].

The v3 verifier enforces **each missing ID belonging to exactly one run**.
The retained ownership histogram is zero with no owner, 38 with one owner,
and zero with multiple owners. The producer's swapped-owner negative control
passed v2's aggregate check and is rejected by v3. Sources: projection
`/reconciliation/journal_orders_missing_by_number_of_owner_journals` and
[V3-CHANGES sections 1 and 5][v3-changes]. This publication does not rerun the
verifier against private receipts.

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
  the original JSON. Revision 2 incorporates that third count and corrects the
  missing-order classification. [V3-CHANGES][v3-changes] records the subsequent
  sliding-window, terminal-event and per-ID corrections. The [re-sealed v2
  addendum][revision] remains historical; the published README's rate definitions
  are updated for v3, while [ADDENDUM-02][order-rule-correction] supplies its
  documented order-ID-rule correction. Neither a
  source-derived wire estimate nor a marker is a fill witness.
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
[order-rule-correction]: ../../evidence/artifacts/ibkr-pacing-20261013/ADDENDUM-02.txt
[revision]: ../../evidence/artifacts/ibkr-pacing-20261013/ADDENDUM-03.txt
[v3-changes]: ../../evidence/artifacts/ibkr-pacing-20261013/V3-CHANGES.md
[publication]: ../../evidence/artifacts/ibkr-pacing-20261013/PUBLICATION.md
[order-ids]: https://interactivebrokers.github.io/tws-api/order_submission.html
[selector-source]: https://github.com/nautechsystems/nautilus_trader/blob/01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25/crates/adapters/interactive_brokers/src/execution/core.rs#L381-L394
[handler-source]: https://github.com/nautechsystems/nautilus_trader/blob/01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25/crates/adapters/interactive_brokers/src/execution/core.rs#L2387-L2434
[cancel-source]: https://github.com/nautechsystems/nautilus_trader/blob/01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25/crates/adapters/interactive_brokers/src/execution/core.rs#L2624-L2643
[paper-policy]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L20-L49
[comparator]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/engines-strategies.json#L240-L287
