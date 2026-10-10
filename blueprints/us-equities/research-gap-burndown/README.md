# Research-factor executable checks, 2026-10-10

The retained runs execute the public research candidates, reproduce causal fold
controls, compare five native forecast arms on identical inputs, and replay the
purged selections through LEAN's native fills, distributions and cash book.
They do not establish alpha, a point-in-time equity universe or broker/account
acceptance. The [closeout record](../../../catalogs/landscape/gap-closeouts/research-factors-ml-2026-10-10.json)
keeps proposals separate from residuals and the approved execution boundary.
Settlement requires the actual two-family PR reads and the shared closeout
loader; the frozen September crosswalk is preserved as history.

The original study already specified a six-session purge. Its raw-price labels,
selected SPY/QQQ/IWM sample and inspected 2021Q1 segment remain historical facts.
This run uses only development sessions through 2020; it cannot restore that
inspected segment as an untouched holdout. Each of the nine original daily,
map and factor inputs matches the original [plan](../research-evaluation/plan.json).

## Chronology and negative controls

Both native skfolio **1.2.9** and **1.8.1** arms produce 20 WalkForward folds.
Zero purge has **24** crossing training-label intervals; all 20 zero-purge
selections are refused by the original selector. Purge six has **zero**
crossings and identical selections across the two versions. Actual bounded
evaluation censors **25 episode decisions** at their own fold boundary; each
candidate's censored label stays without an outcome instead of borrowing a
later fold's prices.

Native CPCV supplies the separate future-side embargo sensitivity: 45 splits,
792 crossing intervals with purge/embargo zero, zero with purge six, and zero
with purge six/embargo six. Excluded indices across splits increase from 864
to 1296 when embargo is added. WalkForward has no embargo parameter; CPCV is
not substituted for the chronological selection experiment. None of these
finite checks proves statistical independence.

The collected [tests](../../../tests/test_research_gap_burndown.py) refuse an
entire missing forecast arm, differing dates, differing training scales,
corrupted exported losses, duplicate/missing cases and altered targets.
Four separate controls fail against the retained pre-fix comparison wrapper.
The pandas3 control reproduces the refused integer-to-float assignment;
explicit native `DataFrame.astype(float)` preserves the source's 1/10000 USD
conversion. [Regression results](regressions.json) retain those failures.

## Same-input forecasts

The [prespecified plan](plan.json) fixes 252 training sessions, purge six,
63-session test folds and a five-close scoring horizon. Every native model
forecasts the six gap sessions plus five target sessions; only those same five
test closes are scored. All five arms have **60 cases** (20 folds × 3 assets)
and identical target dates, origins, observations and training-only MASE scales.
Kronos uses public calendar features and prior OHLCV; the other arms use prior
closes. This is a comparison of supported input interfaces, not an equal-feature
benchmark. The frozen naive control repeats the last available training close.

| Native arm | Mean MAE, USD | Mean MASE | Forecast-call time, seconds |
| --- | ---: | ---: | ---: |
| Chronos-Bolt-small | 5.8051 | 4.3056 | 4.17 |
| Kronos-small | 11.2925 | 8.8684 | 121.93 |
| Last-close naive | 6.5519 | 4.7116 | 0.00 recorded |
| StatsForecast AutoARIMA | 6.3321 | 4.5721 | 15.39 |
| statsmodels ARIMA(1,1,0) | 6.5260 | 4.7084 | 1.05 |

These call times exclude model loading, package installation and downloads;
the naive arm's zero is a recorded convention, not a timing measurement.
Raw-dollar MAE weights higher-price assets more heavily; MASE is also retained.
The 10 paired contrasts use arch's native StationaryBootstrap, block three,
999 replicates and seed 260410. They are descriptive, unadjusted intervals,
not significance tests or a winner-flip rule. Chronos-minus-AutoARIMA mean MAE
is -0.5270 USD, interval [-1.0161, -0.0923]; Kronos-minus-naive is +4.7406 USD,
interval [1.8249, 8.4462]. Checkpoint pretraining contamination is unknown,
and these historical data predate the model releases. No forecast score is
converted into a tradable signal or predictive superiority claim.

## Native selected-target portfolio replay

The [separate frozen engine plan](engine-plan.json) fixes the two illustrative
cost cases before launch. The original purged fold selections create 246
completed-close exposure targets. LEAN rebalances net positions when consecutive
episode targets coincide; this is a portfolio integration, not the independent
reset-to-cash raw-price episode arithmetic. Sizing is frozen at each decision,
with a 2% buffer and at most 1x requested gross. Native MarketOnOpenOrder uses
a later bundled daily bar's open-price proxy. Full-quantity fills and daily
data do not qualify an exact opening-auction fill or realistic market impact.

| Case | Native flat cash, USD | Fills | Native distributions, USD | Fees, USD | Cash residual |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero cost | 105327.36 | 116 | 2798.20 | 0 | 0.00 |
| $1/order, 20bp illustrative slippage | 91011.14052 | 112 | 2619.40 | 112 | 0.00000 |

The stressed portfolio loses value. Cost-dependent sizing changes the fill
count and distributions, so these are not identical-quantity ledgers.
Raw normalization credits native factor-file distributions separately, avoiding
double-counting adjusted prices. LEAN credits those distributions at its modeled
event time; this does not accept real dividend payable-date cash availability.
The analyzer checks `initial - signed fill notional - fees + distributions =
flat cash`, binds callbacks to the engine's exported MOO type, creation time,
tag, symbol and quantity, and rejects fills at or before their decisions.
Each case completes with 4 successful native data requests and zero failed
requests. All **1456** mounted engine/data inputs remain unchanged.

