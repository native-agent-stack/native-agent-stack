# Backtesting engine gap burn-down, 2026-10-10

This cluster starts from native-agent-stack main `0947b01289dcaa9157aa38392a94cf00f592b86d`
and conforms to the shared closeout route at main `8bffa2c41692ef483e91b68e3b15aeb331423d2c`.
Gaps **2 and 6 were already settled on 2026-09-23**. This run re-confirms their
release/comparator evidence on receipt-v2; only **7** has a new proposed closure.
Gaps **0, 4 and 9** remain residual and **1 and 8** retain their actual blockers.
The matrix remains **8 executable-now / 12 open** until same-head GPT and Claude
PASS references supply review credit. This PR grants no new settlement credit.

| Gap | Observed result | Remaining boundary |
| --- | --- | --- |
| 0 | Accepted v2 one_zero comparator PASS; fresh native diagnostic passes 106 execution checks | Frozen fractional slippage and adaptive/margin parity remain blocked |
| 1 | Upstream example/source review and older action-window failure retained | No unchanged equity example or authorized retained Alpaca action-window payload here |
| 2 | Re-confirms September 23 settlement with official release list/tag for latest non-prerelease v1.231.0 | Selected rc5 runtime preserved; no new closure |
| 4 | 12 TestCaseSource cases of the single LEAN method `CanSubmitOrderWhenOutsideRegularTradingHours` pass | Outside-regular-hours submission decisions only; paper adapter initialization and accepted vendor data remain open |
| 6 | Re-confirms September 23 settlement: accepted v2 lean-data PASS; bars/no-attribution refuse their designed checks | No new closure or independent-review tally |
| 7 | Accepted v2 comparison and fresh diagnostic both give end cash 90734.08, matching LEAN; engine-posted dividends 428.64 | New proposed closure; fresh diagnostic does not reset reviewed-first-run acceptance |
| 8 | Prior action-window receipt shows missing split/dividend handling | No authorized retained AAPL quotes/action-window acquisition here |
| 9 | Three native economic cases and a cash refusal backed by two native denial events | Frozen 0.002 slippage/adaptive mappings and calibrated depth remain unqualified |

The other four gaps (3/11 broker login, recovery and continuous paper; 5/10 causal
universe, calibrated data and independent profitability) remain outside this
executable scope. No broker request, credential access, study catalogue rewrite,
STOP-file access or trading-gate promotion occurs in this work.

The isolated official Nautilus rc5 wheel's extension hash matches the accepted
mapping. Five retained LEAN sample files match their frozen hashes. The initial
replay lacked pandas; after installing the vendor-requested pandas 2.3.3, it
processes 725 bars in two fresh engines with equal economic results, no engine
errors, two fills and cash 90734.08. Native replay uses bwrap with no network,
cleared environment, read-only code/runtime/data and one output mount. Bundled
sample bytes establish no original market availability or strategy result.

The fee/margin probe reuses the existing fixture and upstream add_venue/FixedFeeModel:
one target/cash/$1 fee ends at 90732.08; two target/margin ends at 81468.16 without
fees and 81466.16 with two dollars of fees; four target/cash has two native
NOTIONAL_EXCEEDS_FREE_BALANCE OrderDenied events, no fills and cash 100000.00.
The first projection used a wrong summary key. Its observed exit remains 0, but
the corrected receipt rejects its zero-of-four result explicitly. Unexpected
runner/projection errors now propagate to a failed command; only the declared
cash case can count as an expected refusal backed by native events. The economic
and denial events are retained in `raw/native-mechanics-events.json`, projected
from the original primary with its hash; this projection is not a native rerun.

The corrected harness itself was subsequently rerun on 2026-10-11. Its source
hash is 8f9e8db00d8c8575e1d1a1a258144aa14bbf362c90c748de53cfa7b6f5513a6c;
`raw/native-fee-margin-mechanics-corrected-20261011.json` binds that exact source,
the native runner/fixture/mapping inputs, empty-network command and observed
exit 0. Three cases complete and the cash case is `expected_refusal`, with two
native denial events and no fills. Gap 0/9 citations use this rerun; older captures
and projections remain historical evidence. Unmodified primary results and
per-case outputs are retained in the cited packet rather than only by hash.

