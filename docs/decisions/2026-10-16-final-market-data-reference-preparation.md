# Market data/reference FINAL preparation (2026-10-16)

Status: **PREPARATION / GAP draft; private reproduction passed**. No FINAL
admission, runtime/default change, entitlement or order authority is granted.

All main-path citations below refer to
`seathatflowsinourveins/native-agent-stack@caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`.
The scope is the existing layer's three winners and four survivors from the
latest covering sweep, 20260926. No new landscape survey or model read ran.

## F1 run-pin reconciliation

The complete ledger is
[run-pins.json](../../blueprints/us-equities/final-market-data-reference-20261016/run-pins.json).

| Winner | Proposed execution version / source commit | Exact main-value lines |
| --- | --- | --- |
| alpaca-py | 0.44.0 / `cc4cb3b7ba50ae250e621983c2779047fb16bb28` | final-stack.json:9607 verdict, :10422 run; manifests/stack.json:1442 version, :1465 source; runtime uv.lock:105 |
| EdgarTools | 5.61.1 / `7338aa335f6442c52dfa0695422cf1cd27e946e0` | final-stack.json:10652 run; runtime uv.lock:546; retained checkout commit in recapture-v1/edgar-source-commit.log:1 |
| exchange-calendars | 4.13.2 / `dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a` | final-stack.json:9651 verdict, :10664 run; manifests/stack.json:1571 version, :1574 source; runtime uv.lock:603 |

The clean-install plan names Alpaca at :586 and calendars at :590. Its :589
retains EdgarTools 5.58.0 and a pending 5.62 screen. The EdgarTools historical
verdict at final-stack.json:9629 is 5.58.0, while manifests/stack.json:1539
and :1542 identify the distinct 5.60.0 SEC recipe. The scoped correction in
catalogs/us-equities/catalog-refresh-20261009.json:18, :24 and :32 separates
runtime 5.61.1, recipe 5.60.0 and initial-wave 5.58.0; :43 limits the offline
smoke claim. No old verdict, recipe, runtime manifest or lock is rewritten.

The native read-only metadata capture reports the three installed versions
at recapture-v1/existing-host-package-metadata.log:1. The historical evidence
records in the ledger remain historical assertions, not a new acquisition
or a fresh certification that no later record exists.

## Native execution and capture custody

A fresh isolated CPython 3.12.3 venv used the upstream pip installation route
through uv's pip interface. The exact command, observed return code, timestamps
and byte-stream output are retained privately. The newly resolved dependency
closure is frozen; this is not a hash-locked runtime migration.

The upstream EdgarTools offline-audit command at pinned pyproject.toml:253
ran without configured SEC identity or vendor keys. Its untrimmed native
pytest output reports **29 passed, 10 deselected, 4 warnings** at
recapture-v1/upstream-offline-tests.log:24, exit 0. The upstream socket/DNS
guard remains active; `-o env=` suppresses test contact injection. This is
bounded upstream offline testing, not the full suite or SEC acquisition.

Native SDK calls print returned objects/values rather than templated pass
summaries. The native-invoke-final.log reports versions at :1, :2 and :3,
the parsed SGML acceptance wall clock at :4, the Alpaca request object at :5,
XNYS session booleans at :6 and :7, and its early close at :8. Assertions
completed with exit 0. These are offline SDK diagnostics; no Alpaca client
or broker was created. The naive acceptance wall clock does not establish
historical publication time. Actual pinned-source and installed-wheel
hashes are in edgar-source-wheel-hashes.log; the three pairs at :4/:12,
:5/:13 and :6/:14 match.

The 16 native command captures have 32 published derivatives. Each JSON
receipt is labelled `masked_native_capture`; its exact private command,
original stdout/stderr bytes and original recorder metadata remain private
by name only. Public commands use marked placeholders. Both the log and
receipt reproduce through the published
[mask_capture.py](../../blueprints/us-equities/final-market-data-reference-20261016/mask_capture.py).
All unmapped bytes, line endings and trailing whitespace are preserved.
Only published-byte hashes appear publicly. The co-op privately confirmed all
32 derivatives reproduce from 16 retained captures, all 33 inventory hashes/sizes
match, and all 16 command/return-code bindings match. It reran the 5 masker
tests; it did not rerun the 2 recorder custody tests, whose published log
reproduces from its original capture.

