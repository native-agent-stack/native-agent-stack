# Exploratory rate-limit and place-only modes

Both flags are off by default. This is a paper transport probe, never a
strategy or capacity promotion. Ordinary admission, receipt fields and cleanup
remain unchanged when neither flag is set. Native account locking, fixed paper
origins, non-marketable whole-share limits, fresh quotes, STOP checks and foreign
order refusals still apply. No credential, live URL or other lane's state is
added to this protocol.

`--place-only` suppresses individual cancels during the rung, accumulating
resting one-share probes. Cleanup performs **one** native cancel-all request
after the existing complete prefix-ownership listing proves every open order
belongs to this run and preflight was flat. It then requires a complete listing
with zero open orders. A foreign order, unsupported bulk port, partial bulk
result or verification failure is not paper success. There is no hidden
individual-cancel fallback in that mode: a failed cleanup stays `needs_attention`
and uses the already documented separate `recover` path under the owning lane.
The bulk207 status is not interpreted as proof that every order was cancelled.

The native Alpaca port calls `TradingClient.cancel_orders()`,
`alpacahq/alpaca-py@cc4cb3b7ba50ae250e621983c2779047fb16bb28` (installed0.44.0),
`alpaca/trading/client.py:203-215`. Only its explicit place-only session admits
DELETE `/v2/orders`. Ordinary sessions, read-only sessions, data origins and
live origins do not gain this capability. SDK retries stay disabled; a native
bulk request is attempted at most once by the rung, then verified.

`--probe-limit` deliberately permits the requested experimental request rate
instead of `min(configured, observed) * headroom`. The **existing** governor
retains token/rolling-window pacing at that requested rate and records the real
observed header separately. Its remaining-header admission guard is bypassed
only during this explicit experiment. One trading request may be in flight,
so the first observed429 stops new submits/cancels before another admission.
The receipt records that first status/kind/time and the whitelisted remaining,
limit, reset and Retry-After headers. Broker backoff is honored; cleanup restores
normal observed-limit/headroom admission. The flag never applies to `recover`
or `audit` and the CLI refuses those combinations before loading credentials.

This scoped lift answers the owner's explicitly authorized probe; it does not
change any live cap or normal paper policy. Alpaca Support documents the Trading
API as200 requests/minute **per account** and a429 above it:
<https://alpaca.markets/support/usage-limit-api-calls>. The pinned SDK's
`alpaca/common/rest.py:195-207` reacts to configured retry statuses;
`alpaca/common/constants.py:11-13` sets429/504 defaults. The existing guarded
transport observes x-ratelimit-limit/remaining/reset and Retry-After; no new
SDK polling or replacement order/rate implementation is introduced.

## Explicit rung bounds and proposed invocation

Each flagged rung is at most90s; `--probe-limit` is at most250 requests/minute
and one share per probe. Ordinary stock/notional limits and defaults are
unchanged. A place-only operator may **explicitly** provision up to300 open
probes and300,000 USD notional for the bounded rung; these are hard ceilings,
not automatically raised defaults. If the default10-open-order or10,000 USD
notional cap binds first, a missing429 is recorded as no observed onset, not
evidence that the requested load reached the broker. Native buying-power,
collar, unexpected-fill and quote guards remain real failure boundaries.

The following are unexecuted owning-lane examples, through the documented paper
loader, in a clean checked-out reviewed source tree. The coordinator supplies
a between-series account gap and flat/idle reads before and after each release.
The experiment does not overlap lane A's series and never uses lane B's account.

```sh
# R is one of150,200,225,250; credentials are supplied only to the existing loader.
python -B blueprints/us-equities/order-throughput/capacity.py paper \
  --env-file "$PAPER_LOADER_POINTER" --feed sip --cap "$R" \
  --probe-limit --duration 70 --required-windows 1 --max-orders 350 \
  --output "$OWNED_RUNG_DIR/with-cancels.json"

python -B blueprints/us-equities/order-throughput/capacity.py paper \
  --env-file "$PAPER_LOADER_POINTER" --feed sip --cap "$R" \
  --place-only --probe-limit --duration 70 --required-windows 1 --max-orders 350 \
  --max-open-orders 300 --max-open-notional 300000 \
  --output "$OWNED_RUNG_DIR/place-only.json"
```

Keep paths private and never copy an env file or its values into a packet.
Do not set `--acknowledge-positions`, `--acknowledge-open-orders`,
`--accept-adaptive-lane-conflict` or custom paper STOP flags. A current paper
state conflict is refused, not bypassed. An absent onset or a price/buying-power
refusal remains a retained non-measurement of that rung's intended request load.

## Receipt and journal evidence

Flagged receipts include `probe_modes` with place-only/probe-limit booleans,
requested experimental rate, effective trading concurrency, first429 and an
explicit qualification-false marker. `acceptance.passed` remains false for
exploratory modes even if cleanup succeeds. The existing CLI process exit code
continues to distinguish refusal/needs-attention/criteria, so a completed
short rung can exit1 without inventing a capacity pass.

Flagged latency summaries addp90 to the existing p50/p95/p99. The journal adds
per-sequence numeric latency samples and a first429 row before its end record;
the existing recovery parser ignores those additional measurement row types.
No broker order/account identifier is added to the measurement rows. A bulk
cancel is counted separately as one cleanup request, not as one individual
cancelled-order action. Submit-only throughput excludes the cleanup request.
Latencies are submission-to-REST-ack, submission-to-stream-ack and
submission-to-stream-terminal; terminal latency in place-only includes the
deliberate hold until rung cleanup and is not cancel-REST RTT.

Fixture controls prove default-off behavior, first429 stop and safe cleanup
reset, exactly one guarded bulk request, foreign/partial/STOP cases, numeric
p90 recomputation, recovery parsing and paper-only capability fences. They
are synthetic/native-SDK-boundary evidence. No actual Alpaca limit onset,
place-only native rate or three-account aggregate throughput has been measured
by this change. Those runs wait for both reviews and the coordinator's gap.
