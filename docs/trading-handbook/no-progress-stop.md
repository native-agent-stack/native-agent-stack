# THE NO-PROGRESS STOP

A missing research input, an unresolved broker response and an outstanding
position require different handling. Keep the bounded research stopping rule
separate from native execution cleanup. Research closure requires retained
evidence and a named disposition; broker cleanup requires reconciliation and
the recorded numeric-risk contract.
[Sources: bounded research rule:89-101](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/landscape-continuation.md#L89-L101)
and [paper trial contract:21-40](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L21-L40).

## Research: change the evidence, not the calendar

When a comparison lacks a required input, record that input and the fixed
decision rule. Start when those named inputs exist; restarting the survey
without changed evidence does not resolve it. A closed review reopens on a
changed requirement, credible missing capability, retained failure or new
comparison, rather than by adding more candidates to its count.
[Sources: readiness and terminal states:88-113](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/decisions/2026-10-11-layer-resolution-protocol.md#L88-L113)
and [bounded stopping rule:97-101](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/landscape-continuation.md#L97-L101).

For a paper experiment, freeze numeric timeouts, observation window and the
disposition of outstanding orders and positions before execution. Record
pass, fail and inconclusive outcomes without reducing the rule after observing
a run. This page invents no universal elapsed-time, retry-count or profitability
threshold.
[Source: paper policy:21-40](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L21-L40).

## Execution: a stopped strategy is not proof of a flat book

Use the selected upstream's lifecycle before adding recovery glue. Nautilus
documents `on_stop` for cleanup and explicitly asks whether a strategy needs to
cancel orders, close positions or unsubscribe from data.
[Source: strategies.md:85-103](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/strategies.md#L85-L103).

At v2.0.0rc5, `manage_stop` defaults to false. With `manage_stop=True`, `stop()`
performs a market exit before stopping, but may finish after reaching
`market_exit_max_attempts` while orders or positions remain outstanding.
The documented attempt and interval defaults describe the engine; they are
not an accepted operational timeout for a new trial.
[Source: strategies.md:716-740](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/strategies.md#L716-L740).

The same pin warns that a managed stop requested at the end of a backtest
cannot complete its scheduled exit checks after the run ends. An error or
remaining RUNNING state in that case must be interpreted with the actual
order/position evidence. `close_position` and `close_all_positions` submit
closing market orders while leaving the strategy free to submit new orders;
they are not equivalent to a completed stop-and-reconcile procedure.
[Source: strategies.md:726-745](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/strategies.md#L726-L745).

Retain durable intent, one deterministic writer and reconciliation for ambiguous
responses; query the broker state instead of blindly retrying an order. Verify
the outcome independently of model availability. The paper acceptance contract
keeps disconnect, duplicate-intent and restart cases distinct from a finite
successful fill.
[Source: north-star execution boundary:154-172](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/north-star.md#L154-L172).

[Return to the handbook](README.md).
