# Per-lane paper risk ceilings (D6-b)

The CC's 2026-10-13 D6-b instruction follows observed acct-sized-v1 entries
binding the $10,000 per-order clamp. Keep frozen CONTROL configurations and
their original envelopes, while allowing a separately bound acct-v2 config
to name its own capital, per-order notional and quantity ceilings. This is a
paper-engine configuration change, not historical or qualification evidence.
New operational series repin only after this PR lands.

## Sources and origin

The original bounded small-trial ledger is native-agent-stack at
[`b2d7c5b2b0ac8f978dde95f4385336592d3d2869`](https://github.com/native-agent-stack/native-agent-stack/blob/b2d7c5b2b0ac8f978dde95f4385336592d3d2869/blueprints/us-equities/adaptive-paper/safety.py#L58),
`RiskLimits`: default capital 10000, order notional 1000 and quantity 1;
its validation caps capital at 1000000, order notional at min(gross,10000)
and quantity at 100. Those are desk envelopes, not broker account facts.

Official alpacahq/alpaca-py 0.44.0 at
[`cc4cb3b7ba50ae250e621983c2779047fb16bb28`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/requests.py#L333),
`OrderRequest` lines 333-380, represents qty/notional and their mutual
exclusion; it does not supply these desk ceilings. This change keeps the
existing official SDK transport and limit-order path. No broker calls were
made to establish new broker capacity or fills.

## Configuration and enforcement

The optional `risk_ceilings` object accepts only `capital_usd`,
`max_order_notional_usd`, and `max_order_quantity`. Example:

```json
"risk_ceilings": {
  "capital_usd": "2000000",
  "max_order_notional_usd": "40000",
  "max_order_quantity": 1000
}
```

Every missing key retains its old ceiling. Dollar ceilings use the existing
strict positive finite decimal parser (numeric domain <= 1e9); quantity is
a positive integer <= 1e9. Unknown keys, null, booleans, floats, nonfinite
values and out-of-domain values refuse. Explicit lower ceilings bind too.
Separately configured capital/order limits must fit the chosen ceilings.
The gross/leverage envelope, loss/drawdown ratios and all other guards stay.

Both adaptive and mover loaders use `risk_ceiling_kwargs` and `RiskLimits`.
The adaptive `PolicyConfig.max_shares_ceiling` receives only an explicit
quantity ceiling; absent or dollar-only overrides retain 10 shares without
the canonical leverage policy and 100 with it. Notional mode still takes
the minimum of configured quantity, quote-derived quantity and its selected
ceiling. The ledger enforces order quantity and qty times limit price on
reserve and the existing final-send validation path.

Explicit ceilings are included in frozen limits; absent fields are omitted,
preserving old journal bytes. Changed ceilings refuse ordinary reopening.
Lane-B rotation reconstructs the old registered envelope before the existing
reconciled registration transaction; no budget or account-state reset is
introduced. This PR does not add D7's separate capital-transition API.
The mover's independent entry-notional ceiling and 10x exit-headroom rule
remain unchanged.

## Measured local checks

Evidence class: synthetic/local integration, never a broker run. At base
24a209016178, the fail-first module ran 8 tests, rc 1: the 40000 config,
capital/quantity overrides and mover shared override were refused; malformed
ceiling blocks were ignored. The old 10000 ledger boundary already passed.
The regression module requires a 40000 reservation and refuses 40001,
pins both quantity modes and policy bindings, capital limits, invalid inputs,
frozen reopen/rotation behavior, and the raw CONTROL config hashes and
frozen-limit hashes captured before production edits. Existing policy golden
fixtures additionally check byte-identical default decisions.

## Follow-ups

- Acct-v2 series and generators must explicitly select and bind these fields
  after landing; no current series or protected runtime is changed here.
- D7's same-journal capital transition is separate and must preserve realized
  losses, cash, fees, fills, request history and prior config lineage.
- A wider mover entry envelope needs its own sizing/headroom measurement;
  the shared ledger ceiling alone does not widen the mover's entry cap.

An enforcement discrepancy or changed CONTROL frozen bytes overturns this
choice. Broker buying power/entitlement and the configured leverage schedule
remain independent checks; a larger ceiling does not establish either.
