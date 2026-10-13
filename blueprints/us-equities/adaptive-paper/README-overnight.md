# T15 overnight session and status checks

Paper acceptance: **NOT_RUN**. The staged native overnight adapter includes
explicit BOATS REST polling, refreshed asset status, admission and lifecycle
guards for a bounded diagnostic. Hermetic/native fixture execution qualifies
these code paths only; the owning lane's retained broker acceptance is pending.
Frozen N2 sources/configuration remain the run owner's separate input.

`sessions.session_at` now reports OVERNIGHT for 20:00–04:00 Eastern, Sunday
evening through Friday morning. The interval is half-open: 20:00 is OVERNIGHT
and 04:00 is PRE. The session date is the upcoming civil trade date, so a
Monday 21:00 observation belongs to Tuesday. XNYS must actually have that
trade date; skipping to a later trading day would create phantom weekend or
holiday sessions. The overnight preceding a full holiday is closed. An
overnight into an early-close trade date still lasts eight hours. `next_open`
names the next market opening, including Sunday 20:00. RTH dates, holidays,
opens and early closes still come from exchange-calendars 4.13.2.

`DATA_FEEDS` adds the explicit plain string `boats`. The documented endpoint
is `wss://stream.data.alpaca.markets/v1beta1/boats`, and SDK REST quote requests
select `DataFeed.BOATS`. The distinct derived/delayed `overnight` feed is not
admitted as the fresh BOATS feed. Enum-name and endpoint tests prove namespace
selection only, not entitlement, streaming availability or quote freshness.

Preflight preserves each broker asset's `attributes` and produces a separate
`asset_statuses` carrier. `normalize_overnight_status` derives
`overnight_tradable` and `overnight_halted` from that supported SDK asset
response. A missing or malformed attribute list carries unknown values; it
never supplies a default resume. The owner's trading-status receiver consumes
this carrier separately from SIP status messages and all quotes. UTP quote
condition `H` remains a manual quote under #965; status `sc="H"` remains a
halt. Quote conditions and model-supplied top-level flags cannot grant either
D6 check.

For an extended-hours/BOATS port, `Controller.before_submit` checks the carrier
before reserving any BUY or SELL intent. `before_request("submit")` repeats the
check after reservation, before the wire budget and POST. OVERNIGHT requires
explicit `overnight_tradable=True` and `overnight_halted=False`, plus no separate
standing trading halt. Missing, unknown, stale and future carrier observations
refuse; the explicit REST port bounds carrier age by the smaller of its quote
timeout and the risk entry-quote age bound, including movers with a 30-second
transport timeout. Asset refresh uses this same stricter bound.
Out-of-order asset resumes cannot clear a newer halt; restrictive eligibility,
unknown status and halts win timestamp ties in either arrival order.
These guards apply to recovery's transport submission path as well as native
strategy orders. Cancellation and observation remain available.

Existing extended-hours policies continue to admit PRE/RTH/POST only: under
them the runner's controller window (`runner._controller_session`) opens only
in those three sessions. The order-throughput capacity harness (`capacity.py`)
refuses every other session as `market_session_closed`, so it never runs
OVERNIGHT as regular hours. Native
dispatch and exit plans refuse/flag OVERNIGHT unless the explicit REST diagnostic
configuration below and all dispatch-time guards pass. The helper for a proposed
overnight order sets `extended_hours=True` and bounds its DAY window at the
upcoming trade date's 20:00; this pure mapping grants no submission authority.
Held-book financing and prior-RTH-close capture retain the completed RTH date
through an OVERNIGHT observation and midnight. An explicitly reconciled hold
keeps its existing `overnight_holds` disposition; faults and attention do not
become successful holds. The corporate-action lookahead remains conservative:
OVERNIGHT's upcoming trade date and the following trading session are checked.

## Staged overnight adapter

