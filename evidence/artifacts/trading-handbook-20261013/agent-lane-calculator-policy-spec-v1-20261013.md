# Agent-orchestrated paper lane: deterministic calculator policy specification v1

Approved for the PUBLIC repository. It is account-neutral: no account or slot identity, no observed balances or
leverage, no trade tables or incident accounts, no owner text, no paths, and no digest of any private file. It
specifies the policy only. Observations stay in the private trading repository.

## Architecture
- A language model orchestrates broker and market-data tool calls.
- A deterministic calculator holds every number: selection, sizing, exits, position state and receipts. The model
  never computes a size, price level or exit decision.
- The calculator reads its own clock, never a model-supplied time.
- Every receipt carries the calculator version and the run labels, so each rule version is evaluated on its own
  trades.

## Selection
- **Safety gates** (refuse when any fails):
  - ask $1-$2,000;
  - spread ≤ 150 bps;
  - quote ≤ 60 s and last trade ≤ 120 s old;
  - session dollar volume ≥ $1M;
  - day move > 0 (long-only);
  - not a leveraged or inverse ETP: a name rule requires a leverage or inverse marker AND a fund marker;
  - the cost gate: day move ≥ 4 × the quoted spread;
  - the deal-pin screen: a gap ≥ 10% with a session range ≤ 1.5% is refused;
  - the fade gate: refuse at ≥ 10% below the day high.
- **Two candidate groups:**
  - impulse: the largest day moves. Score = day_move% × min(RVOL, 10) × vwap_factor × fade_factor.
  - trend: liquid names (session dollar volume ≥ $50M) up on the day, with max(3-month return%, YTD return%) ≥ 40%.
    Score = horizon_return% × min(RVOL, 3) × vwap_factor × fade_factor.
  - vwap_factor = 1 at or above the session VWAP, else 0.5. fade_factor = 1 − fade% ÷ 10.
  - RVOL = session volume ÷ (median of the prior daily volumes × the elapsed session fraction, minimum 1/96).
- **Confidence** = score ÷ the best eligible score of the same group in the round. It is a score share, not a
  calibrated probability.

## Sizing
- **Base risk:** risk = current equity × (0.25% + 0.75% × confidence).
- **Drawdown control:** risk is scaled by max(0.25, 1 − dd ÷ 6%), where dd is the drop of current equity below the
  day's first equity. This follows the drawdown-constrained sizing principle of Grossman and Zhou (1993), "Optimal
  investment strategies for controlling drawdowns".
- **Stops:**
  - trail% = 25% of the session range, clamped to 1.5%-10% (a broker-held trailing stop per position);
  - halt-prone = session range ≥ ½ × LULD band AND session dollar volume < $200M;
  - effective stop = max(trail%, band%) when halt-prone.
- **LULD bands,** from luldplan.com, "Calculation of Price Bands": Tier 1 and Tier 2 below $3.00: > $3.00 5%, $0.75-$3.00
  20%; Tier 2 > $3.00: 10%. They are doubled in the last 25 minutes for Tier 1 and Tier 2 below $3.00. A pause in the
  last 10 minutes is not reopened.
- **Notional:** notional = risk ÷ effective stop, capped by:
  - 2% of the session dollar volume;
  - 25% of the gross cap per name;
  - gross ≤ 3 × equity (the broker's buying power is the outer bound);
  - the gap budget: Σ over halt-prone holdings of (notional × band) ≤ 6% of equity;
  - the correlated-cluster cap: refuse a candidate whose prior daily returns correlate ≥ 0.7 with two or more held
    names (at least 6 common returns).

## Exits
- **Broker trailing stop** at the per-name trail%.
- **No-progress stop, impulse group only:** a high-water mark below entry × 1.005 within 30 minutes of the fill →
  exit. The name is not re-entered.
- **Buying-power rotation:** a refusal for buying power of a candidate with confidence ≥ 0.3 exits the held name that
  is not eligible in that round and has the least progress (high-water mark ÷ entry).
- **Halt window:** halt-prone positions exit from 15:25 ET.
- **Time exit** at 15:45 ET; flat by 15:55 ET.
- **Restart without selling:** a new run reconciles the broker's positions and open orders against the calculator's
  state (the same symbols and quantities, each trail open for the full quantity, no other open order). It adopts on a
  match and refuses on any difference.

## Practice notes
- Re-derive every numeric limit when a run moves from a smoke test to active trading. Limits chosen for a test's
  safety are not a production design.
- Name every tool argument the instructions rely on from a measured working call.
- Send long candidate lists to the calculator in small batches: a single long command can be refused by an agent
  client's permission layer.
