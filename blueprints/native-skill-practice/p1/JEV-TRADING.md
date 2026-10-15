# Frozen trading classification harness

This extends P1 with the builder and scorer required by the private record
`us-equities-trading/docs/decisions/2026-10-11-jev-harness-case-sets.md`
and `coordination/trading-cc/specs/jev-trading-20261015/JEV-HARNESS-ADDENDUM-01.md`.
Private authority and review records are cited by name and path only; their
comparison digests stay in the owning runner's private provenance file.
The build executes synthetic fake transports only. Both `jev-1.14.0` and
`jev-1.13.0` use the same cases, prompts, option order and seeds in one run.
The extra model-to-model pair is explicitly reported only.

The owning trading runner performs scored execution through `credential_run`
after the PR's two-family reads. The public executable has only `build` and
`syn` commands. The `run()` library seam uses `TypeSafeSDK`, which delegates to
the adopted `gap_crosswalk.call()` transport, typesafe-sdk 0.7.2 with its native
429/529 policy. A scored start verifies the native `credential_run.py typesafe`
parent scope before creating any output. Outside that scope it raises and
creates no SCORED receipt. The key value is consumed only by the SDK invocation
after that check; no store is read here. Private authorization/review files are
verified from an external provenance file. Public receipts carry only their
names/paths, never comparison digests. Headers and exception messages are omitted.

## Files and decision coverage

| Record | Implementation | Named test coverage |
| --- | --- | --- |
| 1; addendum A1/A2 | `jev_trading_run.py`: versioned requests, response-model checks, scored attestation; `MODELS` in scorer | `TransportTests.test_request_version_options_and_response_mismatch_fail_closed`, `test_scored_preregistration_guards_without_invoking_any_transport`, `test_http_contract_has_only_standard_headers_and_no_alias` |
| 2 | Static sets remain classification diagnostics; no availability clock or lane admission is inferred | `BeatsTests.test_canary_failure_missing_report_and_harness_not_pooled` |
| 3 | `jev_trading_cases.py`: all five source pins, stratified FPB split, nine id-list pins, Unicode content exclusion, duplicates and seeded option order | `CaseTests`; frozen-source receipt |
| 4 | `jev_trading_baselines.py`: native finBERT mapping/loaders, 2048-dimensional Nemotron document embeddings, one sklearn logistic head on excluded raw training; Haiku budget and GPU-window gates | `BaselineTests`; `TransportTests.test_haiku_workload_config_cannot_change_between_sets` |
| 5 | `preregistration.pending_sets` and `pending_rules_status`: SEC/openFDA and unfrozen 8-K predicates remain `NOT_RUN`, including Item 6.06 and availability clocks | `TransportTests.test_pending_sets_have_no_acquisition_or_admission` |
| 6 | `jev_trading_scoring.py`: sklearn point metrics, canonical-text cluster bootstrap, original representative rows, failures, Wilson, exact McNemar, uniform sensitivity | `MetricsTests`, including record's hand-computed oracle and independent sklearn resample checks |
| 7 | `jev_trading_canaries.py`: exact expression, option-contract exclusion, +728-day forms/ranges, year guard, fixed 281-item audit; unfrozen masker/auditor are explicit | `CanaryTests`; frozen source/date-subset verification |
| 8 | `latency_sample`, `latency_report`, response-token accounting, Haiku gate | `TransportTests.test_latency_nearest_rank_sample_and_cost_oracle`; `BaselineTests` |
| 9 | Exclusive preregistration before first call, input/content/code hashes, exact request wire bytes, normalized responses, failed/partial receipts and immutable output directories | `TransportTests` with fake transport, socket denial, artifact collision and interrupted-run fixtures |
| 10 | `build_frozen_sets`, `run`, `validate_receipt`: reproducible lists, SYN artifacts and partial receipts; review, scored execution and lane acceptance are future process obligations | `CaseTests.test_builder_requires_the_record_source_pins_and_library_versions`, `TransportTests.test_syn_preregistration_precedes_every_call_and_both_models_share_requests`, `test_invalid_registration_no_calls_and_partial_run_retained`; process-only obligations have no claimed executable test |
| Addendum A3 | `beats`, `harness_beats`: strict F1 lower bound, nonpositive Brier upper bound, model coverage, every applicable pair, named NOT_RUN pairs, canaries and per-set conjunction | `BeatsTests`; guard mutants |

