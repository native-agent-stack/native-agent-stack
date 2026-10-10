# Market-data executable gap closeouts, October 10

The [gap plan](../../../catalogs/landscape/gap-crosswalk-92bb279.json) assigns
eight open executable-now entries to this layer: 1, 4, 5, 7, 8, 12, 17 and 18.
The September wave already retained bounded evidence for all eight. This wave
verifies those published hashes, completes the missing comparator/catalog
integrations and records fresh supported-client checks. It preserves the frozen
crosswalk and every historical failure.

The [source review](../../../catalogs/us-equities/market-data-reference-gap-review-20261010.json)
records current alternative dispositions and the currency/rights boundaries.
The [later-evidence declaration](../../../catalogs/landscape/gap-closeouts/market-data-reference-20261010.json)
names separate, hash-bound receipts per gap. `scripts/component_matrix.py`
joins these records: **only a settled gap leaves the open count**. Partial work
keeps its residual open and visible in the matrix. A gap receipt does not change
the provider winner, independent review, host qualification or strategy gates.

| Index | Change and evidence | Remaining boundary |
| --- | --- | --- |
| 1 / 12 | Pin the missing/empty currency rejection and record Alpaca's optional, ambiguous currency contract. | Cash units remain unresolved; USD is not inferred from a listing or numeric agreement. |
| 4 | Fresh isolated Alpaca 0.44.0 install, real SDK/Requests tests, source fingerprints and the retry-removal negative control. | A later SDK release must earn its own compatibility check. |
| 5 | Promote the existing measured provider-neutral comparator through [compare_providers.py](../authenticated-data/compare_providers.py), with fresh multi-symbol/date-range/precision tests. | Original private September inputs are unavailable here; the retained native-data run is a dated observation. Paid-provider superiority is unmeasured. |
| 7 | Retain official public storage/redistribution clauses and their prior capture integrity. | Actual account agreements and LEAN vendor-data rights need the owner/account lane. |
| 8 | Repeat Feast 0.66.0's native local file-store PIT fixture and make one bounded, credential-free GDELT news attempt. | The fixture is synthetic; macro vintages, a real stream and a server store are unqualified. A refused/empty news attempt never qualifies the news surface. |
| 17 | Index the pinned SEC-API Python hosted-client alternative. | Its free trial does not establish coverage, rights or a matched acquisition comparison. |
| 18 | Index the current quantlab disposition using its actual current README and complete license/tree observation. | No code adoption or native qualification; a software license is absent. |

Use isolated prefixes and the vendor-supported installs:

```sh
uv venv --python 3.13 "$MARKET_SDK_PREFIX"
uv pip install --python "$MARKET_SDK_PREFIX/bin/python" \
  alpaca-py==0.44.0 duckdb==1.5.5 gdeltdoc==1.12.0
uv venv --python 3.12 "$MARKET_FEAST_PREFIX"
uv pip install --python "$MARKET_FEAST_PREFIX/bin/python" \
  feast==0.66.0 pandas==2.3.3 pyarrow==25.0.1
python3 blueprints/us-equities/market-data-reference/run.py \
  --sdk-python "$MARKET_SDK_PREFIX/bin/python" \
  --feast-python "$MARKET_FEAST_PREFIX/bin/python"
```

The [published run receipt](../../../evidence/artifacts/market-data-reference-20261010/published/run.json)
records actual command exits, elapsed times, complete published output hashes,
input hashes and resolved dependency versions. Host paths in logs are replaced
with `~`; those hashes bind the published bytes. A news failure is retained
separately from the required SDK/fixture checks. No credential is read, printed
or copied. No authenticated request, order or paid data call belongs to this run.

Earlier attempts are retained. The old shell mutation helper first
failed to import the temporary test package; the first explicit-package probe
then exposed a missing copy of `scripts/path_safety.py`. Those setup errors
are **not mutation kills**. The corrected probe includes that current source
dependency and requires the retry assertion, one failure and zero setup errors.
The public news attempt returned `RateLimitError`; its refusal remains evidence,
and the accepted SDK/Feast run does not repeat that provider call. The runner
hashes its input generation before execution and checks it again at completion.
The source-binding command reads the exact catalogued commit from
`~/code/upstream/alpacahq/alpaca-py` and compares both installed REST/model files
byte for byte. It records the version, hashes and actual CashDividend fields;
no missing local tag ref is treated as a verified tag binding.
The probe's temporary test module follows the supported
[CPython 3.13 unittest discovery/import contract](https://docs.python.org/3.13/library/unittest.html#test-discovery)
and copies the collector's current source dependency from
`scripts/path_safety.py` at base `0947b01289dcaa9157aa38392a94cf00f592b86d`.
The retained baseline errors and corrected assertion distinguish a setup
failure from a measured guard removal.

The supported mechanisms are the pinned upstream
[Alpaca REST transport](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/common/rest.py),
[Feast FileOfflineStore](https://github.com/feast-dev/feast/blob/1d5be950cf718a674cb01eaf0fd0ad6f0a4c6335/sdk/python/feast/infra/offline_stores/file.py),
[Feast PIT contract](https://docs.feast.dev/getting-started/concepts/point-in-time-joins)
and [GDELT DOC client](https://github.com/alex9smith/gdelt-doc-api/blob/f2e500144b0a6090d63723f94453b32717e5fd23/gdeltdoc/api_client.py).
The comparison follows the already reviewed September recipe and
[LEAN's documented raw daily format](https://www.quantconnect.com/docs/v2/lean-engine/data-format/equity);
it computes no strategy return. The matrix follows the existing strict JSON
loader and receipt path confinement. Late ingested revisions, licensed research
history, provider corrections and permitted reuse remain separate from an
event-time fixture result.
