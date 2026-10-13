# IBKR pacing publication boundary

The canonical JSON, generator and verifier retain the approved trading-cc
**revision 4** bytes unchanged. [V4-CHANGES.md](V4-CHANGES.md) is retained
unchanged and supplies the per-rung correction; [V3-CHANGES.md](V3-CHANGES.md)
retains the earlier sliding/peak/ownership correction. Neither adds a measurement.
Revision-1 through revision-3 predecessors remain inspectable public files, so the
document's superseded commitments have public preimages. Original receipts and
internal probe helpers are not read or copied by this publication.

| Active approved artifact | SHA256 |
| --- | --- |
| `ibkr-pacing-evidence-20261013.json` (v4 bytes) | `841ec5965caa6fa6d1b7d7ed5ddfa34af8ca38ba26028bf6226847fcad368900` |
| `generate_ibkr_pacing_evidence.py` (v4 bytes) | `d14fb1e81fabe1055d4e2a155f2fe76fbe0401dbe7bc30234ca8558d0e308f68` |
| `verify_ibkr_pacing_evidence.py` (v4 bytes) | `b72e5a341915d3f1d863f8aaef9de953c690efd273ee00f1d322d1112eca7913` |
| `V4-CHANGES.md` | `61e93447bad4421d85f3b678b5ed61e1c206d43f92326b88f78ba15cd666a29a` |
| `V3-CHANGES.md` | `edbb14013d15b8e9164685e024ed68b02ec676f8ea3d7f83e6591f3a843cc855` |
| `ADDENDUM-01.txt` | `bbbb4d0096d0cab5577050f1b2ba31348fbc6cf5a1969b251bcb35649963b7f6` |
| `ADDENDUM-02.txt` | `f1de0a311acc5bcd7d7eeddd51e7fef35196dcd76c4f878f1564424f4f834a9c` |
| `ADDENDUM-03.txt` (re-sealed v2 text, unchanged) | `ac6adcea2551c8e9df26efd0fa434d5283dccdc74f8af17f32afba9c7bc9b324` |

The published README updates the rate definition and adapter peak definition
from v3 and the exact corrected rung sentence from V4-CHANGES section 4; it is
no longer byte-identical to the original producer README.
Its original source and the v1-v3 producer seals remain unchanged at the producer.
Published file hashes, including the updated README, are registered natively in
`manifests/evidence.json`. The retained change records' section 6 describes the
producer's pre-publication status; the canonical PR paths now carry v4.

## Current definitions and correction table

Sources: [V3-CHANGES section 4](V3-CHANGES.md) for sliding/peak corrections,
[V4-CHANGES section 4](V4-CHANGES.md) for the superseding rung means, and JSON
`/facts/rate_window_conventions`, `/facts/peak_open_orders_definition`.

| Field | Current meaning | Boundary |
| --- | --- | --- |
| Whole-run `max_1s` | Largest message count in sliding half-open one-second windows anchored at message timestamps | Counted and source-derived wire series remain separate. |
| `best_5s_mean` | Largest sliding five-second count divided by five | Integer microseconds; start included, end excluded. |
| `*_utc_buckets` | Retained revision-2 UTC-aligned values | These historical buckets are distinct from the current sliding maxima. |
| Rung `wire_est_*_msgs_per_s_mean` | Messages inside the rung's own window divided by its recorded seconds | Includes other rungs' cancels sent inside; excludes its orders' cancels sent outside. Earlier means remain `*_by_order_rung`. |
| Rung `counted_msgs_per_s_min/max` | Original receipt slot counters | Fixed slots; a slot maximum is a lower bound of the sliding maximum. |
| Adapter `peak_open_orders` | Submitted orders through their first terminal order event, including rejected/filled/canceled terminals | A rejected cancel is not terminal; no terminal event leaves an order open in the journal counter. |
| Official-client `peak_open_orders` | Original runtime counter, unchanged | A 103-refused order counts until the stale cancel is answered; not recomputable without private per-message records. |
| Missing-ID ownership | V3 checks each missing ID against exactly one owner journal | Retained histogram: 0 missing owners, 38 single owners, 0 multiple owners. |

The section-4 FAIL claims are replaced as follows:

| Corrected claim | Sliding result |
| --- | --- |
| All adapter pairs at or below 50 wire messages/s | Upper bounds m1/m2/m3/m4: **53/47/40/52**, refined **52/47/40/47**; m1 and m4 fail the old upper-bound ceiling. |
| Pair ceiling of 45/s | Upper-bound maximum **53**, with m4 also reaching **52**. |
| B-r5 best five-second upper-bound mean at or below 50 | **51.2** refined and upper bound; B-r6 refined is **56.6**. |
| B-r5 rung-50 slot counter 38 as peak rate | Sliding in-rung maximum **46 counted / 69 wire**. |
| Whole-run B-r5/B-r6 maxima | Counted **46/53**, refined wire **69/78**, upper wire **69/83**, replacing bucket **37/48**, **57/66**, **57/71**. |

