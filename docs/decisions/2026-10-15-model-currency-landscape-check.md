# Model-currency rollover incident: nine sourced landscape checks

Read date: **2026-10-15 UTC**. Base: `a339425ca56ec3fb87dff0fa8ad5dffc83354168`.
The nine October 7 landscape exceptions became eight days old at UTC rollover.
The 42-day release/7-day landscape policy remains unchanged. The source URLs,
read date, candidates, retention reasons and overturn gates are in the nine
updated rows of [the inventory](../../catalogs/foundation/model-currency.json).
This supersedes their October 7 landscape observations; historical decisions
and selected model/weight/tokenizer revisions remain unchanged.

## Method and boundary

First inspected and ran the existing supported proposer:

```sh
python3 scripts/freshness_propose.py --model-currency --state-dir /var/tmp/currency-model-currency-incident-proposals-20261015
```

It reported all nine `refresh_landscape` actions. It checks primary release-line
metadata and proposes review; it does not write landscape judgments or establish
model quality. Current model cards, candidate cards, upstream consumer source
and publisher model searches were therefore read separately. Hugging Face's
installed `hf models info` and `hf models list --author ... --search ... --sort
created_at` supplied current revisions and bounded publisher searches; model
cards were read directly from primary HTTPS sources. No weights, model calls,
inference comparisons or production settings were changed.

## Current role evidence

All links below were read on **2026-10-15**; row sources retain additional candidate
cards and exact available revisions. These are source-review findings, with
selection/acceptance boundaries stated separately.

| Inventory row | Primary role evidence read | Disposition |
| --- | --- | --- |
| `nemotron-3-embed-8b` | [NVIDIA card at selected revision](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16/blob/d1f2f25730bbd775b99b29185134bc86653bf2d1/README.md), [EmbeddingGemma 2 card](https://huggingface.co/google/embeddinggemma-2/blob/914f7f89142e33e77833254d9c9b90c3cef7303b/README.md), NVIDIA Embed publisher search | Selected main unchanged; retain explicit compatible-server/retrieval/memory gate for the newer alternative. October 6 cooldown has elapsed and is removed as a current rationale. |
| `qmd-qwen3-reranker` | [Selected GGUF card](https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/blob/a02f48bb4f057028298c21fa033da2b30d7742d5/README.md), [current qmd loader](https://github.com/tobi/qmd/blob/93d211f9ef4a869a9aed0d075ca767dda552627f/src/llm.ts), Jina 3.5/Horizon/4B GGUF cards | Upstream default unchanged. Record Jina 3.5 explicitly alongside existing candidates; compatible 4B remains a quality/CPU-latency lead rather than a failed loader claim. |
| `qmd-query-expansion` | [Selected card](https://huggingface.co/tobil/qmd-query-expansion-1.7B-gguf/blob/7816de0b72572c6c860ca1eddf97ba9e7fb8cc65/README.md), same qmd loader, publisher search, 0.6B GGUF and LFM2.5 base-v2 cards | Default unchanged. Keep smaller/newer variants as comparison leads; no same-query-set comparison was run. |
| `potion-code-16m-v2` | [Potion card](https://huggingface.co/minishlab/potion-code-16M-v2/blob/e9d2a44ca6a05ac6685f3b23709ea57eb7352d5b/README.md), MinishLab code search, miru tokenlearn/dual cards | No newer MinishLab code model found in the bounded publisher result. Preserve both miru leads and common-harness/reindex gates. |
| `mineru-vlm-gguf` | [Current MinerU registry](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/model/registry.py), [official base card](https://huggingface.co/opendatalab/MinerU2.5-Pro-2605-1.2B/raw/main/README.md), selected Hub main, [current alpine card](https://huggingface.co/aeddix-labs/aeddix-alpine-ocr/blob/69d0b125ccbb1a7ec926116264ed2d968794ebfe/README.md) | Registry still specifies selected Q8_0 plus matching mmproj. Quantizer README is absent (404), not evidence of model retirement. Alpine candidate head updated; expired cooldown removed, GGUF/mmproj and same-scorer gate retained. MinerU-4 bundles are not presumed to be a new VLM. |
| `headroom-kompress-int8-wo` | [Current Kompress card](https://huggingface.co/chopratejas/kompress-v2-base/blob/e00cc5e60ff73b01674ef8fa6da6c5acf6d54181/README.md), publisher search, pinned/current ONNX tree metadata linked in row | Both tree views give the selected artifact the same LFS identity and last modifying commit `b1563631`; head `e00cc5e6` does not reset weight age. Runtime-extra qualification hold remains. |
| `kompress-modernbert-tokenizer` | [ModernBERT card](https://huggingface.co/answerdotai/ModernBERT-base/blob/8949b909ec900327062f0ebf497f51aef5e6f0c8/README.md), current Hub main and Kompress card | Main remains pinned revision and Kompress explicitly prescribes this pairing. Treat as paired tokenizer compatibility, not arbitrary encoder substitution. |
| `magika-standard-v3-3` | [Current model changelog](https://github.com/google/magika/blob/b1909890d4477d34381ce12b31882e9a197706d8/assets/models/CHANGELOG.md), primary PyPI release-line metadata | Changelog still leads with standard_v3_3; latest shipping package remains 1.0.3. Package-bound selection retained, with model/package dates distinct. |
| `background-haiku` | [Current models overview](https://platform.claude.com/docs/en/about-claude/models/overview), [Haiku 5.5 specification](https://platform.claude.com/docs/en/models/haiku-5-5/overview), official release notes | **New successor:** API ID `claude-haiku-5-5`, Active (latest), released October 7. This overturns the earlier no-newer-Haiku statement and triggers the existing availability gate. Record it for normal migration/quality-cost review and authorized application; do not silently replace the in-use 4.5 pin or call 4.5 the current leading Haiku. |

## Acceptance and remaining work

The actual current-date `model_currency_problems(document)` check reproduces nine
errors on the base inventory and zero on the refreshed inventory; no date
argument or validator/policy modification is involved. The full validator and
existing model-currency tests are required before commit. This is integrity and
source review, not a fresh native model-quality/usage qualification.

Any better compatible candidate with accepted common-harness evidence reopens
its role. Haiku 5.5's already-triggered migration review is outstanding. A separate
age-triggered scheduled-refresh follow-up is queued only after this incident PR
lands; existing proposer scheduling/reporting is a starting point, not evidence
that checks are automatically reviewed or refreshed today.
