# Lane A OVERNIGHT stage-start acceptance

This draft qualifies the existing overnight REST port from #1081 at
`ea0a51a6b2a485977d8aaf8e11dc0e93fe820a06`. It is stacked on that implementation:
main at `04f64a056cade587f804da60f6a94f7852f7624d` still refuses an OVERNIGHT
stage start, and #1081 already supplies the missing admission branch.
This acceptance change adds tests and a record; it leaves production code,
CONTROL configurations, source-hash manifests and frozen trading bytes unchanged
relative to its parent. No deployment or broker acceptance is recorded.

The existing `sessions.validate_session_policy` requires BOATS REST, an explicit
enabled overnight block, coupled extended-hours flags, and disabled
`overnight_holds`. It supplies `overnight_enabled` and the configured flatten
lead to the runner. `extended_hours` alone admits PRE/RTH/POST but continues to
refuse OVERNIGHT. An opted-in overnight stage uses the 04:00 ET boundary for
its required duration/cleanup window. Its DAY order expiry is a separate,
later boundary: 20:00 ET on the upcoming trade date. A short remaining overnight
window cannot borrow that later expiry to admit a stage.

`must_end_flat` continues to require flat at every diagnostic boundary because
the overnight port forbids `overnight_holds`. Its flatten lead remains owned by
the port; this record does not widen it or promise that a resting limit fills.
The CC's 2026-10-13 06:11Z P1-B ruling requires a held position to retain an
exit path after 04:00: entries stay refused outside OVERNIGHT, while qualified
reduce-only exits use the existing guards in PRE/RTH/POST. #1081 supplies that
path. The existing regression executes the committed native dispatch plus
ledger/wire guards at 04:00:01 ET and refuses an oversell.

## Retained venue facts and test boundaries

The [public vendor capture excerpt](../../../evidence/artifacts/lane-a-overnight-acceptance-20261013/alpaca-245-trading-excerpt.md)
is retained from the same 2026-10-10 capture the overnight handbook cites.
Its supported overnight orders are LIMIT; DAY and GTC are supported, and the
current diagnostic factory emits DAY. Unfilled DAY orders carry to 20:00 ET
of their trade date. Day-trading buying power does not apply overnight; 2x is
the maximum margin buying power, a ceiling rather than a sizing target.

The acceptance tests invoke actual configuration/preflight/order normalization
with synthetic observations. Existing leverage regressions retain the 2x cap
and Reg-T refusal; these do not establish an account's entitlement. PRE/RTH/POST
and default-policy controls use the same real preflight, while production and
frozen configuration files are compared against the pinned parent without
rehashing them. Venue liquidity, entitlement, real-time BOATS status and data,
order execution, reconciliation and actual paper acceptance remain unmeasured.

## Primary sources

- Alpaca, [24/5 Trading](https://docs.alpaca.markets/us/docs/245-trading.md),
  vendor update 2026-07-07T14:17:11.000Z; retained capture excerpt above.
- native-agent-stack/native-agent-stack #1081 at
  `ea0a51a6b2a485977d8aaf8e11dc0e93fe820a06`: `runner.validate_preflight`,
  `sessions.validate_session_policy`, `order_extended_hours_flag`,
  `extended_session_close`, `must_end_flat`, and `overnight` port guards.
- NautilusTrader 2.0.0rc5 at
  `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`: `TradingState.REDUCING` and
  reduce-only admission in the risk engine, the source mechanism behind the
  existing P1-B exit path. This PR does not repeat a native engine E2E.

## Review and deployment boundary

This is a draft acceptance PR for local and two-family reads. #1081 must land
before this stack can retarget to main. Deployment, service/unit changes,
credential loading and account calls are outside this assignment.
