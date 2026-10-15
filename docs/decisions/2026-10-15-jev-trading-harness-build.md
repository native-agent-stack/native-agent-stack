# Jev trading harness: offline build and synthetic acceptance

Status: implementation and SYN plumbing accepted locally; the scored run remains
with trading-cc after two-family review. No model is selected for lane use.

## Scope and authority

This implements decision 9 of the private trading record
`us-equities-trading/docs/decisions/2026-10-11-jev-harness-case-sets.md` and its
`docs/decisions/evidence/jev-harness-sources-20261011.md` source evidence.
Build authority is `BRIEF-jev-harness-build-r1.md`; model parity and BEATS are
specified by `coordination/trading-cc/specs/jev-trading-20261015/JEV-HARNESS-ADDENDUM-01.md`.
These private records are cited by name/path only. Their verification digests
and reviewer-read digests remain private and are not exported in receipts.

The native-agent-stack base is
`0f4ee075b2ab3af1b099d5ca1ecb8cae02ee3f5b`. This is one extension of P1,
not a new runtime, research survey or model-adoption decision. Its public seams
are the brief's case builder, metrics/bootstrap, BEATS, fake transport and
receipt contract.

## Resolution protocol and bounded delta

The consumed catalog is `catalogs/landscape/us-equities.json`, layer
`research-factors-ml`, whose verdict is `recorded` and whose winners are skfolio
and EdgarTools. These cover existing research-validation and document-ingestion
roles; they do not settle this Jev classification comparison. No matching
Jev-specific wave was found in `catalogs/sota-convergence/layer-verdict-waves.json`.

The last ledger sweep covering this layer is `landscape-sweep-20260926`, with
`catalogs/sota-convergence/manifest-20260926.json` and retained
`evidence/artifacts/landscape-sweep-20260926/returns.json`. Its survivors are
linearmodels, Kronos, Toto and EXAONE-Forecast. The preceding 20260923 sweep's
LightGBM and RD-Agent survivors remain carried forward here; omission is not
adjudication. The latest row also retains a failure reference and a vLLM
pin-movement reopening reference. This build changes none of those verdicts,
does not declare the broader layer FINAL, and does not dispatch new research.
The bounded action is the already committed classification comparison's
builder/scorer, with local primary sources and a fake transport as required by
the build brief. Current upstream currency is an input to the owning scored
runner's preregistration; no network request was made to resolve it here.

## Choice and alternatives

Extend `blueprints/native-skill-practice/p1/` and reuse its locked NumPy 2.5.3,
SciPy 1.18.1 and scikit-learn 1.9.1 environment, Wilson intervals, exact McNemar
and ECE bin implementation. P1's balanced accuracy and its API-confidence J1
ECE cannot substitute for this record's macro-F1 and probability-maximum ECE.
The additional code implements the frozen recipe and validation boundaries;
it does not replace any vendor model, tokenizer, estimator or bootstrap.

Jev uses the adopted typesafe-sdk 0.7.2 transport and its native 429/529 handling
through `tools/sota-convergence/gap_crosswalk.py::call`, as selected by
`docs/decisions/2026-10-05-typesafe-sdk-transport.md`. finBERT and Nemotron factories use their
native pinned local-only loaders; the logistic head uses sklearn defaults with
only the record's max-iteration and seed changes. Haiku and CLM remain behind
their own workload and GPU-window inputs. The pending 8-K/openFDA sets and
unfrozen mask/auditor are explicitly NOT_RUN. No second EDGAR client, acquisition,
broker path, key store, environment file or credential inventory is accessed.

Vectorized bootstrap statistics sum per-cluster confusion, squared-error and
ECE-bin contributions. Named tests compare resampled values with independent
sklearn point computations, including conflicting duplicate labels. This
preserves the specified SciPy call while avoiding repeated estimator setup
inside 10,000 draws. Real model execution is untested by this build.

## Measured evidence

The [build evidence](../../evidence/artifacts/jev-trading-build-20261015/README.md)
retains:

- All nine frozen list hashes reproduced from the five pinned source files;
  final training counts 3,389 / 9,542 / 1,960 and date subsets 108 / 16 / 0.
- The final fake-transport SYN run, with 161 synthetic calls, both model IDs,
  all 22 planned Jev/baseline pair rows and three reported-only parity pairs.
  CLM/Haiku remain NOT_RUN in that dry run. No synthetic number is model evidence.
- Original-head acceptance of 127 tests and 90/90 mutants is retained as
  historical evidence. The review fold supersedes it with the current
  `validation.json` and 108/108 named guard-mutant results.
  Live files were read-only and network namespaces isolated; scratch was under
  `/var/tmp` and removed. Mutation receipts include unchanged-source checks.
- Fail-first corrections with source citations: exact date-expression flags
  (decision 7/JV47), wire option order and baseline preflight (decisions 3/9,
  TypeSafe Choice API), Haiku price arithmetic and frozen order (decisions 4/8),
  ordered-arm diagnostics (decision 3), typed usage retention (decision 9), and
  implementation-source citation lookup (`inspect.unwrap`, CPython 3.12
  `Lib/inspect.py`). The first 66-mutant campaign's two survivors are retained;
  independently isolating those assertions killed both. The expanded final
  campaign covers all explicit refusal guards plus the numeric/ordering rules.

`syn-before-final-audit/`, `syn-before-review-fold/` and the corresponding
historical mutation/validation files retain earlier measurements. Their public
projections omit private record digests and unsupported historical hashes,
with explicit projection metadata and updated projection integrity hashes.
Original private provenance stays in the coordination area by name/path; Git
history is not rewritten. Current `syn/` and `guard-mutants.json` supersede them.

## Combined review correction

The CC FULL, GPT full1 and local review at `ea96de7a` are addressed together.
Private review/authority hashes are removed from the public tree and PR body;
runtime proof comparison happens privately. The native credential-runner start
check refuses before directory creation. The adopted SDK replaces direct HTTP
and preserves its five-attempt 429/529 policy, tested on native MockTransport.
Jev reserves bounded input exposure before each possible SDK attempt and stops
at the token/USD limits. Haiku debits before dispatch, retains unknown charges
and latches its first cap rejection across all conditions and sets.

The exact GPT timeout witness reproduced 619 admitted calls and $4.0235 of
synthetic exposure against the $3.3216 cap at the original head. The correction
permits 511 calls and retains $3.3215 for both timeouts and malformed usage.
Tied-label ECE now uses the accepted prediction in both point and bootstrap
statistics (the reproduced 0.4/0.2 errors become 0.6/0.4). A separate mutant
swaps the real model-minus-baseline arguments and is killed by its named test.
Fail-first cases, sources and verification limits are in `validation.json`
and the expanded implementation map.

The finBERT screen update is recorded at prefix `0bc2ac10dda6` with full ID
unresolved offline, research comparison USE and `cc-by-nc-sa-4.0`; no weights
are redistributed and no licence gate is added. The retained external Jansen
comparison supports the unchanged joint BEATS rule. ai-hedge-fund and
QuantDinger remain rejected for order-path use. T0–T10 are proposed readiness
inputs in `screen-inputs.json`; they require a new sealed addendum and their
separate admission gates.

## Sources and overturn condition

The detailed [implementation-to-source map](../../blueprints/native-skill-practice/p1/JEV-TRADING.md#sota-sources)
cites the exact dataset/model revisions, the TypeSafe API capture, installed
metric source hashes and the retained decision evidence. Source review and
local integration remain distinct from SYN and from future scored measurements.
The [source receipt](../../evidence/artifacts/jev-trading-build-20261015/source-review.json)
records the local upstream bytes inspected, without fetching new pages.

A disagreement with the record, a new dated addendum or a reproduced upstream
behavior at its pin reopens the affected mechanism. The scored report can
settle the preregistered comparison only after its named inputs exist. BEATS
alone never admits a judgment to a feature or order loop; lane admission needs
its separate dated threshold/availability decision.