The earlier fill-validated source-bound native run is
`raw/native-fee-margin-mechanics-fill-validated-20261011.json`, using harness
`e844bde8aee6dd224751c0238dce0b4e07d63f7ff931020ade261b0caebe277a`.
Each completed case has two nonzero round-trip fills, expected configured fees,
reconciled native cash and zero denials/errors; the refusal has zero fills and
two denials. Earlier runs retain their actual source
identity and cannot establish execution of a later harness.

The final-round current-source run is `raw/native-fee-margin-mechanics-final-20261011.json`,
binding harness `7909db7e8611c25ba98fee87000c79aea5c527301c0743c716bc706286b61096`. Gap 0/9 cite this run.
It validates each case's declared target/account, target-sized quantity (304 or 608),
reference entry/exit prices and expected ending cash, independently of the observed
balance. Expected values use the frozen historical plan, the independently accepted
LEAN comparator's expected prices/dividends and the existing fixture's
`target_quantity` function. Both reference JSON inputs are hash-pinned in the harness.
The actual empty-network rerun reproduces three completed cases and the denial-backed
cash refusal, with zero engine errors. No stress/adaptive or strategy acceptance follows.

LEAN source 985ef30ad3ac774218c5ac516b4cb0aa2655730f was exported into an ignored
build directory. Microsoft .NET SDK 10.0.401 was downloaded from official metadata
and SHA-512 checked. The initial upstream test command lacked ICU, then encountered
the default Python library's GIL mismatch. Local libicu78 and explicit Python 3.12
prerequisites allowed 12 cases of the one outside-regular-hours method to pass,
with zero failures/skips. Earlier failed/aborted attempts remain observed failures.
Historical receipts disclose that the recorder omitted the effective environment;
values cannot be reconstructed as observations. A fresh cached upstream test run in
`raw/lean-model-explicit-environment.json`: a cleared, recorded environment,
12/12 passing cases, source/runtime/output hashes and actual exit 0. It supplies
new environment-bound evidence rather than reconstructing historical values.
The failed 4 MB build capture is reduced to a tail, preserving original raw/export hashes and byte lengths in
its receipt, with stderr retained in full.

Public output digests now follow the supported host recorder's published-byte
convention: `scripts/host_receipts.py:1012,1029` at
`8bffa2c41692ef483e91b68e3b15aeb331423d2c`. They hash the final sanitized UTF-8
output or the retained published capture bytes. Unsanitized-output hashes,
unretained stream hashes, derivative original-receipt commitments and embedded
copies of those commitments are removed from publication. Raw originals stay
in private local evidence. Public TRX exports are sanitized and hash-bound;
their counters and actual command exits are unchanged. All 45 machine fields in
the four published TRX copies (`TestRun@name`, `Deployment@runDeploymentRoot` and
every `computerName`, including `RunInfo`) are structurally masked as `[MACHINE]`.
Original command/output locations keep their `~` paths; a separate `published_copy`
binds sanitized repository bytes and their derived digests. Capture deduplication
does not rewrite the original 26 capture paths. The test DLL's original digest stays
only in private local evidence, and its public `private_outputs` entry has no digest.
A masked-home candidate
cannot reproduce the public output digests; the regression checks embedded text,
retained files and every public digest string, including nested historical traces.

The sole current disposition route is
`catalogs/landscape/gap-closeouts/backtesting-engine-2026-10-10.json`, following
main's #982 schema and loader. Gaps 2/6/7 are proposed, 0/4/9 residual, 1/8 blocked;
without review credit all preserve historical counts. The frozen crosswalk stays
unchanged. The bespoke matrix join, wave ledger and record.py/register_changed.py/
summarize.py helpers are removed. Register explicit paths through the existing
scripts.host_receipts.register_file API; never enumerate unrelated untracked files.
Each gap cites evidence for its own scope; deferred gaps do not borrow native
summaries. Existing shared-loader tests cover unknown gaps, altered evidence and
same-head two-family settlement.