## Reproduce offline

Use the existing P1 `requirements-scoring.lock`: NumPy 2.5.3, SciPy 1.18.1 and
scikit-learn 1.9.1. The builder refuses different installed versions. No
dependency is installed by this harness, and no command downloads a dataset or
model. The source manifest is a JSON map with exactly these roles:

```json
{
  "fpb": {"path": "<retained>/fpb-50agree/Sentences_50Agree.txt", "sha256": "<full JV47 digest>"},
  "tfn_train": {"path": "<retained>/tfn-train/sent_train.csv", "sha256": "<full JV47 digest>"},
  "tfn_scored": {"path": "<retained>/tfn-valid/sent_valid.csv", "sha256": "<full JV47 digest>"},
  "fomc_train": {"path": "<retained>/fomc-train/train.csv", "sha256": "<full JV47 digest>"},
  "fomc_scored": {"path": "<retained>/fomc-test/test.csv", "sha256": "<full JV47 digest>"}
}
```

Caller pins must match the record's constants, and the retained bytes must match
the caller pins. The build emits sorted scored, original-training,
final-training and excluded-training ids, hashes, counts and content hashes.
The nine record list hashes and two date-subset hashes must all match. Source
bytes and full generated lists stay in the coordination area; public evidence
contains counts and hashes.

```sh
"$JEV_SCORING_PYTHON" -B blueprints/native-skill-practice/p1/jev_trading_run.py \
  build --sources <coordination>/sources.json --out <private>/frozen-sets.json
"$JEV_SCORING_PYTHON" -B blueprints/native-skill-practice/p1/jev_trading_run.py \
  syn --out <new-private-directory>
"$JEV_SCORING_PYTHON" -B -m unittest tests.test_jev_trading
"$JEV_SCORING_PYTHON" -B blueprints/native-skill-practice/p1/jev_trading_mutants.py
```

For tests and SYN, mount `/` read-only with bubblewrap, bind a newly created
`/var/tmp` directory at `/var/tmp`, mount fresh `/dev` and `/proc`, and use
`--unshare-net --die-with-parent`. Remove scratch after retaining the receipt.
The mutation runner does this for each named test, mounting only its mutant over
the source path; it verifies that the real source bytes stayed unchanged. It
rejects syntax/import failures as invalid campaign results. A test invocation
without the numeric dependencies skips explicitly and is not acceptance evidence.

## Scored-run integration

The owning runner builds the sets from the retained manifest, prepares local
baseline adapters and logistic heads, and then calls `run(packs, new_directory,
TypeSafeSDK(), evidence_class="SCORED", command=..., baseline_adapters=...,
baseline_meta=..., attestation=Path("<private>/scored-proof.json"))` under the
reviewed checkout's native credential runner. The private proof contains path
and comparison-digest pairs for the addendum, both reviewer reads, SDK amendment
and current models/limits capture. `verify_attestation()` verifies those bytes
privately; only a names/paths projection reaches `preregistration.json`. The SDK
version and public wheel pin must match the adopted transport.
It records every absent baseline by name and reason. A missing requested
adapter refuses before the first call.

finBERT uses `AutoTokenizer` and `AutoModelForSequenceClassification` from the
official Transformers loader with the pinned revision and `local_files_only`.
Its current retained Hub revision prefix is `0bc2ac10dda6`; the full ID remains
unresolved offline. The capture citation is
`coordination/ns2604-coop/work-20261012/jev-screen-20261015/CLAUDE-ARM.md`
(Hub metadata read, lastModified 2026-10-12). This supersedes `4556d130`.
The comparison disposition is **USE for research**, with `cc-by-nc-sa-4.0`
recorded and no redistribution. There is no licence gate or licence exclusion.
Resolving the full ID and exercising the cached-weight loader remain explicit
inputs to the owning runner; the BUILD test checks the requested prefix only.
The config's positive/negative/neutral order is checked; FOMC is refused.
`nemotron_native(device)` uses the upstream Sentence Transformers document
encoder. `fit_head(pack, embed)` fits `LogisticRegression(max_iter=1000,
random_state=20261011)` once, without changing other defaults. Its retained
joblib bytes and SHA256 must be frozen before `run`; `FittedHead.predict` uses
that same estimator for raw and transformed text. These factories do not
install software or download weights.

