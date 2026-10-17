# Decision: live Hindsight reranks with ettin-150m on CPU, and its LLM calls are capped at one (2026-10-17)

**Status:** live on NativeHorizonNY.
- The LLM cap of 1 took effect when `hindsight.service` finished starting at 2026-10-17T07:02:17Z, its "Application
  startup complete" journal line.
- The reranker switch went healthy at 09:23:36Z.

This record follows the host change, as the CC's rulings ask:
- #25798 (2026-10-17T09:20:15Z) approved the switch;
- #25997 (09:31:13Z) accepted it and asked for this record.

## What changed on the host

The live unit `hindsight.service` (Hindsight 1.0.0 on 127.0.0.1:23777) reads `~/.config/hindsight/hindsight.env`.
Five lines changed. They are shown here as host lines with the home directory written as `~`; on the host, the model
path is written in full.

```
HINDSIGHT_API_RERANKER_PROVIDER=local
HINDSIGHT_API_RERANKER_LOCAL_MODEL=~/.cache/huggingface/hub/models--cross-encoder--ettin-reranker-150m-v1/snapshots/025501c4e0f9bbeb4c5b198318e0089ff061cc14
HINDSIGHT_API_RERANKER_MAX_CANDIDATES=16
HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU=true
HINDSIGHT_API_LLM_MAX_CONCURRENT=1
```

The env file also holds credential-named settings, so it is never committed. The repository has no renderer for this
file yet (see Residuals).

## Why ettin-150m

- **Method.** The 7.1(b) recall comparison was preregistered before any measurement. 7.1(b) is the reranker screen:
  item 1 of section 7 in the ns51 builder's private handoff (LEDGER 1.11).
  - Its records are private and cited by name only: `RECALL-PREREGISTRATION-20261017.md`, its three amendments, and
    the receipt `RECEIPT-recall-20261017.md`.
  - 60 blind-written queries ran on a throwaway copy of the live bank.
  - RRF was compared with every arm that met the latency fit rule.
- **Results.**

  All arms ran on the CPU.

  | Arm | in_top3 | MRR | p90 latency |
  | --- | --- | --- | --- |
  | ettin-150m (`cross-encoder/ettin-reranker-150m-v1`) | 40/60 | 0.4394 | 2,930.0 ms |
  | ettin-400m | 39/60 | 0.4529 | 7,416.0 ms, above the 7,000 ms bound |
  | LAMAR-600m (`nlpai-lab/LAMAR-600m`) | 34/60 | 0.4408 | 5,976.9 ms |
  | RRF | 19/60 | 0.2749 | 121.6 ms |

- **The rule,** fixed in the preregistration:
  1. Pick the non-RRF arm with the highest in_top3, with ties broken by MRR.
  2. That arm must beat RRF strictly on both in_top3 and MRR.
  3. Its recall p90 must stay at or under 7,000 ms.
- **The result.** That arm is ettin-150m: in_top3 40 against RRF's 19, MRR 0.4394 against 0.2749, and p90 2,930.0 ms.
- **CPU, not GPU.**
  - The live reranker runs on the CPU. `HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU=true` makes the device selector return
    the CPU (`engine/local_device.py:117`, reached from `engine/cross_encoder.py:290`).
  - A GPU placement was measured only with FP16, which Hindsight 1.0.0 makes opt-in:
    `HINDSIGHT_API_RERANKER_LOCAL_FP16` defaults to false (`config.py:1292`, `engine/cross_encoder.py:221`).
  - With FP16 on and a non-CPU device, Hindsight halves only the CrossEncoder's first module
    (`engine/cross_encoder.py:344-345`). In sentence-transformers 6.1.0 that module is the transformer alone
    (`sentence_transformers/cross_encoder/model.py:429-431`). The ettin models' Dense head stays float32, so the first
    `predict` fails with a dtype mismatch.
  - The preregistered GPU arms were that FP16 placement. Both crashed at their first `predict` with no latency sample,
    so neither fits.
  - The private receipt `RECEIPT-fit-a2-20261017.md` records the run and a CPU reproduction of the cause
    (`fp16_halving_repro.py`, 2026-10-17T05:55:18Z).
  - A float32 placement on the GPU was not measured.

