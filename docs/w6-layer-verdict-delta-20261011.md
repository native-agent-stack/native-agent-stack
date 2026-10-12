# W6 terminal resolution for six foundation layers

**All six W6 layers are SCHEDULED.** The terminal records follow the co-op's #1007 LANDED relay and the CC's adjudication of #1021 at `4ddd4822`. No comparison, installation, upstream E2E, invoke acceptance or FINAL is claimed. Each layer has one re-frozen comparison with its id, hash, readiness inputs and fixed rule.

The [delta record](../evidence/artifacts/w6-layer-verdict-20261011/resolution-delta.json) consumes source base `77185991`, the 09-22 verdict wave, the covering 09-23/26/29 sweep adjudications, the retained 10-03 scoped completion, later deployment history, and the exact `c2dee173` final-stack snapshot. The cumulative census remains **33**, including missing-vote-only proposals; pi is separate changed evidence. Later omission never clears a survivor. The historical view has a narrower missing-vote list; this protocol-correct census is retained independently of the derived view or a later generator correction.

| Layer | Cumulative ledger inputs | Latest covering sweep | W6 disposition |
| --- | ---: | --- | --- |
| native-clients | 0 | landscape-sweep-20260929 | SCHEDULED; all own-layer inputs included in the frozen comparator. |
| code-navigation | 3 | landscape-sweep-20260929 | SCHEDULED; all own-layer inputs included in the frozen comparator. |
| document-retrieval | 13 | landscape-sweep-20260929 | SCHEDULED; all own-layer inputs included in the frozen comparator. |
| semantic-rag | 5 | landscape-sweep-20260929 | SCHEDULED; all own-layer inputs included in the frozen comparator. |
| durable-memory | 8 | landscape-sweep-20260929 | SCHEDULED; all own-layer inputs included in the frozen comparator. |
| web-research | 4 | landscape-sweep-20260929 | SCHEDULED; all own-layer inputs included in the frozen comparator. |

The 10-03 re-vote completes **frozen 09-26 proposals**, has no ledger append at the consumed base and does not replace the distinct 09-29 proposal scopes. Its flags can refute a proposed rejection rationale, not a repository's merit. Pi's two scoped adjudications remain separate. Repository identity is case-insensitive; semantic-rag's duplicate SocratiCode source arm is removed.

The [Mac-only 10-02 memory verdict](../blueprints/memory-stack/native-qualification/VERDICT.md) is background deployment history. It is **not** a current-host merit disposition for LangMem, agentmemory, MemPalace or Hindsight. All four, plus every other cumulative memory input and the ai-memory source candidate, are included in durable-memory's nine-arm comparison. The new W6 unit does not relaunch the closed Mac unit. Measured merit on the newest supported model panel governs; no incumbent or installed default is protected. The retained model universe is hash-bound; exact newest supported model revisions, licenses, prompts and common answer-context settings must be sealed before any capture or scoring. Model choice cannot follow comparison outcomes.

**B1 citation correction:** [primary-sources.json](../evidence/artifacts/w6-layer-verdict-20261011/primary-sources.json) now points to the correct role/install/test lines or explicitly withdraws the claim. [The correction witnesses](../evidence/artifacts/w6-layer-verdict-20261011/citation-corrections.json) bind each old/new citation to the lock SHA, actual new source line and source-file hash. The 19 adjudicated lines are corrected/withdrawn, with two additional body-record installation alignments. A null test/role reference is a named qualification gap, never an approximate claim or a statement that upstream has no tests. Every new line was read with `GIT_NO_LAZY_FETCH=1 GIT_OPTIONAL_LOCKS=0 git show <lock SHA>:<path>`; no new candidate discovery ran.

**B2 fixed roles:** the original 42 entries become **46** explicit role-bearing entries: remove one duplicate and restore five memory roles, including the native-file/session dependency. Each arm has `role_ids`, a boolean `dependency`, and a selection scope. Each role maps to specific frozen case indices and mandatory checks in `role_checks`. Vector stores, model servers, embedding/reranking primitives and plugin/file controls do not compete as whole end-to-end retrieval or shared-memory systems. No role/applicability assignment is permitted at run time.

