# Alpaca paper order-rate facts, measured 2026-10-13 (sanitized projection)

This directory is a publication-safe projection of private measurement receipts. It states what was measured about the Alpaca
**paper** trading API's request-rate limit and about one governed order-rate run, with arithmetic that anyone holding the receipts
can reproduce. It contains no account identifier, credential, client order id, price, symbol or file-system path.

## Files

| File | What it is |
| --- | --- |
| `alpaca-throughput-evidence-20261013.json` | The projection: one deterministic JSON document (schema `alpaca-throughput-evidence/1`). |
| `generate_alpaca_throughput_evidence.py` | Builds the JSON from the private receipts. Stdlib only; no network, clock or environment. |
| `verify_alpaca_throughput_evidence.py` | Recomputes every headline number from the raw receipts and prints PASS/FAIL per number (exit 0 only if all pass). |
| `audit_publication_safety.py` | Counts identifier-shaped and path-shaped tokens in files; used for the sanitization audit. |

## What was measured

1. **The trading rate-limit header, on three paper accounts** (lane A, lane B, account C; the mapping to real accounts is private).
   Read-only GETs on `/v2/clock`, `/v2/account`, `/v2/orders?status=open&limit=1`, `/v2/positions` and `/v2/account` again,
   one account per run, between 06:40 and 06:42 UTC. On every account `/v2/account`, `/v2/orders` and `/v2/positions` reported
   `x-ratelimit-limit: 200` and `x-ratelimit-remaining` fell by one per request (199, 198, 197, 196): one shared bucket.
   `/v2/clock` reported its own limit, 1000.
2. **A governed capacity run on the lane A account (run `a2`, 05:12 to 05:18 ET pre-market).** One liquid ETF, 1 share, non-marketable
   limit orders 500 bps below the bid, each cancelled individually, extended-hours orders on. The configured cap was 200 requests per
   minute; the governor admitted 180 (`floor(200 * 0.9)`, a 20-per-minute reserve).
   * 496 orders accepted and 496 cancels acknowledged, no HTTP 429, stream completeness 1.0, zero open orders afterwards, no fills.
   * Five consecutive full one-minute windows of exactly 180 completed order actions (submits plus cancels); a 330.002-second
     submission phase with 991 completed actions (mean 180.181 per minute).
   * Derived: **90 orders per minute, each with its cancel** (`89.999455` over the phase, `90.000` over the full windows).
   * Of the 1,001 trading-origin responses during the run, 1,000 reported limit 200 and one (consistent with the single `/v2/clock` read) 1000, so
     every submit and every cancel response reported 200.
3. **A separate order-count observer** (one read-only listing after the run) matched 496 orders listed, 496 canceled, 0 filled,
   496 submits and 496 cancels. It aligns one-minute windows to the first order's broker time, so its first full window shows 181
   actions against the harness's 180; totals are identical.
4. **A superseded attempt, `a1`**, was refused at the configuration stage before any request because its base URL carried a `/v2`
   suffix (`non_paper_base_url`); `a2` used the bare paper host with an otherwise identical configuration.

## Units

An *order* is one accepted submit. An order with its individual cancel is **two** completed trading requests, and the vendor bucket
counts requests, so a 200-requests-per-minute bucket is at most 100 orders per minute each with its cancel (200 place-only requests).
The governed budget of 180 gave the measured 90 orders with cancel per minute.

## Not measured (do not infer)

* place-only (no cancel) capacity; the harness cancels every probe
* the HTTP 429 onset or any rate above the 180-requests-per-minute governed budget
* simultaneous order-write throughput on several accounts
* sharing of the bucket across connections or keys of one account (a vendor statement, not measured here)
* latency p90 (the receipt records p50, p95, p99 and max with the nearest-rank method; there are no raw samples)
* regular-session behaviour: the run was pre-market

## Latency fields (milliseconds, from the receipt)

| Field | p50 | p95 | p99 | max | n |
| --- | ---: | ---: | ---: | ---: | ---: |
| REST acknowledgement (`submit_rest_ack`) | 20.631 | 24.407 | 32.646 | 157.167 | 496 |
| Stream acknowledgement (`submit_to_stream_ack`) | 32.759 | 38.594 | 62.904 | 149.542 | 496 |
| Stream terminal event, i.e. cancel complete (`submit_to_stream_terminal`) | 368.158 | 388.310 | 2031.212 | 2034.778 | 496 |

## Which private receipt backs which number

| Number | Receipt and field |
| --- | --- |
| limit 200 on account, order and position reads; 1000 on the clock; remaining 199, 198, 197, 196 | the six header-probe receipts (v1 and v2, three accounts): request-ordered limit and remaining |
| 496 submits, 496 cancels, no 429 | `a2` capacity receipt: `orders`, `http_status_counts`, `http_429` |
| five full windows of 180; 330.002 s; 991 actions; mean 180.181 | `a2` receipt: `throughput` |
| latency percentiles | `a2` receipt: `latency` (the journal holds intents only) |
| 1,000 observations at 200, one at 1000; lowest remaining 194 | `a2` receipt: `observed_rate_limit_headers`, `preflight` |
| 496 listed, 496 canceled, 0 filled; windows 181/180/180/180/180/91 | order-count observer receipt |
| refused attempt | `a1` capacity receipt: `status`, `stage`, `refusal_reason`, `config` |
| 89.999455, 90.181272, 90.000, 89.784430 per minute | computed in the projection; formulas in `derived_units.formulas` |

The JSON lists the byte size and SHA-256 of each private receipt file; each was audited to hold no identifier, credential,
user name or path before its digest was listed.

## Verify

```
python3 verify_alpaca_throughput_evidence.py --evidence alpaca-throughput-evidence-20261013.json \
    --capacity-dir <capacity run directory> --header-receipts-dir <directory holding the six header receipts> \
    --observer-receipt <observer receipt file>
```

The verifier is independent of the generator, so it also catches a generator error. The private receipts are not published; the
verifier is for holders of the private state.

## Caveats

One account, one session class, one 330-second submission phase. The receipt's `passed` flag is self-reported by the harness; the
observer block is the separate count check, and it uses the same vendor API, so it does not certify latency. The trade-update stream
logged one reconnect notice with normal closure codes; the receipt reports completeness 1.0 and no health freeze. The vendor's
own statement of the per-account limit comes from its support page and was not re-read for this projection.
