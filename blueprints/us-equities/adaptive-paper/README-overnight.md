# T15 overnight session and status checks

Paper acceptance: **NOT_RUN**. This implementation changes the pure market
clock, feed vocabulary and deterministic submission checks. It does not arm an
overnight lane, change frozen N2 sources/configuration, or qualify a broker run.

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
refuse; the conservative status age bound is the port's existing quote timeout.
Out-of-order asset resumes cannot clear a newer halt; restrictive eligibility,
unknown status and halts win timestamp ties in either arrival order.
These guards apply to recovery's transport submission path as well as native
strategy orders. Cancellation and observation remain available.

Existing extended-hours policies continue to admit PRE/RTH/POST only: under
them the runner's controller window (`runner._controller_session`) opens only
in those three sessions. The order-throughput capacity harness (`capacity.py`)
refuses every other session as `market_session_closed`, so it never runs
OVERNIGHT as regular hours. Native
dispatch and exit plans still refuse/flag OVERNIGHT. The helper for a proposed
overnight order sets `extended_hours=True` and bounds its DAY window at the
upcoming trade date's 20:00; this pure mapping grants no submission authority.
Held-book financing and prior-RTH-close capture retain the completed RTH date
through an OVERNIGHT observation and midnight. An explicitly reconciled hold
keeps its existing `overnight_holds` disposition; faults and attention do not
become successful holds. The corporate-action lookahead remains conservative:
OVERNIGHT's upcoming trade date and the following trading session are checked.

## Remaining acceptance

The installed alpaca-py 0.44.0 exposes the BOATS enum but its `StockDataStream`
constructor accepts only IEX/SIP. The native transport therefore refuses a
BOATS construction as `boats_stream_unqualified_sdk` before constructing a
client. `runner.load_config` and `mover.load_mover_config` both use
`feeds.require_qualified_stream` to refuse a `boats` configuration with the same
reason before credential selection, broker requests or trial-state writes.
This guard covers the pinned SDK's stream-feed restriction; the transport
refusal remains the backstop. It does not substitute another feed, fork the SDK or rebuild its
stream. A supported native BOATS path, authenticated real-time parsing,
per-paper-account entitlement/linkage, refreshed status delivery and the
owning T15 overnight paper/journal run are still required.

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
in `tests/test_adaptive_paper_runner.py`. Its `CLOSED`-labelled case dispatches
at `2026-03-11T00:00:00Z`, which the current classifier identifies as 20:00
Eastern OVERNIGHT. The native BUY LIMIT/DAY must be denied with
`entry_dispatch_session_unavailable`, with no submission to the synthetic
broker port, fill or reserved intent. Paper acceptance remains **NOT_RUN** until its actual run
and retained receipt.

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

The comparison that would replace the current native refusal is a maintained
vendor-supported BOATS stream at an authenticated pin, followed by the same
synthetic guards and the owner's native paper acceptance. The recorded enum
and REST endpoint alone are insufficient.
