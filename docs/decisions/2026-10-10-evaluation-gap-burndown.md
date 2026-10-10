# Evaluation gaps: verified native receipts and remaining scope

The evaluation-experiments row at main `0947b01289dcaa9157aa38392a94cf00f592b86d`
reports ten open gaps, eight executable now. The frozen September 22 crosswalk
predates the retained September 23 wave. Its independent review supports five
complete settlements and three partial advances, but the matrix only reads the
crosswalk and therefore still reports all eight executable entries as open.

This change joins a dated, layer-specific ledger into the existing matrix
generator. It leaves the historical crosswalk, original receipts, winner pins
and host qualifications intact. A complete settlement counts only when the
exact gap text, single-gap receipt outcome, receipt digest and every retained
output digest agree. A missing or changed artifact stops generation. Partial
advances remain open. The ledger also binds the retained review and the current
verification receipt, so reviewers can assess why each outcome is credited.

The regenerated row has **five open gaps, three executable now**. Only this
layer changes. Across the matrix, open gaps become 350 from 355 and executable
gaps become 233 from 238; winner selection and host-status summaries do not change.

## Verified settlements

| Gap | Evidence and scope |
| --- | --- |
| 0 | Both native tools ran the same frozen eight cases, exact-text transform and deterministic scorer; retained faults and native interrupt/resume are verified. |
| 1 | Separate pinned installs and minimal native executions of Inspect, MLflow, River, MTEB and Phoenix are retained, including the MTEB result and Phoenix span round trip. A fresh Inspect install/run is separately dated. |
| 2 | The matched eight-case comparison reproduces exactly. Scorer reproducibility and resume tie; Inspect preserves retried errors in its final log and all eight source-byte hashes. This measures harness behavior. |
| 3 | The committed Inspect fixture freeze hashes agree with the retained run. A fresh pinned mock-model invocation completes all eight cases with zero model tokens. |
| 7 | River's native delayed progressive-validation report binds the retained financial stream. The delayed causality probe observes zero early labels; the immediate control observes 1,797. This is a mechanics check. |

All 77 raw-output bindings named by the eight prior receipts were recomputed
with zero missing or mismatched files. Those executions remain historical.
The new Node contract run passes six tests. A fresh isolated Inspect 0.3.266
installation and native CLI run use the original task and `unshare -rn`, bounded
concurrency/retries and a 1 GiB scope. Its mock-provider source bytes match the
pinned mirror. Three labels match and five do not, reproducing the deterministic
baseline; completion is not eight correct answers or a semantic-quality claim.

## Partial and excluded gaps

| Gap | Why it remains open |
| --- | --- |
| 4 | The Linux code-retrieval replay and Darwin rank agreement are retained. This supplies no financial-document answer judgments, answer quality or net trading performance. A new domain/strategy qualification requires a reviewed protocol and appropriate data. |
| 5 | The native rankers reproduce the 32-query abstention report and 10,000-resample paired bootstrap exactly, including the original rankings. The MRR interval includes zero and the promotion rule does not fire. The queries remain authored over 15 public documents, with leave-one-out calibration on the same pack; independent held-out or real-user queries are still missing. |
| 8 | Native MLflow readback binds 16 parameters, 19 metrics and nine full input-hash tags, with both changed-metric and changed-exit-code controls detected. The chronological code already uses skfolio WalkForward, but its remaining rules and selection logic are project-local. Tracker acceptance does not establish a complete upstream evaluation implementation. |
| 6 | Runtime supervision and broker-authority isolation belong to the runtime and orchestration layers. This slice does not qualify them. |
| 9 | Historical independent-lane disagreement is already adjudicated; it is a catalog-edit entry, not a missing executable experiment. |

No broader receipt is credited for these clauses. Their existing categories
are preserved, so the three partial executable entries remain visible for CC
disposition rather than disappearing through reclassification.

## Reproducibility correction and regression

The retained two-arm comparison had one reproducibility defect: the reader
searched only the native config directory, but publication renames it `cfg-home`.
It silently omitted the retained injected-error record. The reader now supports
both layouts and reproduces the entire stored comparison object exactly. A
collected test fails on the old reader for this omission and passes after it.

The public matrix-count regression also fails against the original main
builder: ten open gaps versus the five genuinely remaining. Further controls
reject missing receipts, changed receipt bytes, changed raw outputs, changed
acceptance text and a false settled declaration over an advanced receipt.
Partial evidence and an absent optional ledger preserve original counts.

## SOTA sources

- Inspect AI 0.3.266, UKGovernmentBEIS/inspect_ai at
  `ec4dfc6953784dc45b79de3147530c89868c6e26`:
  `src/inspect_ai/model/_providers/mockllm.py:15-60` supplies the supported callable
  mock provider; `src/inspect_ai/_eval/eval.py:125,1303` supplies evaluation/retry.
  Primary source was read from the pinned local mirror; the installed mock
  provider has identical bytes.
- promptfoo 0.123.1: the existing frozen echo provider/config and retained native
  `eval`, `--retry-errors` and `--resume` results remain the comparison arm.
  No new provider call or package upgrade is part of this receipt reconciliation.
- agent-retrieval-bench v0.2.1 at
  `b487f3866cc13dd971819cb902517a6a50282404`:
  `src/agent_retrieval_bench/baseline.py:559-644` supplies native ranking and metrics;
  `README.md:95,268` supplies supported installation/tests. The current local
  mirror reproduces the retained abstention/bootstrap result exactly.
- MLflow v3.16.1 at `32792afe5b0183fce10532d3a023f5cfa8612d09`:
  `mlflow/tracking/fluent.py:1456,3225-3250` supplies native input logging/readback.
  The existing exact full-hash tags and dataset-digest limits remain explicit.
- River 0.26.1 at `64285b9dd6c606804753235fe992bcf25b9856ee`:
  `river/evaluate/progressive_validation.py` documents native moment/delay handling.
- MTEB 2.21.0: its versioned README documents supported `mteb.evaluate` and CLI
  execution. The retained STSBenchmark result remains a narrow public-benchmark run.
- Phoenix `arize-phoenix-v20.14.0`: the versioned README documents its supported
  package and server path. The retained native OTLP round trip is bounded to one
  synthetic span on a local server.
- Repository references: `tools/sota-convergence/gap_wave_ledger.py:12-21`
  defines complete versus partial single-gap credit; the dated receipts and
  `raw/review-codex-round1.md` provide the retained acceptance evidence.

The new ledger is
[gap-burndown-20261010-evaluation-experiments.json](../../catalogs/landscape/gap-burndown-20261010-evaluation-experiments.json).
Current verification and fresh native Inspect evidence are in
`evidence/artifacts/evaluation-gap-burndown-20261010/`.