A CLM adapter needs its pinned GPU-window receipt. A Haiku adapter belongs to
its own credential-runner workload and returns probabilities plus input/output
usage; it also supplies a deterministic `token_bound(set, row)` from its owning
native tokenizer. `HaikuBudget` validates its frozen parameters, pricing capture,
estimate and twice-estimate cap, debits a reservation before dispatch and
reconciles known usage afterward. A timeout or malformed usage retains the
reservation as uncertain spend. The first cap rejection latches across all
remaining conditions and sets, making uncalled rows a suffix of the frozen
order. The workload and cap cannot change between sets.
The owning adapter retains its native request/response and ledger receipt; the
harness retains the normalized typed response and its hash. Haiku comparisons
carry `self-reported vs returned probabilities`. The build instantiates neither
paid baseline nor a GPU service.

## Populations, receipts and limits

Headline macro-F1 and coverage include every scored row. Failed responses are
sentinel misses. Brier/ECE use valid rows, and paired differences use the shared
valid population. The bootstrap samples canonical-text clusters and keeps all
their rows, including conflicting labels. McNemar and Wilson use the original
lowest-id representatives; a failed representative is never replaced. The
vectorized resampling statistic uses additive confusion, squared-error and ECE
bin sums, cross-checked against independent sklearn point computations. Both
point and bootstrapped ECE use the accepted `Prediction.label` for correctness
and maximum probability for confidence. A supplied maximum-probability tie
choice is retained; without a supplied choice, the first sorted label wins.

Exactly 1% failures is complete under decision 6's **exceeds 1%** definition.
ADDENDUM-01 also contains "below 1%" wording; the frozen sizes 1,454, 2,388 and
496 cannot realize exactly 1%, so both comparisons agree on all permitted
failure counts. The exact boundary must be reconciled by the record owner
before a population extension; this fold preserves the frozen implementation.

BEATS requires every ran pair's F1 interval entirely above zero and Brier upper
bound at or below zero. It rejects incomplete models and failed/unreported
canaries. Missing baseline pairs remain named `NOT_RUN` rows; zero ran pairs
cannot pass. Harness BEATS is a conjunction of eligible per-set outcomes and
never pools metrics. It confers no lane admission.

Each run creates `preregistration.json`, `calls.jsonl`, `report.json` and
`receipt.json`. The preregistration includes all applicable pins and explicit
NOT_RUN fields for unfrozen inputs. It is hashed before invocation and checked
again before every call. The journal retains exact Jev request wire bytes so
canonical JSON cannot erase the option order. Responses retain allowed typed
fields, response-model identity and usage; arbitrary error/refusal text and
headers are omitted. The receipt records the command, exit code, input/output
hashes and failures. Interruptions preserve the partial journal and receipt;
existing run directories and artifacts are not overwritten.

The SYN fixture uses invented sentences, fake probability vectors and synthetic
latencies/token counts. Its costs are simulated, and all output carries `SYN`.
Source reproduction is local integration, not model performance. No scored Jev,
Haiku, CLM, finBERT or Nemotron inference was run by this build. SDK currency,
native model loading with real weights, paid latency/cost, masking/auditor
selection, pending-set acquisition and paper-lane admission remain separate
measured events. The static date canaries are descriptive counts only.

The Jev preflight checks the 1,000-input-token planning estimate against
$0.386568 per model and $0.773136 combined. That estimate is not a tokenizer:
before dispatch, the budget reserves 65,536 input tokens for each possible
native SDK attempt, conservatively covering the vendor's default 64k context
limit. Known usage reconciles the successful attempt; ambiguous retries and
missing usage retain their reserves. Returned usage above the planning bound
stops that model's remaining calls. A response above the vendor ceiling is
untrusted accounting: the model stops and its reported upper bound becomes
unknown. Reports distinguish known spend from reserved exposure and do not
report unknown charges as zero. Per-arm costs also mark unresolved retry usage
as incomplete and retain the known successful-attempt token count.
The conservative reservation can stop a run
before the planning estimate is exhausted; this is an incomplete comparison,
never permission to increase the cap.

## Screen inputs for later preregistration

The retained `SCREEN-jev-typesafe-20261015.md`, section 5, supplies T0–T10 as
proposals, not admitted J-set scoring. Their readiness requirements are in
[`screen-inputs.json`](../../../evidence/artifacts/jev-trading-build-20261015/screen-inputs.json).
They require a separate sealed addendum. T8 tradeability and T9 order-path
guards also require their own admission after upstream-engine historical E2E.
The ai-hedge-fund and QuantDinger integrations remain rejected because they
use judgments in order paths.

