# Decision: live Hindsight reranks with ettin-150m on CPU, and its LLM calls are capped at one (2026-10-17)

**Status:** live on NativeHorizonNY. The LLM cap has been in place since 2026-10-17T07:02:18Z, and the reranker since
09:23:36Z.

This record follows the host change, as the CC's rulings ask:
- #25798 (2026-10-17T09:20:15Z) approved the switch;
- #25997 (09:31:13Z) accepted it and asked for this record.

## What changed on the host

The live unit `hindsight.service` (Hindsight 1.0.0 on 127.0.0.1:23777) reads `~/.config/hindsight/hindsight.env`. Five
lines changed:

```
HINDSIGHT_API_RERANKER_PROVIDER=local
HINDSIGHT_API_RERANKER_LOCAL_MODEL=~/.cache/huggingface/hub/models--cross-encoder--ettin-reranker-150m-v1/snapshots/025501c4e0f9bbeb4c5b198318e0089ff061cc14
HINDSIGHT_API_RERANKER_MAX_CANDIDATES=16
HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU=true
HINDSIGHT_API_LLM_MAX_CONCURRENT=1
```

On the host, the model path is written with the home directory expanded. The env file also holds credential-named
settings, so it is never committed. The repository has no renderer for this file yet (see Residuals).

## Why ettin-150m

- **Method.** The 7.1(b) recall comparison was preregistered before any measurement. Its records are private and cited
  by name only: `RECALL-PREREGISTRATION-20261017.md`, its three amendments, and the receipt
  `RECEIPT-recall-20261017.md`.
  - 60 blind-written queries ran on a throwaway copy of the live bank.
  - RRF was compared with every arm that met the latency fit rule.
- **Results.**

  | Arm | in_top3 | MRR | p90 latency |
  | --- | --- | --- | --- |
  | ettin-150m | 40/60 | 0.4394 | 2,930 ms |
  | RRF | 19/60 | 0.2749 | 122 ms |
  | ettin-400m | 39/60 | not reported here | 7,416 ms, above the 7,000 ms bound |
  | LAMAR-600m | 34/60 | not reported here | not reported here |

- **The rule.** The best arm must beat RRF on both in_top3 and MRR, with p90 at or under 7,000 ms. That arm is
  ettin-150m.
- **CPU, not GPU.**
  - Hindsight 1.0.0's FP16 path halves only the CrossEncoder's first module (`hindsight_api/engine/cross_encoder.py:344-345`).
  - In sentence-transformers 6.1.0, `CrossEncoder.model` is that module alone (`sentence_transformers/cross_encoder/model.py:429-431`).
  - So the ettin models' Dense head stays float32, and predict fails. The private receipt
    `RECEIPT-fit-a2-20261017.md` records this.
  - Upstream's main branch makes the same call.

## Live measurement, and what callers see

- **Latency.** On the same 30 frozen queries, the live p90 is 5,490 ms (p50 5,114 ms, max 6,169 ms; 30 of 30 returned HTTP
  200). RRF's p90 before the switch was 176 ms.
  - That is 1.5 s under the preregistered 7,000 ms bound.
  - It is about twice the eval arm's p90, because the live worker shares the CPU.
  - The private receipt `RECEIPT-live-switch-20261017.md` records the run.
- **Callers now receive 16 results per recall instead of 34-86.**
  - With `HINDSIGHT_API_RERANKER_MAX_CANDIDATES=16`, Hindsight keeps the top 16 candidates by boosted RRF score and drops
    the rest (`hindsight_api/engine/search/recall_boost.py:210-212` at 1.0.0).
  - So callers get fewer recall tokens, better ranked.
  - A higher cap needs its own fit measurement, because latency grows with the number of pairs.
- **Memory.** The process RSS went from about 0.5 GB to 1.73 GB: 0.84 GiB anon, plus 0.89 GiB of memory-mapped weights.

## Why the LLM cap

- **One semaphore.** All of Hindsight's LLM calls share one process-wide semaphore (`hindsight_api/engine/llm_wrapper.py:59-69`
  at 1.0.0), set by `HINDSIGHT_API_LLM_MAX_CONCURRENT` (`config.py:163`). The default allows 32 (`config.py:1178`).
- **The failure.** Ollama served the model with one slot. Up to 32 long prompts queued behind one another, timed out at
  the 120 s default, and retried. Ollama's unit was OOM-killed twice on 2026-10-17.
- **The measurements** (the CC's #22386 at 06:42:09Z, #22775 at 07:01:56Z and #22797 at 07:03:54Z):
  - a cap of 2 stalled;
  - a cap of 1 tripled the successful calls, to 12 per 15 minutes against 4;
  - lone calls took 22-101.5 s, under the 120 s timeout.

## Guard and rollback

- **Rolling watch.** `hindsight-reranker-watch.timer` runs `hindsight-reranker-watch.service` every 5 minutes. It rolls
  live Hindsight back to RRF when either of these holds:
  - p90 over the last 30 live recalls since the switch exceeds 7,000 ms (decided once at least 10 recalls exist);
  - any caller recall times out: a recall-fallback failure in the Hindsight hooks' `diag.jsonl`, or a live-log line
    that ties a recall or the reranker to a timeout.

  On a trigger, it announces on hcom, rolls back, restarts the unit and disables itself.
- **Rollback by hand.** Set `HINDSIGHT_API_RERANKER_PROVIDER=rrf`, remove the three other reranker lines, and restart
  `hindsight.service`.

## Residuals

- **No plan row.** The plan has no row for the live Hindsight 1.0.0 unit or its env file. The profile still pins
  hindsight-api 0.10.2 for the research instance. Adding the row belongs to the batch that follows PRs #1242 and #1243.
- **Untested rollback path.** The watch's rollback path has not run end to end, because running it would roll live
  back.
- **Probe-based latency.** Natural recall traffic on the live instance is rare. The prompt hooks inject through knowledge
  pages: 411 page lookups and no recall fallback in 17 hours. So the live p90 rests on the 30-query probe.

## Sources

- vectorize-io/hindsight v1.0.0, the installed hindsight-api 1.0.0:
  - `hindsight_api/config.py:604-611` (local reranker settings), `:163` and `:1178` (LLM concurrency);
  - `hindsight_api/engine/cross_encoder.py:344-345`;
  - `hindsight_api/engine/search/recall_boost.py:210-212`;
  - `hindsight_api/engine/llm_wrapper.py:59-69`.
- sentence-transformers 6.1.0: `sentence_transformers/cross_encoder/model.py:429-431`.
- `cross-encoder/ettin-reranker-150m-v1` on Hugging Face, at revision 025501c4e0f9bbeb4c5b198318e0089ff061cc14.
