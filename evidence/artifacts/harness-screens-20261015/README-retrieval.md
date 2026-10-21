# Retrieval A1 screens — 2026-10-15

This packet screens the frozen semantic-rag, document-retrieval and web-research inventory for the Anthropic, OpenAI and research families. It contains **426 family rows**: 42 frozen inventory entries and 100 additional component/layer entries named by the pinned DeerFlow and GPT Researcher sources, each projected into three family tables. Repeated backend names in different repositories are separate adapters, not assertions that their provider versions match.

The result is **2 bounded PASS rows and 424 INCOMPLETE rows; no FAIL rows**. QMD's invocation-only BM25/search/get profile passes the documentary screen for the Anthropic and OpenAI shell-host routes. The other rows retain specific missing source/platform/model/scope/provider evidence. PASS admits a TRIAL only. These results establish neither default selection nor runtime behavior. No catalog, angle record or saturation ledger was changed.

The Meta-family gap is intentional under plan addendum-02: this lane writes no Meta table. Separate fenced-session work owns those rows. Trading, judge and fenced review sessions are excluded from every role proposal here.

## Tables and inventory coverage

| Layer | Frozen entries per family | Named research component/layer entries per family | Rows per family | Tables |
| --- | ---: | ---: | ---: | --- |
| semantic-rag | 12 | 29 | 41 | [Anthropic](semantic-rag.anthropic.md), [OpenAI](semantic-rag.openai.md), [research](semantic-rag.research.md) |
| document-retrieval | 18 | 21 | 39 | [Anthropic](document-retrieval.anthropic.md), [OpenAI](document-retrieval.openai.md), [research](document-retrieval.research.md) |
| web-research | 12 | 50 | 62 | [Anthropic](web-research.anthropic.md), [OpenAI](web-research.openai.md), [research](web-research.research.md) |

Each Markdown table has a matching JSON array. JSON retains full per-requirement reasons, precise citations, family route, inverse finding, conflicts, role proposals, context estimates and cheapest next check. The Markdown tables list the complete status vector and link its sources. Family-independent pin, maintenance, licence and platform observations are in [facts-retrieval.json](facts-retrieval.json). [citation-audit-retrieval.json](citation-audit-retrieval.json) records 115 exact source files and confirms every cited line range exists at its stated commit.

Repeated JSON citations use local `$ref` pointers into `facts-retrieval.json#/sources/`.
Each referenced record retains the full repository/commit/file/line citation and URL.
This keeps repeated family rows from copying the same source records hundreds of times.

## Resolution and method

The resolution inputs are the frozen foundation and final-stack rows. At the base, all three layers are reopened, their angle records are missing, and no terminal FINAL state is established. The existing choices are retained as history: semantic-rag names SocratiCode/Qdrant/vLLM; document retrieval names scoped QMD, MarkItDown and Poppler; web research names Tavily CLI, agent-browser and OpenResearch. Their older receipts do not qualify newer source pins.

This is the bounded A1 delta in the [resolution protocol](../../../docs/decisions/2026-10-11-layer-resolution-protocol.md), using the [converged-candidates rule](../../../docs/decisions/2026-10-12-converged-candidates-only.md) and [angle-record/final checks](../../../docs/decisions/2026-10-12-angle-records-final-check.md). Missing required capability, including a proven entitlement/terms conflict, and abandonment are the only hard disqualifiers. An unverified requirement is UNKNOWN and prevents a PASS; it is not an inferred failure. Licence remains a compliance note.

The layer requirements are retained without replacing them with a component's marketing category:

- Semantic-rag: conceptual code queries, a scoped local index, compatible embeddings and recoverable state.
- Document retrieval: controlled ingestion, source-grounded content and original-body recovery.
- Web research: attributable primary sources and bounded native page commands without adding another standing research-agent stack.

An acquisition tool, embedding library, vector database or parser may have useful source-backed capability while its complete layer contract stays UNKNOWN. That boundary explains many INCOMPLETE rows. A source-only next check is named for each row; no test run is smuggled into an A1 conclusion.

Pre-existing mirrors listed in `~/code/upstream/MIRRORS.json` were preferred, with `GIT_NO_LAZY_FETCH=1` and `GIT_OPTIONAL_LOCKS=0`. Missing pinned blobs were read from public raw GitHub. No mirror was updated, candidate cloned, dependency installed, candidate code imported/executed, provider key read, model invoked or keyed candidate API called. The only Python execution was standard-library source/AST analysis and repository evidence validation/registration. External provider versions and entitlements remain unresolved where only adapter code is pinned.

Most pins use the frozen GitHub facts' latest release; entries without a release use its default-branch commit. GPT Researcher uses the existing v3.7.0 mirror at `0957c301ed06c2a5857b834358c7227c739041d4`. Release/default-branch drift is explicit, particularly HippoRAG and Firecrawl MCP. Vendor installation commands may float: they are documentary references, not executable authorization to install a newer package.

## Family routes and proposals

