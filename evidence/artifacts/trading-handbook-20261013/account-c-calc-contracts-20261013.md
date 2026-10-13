# Account C (agent-native paper lane): calculator contracts and observations, 2026-10-13

Publication-approved projection for the trading handbook. The CC wrote it from its own calculator source and receipts.
It contains no owner text, no local paths and no account identifiers. Account C is an Alpaca paper account traded by a
headless Claude agent through Alpaca's official MCP server. A deterministic calculator holds every number (selection,
sizing, exits, receipts), and the model only orchestrates tool calls.

## Selection (calculator v2.7 to v3.0)
- **Safety gates** (refuse when any fails):
  - ask $1-$2,000;
  - spread ≤ 150 bps;
  - quote ≤ 60 s and last trade ≤ 120 s old;
  - session dollar volume ≥ $1M;
  - day move > 0 (long-only);
  - not a leveraged or inverse ETP: a name rule needs a leverage or inverse marker AND a fund marker;
  - the cost gate: day move ≥ 4 × the quoted spread;
  - the deal-pin screen: a gap ≥ 10% whose session range is ≤ 1.5% is refused (a cash-deal pin);
  - the fade gate: refuse at ≥ 10% below the day high (the impulse has peaked).
- **Groups** (v3.0). Confidence = score ÷ the best eligible score of the SAME group in the round. It is a score share,
  not a calibrated probability.
  - impulse: the largest day moves. Score = day_move% × min(RVOL, 10) × vwap_factor × fade_factor.
  - trend: liquid most-actives (session dollar volume ≥ $50M) up on the day. Score = max(3-month return%, YTD return%)
    × min(RVOL, 3) × vwap_factor × fade_factor. A name with no positive 3-month or YTD return is refused.
  - vwap_factor = 1 at or above the session VWAP, else 0.5. fade_factor = 1 − fade% ÷ 10.

## Sizing (calculator v2.7 risk base, v2.9 halt awareness)
- **Base risk:** risk = equity × (0.25% + 0.75% × confidence), so 0.25% to 1.0% of equity.
- **Stop:**
  - trail% = 25% of the session range, clamped to 1.5%-10% (a broker trailing_stop per position);
  - halt-prone (v2.9, refined v3.0) = session range ≥ ½ × LULD band AND session dollar volume < $200M. The LULD band
    comes from the previous close: > $3.00 → 10% (the Tier 2 value, used because tier membership is not in the
    inputs); $0.75-$3.00 → 20%;
  - effective stop = max(trail%, band%) if halt-prone, else trail%.
- **Notional:** notional = risk ÷ effective stop, capped by:
  - 2% of the session dollar volume;
  - 25% of the gross cap per name;
  - gross ≤ 3 × equity (the broker's buying power is the real outer bound: it measured about 2.5× intraday on this
    account);
  - the gap budget: Σ over held halt-prone names of (notional × band) ≤ 6% of equity. A new halt-prone entry shrinks to
    fit, or is refused when the budget is used up.
- **Source:** the LULD bands come from luldplan.com, "Calculation of Price Bands": Tier 1, and Tier 2 below $3.00:
  > $3.00 5%, $0.75-$3.00 20%; Tier 2 > $3.00: 10%; doubled in the last 25 minutes for Tier 1 and for Tier 2 below
  $3.00; a pause in the last 10 minutes is not reopened.

## Exits
- **Broker trailing stop** at the per-name trail%, placed right after the fill.
- **No-progress stop:** a high-water mark below entry × 1.005 within 30 minutes of the fill → exit (cancel the trail,
  then a limit at the bid). The name is not re-entered.
- **Buying-power rotation** (v2.8): when an entry for a symbol with confidence ≥ 0.3 is refused for buying power, ONE
  held name is marked for exit: the held name not eligible in that round with the least progress (high-water mark ÷
  entry). Winners and still-eligible names rotate last or never. A rotated name is not re-entered.
- **Halt window** (v2.9): halt-prone positions exit from 15:25 ET, before the bands double at 15:35 and before a late
  pause could keep the account from going flat.
- **Time exit** at 15:45 ET and flat by 15:55 ET.
- **Restart without selling** (v2.6): a new trader segment reconciles the broker's positions and open orders against
  the calculator's state (the same symbols and quantities, each trail open as a sell trailing_stop for the full
  quantity, no other open order). It adopts on a match and refuses on any difference.

## Observations (regular session, SIP feed; times UTC)
| Name | Entry | Exit | Outcome | Lesson |
|---|---|---|---|---|
| BMBL | 13:36:07 buy 33 @ 5.97 limit, filled 5.96 (13:37:12); +56.7%, RVOL 1,207 | 13:42:46 flatten 33 @ 5.95 | −$0.33 | A cash take-private at $6.05 pinned near the deal price; move × RVOL cannot tell a pin from momentum. This led to the deal-pin screen. |
| CANG | 14:37:05 buy 11,447 @ 3.63 limit, filled 3.62 (14:37:11); +18.4%, RVOL 7.7 | 14:46:50 broker trail 11,447 @ 3.49 | −$1,488 (about 0.93% of equity, inside its 1% risk budget) | Bought late in the move; it reversed within 10 minutes. Risk sizing held the loss to plan. |
| VEEA | 14:37:22 buy 4,169 @ 5.55 limit, filled 5.54 (14:37:24); +18.0%, RVOL 5.0 | 15:10:37 broker trail 4,169 @ 5.81 | +$1,138 | The same entry rule followed through; the trail let it run. |

## Lessons recorded the same day
- Limits chosen for a smoke test ($200 per name, at most 2 names, a $5-$200 price band) are not a production design.
  Re-derive every numeric limit when a run moves from smoke to active trading.
- Name every tool argument a brief relies on from a measured working call. A guessed argument name made all 50 asset
  lookups fail and tripped the trader's tool-error stop rule, which flattened the account safely.
- The early-impulse check is a proxy (the fade from the day high). A streaming minute-bar scanner is assigned as the
  real early-stage detector.
