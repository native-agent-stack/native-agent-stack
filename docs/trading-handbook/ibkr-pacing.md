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

## Source boundaries

- The vendor pages below were checked on 2026-10-13. They describe API behavior,
  not a new throughput measurement or an account's observed pacing configuration.
- The native adapter source is pinned to the selected engine. This handbook
  does not replace it, accept another engine version, or infer broker parity.
  Source: [selected destination and broker-specific qualification][target].
- No today's sanitized IBKR pacing receipt was supplied with this page's inputs.
  No current paper request count, throughput, session state or order result is
  claimed. Historical policy and synthetic/local controls are not current broker
  measurements. Source: [authority versus execution evidence][paper-policy].
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
[paper-policy]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L20-L49
[comparator]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/engines-strategies.json#L240-L287
