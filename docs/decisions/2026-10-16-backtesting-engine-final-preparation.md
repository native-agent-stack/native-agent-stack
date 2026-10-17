# Backtesting-engine FINAL preparation

Status: **DRAFT / GAP disposition proposed**, not FINAL admission or a new
engine selection. Scope: `us-equities/backtesting-engine` only. Base:
`caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`. No runtime, gate, catalog status or
run pin is changed. The co-op owns the independent two-family adjudication.

The [resolution protocol](2026-10-11-layer-resolution-protocol.md) requires a
run pin, vendor install/tests, invoke evidence and a resolved survivor set.
Admission remains closed under the recorded gate chain. This record prepares
evidence and named gaps for that chain; it admits nothing.

## F1: run-pin reconciliation

All repository locators below refer to the base above. The plan's row is
`docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:151`; its pending
comparison is at:574. It names the engines and reopened state but supplies no
numeric replacement run pin. A plan label does not resolve a pin or qualify an
adapter. The proposed run identities retain the supported source/artifact
mapping already committed, pending the comparison and source-qualified upgrade.

| Pin source | NautilusTrader destination | LEAN retained comparator |
| --- | --- | --- |
| `catalogs/landscape/final-stack.json:8916` / `:8938` winner pins | 2.0.0rc5, source1b0a49d2; free-text winner pin remains unparsed | source985ef30a |
| `final-stack.json:10907` / `:10802` run pins | 2.0.0rc5, parsed version at:10910 and source at:10909 | 985ef30a with documented dependency remediation |
| `catalogs/landscape/lockfile-source-identities.json:8` / `:17` | rc5 version and1b0a49d2 source binding | no LEAN binding in this one-entry document |
| `blueprints/us-equities/runtime-2604/trading-2604-runtime/pyproject.toml:14` | exact `nautilus-trader==2.0.0rc5` | no LEAN package in this Python environment's declared dependencies |
| `manifests/stack.json:1973` / `:1390` | rc5 version; source at:1989 | comparator version/remediation; source at:1393 |
| `catalogs/us-equities/runtime-target.json:32` / `:35` | rc5 requested version and source pin | historical comparison role remains separate |
| `docs/decisions/2026-10-13-engine-currency.md:39` / `:54` | selected rc5 source; rc6 source-watch lead, not adopted | this currency observation is not a comparator adoption |
| `evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/raw/source-pins.json:3` / `:7` | retained rc5 source key | retained985ef30a source key; historical tests are not substituted for a fresh run |
| Native fresh install captures | `native/nautilus-wheel-install.capture:19` reports2.0.0rc5; command at:1 and native rc0 at:32 | `native/dotnet-invariant-version.capture:2` reports SDK10.0.401, not a LEAN engine version |

**Proposed single run pin per winner:**

- NautilusTrader **2.0.0rc5**, tag `v2.0.0rc5`, source
  `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`. Official tag peeling reproduces
  the committed mapping (native/nautilus-tag.capture); installed distribution version and isolated wheel
  agree. Retain until a screened upgrade passes its required replay/recovery
  contract. The [currency record](2026-10-13-engine-currency.md) distinguishes
  rc6 from the later IB transport port; a newer source is not an adopted run.
- LEAN **985ef30ad3ac774218c5ac516b4cb0aa2655730f**, as the historical
  comparator. Keep its historical dependency-remediation identity distinct
  from this clean-source attempt. This preparation does not silently rebase
  the oracle to the co-op comparison's newer source or container image.

Drift and unresolved identity dimensions: the winner text is unparsed at
`catalogs/landscape/final-stack.json:8912`, not parsed into
the final report's pin comparison; run identity is correctly parsed through
the lockfile binding. The bounded lookup in `native/adoption-entry-lookup.capture`
has no matches in either named adoption platform pin file (native rc1); this
is absence, not a measured platform mismatch. rc6/newer LEAN and
the official IB adapter/native port comparison are pending qualification inputs.
The old manifest's dependency-remediation phrase is not an independently
reproduced current build. No report generator or parser is changed to hide it.

## F2 and E2E: measured native scope

Evidence is under
`evidence/artifacts/final-wave-backtesting-engine-20261016/`. The execution
JSON is a source/capture index. Native recorder captures supply the commands,
exits and observations; masking-tool metadata binds the published derivatives.
Command paths use marked placeholders; no raw local path or fingerprint of
unpublished bytes is published.

Nautilus uses its documented release-wheel installation, followed by upstream
tests from the source at the selected commit. Fresh native recorder captures
cover the tag, archive download/extraction and byte comparison of the three
selected test files with the earlier source copies. Three bounded modules pass
**47 tests, zero skips** in a network-unshared sandbox. This is a **BOUNDED SMOKE**,
with simulated/empty-engine inputs. Full at-pin E2E remains a named **GAP**. This is upstream
engineering smoke, not the full vendor suite, a historical-data E2E backtest,
broker acceptance or strategy qualification. Failed setup attempts are retained:
an absent interpreter path, then disabling pytest's cache provider while leaving
its cache-related default options enabled. The corrected test invocation
overrides those options without editing upstream files.

An explicit second command invokes both unchanged upstream statistics-test
functions, which call `BacktestEngine.run`. The fresh native recorder captures
actual engine logs and command exit0 without a driver-generated status object.
That establishes a native **empty-engine simulation invoke** in the preparation
window, with zero market data/orders; it does not establish historical E2E. It does not
establish production wiring, routine usage or invocation of a broker adapter.

