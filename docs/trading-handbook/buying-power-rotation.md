# Buying-power rotation: policy and evidence boundary

A buying-power refusal does not establish that another holding was sold or that
funds became available. This chapter documents the broker mechanism separately
from the **paper trial's rotation policy**, stated in the
[account-neutral public calculator specification v1](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md).
That policy does not establish a newly measured rotation. See
[the source and gap inventory](sources/luld-bp-20261013.json).
The [registered vendor excerpts](../../evidence/artifacts/trading-handbook-20261013/alpaca-buying-power-passages-20261013.md)
retain the cited text. Raw HTML and the docs host's page bundle are not published;
the recorded raw-page SHA256 identifies the captured public source separately
from the extracted artifact's manifest hash.

## What the broker documents

Alpaca applies a buying-power check to opening long buys and short sells.
Existing opening orders reduce available buying power, including orders not
yet filled. Selling a long position or buying to cover does not replenish it
until execution. An accepted sell submission therefore cannot by itself
justify immediate admission of a replacement buy.
Source: [Orders at Alpaca](https://docs.alpaca.markets/us/docs/orders-at-alpaca),
**Buying Power**, capture `alpaca-orders`, SHA256
`55a1ef1b94844fc248d7833535570d19a4bd865ddf303baf857246b44710acac`.

The same documentation distinguishes `partially_filled`, `filled`,
`pending_cancel` and `canceled`. Pending cancellation is not completed
cancellation; a partial fill must not be represented as a completed disposal.
Source: capture `alpaca-orders`, **Order Lifecycle**. The captured website is an
unversioned documentation snapshot, not a claim that this chapter queried a
broker or observed any of those states.

The official alpaca-py v0.44.0 client supplies native order submission and
lookup methods. Reuse those supported interfaces for an approved experiment;
this chapter adds no replacement order writer or retry loop.
[Source: TradingClient at cc4cb3b7, submit and lookup methods:90–160](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/client.py#L90-L160).

## Public trial rotation contract

The specification selects **one held name for exit** when an attempted entry
has confidence at least 0.3 and is refused for buying power. The candidate is a
held name **not eligible in the current round**, with the least progress,
measured as high-water mark divided by entry price. This is a trial allocation
rule, not an Alpaca requirement.
Source: public specification v1, **Exits / Buying-power rotation**, SHA256
`d00cde3a89a7ad939ee0e9b5488a10c9605746416513462253ea84da597393f5`.

The selector does not define a market-cap threshold or a separate numeric
holding-age test. Its selection section describes confidence as a score share,
with the denominator being the best eligible score in the same group.
A threshold of 0.3 therefore must not be presented as a 30% probability
of success. Source: public specification v1, **Selection** and **Exits**.

Re-admission still requires the actual broker state: a selected exit is not a
filled disposal. The captured buying-power rule makes available funds
execution-dependent. The specification does not define a tie-break for equal
progress, every reservation/partial-fill case, a re-entry rule for a rotated
name or a receipt for a completed rotation. These remain the named
`rotation-contract-details` and `rotation-execution` gaps in
[the inventory](sources/luld-bp-20261013.json).
Any additional handling described later remains proposed until its contract
and receipt exist. The public paper contract requires frozen inputs,
deterministic risk, a durable journal, stable identities and reconciliation.
It also requires actual failed or inconclusive outcomes to remain visible.
[Source: paper policy:21–40](https://github.com/native-agent-stack/native-agent-stack/blob/df3a477c84aafed82757d120268ac58dea1fbd30/docs/paper-lane-policy.md#L21-L40).

## Evidence for a completed rotation

A future completion claim needs the refusal, selected holding and its data
revision, disposal order/fills, fresh position and buying-power observations,
and the replacement order's actual disposition. Cite the sanitized native
receipt for each measured result, rather than a narrative summary. A
successful sell alone does not establish admission or a subsequent fill; the
captured broker documentation makes the execution-dependent buying-power
boundary explicit.
Sources: capture `alpaca-orders`, **Buying Power** and **Order Lifecycle**, and
[the public acceptance contract](https://github.com/native-agent-stack/native-agent-stack/blob/df3a477c84aafed82757d120268ac58dea1fbd30/docs/paper-lane-policy.md#L29-L40).

No refusal, ranking observation, sell, fill or replacement trade is reported as
measured in this chapter. Account-specific observations remain private.
Related chapter: [LULD bands and halt-aware sizing](luld-halt-sizing.md).
Index integration follows the reviewed public chapter publications and the
section lead's order.
