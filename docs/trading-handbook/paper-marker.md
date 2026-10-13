# Paper markers and qualification boundaries

A paper marker records a step in admission or execution custody. Its presence is
**not evidence of a fill**, a flat account, a recovered order or a qualified
strategy. Paper authority, readiness and observed broker behavior are separate
claims; one broker's result does not qualify another. Sources:
[paper evidence contract][policy], [broker-specific selected-engine boundary][target].

## Read the implementation's status with the marker

The marker names below come from a **proposal in an open PR**, #1042 at
`8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd`. They describe that exact public helper
source, not a statement that the proposal has landed, is installed, or ran today.
Its review record labels its evidence source review and separately classified
synthetic/local integration checks, with no established broker acceptance or
production operation. Source: [proposal qualification boundary][proposal-record].

| Public helper artifact | What the cited proposal checks | What presence alone cannot establish |
| --- | --- | --- |
| `readiness.json` | Expected deployment/trial/configuration/session bindings, native preflight and writer-lock observations, a fresh observation no older than 30 seconds, flat state and account commitment | A later start, a fill or current flatness after the observation expires |
| `SCAN-READY.json` | Retained scan/input/commitment bytes; reread and revalidated binding before admission | Completed broker execution or independently proved producer completion time |
| `GO.sha256` | Commitment to the issued `GO.json`; publication after its metadata and sequence state are saved | Permission to disregard expiry, freshness, recovery, one-writer or halt checks |
| `GO.used.sha256` | The GO token moved into the trial after validation, before the native paper call | A successful native call, any order/fill, or a successful recovery |

Sources for the table: [readiness][readiness], [scan publication and revalidation][scan],
[GO issue][issue], [start validation and token consumption][start].

## Read admission as a sequence of checks

In the pinned proposal, issue checks halted/held and active-experiment state,
session readiness, availability, request-window state, sequence and previous
handoff, fresh readiness and the scan binding before publishing a GO commitment.
Start rereads the GO payload and its commitment, checks bindings and expiry,
rechecks admission conditions, then moves the token to its used marker before
invoking the native paper path. Thus an issued token is not a substitute for
start-time validation, and a used token precedes the outcome it may eventually
authorize. Sources: [issue][issue], [start][start].

The proposal's previous-stage handoff also requires a bound native recovery
result, flat positions/orders and a drained request window. A handoff name alone
does not satisfy those checks. The source's own review record retains interrupted
publication and recovery-persistence repair as follow-ups; this page does not
describe those gaps as settled. Sources: [handoff validation][handoff],
[retained proposal follow-ups][followups].

## Publish a result, not private marker contents

For public reporting, distinguish observed **pass**, **fail** and **inconclusive**
outcomes from admission metadata and synthetic checks. Keep the engine/adapter
version, task scope and measured result with the evidence; preserve unsuccessful
and unobserved cases. A connection or synthetic test does not establish strategy
quality or live readiness. Source: [paper result contract][policy].

The earlier operational record is cited by name only:
**main-8c95a50d-sequencing-v2**. Its private contents, marker values, account
bindings, paths and digests are not reproduced here. The name is a custody
reference, not publicly inspectable proof of any new operational result.

## Source boundaries

- Helper source citations below are immutable but belong to open PR #1042,
  rather than this handbook's landed base. Their behavior needs the proposal's
  own review and deployment evidence; source reading is not a broker replay.
- This page observes no live or paper endpoint and makes no current-day
  admission, account-state, order or recovery claim. The historical record name
  above supplies no missing public witness.
- The destination remains NautilusTrader 2.0.0rc5 through its native IBKR path.
  Adapter defaults distinguish paper ports from live ports, but a port or marker
  alone is not broker-specific acceptance. Sources: [selected engine][target],
  [pinned native adapter][adapter].
- This is a reading guide. It grants no authority to create, copy, reset or
  consume markers or to modify another process's control state. The required
  execution evidence remains the [paper contract][policy].

[policy]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L20-L49
[target]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/runtime-target.json#L30-L75
[proposal-record]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd/docs/decisions/2026-10-13-paper-deployment-review-fixes.md#L1-L6
[readiness]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd/blueprints/us-equities/adaptive-paper/paper_deployment.py#L897-L918
[scan]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd/blueprints/us-equities/adaptive-paper/paper_deployment.py#L828-L884
[issue]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd/blueprints/us-equities/adaptive-paper/paper_deployment.py#L952-L1006
[start]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd/blueprints/us-equities/adaptive-paper/paper_deployment.py#L1208-L1268
[handoff]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd/blueprints/us-equities/adaptive-paper/paper_deployment.py#L920-L950
[followups]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/8fc7b605b0e083f213aa4d9ecacf27ff02bc52fd/docs/decisions/2026-10-13-paper-deployment-review-fixes.md#L53-L64
[adapter]: https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/integrations/interactive_brokers.md#L23-L34