| Layer | Repository | Role ids | Dependency only |
| --- | --- | --- | --- |
| native-clients | anthropics/claude-code | `coding_research_client`, `session_recovery_client` | no |
| native-clients | openai/codex | `coding_research_client`, `session_recovery_client` | no |
| native-clients | earendil-works/pi | `coding_research_client`, `session_recovery_client` | no |
| code-navigation | oraios/serena | `symbol_navigation`, `reference_graph_navigation` | no |
| code-navigation | anthropics/claude-plugins-official | `native_lsp_distribution` | yes |
| code-navigation | abhigyanpatwari/GitNexus | `symbol_navigation`, `reference_graph_navigation`, `navigation_index_maintenance` | no |
| code-navigation | mibayy/token-savior | `symbol_navigation`, `navigation_index_maintenance`, `reference_graph_navigation` | no |
| document-retrieval | tobi/qmd | `document_retrieval` | no |
| document-retrieval | microsoft/markitdown | `document_conversion`, `document_ocr_layout` | no |
| document-retrieval | tsdgeos/poppler_mirror | `document_conversion`, `layout_referenced_conversion` | no |
| document-retrieval | datalab-to/marker | `document_conversion`, `document_ocr_layout`, `layout_referenced_conversion` | no |
| document-retrieval | opendatalab/MinerU | `document_conversion`, `document_ocr_layout`, `document_retrieval`, `layout_referenced_conversion` | no |
| document-retrieval | docling-project/docling | `document_conversion`, `document_ocr_layout`, `layout_referenced_conversion` | no |
| document-retrieval | Cinnamon/kotaemon | `document_retrieval` | no |
| document-retrieval | huggingface/sentence-transformers | `document_embedding_reranking` | yes |
| document-retrieval | arabold/docs-mcp-server | `versioned_documentation_retrieval`, `document_retrieval` | no |
| document-retrieval | VectifyAI/PageIndex | `document_retrieval` | no |
| document-retrieval | xberg-io/xberg | `document_conversion`, `document_ocr_layout`, `layout_referenced_conversion`, `document_embedding_reranking` | no |
| document-retrieval | pymupdf/pymupdf4llm | `document_conversion`, `document_ocr_layout`, `layout_referenced_conversion` | no |
| document-retrieval | datalab-to/surya | `document_ocr_layout`, `layout_referenced_conversion` | no |
| document-retrieval | alibaba/Logics-Parsing | `document_ocr_layout`, `document_conversion`, `layout_referenced_conversion` | no |
| document-retrieval | baidu/Unlimited-OCR | `document_ocr_layout`, `layout_referenced_conversion`, `document_conversion` | no |
| document-retrieval | datalab-to/chandra | `document_conversion`, `document_ocr_layout`, `layout_referenced_conversion` | no |
| semantic-rag | giancarloerra/SocratiCode | `project_semantic_index`, `semantic_code_retrieval` | no |
| semantic-rag | qdrant/qdrant | `vector_storage`, `multivector_semantic_index` | yes |
| semantic-rag | vllm-project/vllm | `model_serving` | yes |
| semantic-rag | ollama/ollama | `model_serving` | yes |
| semantic-rag | OSU-NLP-Group/HippoRAG | `project_semantic_index`, `semantic_code_retrieval` | no |
| semantic-rag | lightonai/next-plaid | `multivector_semantic_index`, `semantic_code_retrieval`, `project_semantic_index` | no |
| semantic-rag | minishlab/semble | `project_semantic_index`, `semantic_code_retrieval` | no |
| durable-memory | akitaonrails/ai-memory | `shared_memory_backend`, `native_memory_capture` | no |
| durable-memory | anthropics/claude-code | `native_file_session_memory` | yes |
| durable-memory | langchain-ai/langmem | `memory_management_primitives` | yes |
| durable-memory | rohitg00/agentmemory | `shared_memory_backend`, `native_memory_capture` | no |
| durable-memory | MemPalace/MemPalace | `shared_memory_backend`, `native_memory_capture` | no |
| durable-memory | vshulcz/deja-vu | `shared_memory_backend`, `native_memory_capture` | no |
| durable-memory | vbcherepanov/total-agent-memory | `shared_memory_backend`, `native_memory_capture` | no |
| durable-memory | vectorize-io/hindsight | `shared_memory_backend`, `native_memory_capture` | no |
| durable-memory | tigerless-labs/agent-memory | `shared_memory_backend`, `native_memory_capture` | no |
| web-research | tavily-ai/tavily-cli | `web_primary_source_retrieval` | no |
| web-research | vercel-labs/agent-browser | `interactive_browser_retrieval`, `web_primary_source_retrieval` | no |
| web-research | alphaXiv/OpenResearch | `paper_primary_source_retrieval` | no |
| web-research | exa-labs/exa-mcp-server | `web_primary_source_retrieval` | no |
| web-research | adbar/trafilatura | `web_primary_source_retrieval` | no |
| web-research | openai/codex | `web_primary_source_retrieval` | no |
| web-research | webrecorder/browsertrix-crawler | `web_evidence_capture` | no |

**Prior B2-r correction:** Poppler joined content conversion; HippoRAG joined project indexing and semantic retrieval; deja-vu joined memory/capture; trafilatura joined primary-source extraction. MemPalace's capture witness is `README.md:311-316` at `1f0803a31958b30320418356b2db88c4ed9c27f9`, and next-plaid's semantic-search witness is `README.md:22` at `c6c091d7ee14c81206bb28af90d8ff506fd0235e`. The terminal adjudication below preserves those assignments while separating incompatible native output contracts. Recorded source lines/file hashes qualify applicability only, not successful runtime execution.

The terminal adjudication applies advertised roles throughout: agent-browser read joins source retrieval; MinerU search/read and docs-mcp-server join retrieval against qmd. Exact README witnesses are retained. Flat native conversion has no page/coordinate gate; MarkItDown uses native Markdown. Source references have a distinct layout_referenced_conversion case, never invented from flat output. Per-survivor comparison refs/reasons and retained reopen/proposal inputs gate all six comparisons. Licence provenance is metadata, never exclusion. All six files re-freeze under the 599d9bbb adjudication; source pins, arm counts and original fixture bytes remain bound.