An explicit configuration selects `feed: "boats"`, `quote_source: "boats_rest"`,
`overnight: {"enabled": true, "flatten_minutes_before_pre": 10}` and extended
hours with `overnight_holds: false`. It admits the actual XNYS OVERNIGHT window
for entries. Default flatten is 03:50 ET, configurable one to sixty minutes before
04:00. A residual keeps an exit-only PRE/RTH/POST path under the CC's P1-B ruling:
native sell factories set `reduce_only=True`; existing ledger guards bound every
sell to held unreserved quantity. PRE/POST exits are extended-hours LIMIT DAY;
RTH exits are LIMIT DAY with `extended_hours=False`. New entries remain refused
outside OVERNIGHT. Explicit bounded recovery retains its existing journal and
risk history; the active trial's cleanup deadline is never extended automatically.
Quote symbols are bounded to five total,
including any required benchmark. The issuer owns the separate universe scan.
No shipped or frozen diagnostic configuration is changed here.

`BoatsQuoteSource` uses the existing SDK `StockLatestQuoteRequest(feed=DataFeed.BOATS)`
and `StockHistoricalDataClient.get_stock_latest_quote` for each requested symbol.
At most five workers sweep concurrently on a one-second target cadence; each
asset refreshes at least once per strict carrier timeout. Outside OVERNIGHT the
same supported REST request selects SIP for residual exits; ordinary active/tradable
asset state, fresh quotes and standing halt guards are required. SIP entitlement
and broker execution remain owning-lane acceptance, **NOT_RUN**. Each worker owns its SDK
Sessions. Reads use existing guarded HTTP paths, finite SDK request timeouts and
bounded owner callbacks. Shutdown joins the source's workers before closing
their Sessions. A 429 backs off the symbol (2–30 seconds), retaining observations
and order state. Retained quotes/status age naturally and lose admission when
stale; a retry never stamps cached state fresh. The SDK's trading-order stream
remains the supported fill/status path. No BOATS market-data socket is built.

The Controller binds `overnight_check` to the transport and checks quote/carrier
age at reservation, native dispatch, wire-budget admission and immediately before
POST. It refuses missing, unknown, stale and future observations; the carrier
must be broker assets with explicit eligibility and no halt. Native dispatch
retains `entry_dispatch_session_unavailable`/`exit_dispatch_session_unavailable`
when a precondition is missing. Only the explicit REST adapter and complete fresh
inputs admit OVERNIGHT. Plain/streamed BOATS configurations still fail before
credential selection. Delayed `overnight` is never admitted as a fresh feed.

The final carrier
check at the SDK wire boundary returns to the owner loop through the existing
`_on_owner` hook. The journal records that boundary's midpoint and clock before
HTTP, not the earlier reservation midpoint. Execution receipts retain source
execution time, local observation time, latency and signed midpoint slippage;
the execution identity deduplicates replay durably. A missing execution clock
keeps latency unknown. No measured broker timing is inferred from these fixtures.

Broker orders are simple extended-hours LIMIT DAY/GTC; other types, TIFs,
brackets and OCOs are refused. GTC requires the explicit overnight transport
opt-in through normalization, order envelope and SDK request; other transports
retain DAY-only behavior. Client-side trail/time/force exits use marketable LIMIT
sells priced at or below the bid. X1 remains regular-session only and refuses an
overnight plan. A resting exit reprices only after its timeout with fresh quotes
and status; a halt/unknown/stale observation preserves it. Broker stop and
trailing-stop orders are never used overnight.

Before any overnight POST, the ledger persists the carry cutoff, 04:00 boundary
and broker DAY expiry (20:00 of the upcoming trade date). Only a ledger admitting
overnight orders moves to schema 4; older engines refuse it. Reopening the same
ledger retains deadlines and accepted/resting state. A broker `accepted` is never
a fill. The independent owner-loop lifecycle cancels held entries on a halt or
cutoff, regardless of repricing exemptions, and forces flatten at the cutoff.
Held exits in a halt stay resting. Residuals at 04:00 or DAY expiry are flagged,
journaled/notified and frozen for handoff. A successfully flat new trial clears
old carry clocks, while an unresolved trial cannot do so.

`tests/fixtures/adaptive_paper_overnight_cutoff.json` is the third D6 fixture:
accepted entries with halted and unknown status at the cutoff. Tests exercise
real temporary SQLite close/reopen, cancellation, held exits, expiry notification
and freeze. A CI-visible test executes the committed native dispatch method's
AST against protocol fixtures without importing NautilusTrader/alpaca-py; the
native queued-BUY tripwire also exercises OVERNIGHT admission and retained refusal
with the actual pinned engine. These are synthetic guards.

