# Smoke-test budgets and eligibility

Smoke-test affordability limits can silently become selection rules when
carried into a larger trial. The account-neutral public calculator policy
specification requires every numeric limit to be re-derived when a run moves
from a smoke test to active trading. A limit chosen for a test's safety needs
its own justification before becoming a strategy constraint.
[Public policy: practice notes](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md#practice-notes).

Instrument-price eligibility and position sizing are separate policy inputs.
The public specification lists an ask-price gate under Selection and a
risk/effective-stop calculation with notional caps under Sizing. A filter can
remove a candidate before those sizing rules run; increasing its price ceiling
does not itself increase an accepted position's budget.
[Public policy: selection](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md#selection)
and [sizing](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md#sizing).

For a synthetic illustration, `PRICE_MAX = 200` excludes a price of 201
regardless of whether a separate one-share test budget could fund it. This is
an arithmetic example, not a market observation or a recommended threshold.
The review question is why that constant exists: a cheap smoke test, an
independently defined strategy filter, a broker constraint or an inherited
default. Record the reason and measured population before reusing it.

The specification's sizing starts with equity and within-group confidence,
scales risk for drawdown, and divides risk by the effective stop before applying
notional, gross-exposure, buying-power, gap-budget and correlated-cluster caps.
Preserve those separate controls when reconsidering a smoke-only prefilter.
A constant's removal does not itself establish buying power, tradability,
quote freshness, liquidity or a profitable strategy.
[Public policy: sizing](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md#sizing).

The public v1 specification sets a $1-$2,000 ask-price gate and separate
impulse/trend candidate groups. This is a versioned policy specification,
not evidence of market-wide coverage, suitability, engine parity or measured
performance. It supplies no excluded-security count or before/after trading
result, so this page makes no such claim.
[Public policy: selection](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md#selection).

Keep a retained before/after record of the filter, its source revision and the
reason for each refusal. Re-evaluate the same frozen inputs after a change;
report the changed selection separately from order/fill or strategy outcomes.
Record the calculator version with each receipt, as the specification requires,
so results remain attributable to their own policy. This page cites only the
account-neutral public specification; account-specific observations are outside
its evidence scope.
[Public policy: architecture](../../evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md#architecture).
