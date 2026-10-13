# Exploratory rate-limit probe and place-only refusal

Flags default off. Ordinary admission, individual cancellation and receipt
behavior remain unchanged without them. Probes are paper transport research,
not strategy trades or capacity promotion. Fixed paper origins, fresh quotes,
STOP, account locking and foreign-order checks still apply.

## Place-only is unavailable until flat recovery is qualified

`--place-only` is recognized and recorded, but refuses before credential loading,
SDK client creation, preflight, streaming, account locking or submission. The
refusal is `place_only_requires_qualified_flat_recovery` for valid configuration;
invalid arguments retain their own configuration refusals. A refusal receipt is
written with zero submitted probes. A combined `--place-only --probe-limit`
cannot bypass this boundary. There is no place-only native measurement claim.

The earlier implementation returned after a single bulk cleanup and suppressed
ordinary individual cancellation. Synthetic controls reproduced five owned
open orders after partial 207, failed bulk cancellation, incomplete listing or
late foreign arrival; moving the market also left five filled shares (2.5 in
the new partial-fill control). That is unsafe even when labelled needs_attention.
The corrected implementation chooses pre-submission refusal, removes the
cancellation suppression/early cleanup branch, and removes the unused native
bulk capability. These are controls of the real state machine, not observations
from a paper account. Existing foreign orders remain untouched by refusal.

Primary source: alpacahq/alpaca-py0.44.0 at
`cc4cb3b7ba50ae250e621983c2779047fb16bb28:alpaca/trading/client.py:203-215`
returns individual cancellation statuses from `cancel_orders()`; 207 cannot
prove zero open orders. At `:296-324`, `close_position()` places another order,
which is not itself evidence of a flat position. The current guarded port and
prefix recovery have no qualified bounded position-recovery path. No new
liquidation permission or writer is added to make an unsupported flat claim.
The selected SDK remains unchanged. A future place-only implementation must
qualify recovery under the same account lock and prove complete zero-owned-order
listing and independent flat-position reread, including partial fill, broker
backoff and foreign-order cases, before admitting its first probe.

## Rate-limit probing with ordinary cancels

`--probe-limit` lifts the observed-limit/headroom ceiling for one bounded
experiment. The existing governor still paces at the configured request rate;
its remaining-header guard is bypassed only during the experimental phase.
There is one trading request in flight. The first observed 429 stops new
admission and records its status, operation, time, x-ratelimit-limit,
x-ratelimit-remaining, x-ratelimit-reset and Retry-After. Cleanup restores normal
observed-limit/headroom admission and honors broker backoff, using the existing
bounded prefix-owned individual cancellation and complete verification sweeps.
The flags are refused on `recover`/`audit` before credential loading.

Bounds are 90 seconds, 250 requests/minute, and one share per probe. Stock,
notional and buying-power guards remain unchanged; requesting a rate does not
prove it reached the broker. Probe-limit retains the ordinary fast cancellation
path. Its exposure controls do not promise that an arbitrary market movement
can never fill a limit order.

Alpaca's cited support reference is
<https://alpaca.markets/support/usage-limit-api-calls> (200 requests/minute per
account); retained response bytes and digest are a custody follow-up, so that
unmirrored page is not newly independently verified here. Native rate headers
and onset measurements are separate evidence. SDK sources at the same pin,
`alpaca/common/rest.py:195-207` and `alpaca/common/constants.py:11-13`, document
retry handling/defaults; the existing guarded transport keeps SDK retries off.

## Reviewed-head measurement trigger

Only the reviewed source may run, through the documented paper loader, in a
fresh worktree and a coordinator-granted gap with independent flat-and-idle
reads before and after. It remains one writer and uses the released account;
it never overlaps another series or bypasses STOP or lane-state conflicts.

Unexecuted with-cancels example, `R` in 150, 200, 225, 250:

```sh
python -B blueprints/us-equities/order-throughput/capacity.py paper \
  --env-file "$PAPER_LOADER_POINTER" --feed sip --cap "$R" \
  --probe-limit --duration 70 --required-windows 1 --max-orders 350 \
  --output "$OWNED_RUNG_DIR/with-cancels.json"
```

A standalone place-only rung remains unavailable and unmeasured. No native
limit onset or simultaneous three-account independence is claimed by fixtures.

## Receipts and follow-ups

`probe_modes` records requested modes/rate, concurrency and first 429.
Exploratory `acceptance.passed` remains false. The receipt cancellation plan
states when place-only was refused rather than describing unexecuted individual
cancellation. Probe-limit journals retain numeric per-sequence latency samples
and p90 alongside p50/p95/p99; recovery parsing remains compatible. Order and
account identifiers are not added to measurement rows. With-cancels terminal
latency is not cancel REST RTT.

Nonblocking test follow-ups: held-future serialization and single-token bucket
mutation controls. Exact-boolean and otherwise-valid recovery CLI refusal
controls are now pinned; the unused bulk forwarding paths were removed.
Source custody follow-up: retain support-page bytes with observation time/hash.
The protocol is an explicit experimental extension; no private owner text is
published as a vendor claim or quoted instruction.