`test_adaptive_paper_overnight_guard_mutations.py` deletes targeted guards in
memory, never modifying a production file. It credits explicit assertion
failures and restores the exact original module/class identities before the
next case. Two deliberately failed peer configuration contexts also produce
secondary test-context errors; those counts are retained separately. The
restored ordinary test modules must still pass.

## Remaining broker acceptance

The installed alpaca-py 0.44.0 exposes the BOATS enum but its `StockDataStream`
constructor accepts only IEX/SIP. The native transport therefore refuses a
BOATS construction as `boats_stream_unqualified_sdk` before constructing a
client. `runner.load_config` and `mover.load_mover_config` both use
`feeds.require_qualified_quote_source` (`feeds.py:47-50`): default `stream` mode
delegates to `require_qualified_stream` and refuses `boats`; explicit `boats_rest`
admits plain `boats` subject to the overnight configuration guards. Both loaders
check before credential selection, broker requests or trial-state writes.
This guard covers the pinned SDK's stream-feed restriction; the transport
refusal remains the backstop. It does not substitute another feed, fork the SDK or rebuild its
stream. A supported SDK REST path and refreshed carrier delivery are staged above.
Authenticated fresh BOATS parsing, per-paper-account entitlement/linkage,
actual poll-sweep wall time and request p50/p99, and the owning T15 overnight
paper/journal run still require retained native acceptance receipts. A one-second
target cadence is not a measured latency or delivery guarantee.

The PR that removes the native OVERNIGHT
`entry_dispatch_session_unavailable` refusal must include the staged overnight
adapter, the supported fresh BOATS path, the accepted-but-held lifecycle and
carry-boundary behavior below, and the third D6 fixture covering halted and
unknown status at the cutoff. **Admission and lifecycle open together.** The
classifier/status slice may land while these admission requirements remain
pending and the deterministic refusal stays in place.

- A held ENTRY is cancelled at a halt and at its carry boundary, through a
  path independent of any repricing exemption.