## Live measurement, and what callers see

- **Latency.** The 30 frozen queries ran as recalls on the live bank, with budget mid and max_tokens 4096. The private
  receipt `RECEIPT-live-switch-20261017.md` records both runs:

  | Run | p50 | p90 | max | Results per recall |
  | --- | --- | --- | --- | --- |
  | RRF, 09:22:18-09:22:22Z | 126 ms | 176 ms | 241 ms | 31-68 |
  | ettin-150m, 09:23:46-09:26:03Z | 5,114 ms | 5,490 ms | 6,169 ms | 16 |

  - All 60 recalls returned HTTP 200.
  - The live p90 is 1.5 s under the preregistered 7,000 ms bound.
  - It is about twice the eval arm's 2,930 ms, because the live worker's retain and consolidation tasks share the CPU.
- **At most 16 results per recall.** `HINDSIGHT_API_RERANKER_MAX_CANDIDATES=16` caps the candidates the reranker scores
  (`engine/search/recall_boost.py:208-212`):
  - a pool of 16 or fewer passes unchanged;
  - a larger pool is cut to its top 16 by boosted RRF score. That is the plain fusion order unless
    `HINDSIGHT_API_RECALL_STRATEGY_BOOSTS` is set (empty by default, `config.py:1347`).
  - So a recall returns at most 16 results. On the probe each query returned 16, against 31-68 before the switch.
  - A caller that asks for more than 16 now gets at most 16. A higher cap needs its own fit measurement, because
    latency grows with the number of pairs.
- **Memory.**
  - The unit's MemoryPeak was 3,455,795,200 B after the probe, against 567,066,624 B on RRF.
  - At 09:28Z the process RSS was 1,728,112 kB.
  - The cgroup held 0.84 GiB anon and 0.89 GiB file, the memory-mapped weights.

## Why the LLM cap

- **One process-wide semaphore.**
  - Hindsight 1.0.0 gates every LLM call with one semaphore (`engine/llm_wrapper.py:60-69`). It is sized by
    `HINDSIGHT_API_LLM_MAX_CONCURRENT` (`config.py:163`), which defaults to 32 (`config.py:1178`).
  - Upstream's comment there advises 1 for local LLMs such as Ollama (`engine/llm_wrapper.py:61`).
  - Optional per-operation caps (retain, reflect, consolidation and mental-model refresh) are acquired before it
    (`engine/llm_wrapper.py:86-95` and `:138-152`).
- **The failure at the default.**
  - Ollama loaded the model with one slot: `n_slots = 1` in `ollama.service`'s journal at 2026-10-17T06:32:39Z and
    07:09:38Z.
  - In the ten minutes 06:33Z-06:42Z at the default cap, 47 of Ollama's 52 chat calls returned 500.
  - The `user.slice` memory cgroup OOM-killed `llama-server` at 06:31:42Z and 07:08:36Z (kernel journal).
- **The measurement.** `llm_cap_watch.py window` counted calls per minute from the hindsight and ollama journals, into
  the private files `hindsight-llm-cap/before.jsonl`, `after.jsonl` and `after-cap1.jsonl`:
  - **Cap 2,** set at 06:44:11Z: 4 of 16 chat calls succeeded in 06:46Z-07:00Z.
  - **Cap 1,** set at 07:01:21Z and live at 07:02:17Z: 12 of 15 succeeded in 07:03Z-07:17Z.
    - That window includes Ollama's restart after the 07:08:36Z OOM kill.
    - In that one minute, Hindsight logged 59 connection errors and 3 timeouts.
