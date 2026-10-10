# Backtesting engine gap burn-down, 2026-10-10

This cluster starts from native-agent-stack main `0947b01289dcaa9157aa38392a94cf00f592b86d`.
The historical crosswalk labels eight backtesting-engine gaps executable now out
of twelve open. This run settles **2, 6 and 7**, advances **0, 4 and 9**, and
retains the actual input/authority blockers for **1 and 8**. The regenerated
matrix therefore reports **5 executable-now / 9 open**. Remaining work is not
relabelled as accepted because a simulator ran.

| Gap | Observed result | Remaining boundary |
| --- | --- | --- |
| 0 | Accepted v2 one_zero comparator PASS; fresh native diagnostic passes 106 execution checks | Frozen fractional slippage and adaptive/margin parity cases remain blocked |
| 1 | Upstream example/source review and the older retained action-window failure remain available | No unchanged equity example in the pinned example set; no authorized retained Alpaca action-window payload here |
| 2 | Official release list and tag response establish latest non-prerelease v1.231.0 | Selected rc5 runtime is preserved |
| 4 | All 12 unchanged upstream LEAN AlpacaBrokerageModelTests pass | Paper adapter initialization and an accepted vendor dataset remain separate gates |
| 6 | All comparator modes executed; accepted v2 `--lean-data` PASS, `--bars` and no-attribution modes refuse incomplete evidence; historical review excerpt hash checked | No fresh independent-review tally is claimed |
| 7 | Accepted v2 oracle comparison and fresh native execution both give end cash 90734.08, matching LEAN; dividends 428.64 are engine-posted | Fresh replay is diagnostic and cannot reset the reviewed-first-run acceptance |
| 8 | Prior native action-window receipt shows missing split/dividend handling | No authorized retained AAPL quote payload/action-window acquisition on this host |
| 9 | Native fixed fees, margin and cash-refusal diagnostics execute | Frozen 0.002 slippage/adaptive mappings and calibrated depth remain unqualified |

The four other gaps (3/11 broker-login/native recovery/continuous paper and 5/10
causal universe/calibrated data/independent profitability) remain outside this
executable scope. This lane makes no broker request, reads no credentials and
touches no study evidence root, catalogue, STOP file or other lane's bundle.

The official Nautilus rc5 wheel was installed with `uv pip install
nautilus_trader==2.0.0rc5` into the isolated ignored environment. Its extension
hash matches the accepted mapping. The retained five LEAN sample files match
their frozen hashes. The initial replay failed because pandas was missing;
the vendor reporter explicitly requests pandas, and the retained rerun succeeds
after installing pandas 2.3.3. The replay runs inside bwrap with no network,
cleared environment, read-only code/runtime/data and one output mount. It processes
725 bars in two fresh engines, equal economic results, no engine errors, two
fills and native cash 90734.08. No original market availability or strategy result
is established by bundled sample bytes.

The native fee/margin probe reuses the existing fixture and upstream
`BacktestEngine.add_venue`/`FixedFeeModel`. It completes four native cases:
one target/cash/$1 fee per filled order ends at 90732.08; two target/margin ends
at 81468.16 without fees and 81466.16 with two dollars of fees; four target/cash
is refused and ends at 100000.00. These are configured mechanics, not the frozen
stress/adaptive acceptance. A first projection used the wrong public summary key;
that attempt is retained, the projection regression fails first, and the corrected
run consumes the original runner's actual fields without patching economic values.

LEAN source `985ef30ad3ac774218c5ac516b4cb0aa2655730f` is exported from the local
upstream Git mirror into an ignored build directory. Microsoft .NET SDK 10.0.401
is downloaded from its official release metadata and SHA-512 checked. The
unchanged upstream test command initially lacked ICU, then encountered the default
Python library's GIL mismatch. The supported host prerequisites are supplied locally:
Ubuntu libicu78 78.2-2ubuntu1 is extracted without changing the system, and
`PYTHONNET_PYDLL`/`PYTHONHOME` point to the isolated Python 3.12 base. The third
test run executes all 12 tests, zero failures/skips; the earlier prerequisite
failures and zero-test aborted run remain observed failures.

The old gap crosswalk is an immutable reviewed snapshot of source revision
92bb279. It is not rewritten to fabricate a new review. The existing gap-wave
ledger generator now supports a layer filter and honestly carries pending PR
review, instead of claiming an Opus review that never ran. The matrix joins this
single-layer ledger's single-gap settlements only after checking crosswalk
identity and every retained output hash. Multi-gap settlement, unknown gap and
altered output are refused. The count/join regression fails before the join and
passes afterward. No winner, platform, review or trading gate status changes.

Native receipt commands, actual exits, input hashes and raw/exported output hashes
are retained under
`evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/`.
Generated economic summaries exclude native generated identifiers while retaining
the unchanged primary-record hashes. Hash registrations use the existing
`scripts.host_receipts.register_file` path. Scoped receipts await independent PR
review; measurements and remaining gates are separate.
Native text captures retain their original whitespace and newline bytes; the
artifact directory's Git attributes disable text conversion and whitespace
linting for those hash-bound outputs, following Git 2.53.0's gitattributes API.

Sources:

- nautechsystems/nautilus_trader@`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`:
  `crates/backtest/src/exchange.rs:686` and `:1639` (native module/account posting),
  `crates/execution/src/matching_engine/mod.rs:1883` (gap-open ticks),
  `python/nautilus_trader/backtest/__init__.pyi:455` (venue models), and
  `python/nautilus_trader/execution/__init__.pyi:166` (FixedFeeModel).
- QuantConnect/Lean@`985ef30ad3ac774218c5ac516b4cb0aa2655730f`:
  `Tests/Common/Brokerages/AlpacaBrokerageModelTests.cs`,
  `Tests/AssemblyInitialize.cs:65`, `Common/Python/PythonInitializer.cs:189`.
- native-agent-stack@`0947b01289dcaa9157aa38392a94cf00f592b86d`:
  existing `spy-parity/run.py:544`, `fixture_strategy.py:245`, comparator and
  accepted `receipt-v2.json`/`verdict-v2.json`; existing gap-wave receipt vocabulary
  in `tools/sota-convergence/gap_wave_ledger.py:1`.
- Microsoft official SDK metadata:
  <https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json>;
  source/runtime byte commitments are in `raw/source-pins.json`.
- Git@`v2.53.0`: `Documentation/gitattributes.adoc` (`-text` byte preservation
  and the whitespace attribute for native capture files).

Reproduce the matrix and ledger:

```sh
python3 tools/sota-convergence/gap_wave_ledger.py --wave backtesting-gap-burndown-20261010 --owner agent-lab-17 --dir-style catalog__layer --layer backtesting-engine --check
python3 scripts/component_matrix.py --check
python3 scripts/validate.py
```

The full native execution commands are in the per-attempt JSON receipts. Raw
runtime directories are local and optional for published-file validation.
