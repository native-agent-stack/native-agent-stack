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
Native text captures retain byte hashes under the artifact directory's Git
attributes (`-text`, whitespace lint disabled); the bounded build tail is explicitly
marked as a projection, with its original commitment retained.

Sources:

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
