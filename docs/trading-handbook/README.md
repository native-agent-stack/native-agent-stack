# Trading handbook

This index links source-backed procedures for historical research and separately
qualified paper operation. The selected engine is **NautilusTrader 2.0.0rc5**,
at `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`; engine installation, a historical
replay and a broker-specific paper result are separate claims. The published
[runtime target at the input revision](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/catalogs/us-equities/runtime-target.json#L30-L49)
records that selection and its acceptance limits.

| Procedure | Read it for |
| --- | --- |
| [THE ASSET RULE](asset-rule.md) | Distinguishing instrument identity, product characteristics and broker eligibility. |
| [THE DEAL-PIN SCREEN](deal-pin-screen.md) | Binding a proposed engine/data experiment to exact requirements, source pins and evidence. |
| [THE NO-PROGRESS STOP](no-progress-stop.md) | Recognizing a blocked research step and preserving deterministic stop/recovery boundaries. |

Two companion chapters are available for review in [draft PR #1077](https://github.com/native-agent-stack/native-agent-stack/pull/1077):
[Portfolio sizing: evidence and limits](https://github.com/native-agent-stack/native-agent-stack/blob/65f4bdb615610552cc1ac8f2b9d93172ca64fc74/docs/trading-handbook/portfolio-sizing.md)
and [BOATS overnight: verified facts and limits](https://github.com/native-agent-stack/native-agent-stack/blob/65f4bdb615610552cc1ac8f2b9d93172ca64fc74/docs/trading-handbook/boats-overnight-facts.md).
These links identify the submitted source revision, not a landed acceptance.
**IBKR pacing and request boundaries** (`ibkr-pacing.md`) and
**Paper markers and qualification boundaries** (`paper-marker.md`) are pending
publication; they will become links when reviewed files are available. The
index does not substitute a draft chapter for an execution contract.

## Evidence and scope

These pages are **source_review**, prepared on 2026-10-13. They describe native
mechanisms and published requirements; writing the handbook executes no
backtest, changes no gate and establishes no strategy or broker qualification.
Retained source bytes, parser behavior, historical availability and acceptance
remain distinct, as required by the
[trading rules](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/AGENTS.md#L24-L51).

The pages use the existing public records and maintained upstream sources in
[the retained input inventory](sources.json). No market-data acquisition is
needed for this documentation. A daily instrument selection, a strategy limit
or a new comparator result needs its own retained, publication-safe record;
none is inferred from this handbook. The
[research data contract](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/north-star.md#L94-L113)
requires as-known inputs and distinguishes diagnostic results from strategy
evidence. Private operational records are not included in this source inventory.

Historical and paper work use their recorded configuration boundaries. A paper
result does not authorize a switch to a live endpoint or establish live
readiness. This handbook is not an additional approval gate for already
authorized paper work; it preserves the separate input and acceptance contracts
described by the
[paper policy](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L9-L40).

## Engine and comparator references

Use the selected engine's native
[BacktestEngine or BacktestNode path](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/backtesting/apis-and-runs.md#L1-L25)
for the applicable retained data layout. The handbook adds no engine wrapper.
Lumibot has a maintained
[native historical-data adapter](https://github.com/Lumiwealth/lumibot/blob/862504052407df2586122b752a645f88ce87afa1/lumibot/backtesting/pandas_backtesting.py#L1-L15)
and [strategy backtest entry](https://github.com/Lumiwealth/lumibot/blob/862504052407df2586122b752a645f88ce87afa1/lumibot/strategies/strategy.py#L5868-L5905).
Those source references document a comparator implementation; they do not
qualify that revision for a new comparison or replace the selected engine.
The retained
[earlier Lumibot comparison](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/engine-trials/spy-one-zero-20260926/README.md#L20-L28)
has its own pin and failed primary result. A later accepted comparator path
must carry its own source/data/acceptance binding; the two must not be conflated.
