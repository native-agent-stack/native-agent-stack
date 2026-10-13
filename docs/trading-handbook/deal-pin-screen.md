# THE DEAL-PIN SCREEN

A proposed experiment needs a requirement, immutable implementation inputs and
an acceptance rule before it runs. The existing resolution protocol calls for
the layer verdict, the latest relevant sweep and unresolved candidates, then a
bounded action on changed evidence. A new survey does not settle an old
unresolved result.
[Source: layer-resolution protocol:27-67](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/decisions/2026-10-11-layer-resolution-protocol.md#L27-L67).

## Bind the screen to exact inputs

| Screen input | Evidence to retain |
| --- | --- |
| Requirement and candidate disposition | The applicable verdict, sweep, unresolved result and precise capability gap. [Resolution protocol:27-60](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/decisions/2026-10-11-layer-resolution-protocol.md#L27-L60). |
| Native engine and entry point | Release tag, source commit and maintained install/test path; the selected destination remains NautilusTrader 2.0.0rc5. [Runtime target:30-49](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/runtime-target.json#L30-L49). |
| Retained historical input | Source URI, content hash, identifier, availability and revision/adjustment convention. [North-star data contract:94-101](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/north-star.md#L94-L101). |
| Decision procedure | A fixed comparison rule and readiness trigger naming the inputs; a calendar date alone is insufficient. [Resolution protocol:88-105](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/decisions/2026-10-11-layer-resolution-protocol.md#L88-L105). |
| Acceptance scope | Separate historical replay, strategy quality and broker-specific paper qualification, with measured limits. [Paper policy:21-40](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L21-L40). |

## Follow the maintained engine path

NautilusTrader at `1b0a49d2792a9432a3aca3fcb617ce7a630d905e` exposes
`BacktestEngine` for directly loaded inputs and `BacktestNode` for configured,
catalog-backed runs. Choose the path that fits the retained input; do not add a
wrapper to replace an upstream capability.
[Source: APIs and runs:1-25](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/backtesting/apis-and-runs.md#L1-L25).

Lumibot's maintained native
[PandasDataBacktesting](https://github.com/Lumiwealth/lumibot/blob/862504052407df2586122b752a645f88ce87afa1/lumibot/backtesting/pandas_backtesting.py#L1-L15)
and [backtest entry](https://github.com/Lumiwealth/lumibot/blob/862504052407df2586122b752a645f88ce87afa1/lumibot/strategies/strategy.py#L5868-L5905)
provide source references for a comparator path. Inspecting that source is
**source_review**, not a measured acceptance at that pin. The historical
[September comparison](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/engine-trials/spy-one-zero-20260926/README.md#L20-L28)
used a different recorded pin and failed its primary rule. Preserve its outcome;
any later comparator acceptance needs a separately retained binding.

## Close or name the missing input

A selected source pin alone is not FINAL. The resolution contract additionally
requires a verdict, native end-to-end receipt and invoke evidence or a recorded
reason for no invocation. If the evidence cannot choose a winner, retain one
preregistered comparison and its named inputs; omission is not adjudication.
[Source: terminal states:69-113](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/decisions/2026-10-11-layer-resolution-protocol.md#L69-L113).

This screen is for research readiness. Already authorized paper work retains
its own broker, numeric-risk and recovery contract; it does not wait for a
handbook or unrelated research page to be completed.
[Source: paper policy:1-17 and 35-40](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L1-L40).

[Return to the handbook](README.md).
