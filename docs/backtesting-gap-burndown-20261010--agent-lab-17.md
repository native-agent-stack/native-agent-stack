# Gap evidence wave `backtesting-gap-burndown-20261010` (agent-lab-17 layers)

This page summarizes [`catalogs/landscape/backtesting-gap-burndown-20261010--agent-lab-17.json`](../catalogs/landscape/backtesting-gap-burndown-20261010--agent-lab-17.json). It records the executed checks for the `executable_now` gaps the [crosswalk](gap-crosswalk-92bb279.md) assigned to `agent-lab-17`, keyed to the rows at `92bb279`. New receipts await independent review in the PR. No verdict changes here.

Rule: status is the best credit over the receipts naming the gap; settles_gap true/partially/false credit settled/advanced/not_settled, but a receipt naming several gaps credits each at most advanced; not_run means no receipt names the gap. No verdict changes here.

## Totals

| Status | Gaps |
| --- | ---: |
| settled | 3 |
| advanced | 3 |
| not_settled | 0 |
| deferred | 2 |
| not_run | 0 |

Receipts: 8; native model calls recorded: 0.

## Per gap

| Layer | Gap | Status | Receipts |
| --- | ---: | --- | --- |
| backtesting-engine | 0 | advanced | [0-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/0-gap.json) |
| backtesting-engine | 1 | deferred | [1-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/1-gap.json) |
| backtesting-engine | 2 | settled | [2-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/2-gap.json) |
| backtesting-engine | 4 | advanced | [4-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/4-gap.json) |
| backtesting-engine | 6 | settled | [6-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/6-gap.json) |
| backtesting-engine | 7 | settled | [7-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/7-gap.json) |
| backtesting-engine | 8 | deferred | [8-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/8-gap.json) |
| backtesting-engine | 9 | advanced | [9-gap](../evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/9-gap.json) |

## Receipts that refute the incumbent

None.

## Limits

- A status records what a receipt shows about the gap text at the source revision; a later re-record needs a new crosswalk.
- `not_run` gaps stayed open for the reasons recorded in the units' results (budget, shared-account window, or a check that needs the user).
