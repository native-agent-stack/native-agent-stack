# T22 sources and corrections, 2026-10-09

The ten §6 families and three preset columns are untested hypotheses beside the
frozen #16 study. The scope record is us-equities-trading #25 at
`b0994749ca6c52ad07cb3bb70e8b5b6cd4fac910`, read through `git show` after fetching
the PR head. No rank rows, labels or study arms are inputs to these classes.

The landed amendment, us-equities-trading #47 at
`2e0860ccd1d485593d1bd31b8a97c12198ca6b3d`, supersedes exit/scope assumptions:
`docs/decisions/2026-10-09-equities-intraday-scope.md` D1/D2 and the T22 re-plan.
It keeps equity families, pauses option-order families without deleting their
references, and treats exit timing as a versioned parameter measured in research.
All four timing candidates remain untested; none is selected by these fixtures.
The options-flow-to-stock family remains equity-only and OD3-gated.

The timing implementation reuses adaptive-paper's existing session helpers and
`gerrymanoim/exchange_calendars@dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a`
(4.13.2): native XNYS `session_open`, `session_close` and `date_to_session`.
The mirror HEAD was re-verified for this change; no calendar, classifier, engine
or adapter is rebuilt or forked. Nautilus's pinned native `Equity` instrument
type supplies the order-asset gate, rather than inferring it from a symbol or
an option underlying's EQUITY asset class.

T15 owns the shared rich exit disposition and session/adapter capability seam.
Its current #940 interface has ExitContext session/bid/ask and ExitDecision
submit/flag_position/price_rule/limit_price. T22 will bind that accepted interface
at its CC-cued final rebase after #940. Until session support and acceptance,
an overnight research candidate holds and flags at execution. It is not a
blanket-refused candidate or an implicit permission to submit overnight orders.

The requested upstream mirrors were inspected read-only and their native Git
HEADs and clean trees verified. None of the inspected sources ships the complete
Nautilus family/preset interface. This is the demonstrated gap: original family
predicates over available factor observations, configured through registered
presets, with upstream engine callbacks. The engine, market calendar, exit chain,
fill models, latency model, broker transport and request governor are reused.