Masker tests report 5 cases at recapture-v1/masking-tests.log:8; recorder
custody tests report 2 at recorder-tests.log:5. The latter use explicitly
synthetic child output to check failed-command raw retention and overwrite
refusal. They are regression tests, not component or trading evidence.
The recorder extends this preparation's original recorder through CPython's
documented subprocess byte-stream and regular-expression interfaces.

The earlier ten command records lacked retained originals. They and their
derivatives are excluded from this publication, preserved privately only as
unqualified observations. Fresh runs supersede them; none was reconstructed
or relabelled as a valid receipt. Earlier setup/release-API observations have
no qualifying original captures and supply no new native evidence.

## Carried survivors and six angles

The existing `tools/sota-convergence/lane_packets.py` generated the retained
layer packet. Its historical candidate context does not expand this delta.
The seven-candidate
[multi-angle.draft.json](../../blueprints/us-equities/final-market-data-reference-20261016/multi-angle.draft.json)
is a preparation draft, not an accepted angle-convergence record.

At their carried pins, Databento README.md:49, Tiingo README.rst:77 and
Massive README.md:31/:167 require vendor keys. These acquisition paths are
named gaps; no key or account was read. Exact pins, public source hashes and
locators are in
[survivors.json](../../blueprints/us-equities/final-market-data-reference-20261016/survivors.json).

ArcticDB's carried source identity remains
`7d30a6eefe709e5379f1dd7f38b03074750cf1be`. Its separate release trial uses
6.26.0/`e620d8572a1e62c9ec07df8cbc8f5c432cd84325`, already recorded at
catalogs/us-equities/data-research.json:327. The release README.md:77 gives
the pip route; :103 gives local LMDB, :117/:118 the dataframe shape, and
:126/:127 the write/read calls. The native return at
recapture-v1/arctic-upstream-lmdb-smoke.log:16 shows 100000 rows by 10 columns;
exact dataframe assertions exited 0. Input is explicitly **synthetic**. This
bounded local storage diagnostic does not establish market-data quality,
performance, comparative A6 or production use. README.md:26 requires a paid
production/service license; scope/license disposition remains unresolved.

Capability is distinct from upstream engineering quality, community
consensus, net usage, published evaluations and comparative own runs.
Engineering-quality coverage remains unassessed in this draft; consensus
and net usage are unresolved, published-evaluation coverage is unknown,
and matched A6 comparisons were not run. No scores, weight transfer,
superiority or new default are inferred from successful capability smokes.

## Remaining gaps and review boundary

Live SEC/vendor acquisition, licensed as-known universes, correction clocks,
delistings, ticker reuse and original availability remain unqualified.
Alpaca/calendar invokes do not substitute for fresh full upstream E2E.
Provider comparisons and a matched Arctic workload require separately
specified inputs; production storage rights need a disposition. The 5.62
screen and canonical projection updates remain separate work.

The index is
[receipt.json](../../blueprints/us-equities/final-market-data-reference-20261016/receipt.json);
it is a derived inventory, distinct from the recorder's native command
receipts. The co-op performs private reproduction before publication and
dispatches both family reads after the one PR opens. Nothing here admits
FINAL, places orders, enables a service or self-dispatches a model read.

## Primary sources

- [EdgarTools install route](https://github.com/dgunning/edgartools/blob/7338aa335f6442c52dfa0695422cf1cd27e946e0/README.md#L74),
  [offline command](https://github.com/dgunning/edgartools/blob/7338aa335f6442c52dfa0695422cf1cd27e946e0/pyproject.toml#L253),
  [network guard](https://github.com/dgunning/edgartools/blob/7338aa335f6442c52dfa0695422cf1cd27e946e0/tests/_offline_harness.py#L23).
- [Official Alpaca request interface](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/data/requests.py#L86)
  and [calendar source](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/README.md).
- [ArcticDB release LMDB example](https://github.com/man-group/ArcticDB/blob/e620d8572a1e62c9ec07df8cbc8f5c432cd84325/README.md#L103)
  and [license condition](https://github.com/man-group/ArcticDB/blob/e620d8572a1e62c9ec07df8cbc8f5c432cd84325/README.md#L26).
- [Layer-resolution protocol](2026-10-11-layer-resolution-protocol.md).
