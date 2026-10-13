# THE ASSET RULE

Instrument identity, product characteristics and permission to submit an order
are separate checks. A syntactically valid symbol is insufficient: the existing
[order-contract boundary](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/order-contract/README.md#L7-L35)
explicitly leaves asset eligibility, risk and provider validation outside its
local syntax check.

## Check the native instrument and the intended use

NautilusTrader's pinned `Equity` represents a listed share, ETF or similar
cash-market security. Its documented fields include instrument identity, native
symbol, currency, price increment, quantity bounds and timestamps; its quantity
precision is zero. Preserve those native semantics when preparing a replay or
order contract. A product's name does not supply missing metadata.
[Source: NautilusTrader v2.0.0rc5, equity.md:3-39](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/instruments/equity.md#L3-L39).

Broker metadata describes a different boundary. The official Alpaca SDK
separately exposes `status`, `tradable`, `marginable`, `shortable`,
`easy_to_borrow`, `fractionable` and `attributes`. A true value for one field
does not substitute for the others; the SDK also documents non-tradable assets.
Use the fields required by the intended order and its recorded contract rather
than treating a discovered symbol as automatically eligible.
[Source: alpaca-py v0.44.0, models.py:31-70](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/models.py#L31-L70).

Do not infer a leveraged or inverse product policy from the engine's type name.
The native `Equity` model's lack of an inverse costing flag describes that
model's accounting fields; it does not certify a fund's payoff, leverage,
current broker eligibility or historical availability. Resolve the intended
instrument through its recorded data and risk contract.
[Sources: equity.md:35-40](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/instruments/equity.md#L35-L40)
and [frozen trial inputs](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L21-L32).

## Preserve the historical boundary

Retain the symbol identifier, source revision, event time, first available time,
ingestion time and adjustment convention with the dataset. Current tradability
does not reconstruct an earlier investable universe. Include delistings and
corporate actions in the evaluation's declared scope; a replay that omits them
must disclose that limitation.
[Source: north-star.md:94-113](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/north-star.md#L94-L113).

Use upstream data capabilities first. The trading data-integrity boundary
permits glue only for a demonstrated remaining gap, with pinned sources and a
historical-data end-to-end backtest through the upstream engine before a
strategy number is cited.
[Source: trading rules:39-51](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/blueprints/us-equities/AGENTS.md#L39-L51).

This page records checks, not a daily approved product list. A run uses its
own retained instrument, session, data, numeric-risk and paper-execution
contract; the handbook does not create those inputs.
[Source: paper policy:21-40](https://github.com/native-agent-stack/native-agent-stack/blob/993cc890b3ff3fc95fa7cdba51edd726565f9ace/docs/paper-lane-policy.md#L21-L40).

[Return to the handbook](README.md).