| Source | Exact pin | Inspected files and disposition |
| --- | --- | --- |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, version `2.0.0rc5` | `python/pyproject.toml`; `python/nautilus_trader/{trading,common,execution,backtest}/__init__.pyi`; `python/tests/unit/backtest/test_backtest_engine_{surface,custom_data,default_ids}.py`; `crates/model/src/data/custom.rs`. Selected native engine, unchanged wheel. |
| Nautilus regression candidate | `7b766f8825b2539c5b2ac1375e9d97b41c509edb`, version `2.0.0rc6` | `python/pyproject.toml`, same APIs. T13 owns candidate acceptance; this lane retains rc5. Shallow mirrors have no local tag refs; versions are verified in source. |
| [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) | `eab8d5cb97b9982d915944cdaa2df972fa396b22`, MIT | `skills/stockbee-episodic-pivot-analyzer/references/ep_methodology.md`; `breakout-trade-planner/references/minervini_entry_rules.md`; `stockbee-momentum-burst-screener/references/{momentum_burst_methodology,entry_exit_rules}.md`; `vcp-screener/references/vcp_methodology.md`; `position-sizer/references/sizing_methodologies.md`; PEAD screener references. Isolated candidate install, own checks and inverses are required. |
| [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading) | `ddfee8bb548bd6914191cb8fdb695d533ae16b0d`, no top-level licence | `static/strategies/{short-interest-effect-long-short-version,earnings-announcement-premium,trend-following-effect-in-stocks,short-term-reversal-in-stocks}.py`; conceptual source review only. No source copied. Classes use LEAN `QCAlgorithm`. |
| [alpacahq/gamma-scalping](https://github.com/alpacahq/gamma-scalping) | `c80b5e36f4b375b2c096d1370f6d5962f5abb630`, MIT | `README.md`, `strategy/hedging_strategy.py`: option-delta hedging using Alpaca and asyncio. Adjacent architecture, not stock options-flow entry evidence. |
| [alpacahq/options-wheel](https://github.com/alpacahq/options-wheel) | `3698429289065ceb0c13ffcdc31a966c576779ad`, Apache-2.0 | `README.md`, `core/strategy.py`: option selection and wheel orchestration. Adjacent only. |
| [PyneSys/pynecore](https://github.com/PyneSys/pynecore) | `2adbab448ad8f7349706ba4a2f5f9d34ea726496`, version `6.10.8`, Apache-2.0 | `docs/reference/lib/strategy.md`: Pine-compatible decorator/runtime; T16 owns parity, not a replacement for Nautilus. |
| [Lumiwealth/lumibot](https://github.com/Lumiwealth/lumibot) | `862504052407df2586122b752a645f88ce87afa1`, GPL-3.0 | `lumibot/example_strategies/{stock_momentum,stock_bracket,stock_limit_and_trailing_stops}.py`: Lumibot classes, reference only here. |
| [stefan-jansen/alphalens-reloaded](https://github.com/stefan-jansen/alphalens-reloaded) | `97e8389f9cb0e28a01b6d7024194af5cf614e4e1`, version `0.4.5`, Apache-2.0 | `src/alphalens/performance.py`: diagnostics; T21 owns adoption. No execution Strategy implementation. |
| [cvxgrp/cvxportfolio](https://github.com/cvxgrp/cvxportfolio) | `b3f9d75fd6cc4ee42f8f4e918e2532ce3e429b3d`, version `1.5.1`, GPL-3.0 | `examples/paper_examples/rank_and_spo.py`, policy interface: portfolio optimization, reference only here. |
| [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | `f0d2afba7af8a6e6c1b02afde27c9a16413e86ff`, version `1.1.2`, Apache-2.0 plus Commons Clause | New TCC dispatch at 20:03:51Z: `vectorbt[rust]` for fast sweeps. README's published wheel route, `pyproject.toml` exact Rust extra, `.github/workflows/tests.yml` and unchanged `tests/test_engine.py` engine/portfolio parity and inverse checks. Isolated candidate, never the rc5 strategy order path. |

The owner later removed licence as an adoption gate in this private environment
(co-op direction recorded 2026-10-09T19:46:28Z). The source licences above remain
recorded. That permission does not establish a need to copy or replace an engine.
This implementation continues to use conceptual AST references and no GPL source.

The subsequent vectorbt dispatch adds a shared T13/T22 adoption receipt. T13
assigned the one acceptance run to T22 to avoid duplicated heavy jobs. The exact
1.1.2 PyPI releases and vendor tag SHA were checked directly; the initial mirror
manifest did not yet include vectorbt, so its pin/path question was routed. A
separate candidate environment installs the published precompiled Rust wheel;
the source checkout is used only for unchanged vendor tests. Any future sweep
survivor must be re-tested through Nautilus with T13. This work runs no strategy
sweep and cites no candidate performance.

## Corrections to the draft's reference claims

- The AST short-interest concept is long low short interest and short high short
  interest. The squeeze family is explicitly the opposite-sign, long-only
  hypothesis. The AST example uses `SHORTVOLUME` in its Quandl data class; that
  plumbing is not accepted as outstanding short-interest measurement.
- AST `earnings-announcement-premium.py` describes monthly volume concentration
  and expected announcers, not post-earnings drift. The T22 event/gap/volume
  predicate is simplified event momentum. It is not a reproduction of that file.
- AST trend uses all-time closing highs and a ten-period ATR trailing rule. The
  high flag and ATR are supplied from previously known upstream-derived inputs.
  Preset ATR bands are separate hypotheses, not a claim to reproduce the paper.
- AST reversal is a weekly long-short portfolio. T22's five-session long-only
  control is a deliberate variant. No unlicensed implementation was copied.
- Generic CTS breakout and VCP references do not implement a complete premarket,
  float-normalization or halt-reopen strategy. Numeric gates in registry.json are
  newly registered hypotheses. Missing fields suppress entry.

## Published references

- Boehmer, Huszar and Jordan, *The Good News in Short Interest*, SSRN record
  (2009), [DOI 10.2139/ssrn.1405511](https://doi.org/10.2139/ssrn.1405511).
- Frazzini and Lamont, *The Earnings Announcement Premium and Trading Volume*,
  NBER Working Paper 13090 (2007), [DOI 10.3386/w13090](https://www.nber.org/papers/w13090).
- Bernard and Thomas, *Post-Earnings-Announcement Drift: Delayed Price Response
  or Risk Premium?*, Journal of Accounting Research 27 (1989),
  [DOI 10.2307/2491062](https://doi.org/10.2307/2491062).
- Wilcox and Crittenden, *Does Trend Following Work on Stocks*,
  [source-linked publication](https://www.cis.upenn.edu/~mkearns/finread/trend.pdf).
- de Groot, Huij and Zhou, *Another Look at Trading Costs and Short-Term Reversal
  Profits*, SSRN record (2011), [DOI 10.2139/ssrn.1605049](https://doi.org/10.2139/ssrn.1605049).

Publication identifiers are bibliographic leads; Crossref records were checked,
the primary NBER page was retrieved, SSRN returned HTTP 403, and the trend PDF
was not parsed. The predicates are hypotheses, not paper replications.

## Execution choice and overturn condition

The existing adaptive-paper adapter supports simple LIMIT/DAY and rejects
replacement. T15 owns native advanced-order contract/adapter qualification.
`code-managed-limit-v1` is therefore separately registered, and the target
advanced-order profile refuses without submitting. The simple profile reuses
`exits.py` and sends fresh-quote limit exits in PRE/POST as R9 requires. A resting
order is canceled and replaced only after native terminal confirmation; a halt
suspends repricing. The paper governor still budgets all actual requests.

This choice is replaced when T15 exposes an accepted capability interface and
same-input simulations plus hana's review show the target plans behave through
the native adapter. Portability of the Strategy class does not itself qualify
paper adoption, broker order types or overnight sessions. Historical Layer 1.5
E2E, LEAN strategy-matrix reconciliation, cost/delay sensitivity and T16 Pine
parity remain distinct gates. No strategy performance number is cited here.

## Review correction at 216bed68

The TCC's three P2 findings were reproduced against the reviewed head. The
unclassified vectorbt pytest expression is now under `pytest_k_expression`, and
its actual adoption disposition is classified as a withheld label in the
existing blind-export vocabulary. No test or export policy was relaxed.

The same-family registration reproduction raised rc5's native already-registered
error; identical specs at two engine times also generated different default
client IDs. At `nautilus_trader@1b0a49d2`,
`crates/system/src/trader.rs:566-578` checks the configured StrategyId's final tag,
and `OrderFactory.limit` accepts an explicit `ClientOrderId`. T22 now derives the
ID/tag from family, preset, explicit stable instance, instrument, profile and
cohort, and restores its seven-digit client sequence from the existing durable
ledger's maximum matching intent, following `native_strategy.py:102-104` and
`:1018-1026`. Dirty ledger/cache startup refuses entry; a prior terminal entry
attempt remains consumed. The wire governor retains reserve-before-send.

The new native regressions exercise four instances in one engine and one real
LiveNode, fixed IDs under a shifted engine clock, maximum-sequence restoration,
unresolved/position refusal and a real synthetic ambiguous LiveNode submit,
followed by closing/reopening the SQLite ledger and proving no new submission.
Supplying the ledger also exposed rc5's PyO3 allocator keyword boundary; a thin
subclass `__new__` now leaves Python-only dependencies for `__init__`. Both
repository generators rerun in the unchanged T13 rc5 environment, with no native
test skips. Overnight paper/session qualification remains a disclosed boundary.

## Lifecycle correction at 93871505

The earlier matrix could finish a synthetic position while still issuing an
invalid early cancel. A native regression reproduces that cancel at the forced
exit's submission nanosecond, before its four-second timeout. The corrected
pending branch applies deadline cancellation to entries and non-forced exits;
an already-forced time exit observes its normal timeout and can fill once.

The pinned source for cancel-by-ID and cancel-reject dispatch is
`nautechsystems/nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e`,
`crates/trading/src/python/strategy.rs` (`py_cancel_order`,
`on_order_cancel_rejected`) and `python/nautilus_trader/model/__init__.pyi`
(`OrderCancelRejected`). Cancel rejection is non-terminal; missing acknowledgement
does not release an order. T22 keeps that identity, freezes and escalates rather
than submitting a replacement under uncertainty. Acknowledgement grace uses the
same bounded per-role timeout, measured from the cancel request.

Durable safety reuses the existing `safety.Ledger.freeze` and follows
`native_adapter.record_callback_fault`: attempt both the durable halt and
fault_sink even if either fails, retain only safe error types, and stop submits.
Tests close/reopen the actual SQLite ledger and separately verify a pre-existing
halt with no exposure. Held stale/halted/closed/budget hazards have durable
handoff, with no automatic resume. The review's native_strategy line reference
differs in this branch; the equivalent verified failure-isolation pattern is in
native_adapter.py:136-164. No shared paper file is modified here.

Clock primary sources at the same rc5 pin are `crates/common/src/python/clock.rs`
and `python/nautilus_trader/common/__init__.pyi` (`Clock.timestamp_ns`). The
[native timestamp API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/common/src/python/clock.rs#L61-L64)
reads the registered clock. The [LiveNode registration commit](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/live/src/python/node.rs#L1380-L1385)
hands the Python strategy to the trader's [Python strategy registration and clock binding](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/system/src/python/registration.rs#L258-L306),
using the [component clock factory](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/system/src/trader.rs#L282-L290)
before initialization. Upstream does not expose a live-clock constructor or
permit setting live time through the Python clock API. An actual
installed-client probe verified that a strategy registered through
`LiveNode.add_strategy` receives the native Clock before the run. Fixtures borrow
that clock through an independent no-trade actor, use the actual family actor's
clock for events/quotes/journal timestamps, and declare synthetic RTH at the
calendar boundary. They do not change the engine clock or skip weekends.

Ten new lifecycle regressions include nine that fail against unchanged93871505
(13 assertion failures including subtests). The consumed-entry isolating test
already passes there: no unresolved order, position, halt or exhausted sequence
can explain its refusal, and a new instance enters in the positive control.
Removing only the consumed assignment in the isolated baseline makes that test
fail (sequence3 instead of1); the baseline source is then restored. This is
disclosed as missing coverage, not falsely labelled a repaired behaviour bug.
The corrected native suite passes34 tests with zero skips. Local results remain
synthetic engineering; historical timing, paper and performance gates stand.

## Codex correction at 45ebe5c4

The three reviewed findings reproduce on the immutable
`45ebe5c4e996a53fa0627bbfd2087c1e936e86b0` baseline with only the new regression
module overlaid. The native rc5 focused run fails on policy-cutoff entries and
resting buys, halt cancellation, and callback-clock entry anchoring. Positive
controls admit entries before the cutoff and keep pending exits separate.

Comment 4235547318 now uses the existing `_holding_deadline` calendar resolver
to refuse new entries at the selected policy boundary, and latches that boundary
when submitting an entry so a rollover cannot move a resting buy's deadline.
The resolver uses [exchange_calendars session boundaries](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar.py#L1006-L1016)
and [XNYS early-close rules](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar_xnys.py#L157).
The later fractional-second correction schedules cancellation through the
[native nanosecond alert API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/common/src/python/clock.rs#L158-L177),
with [native alert retirement](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/common/src/python/clock.rs#L258-L260).

Comment 4235547324 originally added the pending-entry halt predicate separately
from the pending-exit gate. That predicate did not itself dispatch cancellation
on snapshot acceptance; the subsecond correction invokes the pending-entry path
immediately after the native [custom-data callback](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L640-L643)
accepts the halted snapshot, using the existing [native cancellation API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L1999-L2016).
The original identity survives until [terminal cancellation](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L4252);
[cancellation rejection](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L4208)
is non-terminal, and a missing acknowledgement still freezes with that identity.

Comment 4235547328 anchors
the first buy to `OrderFilled.ts_event`; both its holding timer and selected
calendar deadline therefore describe the fill, including delayed delivery.
The upstream [fill event timestamps](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L4484-L4503)
and [ts_event property](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L4537-L4541)
distinguish execution time from callback delivery; [native fill dispatch](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L576-L580)
preserves that event.

The primary API remains
`nautechsystems/nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e`,
`python/nautilus_trader/model/__init__.pyi` (`OrderFilled.ts_event`,
`OrderCanceled`, `OrderCancelRejected`),
`crates/trading/src/python/strategy.rs` (native event dispatch and
`py_cancel_order`) and `crates/common/src/python/clock.rs` (`Clock.timestamp_ns`).
The unchanged installed 2.0.0rc5 engine reproduces the failures and exercises the
fixes through its quote, custom-data, order and timer boundaries. Shared
`adaptive-paper/sessions.py`, backed by
`exchange_calendars@dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a`, still owns calendar
semantics; no replacement calendar or broker adapter is introduced.

The acceptance generator retains its credential-free subprocess environment
without inherited one-thread test caps, following the CC's corrected suite
resource rule. README records lido's exact-head source answer: the T22 local
residual flag has no established bridge to continuing shared-runner management.
That test-backed follow-up remains a T13-runtime gate under the CC ruling;
synthetic landing and paper acceptance are separate.

The final focused baseline run has six tests and nine assertion failures; the
pending-exit separation control already passes. All six pass after the fix. The
then-regenerated full native receipt has 40 tests, zero skips and 14 matching source
bindings. The matrix has 120 timing candidates, 30 legacy cases, four controls,
ten noncohort inverses and seven matching bindings. Both retain `NOT_CITED`.

## Astra substitute correction after 31d63cd8

The fractional-second native regressions refine the earlier cancellation claims.
A resting entry now arms one native alert at the earliest entry timeout,
explicit entry deadline, explicit exit deadline or latched policy cutoff. Its
callback uses the existing cancellation predicate and retains the original ID
until the native fill or terminal event clears the order and retires the alert.
An accepted halted snapshot drives that same pending-entry path immediately;
pending exits retain their separate halt handling.

On the unchanged pre-fix source, six focused native tests give three assertion
failures: both 15:57:59.500/19:57:59.500 policy straddles miss cancellation, and
the 300 ms halt is only acted on at the 400 ms quote. The four deadline controls
already pass there; they repair missing coverage. Separate single-site mutants
remove the pending-entry deadline, new-entry deadline or pending exit-deadline
force to verify that each isolated guard is necessary.

First-hand before/after logs and pinned offline source captures are retained at
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/strategies-astra-fix-20261010/`:
`native-before.log`, `native-after.log`, the deadline mutation logs and
`upstream-source-captures/SOURCE.json`. The three earlier thread fixes retain
their focused baseline/final logs in the sibling `strategies-codex-fix-20261010/`.
The new source/result digests and exact native acceptance are recorded in the
new correction receipt there; the repository acceptance generators bind the
current source in `test-acceptance.json` and `synthetic-receipt.json`.

The straddle fixture proves cancellation dispatch at the selected boundary.
It still receives the native racing BUY 100 ms later, matched before the cancel
is processed; that fill is accounted through the original order and exited.
Post-cutoff execution exclusion is not claimed. The late-fill ownership and
time-exit assertions remain in the regression. F-2 uses the exception path
below and never depends on venue expiry. GTD or IOC remains an optional
execution-profile capability qualified per broker later. Complete paper
acceptance of the exception path remains required before a non-synthetic run.

Pending exits intentionally retain their working order and original identity
through a halt, with timeout/deadline processing resumed after the halt clears.
The existing native pending-exit separation test pins this policy. F-1 remains
on T13-runtime/T15 acceptance before the first non-synthetic run: decide
hold-and-flag versus cancel-and-escalate with the applicable caps and residual
management. The subsecond snapshot-halt fixture receives terminal entry
cancellation at 400 ms and stays flat. No broker, historical timing,
continuing-manager or performance qualification is inferred from these
synthetic engine runs.

## Native instrument-status correction after 79a17b21

The native-status review reproduced a missing subscription and callback at
`79a17b2196f08af507248941262023544cf10d62`: an `InstrumentStatus(HALT)` at
300 ms did not cancel a resting entry, which filled after native resumption.
The pinned primary source is
`nautechsystems/nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e`:
the [InstrumentStatus fields and event/availability timestamps](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L2480-L2519),
[native strategy callback](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/trading/__init__.pyi#L645)
and [native subscription API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/trading/__init__.pyi#L784-L789)
are implemented by the [Python subscription binding](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L2744-L2764)
and [native callback dispatch](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L756-L763).
The [MarketStatusAction definitions](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/enums.rs#L969-L1002)
distinguish trading, quoting without trading, halt, pause, suspension and
unavailability. The correction uses those upstream events without a custom
transport or a quote-condition mapping.

The strategy subscribes to instrument status and immediately drives the
existing pending-entry cancel path when it accepts a halt. A status-halt latch
is separate from the factor snapshot's halt flag. Non-halted snapshots cannot
clear it, nor can a stale, future or no-change native status. An accepted native
`TRADING` action clears only the status latch; an explicit `is_trading=False`
still blocks trading. A halted snapshot remains independently binding.
Pending exits keep the intentional policy and pinning test described above.

LiveNode also requires a status-capable data client. The upstream
[client status-subscription extension](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/live/clients.py#L267-L268)
raises `NotImplementedError` by default, and the
[vendor client template](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/examples/live/_template/data.py#L101-L103)
declares that required extension. The shared adaptive-paper `AlpacaDataClient`
does not implement it. `native-live-startup-failure.log` reproduces the native
operation failure and `ShutdownSystem` when the new strategy subscribes.

The synthetic LiveNode fixtures now declare a status publisher at that client
boundary and emit real `InstrumentStatus(TRADING)` through the
[upstream queued-data output](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/live/clients.py#L192-L193).
Their existing callback, order and restart assertions remain, and they require
observable native status delivery. This fixture capability does not qualify a
broker status stream or repair the shared adapter. Actual status subscription
and publication for the runner remain an owning T13-runtime adjudication and
qualification item before a non-synthetic run; directly using the unchanged
adapter with this subscription fails closed. No subscription exception is
silently swallowed and no shared adapter or transport is changed here.

First-hand results are retained under
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/strategies-t22-p2-prepare-20261010/`.
The initial valid `native-status-before.log` has three assertion failures on
the unchanged native-status path. `native-status-final-controls.log` exercises
both carriers, native resumption, stale/future status refusal, action-only halts
and explicit non-trading flags in the unchanged installed rc5 engine. Entry
cancellation is dispatched at 300 ms, native terminal confirmation arrives at
400 ms and no fill occurs. Original-ID and consumed-entry assertions remain.
`native-consolidated-executions.json` binds these controls and individual
handler/subscription/dispatch/latch/availability/ordering/action/flag/resumption
mutants, plus the two admission/startup guards and three optional lifecycle
controls. Each removed guard produces an assertion failure without native
skips. Initial runner selection/import errors are retained separately and do
not count as failing-first evidence.

The same packet retains exact pinned excerpts in
`native-status-source-captures/SOURCE.json` and
`clock-source-captures/SOURCE.json`. The existing correction-record check first
fails for the absent clock/source record, then passes with native timestamp,
LiveNode registration and actual Python clock-binding citations. It also
requires the status correction's pinned API/dispatch/enum citations and retained
first-hand evidence. The admission and durable-ledger tests repair missing
coverage; the synthetic development-labelled startup control does not qualify
historical data. The CC-cued integration onto main
`0947b01289dcaa9157aa38392a94cf00f592b86d` regenerates the source-bound
acceptance receipts and evidence metadata. Its fresh controls, snapshot-halt
guard mutant and full validation are retained in the sibling
`strategies-pr938-integration-20261010/` packet; earlier preparation results
remain distinct from the integrated head.

## F-2 post-cutoff fill exception and synchronous risk handoff

The revised F-2 definition requires a fill executed at or after the selected
policy cutoff to be logged/flagged as `post_cutoff_fill`, immediately reflected
in exposure and daily-loss state, then closed by the next session-permitted exit
or held/flagged under F-1. It does not rely on venue-enforced expiry.

The mechanism retains the [native fill event timestamp](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L4484-L4503)
and [native callback dispatch](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L576-L583).
The execution timestamp is compared with the entry's latched earliest deadline,
so a pre-cutoff execution delivered later is not misclassified. Owned quantity,
cost basis and fill identity are updated before the synchronous injected sink
is called. Duplicate native trade IDs cannot apply the exception twice. The
callback accepts no awaitable accounting result; a deferred or failed sink
uses the existing durable freeze/escalation path with owned residual retained.
Only fixed exception/acknowledgement labels and timing are added to the trace;
account totals are never copied into it.

The sink uses Python 3.12's official
[inspect.isawaitable contract](https://docs.python.org/3.12/library/inspect.html#inspect.isawaitable)
to refuse deferred state updates, retiring an unawaited coroutine before the
existing callback guard freezes and escalates.

The strategies/T14 boundary is
`post_cutoff_fill_sink(strategy, native_order_filled, cutoff_ns)`. The account's
single writer supplies the complete post-fill native `AccountSnapshot`, owner
`CapsConfig`, frozen trade-day anchors and current UTC time to the owned
coming `risk.caps.post_cutoff_fill(state, snapshot, caps, now) -> AccountState`, then
installs that returned state before the sink returns. The underlying governor
seam is [UET risk.check and State at the selected merged main pin](https://github.com/seathatflowsinourveins/us-equities-trading/blob/586171951a1595cfd0811cfb8b9c012897eb9543/risk/__init__.py#L119-L198).
The new caps consumer is the T14 follow-up's declared interface: no
implementation/binding is supplied by this repository or the selected merged
UET main pin. It is not a PR-branch commit dependency or an already-qualified
cross-repository runtime. A family
actor cannot derive account-wide holdings, uncertain reservations or opening
P&L anchors from its one instrument. A synthetic run without the sink remains
explicitly `post_cutoff_risk_sink_unqualified`.
Non-synthetic startup independently requires a callable sink and the durable
ledger. An isolated native startup regression removes that guard and fails;
the existing supplied-ledger control explicitly supplies the sink so the two
requirements cannot mask each other's removal.

The new native test uses a declared one-instrument account producer and the
actual unchanged rc5 [portfolio exposure API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/portfolio/__init__.pyi#L115-L121)
and [portfolio P&L API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/portfolio/__init__.pyi#L101-L107)
after the racing fill. It verifies exposure/loss state has moved before the
strategy callback returns, exact original identity, single application on a
duplicate event and the subsequent native time exit. The deferred-result test
verifies freeze/escalation and retained owned residual. The earlier delayed
callback control proves execution-time classification. First-hand red/green
logs and isolated exception/callback/awaitability mutants are retained in
`strategies-pr938-integration-20261010/`; T14 independently owns the actual caps
transition tests. Neither fixture substitutes for paper acceptance of the
real main-to-main account writer, or qualifies F-1's held residual management.

## Clock-leading halt correction after 0ea8aee2

The status handler's availability fence accidentally rejected halts, preventing
entry cancellation when the venue timestamp led the host clock. The pinned
primary mechanisms remain the rc5 [InstrumentStatus timestamp/action fields](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L2480-L2507),
[native status callback](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L756-L763)
and [HALT/non-trading actions](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/enums.rs#L969-L1002).
The correction applies negative trading signals at observation and records the
event/init lead in `status_clock_ahead`. Only a TRADING resumption requires
available, ordered timestamps. The initial correction bounded future halting
timestamps at observation time. The F-1 follow-up below supersedes that fence:
it preserves raw stamps and refuses a resumption stamped before an observed halt.
Neutral metadata neither resumes trading nor moves the fence.

First-hand results are retained at
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/strategies-pr938-status-clock-fix-20261010/`.
`native-clock-before.log` reproduces missing cancellation for 1 ms/400 ms venue
lead, an init-clock lead and a stale halt, plus the missing active halt in the
resumption controls. `native-clock-after.log` verifies cancellation at 300 ms
delivery and terminal confirmation at 400 ms, with no fill. Future/stale TRADING
still cannot clear the latch, while an available ordered resumption can. The
unchanged owning `probe938_future_halt.py` SHA256
`014ce90f8982028dd93cb1da743960f279add024ec27fe0b985a056da8efec1f`
is retained by digest; `owning-probe-before.log`/`owning-probe-after.log` measure
all five clock leads independently. The init-lead fixture shifts metadata at
the native callback seam because the native simulation schedules by ts_init;
it does not claim that the backtest dispatcher normally delivers future init.

The F-2 cutoff now uses the same earliest deadline latched before entry submit
and armed through the existing [native nanosecond alert API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/common/src/python/clock.rs#L158-L177):
policy cutoff, explicit entry/exit deadline or entry timeout. Classification no
longer omits spec-level deadline and timeout races. `earliest-cutoff-before.log`
fails three native subcases; the corrected cases sink the owned late fill at
the delivery step, retain the original ID and close through the permitted exit.
The marker forces the next session-permitted time-exit rather than waiting for
a later unrelated holding deadline; its isolated guard regression fails for
both the explicit-entry-deadline and entry-timeout races when removed.
The original policy-cutoff native portfolio/state test remains binding.

The native status latch and its ordering fence are memory-only. A restart does
not establish resumption; snapshot and durable ledger halts remain separate,
and fresh broker status/restart reconciliation or journal persistence must be
qualified by the owning runner before any non-synthetic run. The coming T14
consumer interface remains explicitly unimplemented/unbound at this repository
and selected merged UET main pin. This correction adds no broker status producer,
T14 implementation or paper acceptance claim.

## Unsupported OVERNIGHT hold and cutoff coverage controls

The existing T22 unsupported-session hold must survive a classifier extension
that names the 20:00–04:00 ET window `OVERNIGHT`. The implementation now holds
`session.kind.name in ("CLOSED", "OVERNIGHT")` before entry or exit admission,
retaining the existing `closed_session_requires_handoff` durable freeze and
escalation. Current shared calendar boundaries remain based on the pinned
[exchange-calendars session API](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar.py#L1006-L1016).
The dated hold policy remains in [the trading scope decision](https://github.com/seathatflowsinourveins/us-equities-trading/blob/586171951a1595cfd0811cfb8b9c012897eb9543/docs/decisions/2026-10-09-equities-intraday-scope.md).
No classifier or broker transport is rebuilt here.

The two existing native hold tests run with a test-only public-name overlay at
the shared calendar boundary; an additional native case pins both names for
flat entry refusal and held-position durable escalation. They do not import
or test against another PR branch. Before/after and per-name mutant evidence
are retained in this correction packet. Initial fixture attempts that used a
naive clock are retained separately and are not accepted fail-before evidence.

The native cutoff controls now distinguish execution exactly at the armed
deadline from one nanosecond before it, require `post_cutoff_risk_applied` on a
completed synchronous sink, and require `post_cutoff_risk_sink_unqualified`
when an eligible synthetic fill has no sink. Single-site comparator, ack-label
and missing-sink-flag mutants fail those oracles. The source is the same pinned
rc5 fill timestamp/callback mechanism cited above. The coming T14 consumer
name is an interface declaration, not an implemented or bound dependency in
this repository or the selected merged UET main pin; T14 publication still
requires a separately verified main-to-main account-writer binding.

## F-1 halt-state and held-exit follow-up

The policy source is us-equities-trading
[`docs/decisions/2026-10-10-halt-exit-policy.md` at f8c607bc1f1f0205fdc87095f47df150d2f78117](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md#decision).
Decisions 1–3 require immediate negative halt signals, held/flagged working
exits with a notice every ten minutes, and no new order into a halt or unknown
state. Its reasoning and acceptance sections define the three entry-fill
windows around the entry's own deadline and cancel-acknowledgement freeze.

The upstream landscape remains the installed, unchanged NautilusTrader
2.0.0rc5 engine at `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, with rc6 retained
only as the separately selected regression candidate in `~/code/upstream/MIRRORS.json`.
The following supported rc5 mechanisms were checked directly in the mirror;
the same installed engine executes these regressions. No adapter, scheduler,
matching engine or risk state is rebuilt.

| Correction | Pinned upstream mechanism | Regression |
| --- | --- | --- |
| P3-A: preserve raw event/init stamps; reject an older available resumption | [InstrumentStatus fields](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L2480-L2507), [native status callback](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L756-L763) | Raw event lead and init lead independently fence stale TRADING; snapshot resumption has the same raw fence and a later positive control |
| P3-A: absent/expired named state blocks every new order | [Cached custom-data event/init stamps](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/data/custom.rs#L53-L88); local `snapshot_data_type` supplies instrument scoping and FactorSnapshot supplies validity | Expired state blocks a fresh-quote exit; final submission blocks BUY/SELL even when the caller bypasses drive; a working exit stays held and the session is notified |
| P3-B: a leading halted snapshot acts immediately while future factors remain unavailable | The same [custom-data wrapper](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/data/custom.rs#L53-L88) and existing on_data callback | 1 ms and 400 ms init leads cancel the original entry at the 300 ms delivery; future stamps cannot silently clear the halt |
| P3-B: flag/notify a working exit at observation and every ten minutes; preserve its identity | [Native nanosecond time alert](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/common/src/python/clock.rs#L158-L177), F-1 decision 2 | Fractional-second halt at 2.3 s produces notices at 2.3, 602.3 and 1202.3 s, with one unchanged working exit and no cancellation/replacement |
| P3-B: a held exit's DAY-expiry callback freezes before returning | [Native order-expiry dispatch](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L504-L511), F-1 decision 2 | Explicit state-machine expiry callback during a halt preserves the residual, flags/notifies and freezes; this does not qualify venue-driven expiry |

First-hand logs are retained in
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/strategies-halt-exit-followup-20261010/`.
`current-main-red-v4.log` executes the new native tests with the unchanged
production module from main-derived baseline `a7c15bd051088d0493d58bd84a3c8c35dcde6624`:
nine test methods fail eighteen assertions, with no unexpected errors/skips.
`focused-green-v4.log` passes those cases, the three fill windows and the
adjusted raw-stamp/notification/calendar controls. The calendar fixture's
synthetic halt state is deliberately valid across its one-day callback delay,
so its execution-time anchor remains isolated from the new freshness fence.

The cue's P3-1 classification was already fixed in `a9e4eeb7`, which landed
before this follow-up baseline. It is preserved, with the record's three
unprocessed-halt-cancel fill windows added as native controls. The historical
production module at `0ea8aee2faaba9a7723550e1b3bca75f6db7480f` fails the late
two windows (`P3-1-historical-red-v4.log`); current main already passes
this classification. The historical failure is not represented as a failure
of current main. The entry's own earliest deadline remains the cutoff; the
halt-cancel dispatch time does not become a new cutoff.

Twelve targeted single-site mutants fail thirty-four assertions, with no unexpected
errors/skips. They independently remove raw native/snapshot fences, ignore a
leading snapshot halt, omit producer expiry or final submission refusal,
silence/delay the held-exit notice, omit expiry handoff, restore the historical
policy-only cutoff, and cancel a held exit. The notice control places quotes
after the exact ten-minute boundary so only the native alert can satisfy it.
`reproduce.py`, the individual mutant logs and `final-regression-results-v4.json`
are retained in the same packet; production overlays are compiled in memory
and print their exact source hashes without editing the worktree's source.

The synthetic producer is named by the instrument-scoped `t22-factors-v1`
subscription. Its explicit boolean and `valid_until_ns` gate final submission
as well as drive. Native status halts and snapshot halts are independent vetoes;
neither carrier clears the other's active halt. Raw fences are memory-only,
and paper producer/freshness/restart qualification remains T15 work. No source
here establishes broker cancel behavior, venue-driven DAY expiry, partial
reopening fills or the seven-assertion T15 paper acceptance. The existing T14
account-writer binding and historical Layer 1.5 boundaries remain unqualified.

The same rule 3 also closes an input-default gap: a missing `halted` JSON field
previously defaulted to False and authorized BUY/SELL orders. The native
`omitted-halt-native-before.log` fails both startup and held-position cases
without callback errors. `FactorSnapshot.halted` now defaults to None, meaning
unknown; the typed contract accepts only None or an actual boolean. An unknown
update immediately vetoes orders and cannot clear an observed halt. Existing
synthetic LiveNode fixtures now provide their known False state explicitly.
The policy is decision 3 at the full F-1 pin above; the upstream
[optional trading-state field](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/model/__init__.pyi#L2480-L2507)
likewise distinguishes missing state from False. Baseline reproduction overlays
both the input contract and families.py at the named production pin; other
fixture dependencies use the follow-up worktree. Two additional mutants
restore the False default or ignore an unknown update and fail these controls.

## PR994 first-read corrections at 3cb302ab

The co-op first read (verdict SHA256
`ce792c92731b56c7226bac49689826e7bb5af95b67ddd9011d0214a84d6807a1`)
raised an unknown-state cancellation concern and found that held-notice timing
disappeared on restart. The trading-cc read (`d6fc397c45eafd843a8fd64e8448d41546ece0913ac16434105ed315776ace5e`)
and reviewer read (`b4df9cb281c0826e7eb83ce5a152d333e13d7b6a7fec61394c2b0790edcfbe5a`)
reproduced two blocking faults: notification could prevent a partially filled
entry's cancellation, and a routine notice sent through `session.fail` stopped
the native actor. The reviewer also found 67 survivors in a 110-mutant census.

The CC's 2026-10-11 03:07Z ruling retains conservative entry cancellation when
producer state is missing or expired. [F-1 decision 1, lines 16–18](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md#L16-L18)
cancels entries; [decision 2, lines 19–25](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md#L19-L25)
protects working exits from cancellation/replacement while halted or unknown;
[decision 3, lines 26–28](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md#L26-L28)
blocks every new submission. The upstream [native cancel command](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L2001-L2016)
reduces the resting entry's remaining risk and retains the original identity
until confirmation. Native and SDK-free controls pin missing/expired state;
native replacement controls confirm cancellation before refusing a new order.

`_drive` now dispatches cancellation before attempting notification. The
separate `notice_sink=None` has no fallback to the failure sink. Delivery
exceptions record their type as `stop_error`, preserving cancellation and the
next timer. The existing freeze path keeps its failure sink, and resumption
retains the freeze's reason flag. A native partial-fill regression uses the
upstream [DefaultFillModel and liquidity-consumption contract](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/backtesting/fill-models.md#L28-L45)
and [L1 passive-fill semantics](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/backtesting/fill-prices-and-matching.md#L132-L150), with a quote size of
three: the original seven-share BUY owns three and cancels its remaining four
at the halt, even with a raising notice sink. A second native control binds a
stopping failure sink and verifies both explicit and default-none notice ports.

The notification correction adopts the existing [Ledger metadata and
transaction boundary](https://github.com/seathatflowsinourveins/native-agent-stack/blob/3cb302ab4dab7ecfe605786723758f99c9b78605/blueprints/us-equities/adaptive-paper/safety.py#L427-L527)
and [Python SQLite transaction control](https://docs.python.org/3.12/library/sqlite3.html#transaction-control).
`halt_notice.py` stores a versioned, instance-scoped identity, original order
ID, reason, active state, last-notice and next-due nanoseconds in that existing meta
table, using its lock/transaction and FULL-synchronous WAL configuration. It
creates no database, schema, order manager or scheduler. Minimal synthetic
ports use an explicitly session-only view; that fallback proves no process
durability. Real-ledger tests close the connection and recreate the strategy.

Startup restores/rearms through the existing [native nanosecond alert](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/common/src/python/clock.rs#L158-L177)
before a startup refusal can return. A frozen recovery instance delivers
notices without adopting exposure or submitting commands. The original due
time survives restart; overdue intervals coalesce into one immediate notice
and a new ten-minute interval from delivery. The record survives resumption
as inactive until exposure resolution. An owned final SELL clears it; explicit
session reconciliation can clear it only after strategy, ledger and cache are
flat and have no unresolved orders, and does not unfreeze trading.

First-hand packet:
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/strategies-pr994-gpt-fix-20261011/`.
The unchanged review probe (SHA256
`979e6e072f9699a3d1be9b736434f42f0ecb8dffa77655aab0ff2eea64f4d4d1`)
has an unchanged 3cb302ab run with four tests and three assertion failures.
The co-op's approved `notice_probe_adapter.py` (`62bb2dc9b22756880a452407216834274d6b6624ce0f63b465c62013505e504b`)
binds only the probe's recording callback to `notice_sink`; assertions and
probe source remain unchanged. Both cadence probes pass. The two probes
`test_missing_producer_does_not_dispatch_cancel` and
`test_expired_producer_does_not_dispatch_cancel` remain expected red under the
CC's ruling; they are adjudicated policy disagreements. The real-ledger native
regression preserves +603 s after a restart at +100 s, and attempts one notice
at an overdue +2,000 s restart followed by the next at +2,600 s. The partial-fill,
separate-sink and retained-freeze-flag regressions fail four assertions against
3cb302ab and pass after correction. The ten reviewed witness tests are included
with explicit notice-port binding where routine notices are asserted.

The locked rc5 runtime runs both touched modules: 101 tests pass, zero skips;
85 exercise SDK-dependent native integration. System Python runs the lifecycle
module with six portable tests passing and 68 SDK-dependent tests skipped.
These metadata-only checks retain
the actual SQLite Ledger; when exchange-calendars is absent, its unrelated
calendar port rejects every attempted query. No calendar behavior is inferred.
The four review probes are additional SDK-free logic checks. Source-bound
acceptance and matrix receipts separately identify what actually ran. The
reviewer's mutation runner and explicit line/notice-port remapping are retained
in the packet for before/after comparison. The equal-stamp mutation needs a
leading halt whose factors were never installed: a later available resumption
may equal either raw fence dimension while satisfying the separate snapshot
revision check. Its three native cases pass and reject the stricter `<=` mutant.
Broker/session reconciliation and
T15's seven paper assertions remain unqualified.

## PR994 witness coverage at 1762d7b3

The expiry callback can first observe an expired producer. The native regression
now injects that callback while a real exit is working and inspects the result
before another drive: the separate notice, instrument/instance/original-order
identity, last-notice and next-due timestamps, active record, retained quantity,
terminal pending state and handoff freeze. A SQLite close/reopen also verifies
the exact persisted record. This follows [F-1 decision 2, lines 19–25](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md#L19-L25)
and the selected rc5 [expiry callback](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/trading/__init__.pyi#L659),
with the existing metadata/transaction boundary cited above. It is an injected
native callback witness; venue-driven DAY expiry remains unqualified.

The real-ledger native restart test records every failure-sink invocation.
At +100 s it receives only the two startup reconciliation freezes; routine
notices at +603 s and +1203 s do not call it again. At an overdue +2,000 s
restart, the immediate first notice precedes startup reconciliation and its
freeze; the +2,600 s routine notice adds no stop. The native E06 negative
control fails one assertion and N17 fails both restart subcases, with no errors
or skips; both native methods pass with production unchanged.

Four additional SDK-free tests execute exact production methods with the
actual SQLite Ledger and synthetic clocks/command ports. They isolate a
RuntimeError from metadata persistence while pinning cancellation, delivery,
lost-durability flag/trace and re-arm; retained recovery metadata after actual
startup freezing and a subsequent flat journal/non-halted state; each individual
reconciliation refusal signal; and preservation of an existing durable freeze
without another failure-sink call. The existing real-ledger position refusal
completes all six reconciliation signals. These are local logic/integration
checks, not native engine or broker reconciliation acceptance.

The final trading-cc read at 1762d7b3 (SHA256
`b834c967cedb01e4b1a540ec4afc2880a294335e6d7d245e6983fa6eacb84883`)
withdraws the single-site restored-passive F5 finding: startup freezes the
recreated actor, and F6 separately protects its retained record. The recovery
property follows its validated witness (SHA256
`b7f3b20622607d10ade83f813f9c063e970472c3156ff3c2c6061c658c66f2c5`).
F5 and F6 individually pass; removing both fails the retained-record assertion.
An earlier unfrozen synthetic recovery fixture and its F5 kill are superseded
because they did not preserve the recreated actor's actual startup invariant.

The unchanged engine and ledger implementations remain the selected sources;
this follow-up changes tests, source-bound acceptance and documentation only.
The supported generator runs 106 tests without skips: 86 SDK-dependent native
tests and 20 contract/portable checks. System Python separately runs ten
portable tests and skips 69 SDK-dependent lifecycle tests.
Reader inputs, native positive/negative controls and both mutation censuses are
retained in `~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/strategies-pr994-witness-fix-20261011/`.
The earlier first-read counts above remain evidence for their named correction.
Notice containment applies to errors derived from `Exception`; a
`BaseException` interruption is outside that guarantee. Native-carrier
equal-stamp coverage, corrupted/inactive-record variants, failures while
clearing metadata and re-entrant native stop remain disclosed boundaries.

The cumulative reviewer micro (SHA256
`450484c2d964f082a82e9caeea957fa5549ea49f7b3070cb4214d662a39934b0`)
supplies a synthetic LiveNode restart probe using the unchanged FakePort
fixture, real SQLite and `fault_sink=session.fail`. Reproduced at final source,
the head delivers its notice at +3 s, calls the failure sink only for the two
startup freezes and stays active until the requested +8 s stop. N17 adds
`held_halted` to that sink and stops at about +3.1 s. This closes the earlier
startup-stop qualification doubt for that fixture; broker/session readiness
and paper acceptance remain separate. No performance claim changes.

## PR994 connector corrections at 7956bb3a

Two connector P2 threads expose gaps missed by the earlier review witnesses:
[equal accepted-snapshot replay](https://github.com/seathatflowsinourveins/native-agent-stack/pull/994#discussion_r4240681279)
and [non-synthetic notice-port admission](https://github.com/seathatflowsinourveins/native-agent-stack/pull/994#discussion_r4240681286).
At the reviewed parent, the native rc5 regressions run two methods and fail
three assertions, with no errors or skips: replay retains `held_halted`, and
both omitted/non-callable sinks leave development startup enabled. The named
callable positive exercises a native BUY. Synthetic factors carrying
development labels prove admission behavior only, not qualified market data.

An identical accepted False snapshot now clears the snapshot halt latch before
its early return, after availability and raw event/init fences pass and only
after confirming exact equality with the accepted revision. The accepted
factor object is retained; its validity is not extended. Pending/held exposure
is driven after the resumption. Equal conflicting revisions still freeze;
future/older resumptions are refused, and the independent native status veto
remains active. The native replay regression observes an accepted False
snapshot, an older late True snapshot, then the exact False replay and a BUY.
Separate native controls pin conflicting, future, older and native-halt cases.

This follows [F-1 decisions 1–3](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md#L16-L28)
and rc5's [custom-data callback dispatch](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L640-L645).
The ordering/idempotence rule is local glue; upstream supplies the callback
and [cached data timestamps](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/data/custom.rs#L53-L88),
not this producer's halt-latch policy.

Non-synthetic startup now requires a callable notice sink after its existing
durable-ledger and post-cutoff-accounting gates, before subscriptions or orders.
It reuses the selected rc5 [startup callback](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/trading/src/python/strategy.rs#L336-L341)
and existing freeze/ledger boundary. Missing or non-callable notice ports freeze
with `startup_notice_sink_required` and sequence zero; the callable control
still submits. Synthetic fixture defaults remain explicitly permitted.

Failing-before/after logs, review thread identities, pinned source verification,
supported acceptance/matrix regeneration and final checks are retained in
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/strategies-pr994-codex-fix-20261011/`.
Earlier census results above bind their named prior correction and are not
represented as a rerun on this new production change. Broker/data/paper
qualification boundaries remain unchanged.
