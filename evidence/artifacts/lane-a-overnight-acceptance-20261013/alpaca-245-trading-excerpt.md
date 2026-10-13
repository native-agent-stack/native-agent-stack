# Alpaca 24/5 Trading: bounded retained public excerpt

Source: https://docs.alpaca.markets/us/docs/245-trading.md
Vendor `updatedAt`: 2026-07-07T14:17:11.000Z.
Original public-page capture: 2026-10-10, the capture cited by the overnight handbook.
The paragraphs below are copied verbatim from that retained capture; line references
name its original lines. This excerpt is source evidence, not broker acceptance.

## Overnight window (original line 26)

* **Overnight Session:** 8:00 PM - 4:00 AM ET (technically occurs on the evening before the trade date)

## Order shape and DAY expiry (original lines 64-67)

* **Order Type:** Only `limit` orders are supported during the overnight session.
* **Time-in-Force (TIF):** The supported TIF options are `day` and `gtc`.
  * **`day`:** Orders placed during the overnight session will remain active through the regular and after-hours sessions of the upcoming trading day. If unfilled, the order is canceled at 8:00 PM ET.
  * **`gtc`:** Good-Til-Canceled orders remain active across trading sessions until they are either filled or explicitly canceled. The table below summarizes the supported `gtc` configurations and their default corporate action handling.

## Overnight buying power (original lines 90-92)

### Are there restrictions on margin or buying power during the overnight session?

Yes. Day Trading Buying Power (DTBP) does not apply to the overnight session. This means 2x multiplier is the max margin buying power for overnight session trades. If an account uses DTBP for an order during the post market session, the order might be rejected (at 8 PM ET) due to insufficient buying power (if reg\_t or non-DT buying power is insufficient).