Old AttributeError/TypeError red captures remain historical failed attempts and
are not defect-first evidence. `raw/cc-defect-regressions-red.json` records 11
assertion failures and zero errors after the authorized rebase and before fixes.
They reproduce 5/9 versus 8/12, swallowed projection failure, missing/wrong
verdicts and the requested scope corrections. Boundary tests are synthetic;
retained native measurements keep their separate provenance.

Comparator execution requires fresh output, the expected exit and the exact
designed non-PASS check id/field/status set. Missing/invalid output or an unrelated
crash refuses the run. Future command capture uses scripts/host_receipts.py;
execute_comparators.py prints its allowlisted effective environment for capture.
It accepts `--output` naming a new directory outside the checkout; without it,
it creates a fresh temporary directory and prints its path. Existing directories
and checkout paths are refused before any comparator launches. All four retained
verdicts remain unchanged. An actual driver reproduction executes all four modes
into fresh output: accepted lean-data passes, and the other three refuse exactly
their designed checks (`raw/codex-p2-comparators-reproduced.json`).

Execution summaries are recomputed from non-precondition rows with the supported
partition/count rule at `spy-parity/compare.py:1064-1074`, pinned at
`8bffa2c41692ef483e91b68e3b15aeb331423d2c`; copied summaries cannot conceal truncated
rows. `raw/final-round-regressions-red-20261011.json` observes five new tests failing
with 64 assertions and zero errors on unchanged 5a2eb0ee source/evidence. Its exact
test bytes are retained at `raw/sources/final-round-test-source.py`. The same regression
source is used by CI, and structural failures never print an original machine value.

Adjacent checks cover all four modes' output/failure transitions, fresh directory
creation, stale-output refusal, missing/wrong verdicts, native projection errors,
unexpected denials and source-bound gap 0/9 citations. Driver CLI/test call sites
and mechanics main/project_result call sites were verified directly because
graph coverage is absent for these new files.

The cited-source/capture packet is
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/engine-qual.pr979-codex-p2-20261011/`
with `MANIFEST.sha256`: pinned vendor/repository blobs, historical captures,
original full failed build output, actual replay/mechanics primaries, LEAN TRX
and fresh comparator outputs unchanged. Registered repository hashes bind
committed evidence; the attachment manifest authenticates local primaries.
The updated correction packet is
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/engine-qual.pr979-final-corrections-20261011/`,
with its own MANIFEST.sha256 and the immutable prior packet under base/.
Historical recorder bytes are registered at raw/sources/record-6705aa5c.py;
all 28 references bind the Git blob and SHA-256, surviving a squash. Four
unrecoverable-input receipts are explicitly historical drafts. codex-p2-red.json
is re-recorded with retained committed test bytes f88867d4 from 663349f6; the
draft receipt remains in the prior packet. New correction-test bytes are retained
with their own red receipt, and the checkout inverse reproduces actual hash drift.
Native text captures retain byte hashes under the artifact directory's Git
attributes (`-text`, whitespace lint disabled); the bounded build tail is explicitly
marked as a projection, with its original commitment retained.

That earlier commitment is retained privately. The current public review packet
is `~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/engine-qual.privacy-public-20261011/`
with a new MANIFEST.sha256 containing only published/sanitized bytes. Earlier
packets and original commitments are private evidence and are not included under
the new public packet's manifest. Sanitization preserves observations while
removing identifiers and confirmation oracles; it is not a new native run.

