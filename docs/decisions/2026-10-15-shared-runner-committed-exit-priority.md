# Shared runner committed exit targets and reason priority

## Scope and status

This fresh change starts from main
`9cf1225581ffca6ea42e30076ddd7ac9074f828f`, carries all sanitized content of
PR #1091 at `7511c8ae350f4e1b868b097fb163284a4822ff12`, and corrects the
unchanged-target, changed-reason case described below. #1091 remains parked;
this change requires fresh full reviews by both review families and the CC.
The CC retains landing ownership. The overnight-admission work in #1095
remains dependent on the prerequisite landing.

The carried change includes whole-share sell chunking, durable reduction
targets, completion and scale-in handling, refusal pacing and reconciliation,
typed native denial handling, integrity-loss cancellation, isolated fixtures,
and the integration with landed #1119. Its historical evidence remains in
[the sell-chunk decision](2026-10-13-adaptive-paper-sell-chunks.md). The new
behavior is confined to reason priority in `exits.py` and the durable commitment
and cancel-acknowledgement paths in `native_strategy.py`.

## Problem and decision

With 100 shares held at 100.00, a quote of 100.50 triggers a full take-profit
target of zero. The $10,000 envelope permits an initial 99-share limit at
100.48; it remains unfilled. A subsequent quote of 99.70 triggers stop-loss,
also with target zero. The parked patch updates durable state only for a
lower target or a new cycle, so it retains `take_profit`. With a replacement
tolerance of 100 bps the roughly 80 bps price move does not request a cancel;
at zero tolerance it requests cancellation but stages the old take-profit
reason. The stop's changed price rule is lost in both cases.

An unfinished commitment now strengthens along two independent dimensions:

- The target is the minimum of its previous target and a newly proposed
  target. A stronger reason cannot relax an already committed reduction.
- The reason follows the fixed order below, promoting only. A tighter target
  or later weaker signal cannot downgrade the existing reason. Repeated
  fractional take-profit retains its existing target; completed cycles keep
  their existing re-arming behavior.

The persistence order, strongest first, is:

| Rank | Reason |
| --- | --- |
| 11 | `trial_end` |
| 10 | `rotation_flatten` |
| 9 | `corporate_action_flatten` |
| 8 | `gap_risk_stop` |
| 7 | `risk_off` |
| 6 | `quote_stale` |
| 5 | `stop_loss` |
| 4 | `trailing_stop` |
| 3 | `time_exit` |
| 2 | `take_profit` |
| 1 | `portfolio_rotation` |
| 0 | `rebalance` |

Unknown reasons rank below these known reasons. Equal priorities retain the
existing reason. This order governs an unfinished commitment; the policy's
first-matching-rule order for a new decision is unchanged. Forced liquidation,
corporate-action and gap priority follow the existing guard precedence. Risk
and expiry strengthen an outstanding profit-taking commitment.

There is a second timing boundary: a stronger reason may arrive after a
cancel request but before its acknowledgement. The strategy now refreshes the
staged reason and price rule from the stronger unfinished durable commitment
before the acknowledgement-time guards and submission. It still waits for
cancellation before submitting a replacement, uses a fresh quote and the
current owned quantity, and applies the existing share/notional envelope.

Existing replacement enablement, attempt limits, minimum intervals, refusal
state and session/freshness guards continue to apply. Reason promotion does
not grant permission to bypass them. These fixtures establish exit mechanics;
they do not establish a broker fill, strategy profitability or operating
qualification.

## Fail-first evidence

Receipts are in
`evidence/artifacts/adaptive-paper-committed-exit-priority-20261015/`.

| Case | Bare main at the pinned base | Main plus carried #1091 | Corrected |
| --- | --- | --- | --- |
| Full TP then stop, 0 bps tolerance | Passes | Cancels with stale TP reason | Cancels and replaces with stop |
| Full TP then stop, 100 bps tolerance | Passes | No cancel requested | Cancels and replaces with stop |
| Stop arrives while TP cancel is pending | Stale TP replacement | Stale TP replacement | Stop reason and price rule at acknowledgement |
| Lower target with a weaker proposed reason | Not asserted | Downgrades the reason | Keeps stronger reason and lowers target |
| Stronger reason with a higher proposed target | Not asserted | Retains TP reason | Keeps target zero and promotes stop |
| Stop, gap and corporate-action promotion; journal reopen | Not asserted | First promotion fails | All promotions and persistence pass |
| New position after a completed stop | Not asserted | Passes | Passes |