A **page reference** is an explicit native page ordinal normalized to the one-based authored page, with an exact quoted source fragment. A **layout reference** is a native stable block/line/table locator that reads back that fragment, or an explicit rectangle/polygon normalized to PDF points. Native boxes must enclose the authored text/table anchor within the fixed two-point edge tolerance. Page-only, stable-block and geometric dimensions remain separate: a page anchor cannot claim geometric quality. The native reference form is fixed before execution; flat Markdown is never assigned synthetic page numbers or coordinates.

**A1 review metadata:** `next_review=2026-10-22` comes from each layer's verdict in the landed final-stack view and closes the earlier condition-1 metadata gap. It is review metadata, not a wait date. The supported `run_pin` reader finds all 13 historical entries; `is_definitive` returns false/reopened for each at the recorded reader date. These readers do not supply runtime E2E or invoke evidence.

The seven known version deltas are explicit in each terminal record's `run_pin_reconciliation`: Codex 0.162.1 versus operational 0.160.0; MarkItDown 0.1.7 versus 0.1.8; SocratiCode 1.14.0 versus 1.15.0; ai-memory 2.6.0 versus 2.4.1; vLLM 0.31.0 versus 0.30.0; agent-browser 0.38.1 versus 0.38.2; OpenResearch 0.2.7 versus 0.2.15. Newer locked sources test changed mechanisms; older locked sources are explicitly version-qualified controls consumed by catalog evidence. The immutable source pin governs the experiment, with no receipt transfer to a different operational pin. A selected deployment must go through supported adoption into a matching `runs[]` pin, then its own upstream E2E and invoke/role evidence. HEAD/version-only equivalence for other sources is not assumed.

| Single comparison | Current re-frozen preregistration SHA256 |
| --- | --- |
| [w6-foundation-native-clients-20261011](../evidence/artifacts/w6-layer-verdict-20261011/comparisons/native-clients.json) | `e70391bd323583f77a78e3327d29491a677e2fe7e5176c31d82e633fef124947` |
| [w6-foundation-code-navigation-20261011](../evidence/artifacts/w6-layer-verdict-20261011/comparisons/code-navigation.json) | `e0ed8b0e911db34f91b57bea5b3d31a89c2a2f32287a177002654b38a59df40f` |
| [w6-foundation-document-retrieval-20261011](../evidence/artifacts/w6-layer-verdict-20261011/comparisons/document-retrieval.json) | `a06410fcea30b7638c56ac1df280c0a96f9912ec563459482351d167b61e4f11` |
| [w6-foundation-semantic-rag-20261011](../evidence/artifacts/w6-layer-verdict-20261011/comparisons/semantic-rag.json) | `50ca296465f89d6a0aa643c67a063a3ded5eb38394462c5ec495972fa884b02c` |
| [w6-foundation-durable-memory-20261011](../evidence/artifacts/w6-layer-verdict-20261011/comparisons/durable-memory.json) | `6450b9467c9345a67dc4fb571429b1c055fa924f8b422c8b7ab48aebeaba5cee` |
| [w6-foundation-web-research-20261011](../evidence/artifacts/w6-layer-verdict-20261011/comparisons/web-research.json) | `db1df25eed815d73ce09e518f0a01895b95732821e01bf22e95e8bad01a41819` |

These hashes supersede earlier registrations before any run under the terminal adjudication. Readiness names exact source-pin runtime/E2E receipts, committed model/instrumentation seals, scoped native use and an isolated queued runner. #1007 LANDED is satisfied; the remaining runtime inputs are not yet retained. A comparison starts as soon as those named inputs exist, with no calendar trigger. These small sealed fixtures qualify bounded contracts, not representative quality or universal SOTA.

The existing unittest record contracts in [test_w6_layer_verdict_records.py](../tests/test_w6_layer_verdict_records.py) reproduced the false citations, duplicate, unbound roles/checks, omitted memory candidates and review metadata before the correction. The added B2-r regressions also fail against the retained d7d9df1f role assignments and check identical case coverage plus the two README-advertised roles. They verify record consistency only, never runtime behavior. Publication, final-stack and leak checks remain separately required before the single leased push.

The derived view's post-#1007 skills-lifecycle source fingerprint is refreshed through the unchanged generator's own supported output, with its publication guard accepted and parsed run/layer arrays unchanged. #1025 owns that main correction; the branch is rebased onto descendant main. Terminal provenance remains bound to the original `c2dee173` snapshot. No generator mechanism, selected runtime, paper unit/configuration, sealed bundle or Monday recorder changes.

Monday heavy E2E uses `systemd-run --user --scope -p CPUWeight=idle`; a full suite needs SUITE-REQUEST and SUITE-GO. Cued landings and the paper path retain priority. Astra's first read and the CC's Claude delta read apply to the final head. All claims made by this closeout remain source_review unless the separate integrity checks are labeled local_integration.