- A held EXIT in a halt deliberately remains resting, as
  `native_strategy.cancel_expired` specifies (E4), consistent with
  [uet#63 decision 2 (F-1), at f8c607bc](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md).
  At DAY expiry the position is flagged, the session is notified and the
  instance freezes for handoff.
- A broker `accepted` observation is resting, never execution. The carry
  deadline is persisted; the cutoff fixture covers both halted and unknown
  status.

T15 owns adaptive-paper transport and feeds, overnight quote qualification
and the halt-status publisher; T22 consumes them. The qualification record
must name the process that owns the market-data stream under D5's single-stream
rule (the watcher is the candidate) and establish the status-carrier freshness
bound. These are required acceptance work, with no measured live bound or
stream-owner claim supplied by this slice.

The committed admission tripwire is
`IntegratedRunner.test_native_queued_buy_rechecks_dispatch_session_and_preserves_supported_sessions`
in `tests/test_adaptive_paper_runner.py`. Its unqualified `OVERNIGHT_REFUSED` case dispatches
at `2026-03-11T00:00:00Z`, which the current classifier identifies as 20:00
Eastern OVERNIGHT. The unqualified native BUY LIMIT/DAY is denied with
`entry_dispatch_session_unavailable`, with no submission to the synthetic
broker port, fill or reserved intent. Paper acceptance remains **NOT_RUN** until its actual run
and retained receipt.

`MainCommandGateWiring.test_main_preserves_extended_session_window_at_controller_construction`
drives `runner.main()` through Controller construction.
`MoverCommandSessionWiring.test_paper_main_preserves_extended_session_window_at_controller_construction`
drives `mover_runner.main()` through MoverController construction. Both use
PRE/RTH/POST controls and an OVERNIGHT clock.
`MoverCommandSessionWiring.test_recover_main_preserves_extended_session_window_at_controller_construction`
drives `mover_runner.main()`'s `recover` path through MoverController construction
with the same controls. Scripted preflight isolates each constructor's own
window; credentials, account state and broker operations are fixtures.
These three tests run unconditionally in CI without NautilusTrader or alpaca-py.
The original native-class copies remain additional local runtime coverage;
those copies skip in CI and do not establish CI execution of these pins.
All three tests pin `market_open` and the close passed to the controller:
20:00 ET in PRE/RTH/POST, and the preflight close unchanged in OVERNIGHT.
Bypassing a paper `_controller_session` call or always opening mover `recover`
fails the corresponding OVERNIGHT assertion; passing the broker close in a
supported session fails the close assertion.

`OvernightCitationCorrections` binds the three corrected citations to
`tests/fixtures/adaptive_paper_citations/`: two bounded public vendor fixtures
and F-1 pin/source metadata. Full source captures remain in the review packet.
The recorded old/new Decision 2 hashes differ in wording; they do not claim byte
equality. These checks use no network or private files in CI.

## Primary sources

- Alpaca [24/5 Trading](https://docs.alpaca.markets/us/docs/245-trading.md),
  updated 2026-07-07T14:17:11Z, fetched 2026-10-10: hours, trade date, holidays,
  half-days, eligibility/halt attributes and DAY carry boundary. Fetched SHA256
  `ead2fa117d2fd65384d69cd711f6846fd81b44a7f72486c8a1dcaf80a54e196c`.
- Blue Ocean Technologies [venue hours](https://blueocean-tech.io/), fetched
  2026-10-10: NMS stocks 20:00–04:00 Eastern, Sunday–Thursday evenings. The
  unversioned venue page is source review, not a captured broker acceptance.
- Alpaca [Real-time Stock Data](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data.md),
  updated 2026-05-18T07:19:29Z, fetched 2026-10-10: `v1beta1/boats` and the
  separate Trading Status channel. Fetched SHA256
  `5a1857f5d0cd4652079dadd45df0a674b370ea725e8ddf2c9f1ccb4ade211f83`.
- Alpaca [Get an Asset by ID or Symbol](https://docs.alpaca.markets/us/reference/get-v2-assets-symbol_or_asset_id.md),
  the endpoint behind `TradingClient.get_asset`, updated 2026-05-27T17:58:22Z,
  fetched 2026-10-11: `attributes` is a list of strings whose values include
  `overnight_tradable` and `overnight_halted`. Fetched SHA256
  `a379eba034acae0aee1ba85158c830264698019670324fdca30e7b8ea28694a4`.
- Alpaca [Historical Stock Data](https://docs.alpaca.markets/us/docs/historical-stock-data-1.md),
  updated 2026-02-11T05:30:13Z, fetched 2026-10-11: the `overnight` feed is
  Alpaca's feed derived from the BOATS source, with trades 15 minutes delayed
  (the derived/delayed feed above). Fetched SHA256
  `f5c481f99797985246a69fc2938871ee2e2820b8ff106b20b1e0493d7a985fad`.
- [alpaca-py v0.44.0](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28),
  commit `cc4cb3b7ba50ae250e621983c2779047fb16bb28`:
  `alpaca/data/enums.py:56-73` (BOATS and derived OVERNIGHT),
  `alpaca/trading/models.py:70` (`Asset.attributes`),
  `alpaca/trading/client.py` (`get_asset`, supported Trading API read), and
  `alpaca/data/live/stock.py:47-48` (native IEX/SIP restriction).
- [exchange-calendars 4.13.2](https://github.com/gerrymanoim/exchange_calendars/tree/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a),
  commit `dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a`:
  `exchange_calendars/exchange_calendar_xnys.py` and native session APIs.
- Landed D6/T15 scope:
  [us-equities-trading at 586171951a1595cfd0811cfb8b9c012897eb9543](https://github.com/seathatflowsinourveins/us-equities-trading/blob/586171951a1595cfd0811cfb8b9c012897eb9543/docs/decisions/2026-10-09-equities-intraday-scope.md),
  D6 and T15. This is owner policy; broker/venue facts above remain primary.

The stream comparison remains a maintained vendor-supported BOATS stream at an
authenticated SDK pin, followed by the same guards and the owner's native paper
acceptance. The accepted REST path uses the held pinned SDK, while its cadence,
entitlement/linkage and paper execution remain measured acceptance work.