- **The rulings.**
  - The CC approved cap 2 in #22386 (06:42:09Z), and allowed cap 1 in #22775 (07:01:56Z).
  - In #22797 (07:03:54Z) it kept cap 1 and the default 120 s timeout (`config.py:1182`), on the lone-call times of
    25-68 s that it cites there.
  - The 07:03Z-07:17Z window, measured afterwards, agrees.

## Guard and rollback

- **Rolling watch.** `hindsight-reranker-watch.timer` runs `hindsight-reranker-watch.service` every 5 minutes. It rolls
  live Hindsight back to RRF when either of these holds:
  - p90 over the last 30 live recalls since the switch exceeds 7,000 ms (decided once at least 10 recalls exist);
  - any recall-related failure since the switch. That is either an event in the Hindsight hooks' `diag.jsonl` whose
    name ends in `_failed` and names recall or observations, or a live-log line that ties recall, the reranker or the
    cross-encoder to a timeout.

  On a trigger, it announces on hcom, rolls back, restarts the unit and disables itself.
- **Where it lives (host only):**
  - `~/.local/share/native-agent-stack/hindsight-reranker-watch/watch.py`, with its copy of `live_switch.py`;
  - the units `~/.config/systemd/user/hindsight-reranker-watch.service` and `.timer`;
  - the state file `~/.local/state/hindsight-reranker-watch/last.json`.
- **Rollback by hand.** Set `HINDSIGHT_API_RERANKER_PROVIDER=rrf`, remove the three other reranker lines, and restart
  `hindsight.service`.

## Residuals

- **No plan row.** The plan has no row for the live Hindsight 1.0.0 unit or its env file. The profile still pins
  hindsight-api 0.10.2 for the research instance. Adding the row belongs to the batch that follows PRs #1242 and #1243.
- **Untested rollback path.** The watch's rollback path has not run end to end, because running it would roll live
  back.
- **Probe-based latency.** Natural recall traffic on the live instance is rare.
  - The hooks' `diag.jsonl` shows 411 `pages_ok` since 2026-10-16T16:10Z, and no recall fallback
    (`RECEIPT-live-switch-20261017.md`).
  - So the live p90 rests on the 30-query probe.

## Sources

- **vectorize-io/hindsight v1.0.0,** commit 39c65ffe2f140d0c84cee58566cad8900c5b9908
  (https://github.com/vectorize-io/hindsight/tree/39c65ffe2f140d0c84cee58566cad8900c5b9908). The cited files sit under
  `hindsight-api-slim/hindsight_api/` and are byte-identical to the installed hindsight-api 1.0.0:
  - `config.py:163`, `:604-611`, `:1178`, `:1182`, `:1292` and `:1347`;
  - `engine/cross_encoder.py:221`, `:290` and `:344-345`;
  - `engine/local_device.py:117`;
  - `engine/search/recall_boost.py:208-212`;
  - `engine/llm_wrapper.py:60-69`, `:86-95` and `:138-152`.
- **UKPLab/sentence-transformers v6.1.0,** commit b0bf39968ba461c34b29372144794eff1be06f6d:
  `sentence_transformers/cross_encoder/model.py:429-431`
  (https://github.com/UKPLab/sentence-transformers/blob/b0bf39968ba461c34b29372144794eff1be06f6d/sentence_transformers/cross_encoder/model.py#L429-L431).
  The installed 6.1.0 wheel carries the same lines.
- **`cross-encoder/ettin-reranker-150m-v1`** on Hugging Face, at revision 025501c4e0f9bbeb4c5b198318e0089ff061cc14
  (https://huggingface.co/cross-encoder/ettin-reranker-150m-v1/tree/025501c4e0f9bbeb4c5b198318e0089ff061cc14).
- **`nlpai-lab/LAMAR-600m`** on Hugging Face, at revision 3af1f97945392da8ef46217640641355928aeb59
  (https://huggingface.co/nlpai-lab/LAMAR-600m/tree/3af1f97945392da8ef46217640641355928aeb59).