The engine is unmodified QuantConnect/Lean at `80e7843f…`, built with the official
hash-verified .NET **10.0.401** archive. ICU78 was extracted from the native distro
package into the private SDK prefix; no host package was installed. Restore and
build retain upstream package/compiler warnings. The engine sandbox reuses the
existing [native isolation](../execution-realism/run.py): read-only data/binaries,
no network, and no account store. First-attempt SDK, decimal-parse, zero-fee
currency and changed data-monitor-default failures remain in the bundle.
Financing, depth/participation/capacity, PIT-universe and selected Nautilus/broker
acceptance remain open. This comparison does not change the runtime destination.

## Candidate scope and retained artifacts

The 15 candidates named by historical gap 5 now have fresh executions through
their own interfaces: ArcticDB LMDB; sktime fit/predict; Alphalens cleaning/IC;
Chronos; tsfresh extraction; Haystack BM25; river predict-then-learn; StatsForecast;
Docling HTML conversion; arch GARCH/bootstrap; Ray Serve deployment/handle;
TimesFM3 CPU; statsmodels; sentence-transformers CPU embeddings; Qlib CSRankNorm.
Imports alone receive no credit. Qlib's processor is not its full model/data
pipeline, and the three-document/HTML fixtures do not accept a filing corpus,
financial-NLP quality or production serving. The smaller Haystack/Qlib checks
do not erase the failed acceptance criteria in the older gap-wave2 receipts.

The c13 vendor backtest-expert CLI distinguishes four seeded summary defects
from a clean control (scores 27 versus 91) and refuses invalid metrics; its own
49 tests pass. Its aggregate-input interface cannot detect a latent timestamp
look-ahead defect. Its emitted `Deploy` text is a vendor fixture score and has
no promotion authority. This is no generative Claude skill review. The actual
c16 Kronos/naive result is retained even though Kronos is worse on this fixture.

The [run bundle](runs.json) is a sanitized projection of 34 named attempts,
including eight failures and one incomplete Ray attempt. Original per-file
hashes, freezes, outputs, warnings, native engine exports and callbacks remain
distinct from projection hashes. A bounded attempt without a receipt stays
`incomplete`. [Source history](source-history.json) retains two exact wrapper
snapshots; some other failed variants have source hashes and receipts but no
archived full wrapper bytes. [Sources](sources.json) records repository/file
pins, model revisions and the bootstrap paper. [Supporting checks](supporting-checks.json)
and [environment versions](environment-versions.json) distinguish hash-locked
packages from installed-version records. `publish.py` only projects named
native run artifacts; gap judgments belong to the shared closeout loader.

## Reproduction

Choose fresh external directories as `RESEARCH_STATE`, `LEAN_SOURCE`,
`MODEL_CACHE`, `KRONOS_SOURCE` and `SKILL_SOURCE`; never point them at a peer's
run or account store. Preserve failures and use a new output name for each run.
The numerical environment uses the hash lock; the original splitter arm uses
the existing research-evaluation lock. Model/candidate installed versions are
recorded separately; install PyTorch CPU wheels through the official
`https://download.pytorch.org/whl/cpu` index. The full Docling extra resolved GPU
runtime dependencies in candidate-utils; no GPU was used by its HTML probe.

```sh
uv venv --python 3.12 "$RESEARCH_STATE/numerical"
uv pip sync --python "$RESEARCH_STATE/numerical/bin/python" --require-hashes \
  blueprints/us-equities/research-gap-burndown/requirements.lock
"$RESEARCH_STATE/numerical/bin/python" blueprints/us-equities/research-gap-burndown/run.py chronology \
  --lean-source "$LEAN_SOURCE" --out "$RESEARCH_STATE/chronology-new"
"$RESEARCH_STATE/numerical/bin/python" blueprints/us-equities/research-gap-burndown/run.py classical \
  --lean-source "$LEAN_SOURCE" --out "$RESEARCH_STATE/classical-new"
"$MODEL_PYTHON" blueprints/us-equities/research-gap-burndown/run.py models \
  --lean-source "$LEAN_SOURCE" --model-cache "$MODEL_CACHE" \
  --kronos-source "$KRONOS_SOURCE" --out "$RESEARCH_STATE/models-new"
"$RESEARCH_STATE/numerical/bin/python" blueprints/us-equities/research-gap-burndown/run.py compare \
  --classical-result "$RESEARCH_STATE/classical-new/receipt.json" \
  --model-result "$RESEARCH_STATE/models-new/receipt.json" --out "$RESEARCH_STATE/matched-new"
"$RESEARCH_STATE/numerical/bin/python" blueprints/us-equities/research-gap-burndown/engine_run.py \
  --lean-source "$LEAN_SOURCE" --dotnet "$DOTNET_PREFIX/dotnet" \
  --chronology "$RESEARCH_STATE/chronology-new/receipt.json" --out "$RESEARCH_STATE/engine-new"
"$RESEARCH_STATE/numerical/bin/python" -m unittest \
  tests.test_research_gap_burndown tests.test_research_evaluation -q
python3 scripts/component_matrix.py --write
python3 scripts/component_matrix.py --check
python3 scripts/validate.py
```

Public model files use native `hf download <model> <explicit files> --revision
<immutable revision>` in a fresh `HF_HOME`, with implicit token disabled, followed
by `hf cache verify`. Verification covered the 2 required files of each forecast
checkpoint and 10 embedding-model files, not full repository snapshots.
Inference sets `HF_HUB_OFFLINE=1` and reads those local CPU artifacts.
The [native source-build recipe](../engine/README.md) applies with the new LEAN
pin and the private ICU selection recorded above. Run the native restore with
an explicit public-only NuGet.Config, then the launcher project build with
`--no-restore --disable-build-servers -m:2`; preserve its warnings. Hosted CI
owns full discovery; locally run the touched modules and FULL validator.