The family projection follows the supplied scope. Claude Code shell/MCP routes do not automatically qualify Claude Agent SDK/API tools or Pi/OpenCode Claude slots. Codex routes do not automatically qualify other GPT workers, and any model invocation through a GPT profile still needs the independently screened OmniRoute route. Internal DeerFlow/GPT Researcher modules are research-family components; choosing a Claude or GPT model inside one does not, by itself, install its modules into a different native client.

A row marked **not served** means the bounded pinned read did not establish a native route into that family. It is an explicit evidence gap, not a universal impossibility claim. Research-family MCP consumers are documented by [DeerFlow's MCP loader](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/mcp/tools.py#L1-L44) and [GPT Researcher's configuration contract](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/docs/docs/gpt-researcher/retrievers/mcp-configs.mdx#L41-L99); actual server packages, schemas and scope still need resolution.

Every role assignment and profile binding is **CANDIDATE / PROPOSAL**, routed to the layer protocol. No builder/reviewer/auditor/researcher/CC/co-op/worker default is set by this packet. The CC and co-op remain unassigned in these rows. Documentation supports capability; it does not itself endorse the proposed role matrix.

## Named research components

The rows enumerate DeerFlow community tool backends, its RAGFlow/LightRAG knowledge-search adapters, document ingestion and PyMuPDF4LLM/MarkItDown conversion, MCP client routing and the relevant disabled MCP examples. Their names come from pinned [config.example.yaml](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/config.example.yaml#L748-L1061), [file_conversion.py](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/utils/file_conversion.py#L1-L40) and [extensions_config.example.json](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/extensions_config.example.json#L23-L75).

GPT Researcher rows enumerate each source retriever/scraper, nine loader classes, sixteen named embedding providers, three documented vector-store examples, two context retrievers and MCP routing. These are the parent's own integration code, not independent qualifications of a remote service or model. Sources include [search engines](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/docs/docs/gpt-researcher/search-engines/search-engines.md#L30-L50), [loader dispatch](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/document/document.py#L69-L101), [embedding provider list](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/memory/embeddings.py#L6-L22), and [vector-store mode](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/docs/docs/gpt-researcher/context/vector-stores.md#L3-L9).

Only directly named external omissions material to these routes are recorded as leads: Hayhooks, vLLM-Metal, gptr-mcp and Docling's separately packaged MCP/API routes. Their naming citations are retained in facts-retrieval.json. No discovery sweep or trial of these leads was performed.

## Source findings that constrain the next stage

The four maintenance leads were independently checked against unauthenticated GitHub repository and default-branch commit endpoints on 2026-10-15. All four remain non-archived and have no default-branch commit since the supplied cutoff. Their last commits are:

| Repository | Last default-branch commit | Commit date |
| --- | --- | --- |
| kapillamba4/code-memory | `5a8db166ca11a90c093ba4a9a54d266cde756f54` | 2026-05-20 |
| andrewyng/context-hub | `67dcbeb2eb42c808549f08397920ad58be7c2206` | 2026-05-31 |
| Cinnamon/kotaemon | `9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9` | 2026-05-30 |
| datalab-to/chandra | `d4f7467435aa4137d9539f000ddf0b7ced3eb43f` | 2026-06-26 |

The exact API URLs, timestamps and commit links are in `maintenance_rechecks` in facts-retrieval.json. This establishes inactivity, not abandonment. The rows remain INCOMPLETE.

At vLLM v0.31.0, a blanket macOS unsupported finding would be wrong: [experimental Apple CPU support](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/docs/getting_started/installation/cpu.apple.inc.md#L4-L43) is documented, and [Metal is a separate plugin](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/docs/getting_started/installation/gpu.apple.inc.md#L4-L28). Neither proves the selected embedding model fits the 4090's 24 GB or the destination Apple's available RAM.

MinerU documents tier minima of 2/8/16 GB RAM and, for selected accelerated tiers, 8 GB+ accelerator memory ([README:454-460](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/README.md#L454-L460)). Those minima are not measured peak memory. The target Apple machine's installed memory was not supplied. A model's download size or parameter count is never substituted for its runtime envelope.

GPT Researcher's [loader projection](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/document/document.py#L51-L62) retains raw content but reduces source paths to basenames. The original-body requirement stays UNKNOWN for equal-named files from different directories. No upstream fix or execution is claimed.

Tavily's [set-default/unset-default](https://github.com/tavily-ai/tavily-cli/blob/3485f78f135b984ae8509c6c9cc493951fcf41dc/README.md#L521-L537) modifies native client settings and does not restore earlier custom values. SocratiCode's [plugin documentation](https://github.com/giancarloerra/SocratiCode/blob/3d3a4a4d427cb0f29de4f5dd1360da52896f62df/README.md#L129-L139) says its plugin already bundles MCP. These are concrete config/duplication conflicts, not reasons to modify any live profile during this screen.

## Context estimates and reuse

All costs are **ESTIMATE**, using `ceil(UTF-8 bytes / 4)`; no tokenizer was invoked. Counts refer to selected source literals at exact commits, with line ranges and payload/source hashes. They are not measured sessions.

- Invocation-only CLI/library and disabled-family profiles count an empty automatic injection set: 0 incremental tokens. This excludes the host's existing system/tool surface and task-time output. Optional skills, plugins, hooks and MCP are separate routes, not silently included in that zero.
- SocratiCode's 25 decoded top-level tool description strings total 1,259 estimated tokens. Firecrawl MCP's six literal top-level descriptions total 812. Tool names, input schemas, framework framing and conditional surfaces are additional, so complete MCP totals stay UNKNOWN.
- DeerFlow tool counts retain normalized Python docstring inputs and their source ranges. Framework docstring parsing and schema generation can change the final injection; the source-input subtotals are explicitly not serialized-schema totals.
- Parent runtime startup is reused from wave 1. DeerFlow's lead template is 3,115 estimated tokens; the Codex GPT-6 Astra template is 5,357. Neither is a total. Their original counted text, hashes and missing categories remain in the cited wave-1 rows; they were not re-derived here.
- A real isolated session-start receipt supersedes the corresponding source estimate later.

Family-independent Codex and DeerFlow metadata is reused by full-commit citation from [PR #1185 at c6a0004525aef204b92caf1a0e4b405478bb0fb1](https://github.com/seathatflowsinourveins/native-agent-stack/pull/1185): `candidate-facts-runtime.json`, `native-clients.openai.json` and `workers.research.json`. Table shape also follows [PR #1184 at 278ecc5de5c6c4cfbf58b13798b1ec6c697459f8](https://github.com/seathatflowsinourveins/native-agent-stack/pull/1184). Layer-specific source contracts are this lane's new reads. No earlier runtime acceptance is extended to a new adapter/provider/model.

## Inputs and hashes

Coordination inputs are retained locally; this packet records identifiers/hashes without reproducing private direction text.

| Input | SHA-256 |
| --- | --- |
| inventory-8053f14e7.json | `a95affd3270f14f737a1efa63cc4d184f5475b019c162a9e70034d4550139dc5` |
| gh-facts-20261015T2003Z.json | `06ba47908d8506a777478d9331da7a2487225c555addd9519510a550fd07140c` |
| Base direction | `464f655d433817e25349ec7cbe335d6d4b3793b0c08a39c9a0fb2697d823b6f9` |
| Direction addendum-03 | `bcf3b0ae2e721778ffb49d01edb6201fc12832a253e3d8e6d569521d86b2f044` |
| Direction addendum-04 | `7ddd99fb5d9a50367062f854deb3b071077dc5de123b2b2a5270a4e24e01913d` |
| Direction addendum-05 | `66cae758e0416f1951f065363b685aa687f3b09fc8af3968e4e7e3e5efbaa438` |
| screens-plan-20261015T2007Z.md | `7da92c9717f1c10df3b4a373bc76684fc07e1b3a6d5df61b607c968e9186cea0` |
| Plan addendum-01 | `742481e59cf025805926df0d91f2692e58fc615e25bc43eca6304d649d573c82` |
| Plan addendum-02 | `ef2d3259b403fb0883b79e01bd18386d7c6f216ddfbcad45a8fcb58b7b697283` |
| Correction ROW | `c75fd83da2664e94ff3064ff9d938ac36b9bde85a733803c3f0ebe4b6d98455c` |
| Correction addendum-01 | `10ca572d6ab73d3be54c4dafd5d487941efceb964113a07a8189069c12cde3d6` |
| Correction addendum-02 | `bf91dd21113dadb4401be1905a310621f79859e9fcfef8ac3b66e6351db648a0` |
| AGENTS.md at base | `badc1a93731095641e71ae1bf1d5ae5d5021e522c1da62926ddc65268f5c10a1` |
| Layer-resolution protocol | `010e39f2a915cc1ea1e163d56cb0f8cbfbd9cedb14a9fd7f78b2defd24648c58` |
| Converged-candidates rule | `9fa59ac054e7f82200efcc34d7d391d4847782a121afdbf02a42e2bfe2236656` |
| Angle-record final-check decision | `ccc714ce335d8fe2eb28e6a05f1ff11d5d594972560d7983c4a648e3780a7181` |
| Angle schema | `0b8c2ef46b20ec8c62b8acb9479780b1044ca79abc44c4a3099842a074c399ff` |
| foundation.json | `55751afc9a6e3d2dd814d5ba35d811ea9424464ccc417234b8cb6d08864e48b8` |
| final-stack.json | `e482c30346bbe97fc06a8909a43e86d8d69a93983a443747f92ad7d3d8b9d46d` |

## Validation and review boundary

The packet's structural/citation checks and repository validation are retained separately in `checks-retrieval.json`. Each evidence file is registered with `scripts/host_receipts.py`'s `register_file(root, path)` function; that function is not a CLI subcommand at the base. No new repository script is added.

The co-op's GPT read and the CC's Claude read are required before landing. They are not claimed completed by this source packet. The branch starts at `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`; registry re-derivation and rebase belong to landing.
