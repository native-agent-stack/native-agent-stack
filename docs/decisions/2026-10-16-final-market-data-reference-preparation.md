# Market data/reference FINAL preparation (2026-10-16)

Status: **PREPARATION / GAP draft; both families folded and full private check passed**. No FINAL
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

The initial capture family has 16 native commands and 32 published derivatives. Each JSON
receipt is labelled `masked_native_capture`; its exact private command,
original stdout/stderr bytes and original recorder metadata remain private
by name only. Public commands use marked placeholders. Both the log and
receipt reproduce through the published
[mask_capture.py](../../blueprints/us-equities/final-market-data-reference-20261016/mask_capture.py).
All unmapped bytes, line endings and trailing whitespace are preserved.
Only published-byte hashes appear publicly. The co-op's initial check confirmed all
32 initial derivatives reproduce from 16 retained captures, all 33 initial
inventory hashes/sizes match, and all 16 initial command/return-code bindings match. It reran the 5 masker
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
The fold now supplies upstream Alpaca/calendar suites; their offline results
do not qualify live service, credentials, broker state or historical data.
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

## Scope-locked review fold

The CC record is cited by name: MICRO-full-7d740ccb.md. The reviewed head
was held fixed until GPT ACK was relayed; both families' findings are
combined in this one correction. This fold still admits no FINAL/default.
Its machine record is
[fold-review-corrections.json](../../blueprints/us-equities/final-market-data-reference-20261016/fold-review-corrections.json).

Every carried survivor now points to its exact reviewed_commit value at
landscape-sweep-20260926/{databento-databento-python,hydrosquall-tiingo-python,
man-group-arcticdb,massive-com-client-python}.json:7. Databento's carried
25eef4ee source pyproject.toml:3 says 0.87.0; data-research.json:65 and
lane-packet.json:42 retain 0.86.0/e675ef30. Massive's carried 481e5c27 differs
from the 2.8.0/3c247d78 identity at data-research.json:112 and packet :14.
The ledger preserves these scopes and makes no version inference at the
Massive carried commit. Arctic A1 at carried 7d30a6ee is source-only; the
6.26.0/e620d857 run is explicitly a separate release capability record.

All three proposed run commits now have native official tag records and
complete native PyPI release records under fold-v1/. Each selected release
wheel SHA256 equals its accepted runtime-lock wheel entry; native uv
`--no-deps --require-hashes` installed those exact wheels in fresh scratch.
Alpaca's pinned pyproject.toml:4 is a dynamic 0.0.0 placeholder, with backend
at :44 and dynamic versioning at :51. Version evidence comes from the
official tag, PyPI wheel record and hash-pinned installation instead.
This is release identity, not a bit-for-bit source rebuild.

The deterministic original/fold/final closure audits retain every installed
package comparison. For example, recapture-v1/install.log:50 reports
numpy 2.5.4 versus accepted uv.lock:1553's 2.5.3; :57 reports pydantic 2.14.1
versus uv.lock:1915's 2.13.5. Other deltas are retained. Package execution
pins agree; these resolved closures are not locked runtime migrations.

The upstream Alpaca suite now reports **320 passed, 19 skipped, 2 warnings**
at fold-v1/alpaca-upstream-tests-fold.log:39. Its :20 through :38 individually
name all 19 upstream live cases and the need for `--run-live` or
`ALPACA_RUN_LIVE=1`; pinned tests/live/conftest.py:100 supports that live
service/credential/broker reason. The mock fixture is tests/conftest.py:21;
the vendor command is Makefile:22 and test dependencies pyproject.toml:30,
:31 and :32. No live flag or real credential was supplied. An initial
collection failure from isolating upstream flat helper imports is retained;
default upstream collection with the installed wheel preloaded succeeded.

The full exchange-calendars CI target at pinned .github/workflows/main.yml:51
reports **10042 passed, 1 xfailed, 2497 warnings**, exit 0, at
fold-v1/calendar-upstream-tests.log:255. Pytest reports 707.37 seconds, inside
the native 15-minute process bound. The whole upstream tests/ target ran
with two local workers and its test dependency group at pyproject.toml:42.
No subset fallback was needed. Warning categories at log :225 and :235
remain disclosed: deprecated class-scoped fixture methods and NumPy generic
timedeltas. This is offline calendar code evidence, not market-data history.

A nonremovable Python audit hook stops before socket/DNS; the negative
control at network-guard-calendar.log:3 and matching recorder exit 86 proves
refusal. Upstream broker/order fixtures remain mocks. The suites cannot
reach a real broker; no account or order state changes.

The fold publishes 35 further command captures and 70 further derivatives.
Together with the initial family, the current publication contains **51
capture pairs / 102 masked derivatives**, plus the packet: 103 inventory
outputs. There are 52 privately retained originals: one earlier help capture
is private-only because it included an unmasked generic home-path example.
Its native replacement uses the declared example-home placeholder; no old
output was reconstructed or silently normalized.
Three command exits 1 retain failing-before regressions or the collection
setup failure; three exits 86 are expected network-refusal controls.
The other 45 commands exited 0. No failed run is relabelled as a pass.

New synthetic regressions first failed for JSON-escaped non-ASCII, quote and
backslash literals, then passed with explicit encoded aliases. The current
masker has 7 cases; custody has 2. All untouched bytes remain exact; no JSON
parsing, reserialization or whitespace normalization is used to mask output.
The original 32 derivatives locally reproduce unchanged, but the changed
masker and all 102 derivatives passed the new private co-op reproduction check.
The historical uncaptured setup exits 128 and 1 are explicitly reported
observations, not independently verifiable native evidence.

Native installed-client help documents uv pip at uv-pip-install-help.log:3,
`--no-deps` at :35 and `--require-hashes` at :38. Pytest's override form is
pytest-override-help-final.log:173; the pinned Edgar environment configuration is
pyproject.toml:415. Thus `-o env=` suppresses the upstream contact assignment.
The co-op relayed GPT ACK and privately reproduced all 102 current derivatives
from 51 public capture pairs, verified all 103 output bindings and private raw
integrity, and reran 7 masker plus 2 custody tests. The separate sequential
actual-wheel-digest check also passed. All three private hashed requirements
match the native PyPI release records captured before the successful
require-hashes installation; uv verified the downloaded wheels against those
published digests. One normal fold commit/push is released.

GPT's two P3s remain explicit follow-ups: support the dotted module runner for
test_mask_capture.py, and record private completion for process-launch OSError
before broader recorder reuse. The verified standalone/discovery import and
current launch-failure behavior remain as checked. A failed launch creates no
successful public receipt. Neither deferred change is presented as implemented
or tested in this fold. The private verdict is cited by name only:
GPT-VERDICT-7d740ccb6.md.