LEAN source download/extraction and selected test/project/initializer byte
comparisons now have native captures. The existing isolated SDK reports10.0.401;
its original archive-install provenance remains a named gap, not a fresh
installation receipt or an independently reproduced binary. The native normal
SDK invocation fails134 for missing ICU. The co-op requested a
process-scoped retry using Microsoft's documented
`DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`. That mode makes SDK invocation and
restore pass (`native/lean-invariant-restore.capture`), and the bounded model-test
attempt is recorded with its actual outcome: the test host aborts in
`Python.Runtime.Py.GILState.Finalize`; exit1, TRX total/executed/passed all0.
This fresh LEAN E2E and native engine invoke remain **GAP**, not a pass. SDK,
restore and build completion do not establish an engine invocation.
Invariant-mode results cannot qualify culture-sensitive ICU
behavior. The restore also reports dependency advisory warnings; no dependency
rewrite, vulnerability clearance or historical-remediation reproduction is
claimed. No brokerage connection or credential is used.

## Carried survivors and the six-angle draft

The current verdict is the frozen20260922 pairing; the layer is reopened and
its reported12gaps are not silently closed. The latest ledger row is Oct9 Pine.
Newer completed Oct13 backtesting sweep sources are available at public commit
`a049170124469c7cdbdff532135ea1fe46401b81`, although their ledger append remains
pending at this base. Both the manifest and retained returns were read.

`tools/sota-convergence/lane_packets.py` is executed through its existing CLI.
The retained [layer packet](../../evidence/artifacts/final-wave-backtesting-engine-20261016/layer-packet.json)
is the exact file emitted by the supported CLI using the Oct13 manifest at
`a049170124469c7cdbdff532135ea1fe46401b81`, through `--root` on that frozen input
tree. Its native command/rc is in `native/lane-packets-oct13.capture`.
`latest-sweep-candidates.json` separately preserves the first four recorded
candidate gap/comparison/disposition fields verbatim with their source pointers.
These are inherited source claims, not fresh measurements. The seven earlier
unresolved survivors remain separately carried in the angle draft. No new survey
or model call occurs; authored paraphrases do not stand in for recorded fields.

The [multi-angle draft](../../evidence/artifacts/final-wave-backtesting-engine-20261016/multi-angle-draft.json)
keeps capability at pin, upstream engineering quality, community consensus,
net usage, published evaluations and our measured runs separate. Internal
two-family agreement is not public community consensus; installations are not
net usage; local engineering diagnostics are not independent strategy evidence.
Survivor reviewed commits and source-review claims cite the retained per-candidate
file at:7/:13. Unsupported angle cells are explicitly named missing captures,
not generic findings or measured evidence. Disputed and absent dimensions remain explicit for co-op adjudication. No one
angle, source watch, smoke count or winner label decides the layer.

The co-op comparison is cited **by name only**:
`engine-compare-20261015/PHASE1.md` and `RESUME.md`. Phase1 records pins/costs.
The co-op confirms **phase2 NOT RUN**, pending owner credential prerequisites;
the sealed scorer's checks do not constitute executed engine comparison.
Timing/fill parity is one pending capability/measured-run input, not the whole
engine decision. This lane does not run phase2, purchase anything or access
credentials. The draft proposes a named GAP rather than fabricating FINAL.

## Sources and evidence boundary

Native receipts are the util-linux `script` captures under `native/`, including
their own exact command and `COMMAND_EXIT_CODE` footer. Public copies are labelled
deterministically masked derivatives; `mask_capture.py` and its unit tests publish
the rule. Hostname, home and user context are explicit private inputs; publication CLI
requires helper/direct-import bytes matching caa22414; ordinary mask_bytes calls
are not hash-gated against later unrelated main edits. CPU/OS/RAM/
swap fields use marked substitutions without removing lines. Raw captures
remain private and are named only. `execution-receipt.json`
is a source/capture INDEX, not itself a native run receipt. Generated diagnostics
and the six-angle draft are not substitutes for native captures.

- `nautechsystems/nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e`:
  `docs/getting_started/installation.md:58` (vendor release-wheel install),
  `CONTRIBUTING.md:94` and `Makefile:1370` (upstream pytest path),
  `python/pyproject.toml:152` (test runner requirement),
`python/tests/unit/backtest/test_backtest_engine_statistics.py:69` and:82
  (the native invokes; `engine.run` at:74/:87). Exact test preimages are retained
  only in private horizon vendor custody, with upstream copyright notices and
  original licenses. Public `source-pins.json` retains URLs, pins and source
  hashes; the historical LEAN binding remains at the older source-pins.json:7.
  The landing branch is rebuilt as one fixed-tree commit on main. Removed
  third-party copies remain reachable from the PR timeline; GitHub caches and
  local backup refs may retain them. No global erasure is claimed.
- `QuantConnect/Lean@985ef30ad3ac774218c5ac516b4cb0aa2655730f`:
  `readme.md:160` (Linux source build), `Tests/QuantConnect.Tests.csproj:7`
  (net10.0), `Tests/Common/Brokerages/AlpacaBrokerageModelTests.cs:31`
  (bounded offline model test; no adapter initialization claim).
- Microsoft's [globalization runtime configuration](https://learn.microsoft.com/en-us/dotnet/core/runtime-config/globalization#invariant-mode),
  **Invariant mode**, fetched2026-10-16; retained served-page excerpt names the
  process variable and its loss of culture-specific data. This is a dated
  official documentation observation, not a fabricated source commit.
- Existing comparison/currency/parity receipts retain their own dates and
  evidence classes. No historical receipt, gate, lockfile or runtime is edited.

No market-data acquisition, broker order/account call, service enable, model route/default,
FINAL admission or strategy numeric claim is part of this preparation. A future
FINAL decision must resolve the named comparison/survivor and evidence gaps,
then pass the admission chain and independent two-family reads.
