# Alpaca buying-power and order-state passages

Evidence class: `source_review`. Bounded excerpts from the public vendor page,
parsed with MinerU 4.0.10, local flash. Navigation, images, scripts, page-data
bundles and curl examples are omitted. Raw HTML is retained privately and is
not published. The source hash below identifies that public-page capture;
the evidence manifest separately hashes this extracted artifact.

Source URL: https://docs.alpaca.markets/us/docs/orders-at-alpaca

Retrieval window: 2026-10-13T15:33:14Z through 2026-10-13T15:35:26Z.
Version: unversioned official documentation, as read in that window.
Raw source: `alpaca-orders.html`, 700,254 bytes.
SHA256 of the capture of a public page, read in that window:
`55a1ef1b94844fc248d7833535570d19a4bd865ddf303baf857246b44710acac`.
Parser locator: `doc:55a1ef1/tier:flash/page:1`.

## Buying Power — excerpts

To accept orders that open new positions or add to existing ones, your account must have sufficient buying power. Alpaca applies a buying power check to both long buys and short sells.

The order’s calculated value is then compared against your available buying power to determine whether it can be accepted. Note that your available buying power is reduced by existing open buy long and sell short orders. Your sell long and buy to cover orders do not replenish your available buying power until they are executed.

For example, if your buying power is $10,000 and you submit a limit buy order with a value of $3,000, the order will be accepted and your remaining available buying power will be $7,000. Even if the order remains unfilled, it will continue to count against your available buying power until it is either executed or canceled. If you then submit another order with a value of $8,000, it will be rejected.

## Order Lifecycle — selected table rows

An order executed through Alpaca can experience several status changes during its lifecycle.

| status | description |
| --- | --- |
| `partially_filled` | The order has been partially filled. |
| `filled` | The order has been filled, and no further updates will occur for the order. |
| `canceled` | The order has been canceled, and no further updates will occur for the order. This can be either due to a cancel request by the user, or the order has been canceled by the exchanges due to its time-in-force. |
| `pending_cancel` | The order is waiting to be canceled. |

These excerpts document the vendor's published mechanism; they are not an
account observation, a newly measured rotation or proof of completed disposal.
