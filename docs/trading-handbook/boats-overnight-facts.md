# BOATS overnight: verified facts and limits

BOATS data, an overnight market session, asset eligibility and authority to
submit an order are separate facts. This page records the public vendor and
implementation evidence read on 2026-10-13. In the pinned public implementation
snapshot, overnight paper acceptance remains **NOT_RUN**. A feed name or a
calendar label does not establish a working paper-order path.
[Recorded implementation scope](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-overnight.md#L1-L21).

## Feed names are not interchangeable

| Name | Evidence at the pin | Consequence |
| --- | --- | --- |
| `boats` | alpaca-py calls BOATS Blue Ocean overnight US trading data | Use the BOATS identity when that source is required; verify transport and entitlement separately. |
| `overnight` | alpaca-py calls it derived overnight data; the retained vendor document says trades are 15 minutes delayed and adjusted to fit the bid–ask spread | Do not present it as the fresh BOATS feed. |
| IEX / SIP | The pinned stock-stream constructor allows only these two feeds | An existing constructor cannot admit BOATS merely because the enum exists. |

Sources: alpaca-py **0.44.0**, commit
`cc4cb3b7ba50ae250e621983c2779047fb16bb28`,
[feed enum](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/data/enums.py#L56-L73),
[stock-stream restriction](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/data/live/stock.py#L34-L48),
and the retained public [historical-data document](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/tests/fixtures/adaptive_paper_citations/us_docs_historical-stock-data-1.md#L58-L72).

The documented BOATS WebSocket address is
`wss://stream.data.alpaca.markets/v1beta1/boats`. This is a published endpoint
fact, not a connection instruction or an observed connection. The repository's
feed vocabulary includes `boats`, while its separately qualified stream set
contains only `iex` and `sip`; `require_qualified_stream` refuses BOATS with
`boats_stream_unqualified_sdk`. Naming the endpoint does not qualify an SDK
override, a rebuilt stream or a substitute feed.
[Endpoint record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-overnight.md#L17-L21),
[separate vocabulary and stream guard](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/feeds.py#L10-L42).

## Session time and trade date

The retained Alpaca 24/5 source record describes the overnight window as
**20:00–04:00 Eastern**, Sunday evening through Friday morning. The public
calendar implementation treats it as half-open: 20:00 is overnight, 04:00 is
premarket. The session belongs to the upcoming civil trade date; Monday
21:00 belongs to Tuesday. Its calendar requires that actual next date to be
an exchange session rather than jumping over a holiday to a later date.
These are source-reviewed vendor facts and calendar behavior, not broker
acceptance observations.
[Window/calendar record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-overnight.md#L7-L15),
[retained primary-source provenance](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-overnight.md#L132-L143).

## Eligibility and halt status

The retained public asset schema distinguishes `overnight_tradable` from
`overnight_halted`: an eligible asset can still be blocked for overnight
trading. The SDK asset response's attributes are the source for the
implementation's separate status carrier. Missing or malformed attributes
produce unknown values, rather than a default resume. Quote freshness and
asset status remain different checks.
[Public vendor schema excerpt](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/tests/fixtures/adaptive_paper_citations/asset-attributes.json#L2-L25),
[status normalization](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/transport.py#L610-L627).

The implemented overnight submission checks require explicit eligibility and
no overnight halt, fresh status, and no separate standing trading halt.
They run before reservation and again at the final submission boundary.
These deterministic guards are implementation evidence; they do not prove
entitlement, real-time status delivery, fills or reconciliation.
[Status and submission scope](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-overnight.md#L23-L41).

## What remains unqualified in this snapshot

A supported native BOATS stream, real-time parsing, paper entitlement and
linkage, refreshed status delivery and an actual overnight paper/journal run
remain separate acceptance inputs. The pinned SDK's IEX/SIP restriction
causes an early refusal before a trial is admitted. The public record also
retains an overnight entry-dispatch refusal and requires admission and
lifecycle coverage to advance together. No connection, data acquisition,
order or account check was performed for this handbook.
[Remaining acceptance and refusal](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-overnight.md#L58-L76).

An order accepted by a broker is resting, not proof of execution. A calendar
classification and a paper order result also say nothing by themselves about
strategy merit, realistic live liquidity or achievable capacity. Keep any
future acceptance record's data, session, engine and lifecycle scope beside
the result; a later record supersedes this snapshot explicitly.
[Lifecycle acceptance boundary](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-overnight.md#L72-L95),
[paper scope limits](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/runtime-target.json#L220-L224).