The exact stop cases use real policy decisions and a private durable Ledger.
They set the policy share cap to 99 so bare main's first order fits the same
$10,000 envelope; the carried implementation derives that chunk from the
ledger envelope itself. The order factory and broker acknowledgements are
synthetic. Gap/corporate-action outcomes and the two independent-axis cases
use explicitly synthetic inputs to the real strategy and Ledger.

The seven-test fail-first run has six assertion failures, no errors or skips;
the lifecycle control already passes. The corrected focused run passes all
seven. Bare main passes the two exact tolerance controls and separately fails
the pending-cancel case. The record therefore does not claim that the exact
100-bps regression exists on bare main.

The complete bounded runtime run passes 576 tests with no failures, errors or
skips: 208 core, 159 transport/stream, 202 policy/extended/corporate-action, and
seven native integration tests. Fourteen existing temporary-directory
ResourceWarnings remain visible. Commands use the pinned CPython 3.12.3 /
NautilusTrader 2.0.0rc5 / alpaca-py 0.44.0 runtime, `nice -n 19`, a network
namespace, an explicit checkout source root, and private fixture state.

## SOTA sources

- The maintained native-agent-stack reference at the pinned main base:
  [reason-to-price-rule mapping and stop rule](https://github.com/native-agent-stack/native-agent-stack/blob/9cf1225581ffca6ea42e30076ddd7ac9074f828f/blueprints/us-equities/adaptive-paper/exits.py#L83),
  [replacement rule/price comparison and staging](https://github.com/native-agent-stack/native-agent-stack/blob/9cf1225581ffca6ea42e30076ddd7ac9074f828f/blueprints/us-equities/adaptive-paper/native_strategy.py#L1171),
  [corporate-action precedence](https://github.com/native-agent-stack/native-agent-stack/blob/9cf1225581ffca6ea42e30076ddd7ac9074f828f/blueprints/us-equities/adaptive-paper/corporate_actions.py#L26),
  and [forced-exit reason vocabulary](https://github.com/native-agent-stack/native-agent-stack/blob/9cf1225581ffca6ea42e30076ddd7ac9074f828f/blueprints/us-equities/adaptive-paper/strategies.py#L148).
  The source read and the bare-main controls agree on the replacement mechanism.
- The failing durable commitment is pinned by
  [the parked implementation](https://github.com/native-agent-stack/native-agent-stack/blob/7511c8ae350f4e1b868b097fb163284a4822ff12/blueprints/us-equities/adaptive-paper/native_strategy.py#L1135).
  The carried production bytes equal that source before this fix. The new
  fixed priority is an explicit local persistence policy, not a vendor claim.
- The carried whole-share implementation retains the supported native
  quantity/event contracts from
  [NautilusTrader at 1b0a49d2792a9432a3aca3fcb617ce7a630d905e](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/types/quantity.rs#L126)
  and its [native risk precision guard](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/src/engine/mod.rs#L2148).
  Existing source pins and evidence for all other carried mechanisms remain
  in the sell-chunk decision. No new engine, adapter, dependency or harness is
  adopted, and no landscape layer is reopened by this bounded correction.

## Review brief and provenance

Review the full carried change from main, explicitly including the
**unchanged-target, changed-reason** sequence and a stronger reason arriving
while cancellation is outstanding. Also inspect independent target/reason
monotonicity, completed-cycle re-arming, and guard ordering at replacement.

The triggering records are cited by name only:
`pr1091-7511c8ae/review_output.json` and
`ruling-cc-20261015T1553Z-pr1091-park-exit-reason.md`. No unpublished review or
helper content digest is bound here. The nine removed provenance commitments
remain excluded. Dated historical receipts remain unchanged; their two
existing host-local review locators retain their separately recorded
portability follow-up.

All other recorded P3 follow-ups remain separate. No live paper unit,
credential store, broker endpoint, runtime lock, STOP or ISSUER-HOLD is used or
changed by this work. Tests use private temporary guard paths and block host
STOP access before filesystem inspection.
