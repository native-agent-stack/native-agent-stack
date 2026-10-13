# Portfolio sizing: evidence and limits

This page describes public sizing mechanisms and their evidence boundaries as
read on 2026-10-13. NautilusTrader **2.0.0rc5** is the selected engine, at
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`. Engine selection and a bounded
paper implementation do not establish a profitable strategy or broker parity.
[Selection and pin](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/runtime-target.json#L30-L46).

## Three separate sizing questions

| Question | Supported mechanism | What the evidence establishes |
| --- | --- | --- |
| How many units fit a specified loss budget? | Nautilus `calculate_fixed_risk_position_size` / `FixedRiskSizer` | An upstream sizing calculation with instrument precision and limits; no recommended risk fraction. |
| How much portfolio exposure is already committed? | Native Portfolio queries and the paper ledger's held/pending exposure | State/accounting inputs for sizing; not evidence that a proposed allocation is suitable. |
| May this particular intent be submitted now? | Independent paper ledger and final transport validation | Numeric/session/quote refusals remain separate from the strategy proposal. |

Sources: upstream [fixed-risk calculation](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/src/sizing.rs#L39-L117),
[Portfolio contract](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/portfolio.md#L3-L22),
and the public [ledger interfaces](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-safety.md#L25-L56).

## Use the engine's own sizing path

The pinned fixed-risk function takes an instrument, entry and stop prices,
equity, risk fraction, commission rate, exchange rate, optional hard limit,
batch size and unit count. It derives size from riskable money and price
distance, accounts for the instrument multiplier, applies the optional hard
limit, floors positive batches and caps at the instrument's maximum quantity.
Invalid inputs or arithmetic/quantity representation failures return errors;
zero exchange rate or zero price distance returns zero quantity. These are
properties of the upstream calculation, not a guarantee that a stop executes
at the requested price.
[Nautilus sizing.rs:39–117](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/src/sizing.rs#L39-L117).

Python callers use the engine's `nautilus_trader.risk` sizing classes rather
than reimplementing that calculation. The upstream tests import
`FixedRiskSizer`, `PositionSizer`, `Money`, `Price` and `Quantity`; their sample
risk fraction belongs to a synthetic instrument fixture and is not an equity
portfolio recommendation. No upstream suite or engine run was repeated for
this handbook.
[Pinned sizing tests](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/tests/unit/risk/test_sizing.py#L19-L37).

## A proposal still passes independent limits

The public paper implementation separates policy allocation from submission.
Its policy computes a budget below the configured gross ceiling, reduces
allocation with the signal's volatility, caps order notional, and limits whole
shares by both the order cap and remaining budget. On the explicit leverage
path it counts current holdings and pending buy notional, including holdings
that an exit decision has not yet sold. These describe this implementation's
research policy, not a demonstrated optimal allocation or a generic Nautilus
default.
[Allocation implementation](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/strategies_v1.py#L462-L505).

The ledger checks quantity and order notional independently, requires whole
shares for entries, limits unresolved orders and exposed symbols, and refuses
new risk when held-position marks are stale. Its default aggregate check caps
new exposure by the lesser of the effective gross cap and marked allocated
equity. A validated leverage path adds its own envelope; changing a model's
proposal cannot bypass these checks.
[Ledger reserve checks](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/safety.py#L993-L1027).

Reservation and transmission are separate steps. The documented ledger
interface requires revalidation after waits and immediately before submission;
a duplicate intent does not authorize a second order. Quantity, price, quote
freshness, session, loss and cleanup bounds still apply to risk-reducing exits,
and a finite limit-order mechanism cannot guarantee a flat finish.
[Reservation/revalidation contract](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-safety.md#L17-L56).

## Read a ceiling as a ceiling

Configured leverage is permission to reach a bounded exposure, not a target
that the policy must attain. The public record separates achieved gross-to-
equity leverage from configured limits and requires achieved-exposure evidence
for its ladder gates. A clean completion alone does not prove that a higher
leverage range was exercised. Do not turn those historical gate thresholds
into sizing advice.
[Ceiling and achieved-exposure distinction](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/adaptive-paper/README-safety.md#L384-L415).

Lumibot is a comparator path, not a change to the selected Nautilus engine.
The public catalog snapshot reviewed Lumibot **4.6.11**, source
`862504052407df2586122b752a645f88ce87afa1`, as conditional source review and
kept historical simulation, fill semantics, recovery and broker acceptance as
separate work. That snapshot supplies no accepted sizing or portfolio-parity
result. Any subsequent accepted comparison must be cited with its own retained
record and scope before claiming more.
[Dated comparator scope](https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/engines-strategies.json#L241-L259).