Jansen's external 2026-10-13 article, "Testing Jev on Financial Documents",
is reported in that screen: 3,006 filings, 11 8-K categories, item numbers and
headings removed; Jev 1.13 at 79.3%, logistic regression at 89.4%, LightGBM at
91.3%, and trained models overtaking at 800 labels. These are external reported
results, not this harness's metrics; the primary article/code was not reverified
offline, and this record does not rename its percentage metric macro-F1.
It supports retaining the existing joint F1/Brier BEATS requirement.

## SOTA sources

- Binding recipe and source evidence, held privately in `us-equities-trading/`:
  `docs/decisions/2026-10-11-jev-harness-case-sets.md`, decisions 1–10, and
  `docs/decisions/evidence/jev-harness-sources-20261011.md`, JV1–JV52.
- [TypeSafe HTTP API](https://docs.typesafe.ai/api.md), retained capture SHA256
  `6b760275f89341fe15cff80c28aacae94d7d0c0c99afcd987ec0bca680b5713a`:
  Evaluation endpoint, Request body, Choice and Response body. ADDENDUM-01
  supplies the two model IDs; this build performs no live currency check.
- [TypeSafe SDK 0.7.2](https://github.com/typesafe-ai/typesafe-sdk-python/tree/f078f1e208a0d885154dc758344ae4fce77ac168),
  `_core/retry.py`, `_core/transport.py` and `_core/response_types.py`, through
  the adopted [SDK transport decision](../../../docs/decisions/2026-10-05-typesafe-sdk-transport.md).
  Five total attempts; only 429/529; 1/2/4/8-second backoff; no jitter,
  Retry-After or connection/timeout retries; 60-second attempt timeout.
  The qualified wheel and native MockTransport tests exercise this policy.
- Native start boundary: `tools/credentials/credential_run.py::parse_args`
  and `run_command` at repository base `0f4ee075b2ab3af1b099d5ca1ecb8cae02ee3f5b`.
  Only public parser/source/process metadata is inspected; ancestry is an
  accidental-start check, not authentication against a hostile same-user process.
  Private proof validation checks bytes, not the meaning of reviewer approval;
  trading-cc retains that acceptance decision.
- ECE correction: `p1_scoring.py::expected_calibration_error` at the same
  repository base, whose `correct` argument is prediction accuracy. The two
  tie regressions cover the point and actual 10,000-draw clustered interval.
- [Financial PhraseBank loader](https://huggingface.co/datasets/takala/financial_phrasebank/blob/8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964/financial_phrasebank.py),
  ISO-8859-1 and last-`@` parsing; TFN
  `ccbe24de388e287beb92dd393a335c376b350ac3`; FOMC
  `6b0283f55f0005a6d38d49f271d795c21fccc1a3`; all file hashes are JV47.
- [scikit-learn 1.9.1](https://github.com/scikit-learn/scikit-learn/tree/1.9.1),
  `model_selection/_split.py`, `metrics/_classification.py`,
  `linear_model/_logistic.py`; [SciPy 1.18.1](https://github.com/scipy/scipy/tree/v1.18.1),
  `stats/_resampling.py` and `stats/_binomtest.py`; NumPy 2.5.3
  `random.default_rng`. Existing P1 lock and installed sources are reused.
- [finBERT](https://huggingface.co/ProsusAI/finbert/tree/0bc2ac10dda6),
  Hub prefix and capture boundary above; the older JV16–17 card/config remain
  historical source checks, not proof of the new full revision.
  [Nemotron 1B](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/tree/c0c9fea93ea424587517f2c59e20db9f1d6bf615),
  README's Sentence Transformers example; [CLM-8B](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B/tree/e939398d4556fcd9400c76fa8c5a513202f42b0a),
  README's typed client. These retained sources are JV16–19.
- Haiku's structured output, pinned snapshot and pricing: retained Anthropic
  primary-source captures JV20, JV21 and JV52. The record's own-workload gate
  is JV51. No larger language-model runtime or new harness is adopted here.

The bounded layer-resolution record and measured build evidence are in
[`evidence/artifacts/jev-trading-build-20261015`](../../../evidence/artifacts/jev-trading-build-20261015/).