Unchanged counts and official means: official rung-50 mean 49.95 messages/s, 500 orders
in 20 seconds, rate 1,500 orders/minute and 2,997 messages/minute; adapter rung-30
means now **44.75 refined / 44.8 upper** wire messages/s. Rung40 means are
**51.3/56.5** and rung50 **49.05/56.45**; three of those four remain above50.
Source: [V4-CHANGES section 4](V4-CHANGES.md). The rung-30 sliding maxima are
63 refined / 64 upper wire messages; a mean is not a burst ceiling. Adapter
`pacing_error_count`, code-100 lines and pacing-text lines remain zero; no
disconnect occurred. Official-client receipt maxima are unchanged and its
true rung-50 one-second maximum is at least 51, without recomputable message times.

**Whether a sliding 1 s window above 50 wire messages is above the cap depends
on how the Gateway counts, which this evidence does not establish.** Hidden
requests remain source-derived and stamped with cancel-row timestamps. Per-rung
window replay matches 38 of 40 receipt grids; two differ by one message. Sources:
[V3-CHANGES sections 4–6](V3-CHANGES.md) and JSON `/facts/rate_window_conventions`.

## Producer verification and predecessor custody

[V3-CHANGES sections 1 and 5](V3-CHANGES.md) retain the producer's failing-first
controls for per-ID ownership, sliding windows and terminal-event peaks.
The producer reports **174 passing checks** with the pinned `core.rs` source
check, or **169** without it. V2's 82 checks accepted the swapped-owner negative
root; v3 rejects it. These are attributed producer results. This documentation
change checks approved bytes and public consistency, without reading original
private roots or independently replaying broker measurements.

V4's [verification record](V4-CHANGES.md) reports **223 checks without** the
pinned source check, **228 with** it, and byte-reproducible generation across
three Python versions. Per-rung means are independently window-derived; mutation
controls reject changed means and cancel-window classifications. These remain
producer-attributed results, not an author private-input replay.

All nine earlier producer preimages remain in this directory with versioned names:
`generate_ibkr_pacing_evidence.v1.py`, `verify_ibkr_pacing_evidence.v1.py`,
`ibkr-pacing-evidence-20261013.v1.json`, and their `.v2.py`/`.v2.json` and
`.v3.py`/`.v3.json` counterparts.
They are historical source, not the active verifier or current measurement schema.
ADDENDUM-03 stays exactly at its re-sealed v2 text; its old aggregate-ownership
statement is superseded by the v3 per-ID checks. ADDENDUM-02 corrects the earlier
README's undocumented-rule statement. The 35/1/2 missing-order split and
transcript-derived third broker count of 10,313 remain unchanged.

## Text commitment guard

The re-sealed addendum omits the internal unpublished probe commitment.
[scripts/check_text_digests.py](../../../scripts/check_text_digests.py) admits file
preimages only from indexed regular publication files. Untracked/ignored files
and symlinks cannot justify commitments. Full and 7+ character prefixes are
checked; decimal-only numeric labels are not treated as digest commitments.
Findings print locations/lengths without unresolved values or prefixes.

Audited [public references](text-digest-public-references.json) carry their source
URL and class: public Git commits and the image identifier named by the unchanged
vendor Markdown. The latter must match both the indexed capture hash and its
literal image-path witness; it is not claimed as an image content hash. No binary
image is included in this text-only packet. The marker record's short commit
resolves to an ancestor of public main; private operational contents stay excluded.

## Official source captures

These unchanged Markdown responses were checked on 2026-10-13. They have no
advertised version tag in their bytes.

| Capture | Official source | SHA256 |
| --- | --- | --- |
| [pacing-introduction.md](pacing-introduction.md) | <https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/introduction.md> | `f85d35eccd35c267ff7cba983d057082ddb0936490a988122c93715e00641d2d` |
| [pacing-behavior.md](pacing-behavior.md) | <https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/pacing-behavior.md> | `608161d8d9ddfcdfba5d02a931fb5e082ae7c8a821a8d34851bbc4454c506d54` |
| [small-bars.md](small-bars.md) | <https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/pacing-violations-for-small-bars-30-secs-or-less.md> | `fa12f6d99bd60939f181e451ecd79018ba6bdcdf9b77c26a21ec7cc43d6c27eb` |

The official legacy order-submission page was checked for its `reqAllOpenOrders`
rule on 2026-10-13; it is not used for current pacing numbers:
<https://interactivebrokers.github.io/tws-api/order_submission.html>.
The measured adapter remains `nautechsystems/nautilus_trader` at
`01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25`, native cancel path
`crates/adapters/interactive_brokers/src/execution/core.rs:381,2387,2417,2429,2624,2637`.
This differs from selected rc5 and makes no engine re-pin or broker acceptance claim.
