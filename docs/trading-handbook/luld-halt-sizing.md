# LULD bands and halt-aware sizing

LULD price bands constrain eligible trades; they do not promise that a position
can be liquidated at a chosen loss. This chapter separates the published Plan
mechanism from the **paper trial's sizing policy**, documented in the
[account-neutral public calculator specification v1](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md).
Reading that policy is source review, not a new execution result. Evidence
status and captured public bytes are recorded in
[the source inventory](sources/luld-bp-20261013.json).
The [registered public-source excerpts](../../evidence/artifacts/trading-handbook-20261013/luld-public-passages-20261013.md)
retain the cited passages and capture provenance; raw page bundles are not
published.

## What the public sources establish

The official [LULD overview](https://www.luldplan.com/) describes upper and lower
bands around a reference price based on eligible transactions over the preceding
five minutes. Percentage parameters depend on security tier and price bucket;
the overview identifies regular-hours applicability. A single last-trade price
or a universal percentage is therefore insufficient to reconstruct the applicable
band. Source: capture `luld-overview`, sections **Overview** and **Calculation of
Price Bands**, SHA256 `b55070d97cbed50cab844c95dac70a825b31c06a5cb9820a2e941b53ab44f4c3`.

For a previous close above $3, the overview lists a 5% parameter for Tier 1
and 10% for Tier 2. It describes doubling during the last 25 minutes for all
Tier 1 securities and Tier 2 securities below $3; the separate Tier 2 table
above $3 lists 10% through 16:00. A late-session doubling claim therefore needs
the security's tier and price bucket. Source: the same capture, **Calculation
of Price Bands**, including its two parameter tables and doubling note.

The overview describes a limit state that can lead to a trading pause when it
does not resolve within 15 seconds. A paused market and its reopening process
are different from an ordinary executable quote. For sizing analysis, retain
the applicable band observations and session context; do not equate a band with
a guaranteed stop execution price. Source: the same capture, **Operation of
Price Bands**; the retained
[20th Amendment Plan PDF](https://cdn.luldplan.com/plans/LULD-Plan-Amendment-20.pdf)
provides the historical provisions in **Sections V–VII**. Its edition is posted
May 5, 2020, not a certification of every later amendment. Capture `luld-plan-20`,
SHA256 `81315450525e7f98077d4054c7125d5f69b8800a628b6c6ba677f1fb726d4ac0`.

The [official Plan index](https://www.luldplan.com/plans) also links a 2026
document whose opening identifies proposed additions and deletions. That
document is retained for source comparison, **not treated as proof that its
proposed language is effective**. Neither an index listing nor this chapter
qualifies overnight trading. Sources: captures `luld-plan-index` and
`luld-plan-2026`, with the latter's cover page identified in the inventory.

## Trial sizing and the 6% gap budget

The public specification states the following calculator policy. Let `E` be
current equity, `c` confidence, `N` position notional, and `b` the band fraction.
Base risk is `E × (0.0025 + 0.0075 × c)`. Its drawdown control scales base risk
by `max(0.25, 1 − dd / 0.06)`, where `dd` is the fractional drop of current
equity below the day's first equity. Initial notional is **scaled risk** divided
by the effective-stop fraction. These are stated settings, not measured
drawdown or execution results.
Source: public specification v1, **Sizing**, SHA256
`d00cde3a89a7ad939ee0e9b5488a10c9605746416513462253ea84da597393f5`.

Here `c` is the calculator's confidence score. The specification's **Selection**
section describes normalization within each selection group; it does not
establish a calibrated probability of profit for the sizing equation.

The trailing percentage is one quarter of session range, clamped to 1.5%–10%.
A name is classified as halt-prone when its session range is at least half the
band and session dollar volume is below $200 million. For such a name the
effective stop is the larger of the trail and band. The specification cites
tier-dependent LULD rules and late-session doubling. Applying them needs the
actual tier, previous-close bucket and session context; a universal Tier 2
percentage is insufficient. This source review supplies no as-known band
observation for an executed entry.
Sources: public specification v1, **Sizing / Stops** and **LULD bands**, and
capture `luld-overview`, **Calculation of Price Bands**.

The additional trial gap budget is:

```text
sum(N_i × b_i for held halt-prone names) ≤ 0.06 × E
```

**The denominator is equity**, not buying power, gross exposure or a percentage
of the new order alone. The specification caps notional at 2% of session dollar
volume and 25% of the gross cap per name, with gross exposure bounded by 3×
equity and broker buying power as an outer constraint. It also refuses a
candidate whose prior daily returns correlate at least 0.7 with two or more
held names, requiring at least six common returns. These are trial settings,
not exchange rules or a guarantee that losses cannot exceed 6%.
Source: public specification v1, **Sizing / Notional**.

Equivalently, define remaining modeled gap capacity as
`R = max(0, 0.06 × E − sum(N_i × b_i))` over the held halt-prone names.
For an additional halt-prone entry with a positive band fraction `b`,
its gap-budget notional ceiling is `R / b`, before the other sizing caps.
If held positions already consume or exceed the budget, `R` is zero and
there is no gap capacity for another such entry. This is an algebraic
restatement of the specification's constraint; it does not specify an
automatic disposal of existing positions.

For an explicitly **synthetic arithmetic illustration**, if `E = $100,000`,
the aggregate modeled gap budget is $6,000. A held $20,000 notional with
`b = 0.10` uses $2,000 of that budget, leaving $4,000. A new name with the same
band has a gap-budget ceiling of $40,000 before the other caps apply. This
illustrates the stated equation; it is not a trade or a replay result.

## Trial halt-window exit

The specification states that halt-prone positions begin their exit **from
15:25 ET**. Its separate time-exit policy starts at 15:45 ET and targets flat
state by 15:55 ET. These are paper-trial boundaries, not LULD-mandated
liquidation times or proof of completion.
Source: public specification v1, **Exits / Halt window** and **Time exit**.

The 15:25 ET policy applies to the trial's halt-prone classification.
It does not mean that every classified security's actual band doubles at 15:35:
halt-prone classification and the vendor's doubling categories are different
inputs. Neither a scheduled exit start nor a band change establishes that a
liquidation order can fill during a pause.
Sources: public specification v1 and capture `luld-overview`.

The specification does not supply a holiday/early-close adjustment, execution
receipt for this exit rule, or full quantity-rounding/timestamp inputs.
Those remain named gaps in [the registered inventory](sources/luld-bp-20261013.json).
Treat any use outside the stated regular-session context as proposed until
its own contract is retained. The public paper contract requires numeric
quantity/notional, exposure, loss, timeouts and end-of-window position/order
disposition before execution.
[Source: paper policy:21–40](https://github.com/native-agent-stack/native-agent-stack/blob/df3a477c84aafed82757d120268ac58dea1fbd30/docs/paper-lane-policy.md#L21-L40).

## Stop and reconciliation boundary

The selected NautilusTrader v2.0.0rc5 source documents that a managed stop can
reach its attempt bound with orders or positions still outstanding. Its closing
methods submit orders; they do not prove a halt-time exit completed. Keep this
native behavior distinct from the proposed 15:25 ET policy and require a
receipt for any claimed completion.
[Source: strategies.md:716–745](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/strategies.md#L716-L745).

This is documentation and source review. Related chapter:
[Buying-power rotation](buying-power-rotation.md). Index integration follows
the reviewed public chapter publications and the section lead's order.
Account-specific observation pages belong in the private trading repository.