The final-round public packet is
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/engine-qual.final-public-20261011/`.
It contains current public artifacts, exact final source/tests, bound source extracts,
native primary results and confirmation captures. Private DLL/original-output
commitments are outside it. Failed pre-registration and pre-citation runs are retained
as failed observations; the final focused/adjacent set passes 367 tests.

Sources:

- CPython v3.12.4 `xml.etree.ElementTree` at
  `8e8a4baf652f6e1cee7acde9d78c4b6154539748`, `Lib/xml/etree/ElementTree.py`:
  the structural CI regression uses the supported `parse` and `iter` APIs and
  attribute dictionaries; no XML parser is reimplemented. The original TRX trees
  were compared with only the three authorized machine fields masked, preserving
  every other XML attribute, counter and text value. This source was fetched from
  the pinned official repository because the local CPython mirror lacks that ref;
  the mirror gap is recorded for the upstream-sync follow-up.
- CPython v3.12.4 at `8e8a4baf652f6e1cee7acde9d78c4b6154539748`:
  <https://github.com/python/cpython/blob/8e8a4baf652f6e1cee7acde9d78c4b6154539748/Lib/tempfile.py>
  (`gettempdir`:313 and `mkdtemp`:360), Lib/pathlib.py:690,1228
  (`is_relative_to` and `resolve`), Doc/library/tempfile.rst and pathlib.rst.
  These pinned sources are retained unchanged in the current packet. Both default
  and explicit output parents are resolved and checked before creation; caller-relative
  input paths are resolved before the child's cwd changes. Every refusal mode also
  requires its retained execution counts. Completed native cases require two
  nonzero round-trip fills, the configured commission per fill and a reconciled
  economic cash transition; empty/flat cases refuse. Cross-checkout regression
  uses Git's native autocrlf checkout and an absent-attribute control showing drift.

- nautechsystems/nautilus_trader@`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`:
  `crates/backtest/src/exchange.rs:686,1639`,
  `crates/execution/src/matching_engine/mod.rs:1883`,
  `python/nautilus_trader/backtest/__init__.pyi:455`,
  `python/nautilus_trader/execution/__init__.pyi:166`, and
  `crates/risk/tests/risk_engine.rs:4972,5043` (native free-balance denial).
- QuantConnect/Lean@`985ef30ad3ac774218c5ac516b4cb0aa2655730f`:
  `Tests/Common/Brokerages/AlpacaBrokerageModelTests.cs:31-56`,
  `Tests/AssemblyInitialize.cs:65`, `Common/Python/PythonInitializer.cs:189`.
- native-agent-stack@`0947b01289dcaa9157aa38392a94cf00f592b86d`:
  existing `spy-parity/run.py:544,630-698`, fixture_strategy.py:245,
  accepted receipt-v2.json/verdict-v2.json and gap-wave receipt vocabulary.
- native-agent-stack@`8bffa2c41692ef483e91b68e3b15aeb331423d2c`:
  `catalogs/landscape/gap-closeouts/README.md`, schema.json and
  scripts/component_matrix.py (supported closeout/review route);
  `blueprints/us-equities/engine-nautilus/spy-parity/compare.py:564,735,817,1037`
  (designed refusal checks).
- Prior settlement: `catalogs/landscape/gap-wave2-20260923--agent-lab-17.json`
  and `docs/gap-wave2-20260923--agent-lab-17.md`; retained receipts
  `evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/2-nautilus-latest-stable-release.json`
  and `6-comparator-modes-and-review-count.json`.
- Microsoft SDK metadata:
  <https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json>;
  source/runtime commitments retained in raw/source-pins.json.
- Git@`v2.53.0`: Documentation/gitattributes.adoc (native capture byte preservation).

Reproduce through the supported generators and focused checks:

```sh
python3 scripts/component_matrix.py --check
python3 scripts/new_host_grand_list.py --check
python3 -m unittest tests.test_backtesting_gap_burndown tests.test_gap_closeouts tests.test_component_matrix tests.test_new_host_grand_list
python3 scripts/validate.py
```

Full native commands and actual exits are retained in per-attempt JSON receipts.
Local ignored runtime directories are optional for published-file validation.
