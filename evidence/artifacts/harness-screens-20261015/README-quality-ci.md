# Quality, GitHub automation and CI A1 screens — 2026-10-15

This record screens the frozen 11 quality-evaluation, 6 git-github-automation and 13 ci-supply-chain candidates separately for anthropic, openai and research: 90 rows across nine tables, with 29 unique repositories. It is **source_review** only. No candidate was installed, cloned and run, invoked, benchmarked or granted access. No model, keyed research API, workflow dispatch, PR review or PR comment was invoked. The repository validator is the separately required local check.

The screen is bounded by [AGENTS.md at the inventory base](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/AGENTS.md), the [layer-resolution protocol](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/docs/decisions/2026-10-11-layer-resolution-protocol.md), the [A1 admission rule](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/docs/decisions/2026-10-12-converged-candidates-only.md), and the [angle record decision](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/docs/decisions/2026-10-12-angle-records-final-check.md) and [schema](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/catalogs/landscape/angles/schema.json). No catalogs, angle records, saturation ledger, workflows or rulesets change.

## Resolution and scope

At base `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`, all three final-stack rows are reopened and none is FINAL. The [frozen foundation requirements and choices](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/catalogs/landscape/foundation.json) and [final-stack rows](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/catalogs/landscape/final-stack.json) were read, including winners, alternatives and open gaps. The verdict wave is [20260922](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/catalogs/sota-convergence/layer-verdicts-20260922.json). The completed 20260923, 20260926 and 20260929 sweep records were consumed through the [ledger](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/catalogs/saturation/ledger.json), their retained manifests, and the [20260926 returns](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/evidence/artifacts/landscape-sweep-20260926/returns.json) and [20260929 returns](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/evidence/artifacts/landscape-sweep-20260929/returns.json). The 20260923 return gap remains a retained gap; later omission does not adjudicate a survivor.

The latest covering sweep is 20260929. Carried unresolved survivors include MTEB and Inspect AI for quality; Claude Code Action and sem for GitHub automation; and Safe Chain, poutine, DataDog's firewall, both actionlint repositories and Socket sfw-free for CI. The deterministic inventory also retains catalog winners/alternatives and Harbor. The bounded delta is this A1 screen of those 30 inventory entries, not a new discovery sweep or an A6 comparison. Existing gaps in independent regression detection, matched evaluations, worktree recovery, PR lifecycle receipts, complete inventory and current hosted publication remain open.

The catalog's complementary candidate roles are preserved. Every layer clause is shown in `requirements_result`; a tool that contributes one documented part does not thereby supply other parts. GitHub worktree management, structural diffing and PR transport, for example, are separate contributions. A **PASS** is eligibility for that expressly scoped contribution only. UNKNOWN clauses outside that contribution remain visible as layer gaps; they are never treated as a complete-layer pass. Missing capabilities required for the selected contribution remain blockers or disqualifiers. The matching table and JSON state the selected scope, not a new default.

The only hard-disqualifier categories are missing required capability (including a demonstrated entitlement/terms conflict) and abandonment. A licence is a compliance note and never a verdict input. Missing documentation is UNKNOWN, with a bounded next source check. No 90-day activity cutoff is treated as an abandonment rule.

## Results

| Layer / family | PASS, trial eligible | INCOMPLETE | FAIL |
| --- | ---: | ---: | ---: |
| [quality-evaluation.anthropic](quality-evaluation.anthropic.md) | 1 | 9 | 1 |
| [quality-evaluation.openai](quality-evaluation.openai.md) | 1 | 9 | 1 |
| [quality-evaluation.research](quality-evaluation.research.md) | 0 | 10 | 1 |
| [git-github-automation.anthropic](git-github-automation.anthropic.md) | 3 | 3 | 0 |
| [git-github-automation.openai](git-github-automation.openai.md) | 3 | 3 | 0 |
| [git-github-automation.research](git-github-automation.research.md) | 0 | 6 | 0 |
| [ci-supply-chain.anthropic](ci-supply-chain.anthropic.md) | 6 | 7 | 0 |
| [ci-supply-chain.openai](ci-supply-chain.openai.md) | 6 | 7 | 0 |
| [ci-supply-chain.research](ci-supply-chain.research.md) | 6 | 7 | 0 |

All 90 rows retain a pin, requirements, installation path, inverse finding, conflicts, role proposal, startup estimate/boundary and verdict. The [shared facts](facts-quality-ci.json) contain primary read identities, SHA-256 digests, platform references, maintenance confirmations, reused facts and lifecycle constraints.

- **Retired source:** openai/skills is FAIL for the current-source role because its pinned README explicitly deprecates the repository and names a successor. This reuses wave-1's substantive finding; inactivity alone is not the reason.
- **Inactive sources:** openai/codex-plugin-cc, rhysd/actionlint and Socket sfw-free are not called abandoned. The bridge's confirmation is reused; anonymous primary GETs confirm actionlint's latest default-branch commit on 2026-04-19 and sfw-free's on 2026-03-31, with archive=false. Their maintenance or current runtime contracts remain unresolved.
- **Exact artifact boundary:** Promptfoo's frozen newest release tag names code-scan-action-0.2.2, while package.json at that commit says 0.124.1. It is not silently relabelled as an npm-release binding. Safe Chain's 1.5.25 source retains 1.5.24 installer/checksum examples; a version substitution must not reuse the old digest. Dependabot's core source tag is not asserted to be GitHub's deployed service version.
- **Research integration:** generic shell commands, Python libraries and Markdown compatibility are not asserted to be native DeerFlow/GPT Researcher adapters. Rows without a demonstrated native route explicitly say not served/INCOMPLETE. Repository CI checks can be model-independent adjuncts without registering tools inside a research runtime.

Every factual statement in these findings resolves to the candidate's cited pinned source or frozen/reused source record in the tables and shared facts.

## Method and measured boundary

The pinned Git object was read from a registered `~/code/upstream/MIRRORS.json` mirror when present, with `GIT_NO_LAZY_FETCH=1` and `GIT_OPTIONAL_LOCKS=0`. Otherwise public raw GitHub content at the full commit, anonymous GitHub metadata/release GETs, or dated official documentation was read. No candidate source was imported or executed. The context-mode skill/tools indexed and filtered source material; standard-library read-only parsing selected relevant lines. Source hashes cover the complete fetched file, while selected line numbers identify the excerpts used. Failed path lookups remain in shared facts and are not positive evidence.

Frozen release tags resolve to the supplied full commits; a commit-only source stays commit-only. GitHub Action installation rows use full 40-character SHAs. Vendor service docs have the read date, and a managed deployment is not inferred from a repository tag. Installation syntax with an explicit version is a candidate substitution of the documented package route, not proof of registry-to-commit equality. Unresolved binding is named before any trial.

Linux binary support plus Microsoft's [WSL2 Linux-kernel/system-call contract](https://learn.microsoft.com/en-us/windows/wsl/about), read 2026-10-15, is a conditional source inference, not a WSL2 test receipt. Runner support for ordinary CLIs is likewise conditional on the documented OS/runtime and GitHub's [run-step contract](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsrun) and [self-hosted-runner contract](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners), read 2026-10-15. CI-only local fields are explicitly not applicable. Environment-specific or architecture-dependent components stay UNKNOWN where their source contract was not established.

Inverse findings are bounded to consumed documentation. “None documented” does not mean removal is impossible. A suggested package/binary/environment removal remains PROPOSAL when the candidate does not document it. A workflow disable is not an app uninstall, credential revocation, data deletion or attestation deletion.

All **SUITED ROLES** and profile selections are **CANDIDATE / PROPOSAL**, routed to layer resolution. A cited capability motivates the proposal but does not settle it. These rows do not grant workers tools, change API entitlements, register global hooks, or inject anything into fenced trading, judge or review sessions.

Startup numbers are **ESTIMATE**, never measured: sum `ceil(UTF-8 bytes / 4)` over exact selected injected components. For a standalone CLI/CI-only profile the selected automatic model-injection set is empty: 0 bytes, 0 tokens, with the installation/CLI source cited. This is a profile estimate, not a claim that a downstream agent, evaluation, browser command or model session consumes zero tokens. On-demand output and full bodies are excluded and explicitly bounded. The TypeSafe 168-token and historical OpenAI-skills 184-token metadata figures are reused from exact wave-1 frontmatter ranges. The Codex bridge has a 298-token metadata subtotal with file/range/content hashes; its total is UNKNOWN. Claude Code Action's assembled prompt and built-in MCP schemas are also UNKNOWN. A real native session-start measurement supersedes these static counts.

No performance, model-quality ranking, A6 comparison, upstream test result, host compatibility, installed state, workflow result or production entitlement is claimed.

## Shared facts reused

The coordination copies were checked byte-for-byte against the supplied wave-1 Git commits; they matched. Shared pin, maintenance, platform/licence facts and context counts are cited, not independently re-derived:

| Source | SHA-256 | Reused rows |
| --- | --- | --- |
| [facts-frameworks.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/278ecc5de5c6c4cfbf58b13798b1ec6c697459f8/evidence/artifacts/harness-screens-20261015/facts-frameworks.json) | `46fb327516a2dee72fd0ed3d5abde3ba0c1d63400b05a3c5c65a1e4981346cec` | openai/skills, typesafe-ai/skills, MCP Inspector |
| [candidate-facts-runtime.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c6a0004525aef204b92caf1a0e4b405478bb0fb1/evidence/artifacts/harness-screens-20261015/candidate-facts-runtime.json) | `789e9f7979de408ec7efb29758232fe79c7d88d4cf185f5b38770e99be61f042` | Worktrunk, codex-plugin-cc |
| [platform-assets-runtime.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c6a0004525aef204b92caf1a0e4b405478bb0fb1/evidence/artifacts/harness-screens-20261015/platform-assets-runtime.json) | `e079b1aff24d67d29ed837b1a124239ca117faa594a0d3ec3af0027a90123a4f` | Worktrunk platform assets |
| [workers.anthropic.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/c6a0004525aef204b92caf1a0e4b405478bb0fb1/evidence/artifacts/harness-screens-20261015/workers.anthropic.json) | `44eecbed9c11e960fb2d2414b53b99639aed1f2761b7a9f83e7a5efb98b865dd` | codex-plugin-cc metadata components and host inverse |

The wave-1 PR heads are #1184 at `278ecc5de5c6c4cfbf58b13798b1ec6c697459f8` and #1185 at `c6a0004525aef204b92caf1a0e4b405478bb0fb1`. New source reads fill this lane's capability/install/conflict requirements; they do not repeat family-independent analysis three times.

Primary sources also named openai/plugins, Playwright CLI/MCP, inspect-skills, Gitleaks Action and Socket Action. They are recorded as **source-named, not in this inventory, not screened** in shared facts, with the originating pinned citation. They add no rows or admission. No search/discovery sweep was run.

## GitHub lifecycle and review boundary

GitHub's [ruleset documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets), read 2026-10-15, supports required reviews, named status contexts and an expected GitHub App source. It does not identify a reviewer's model family. GitHub's [merge-queue documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue), read 2026-10-15, requires `merge_group` for Actions checks required on a merge queue.

Mapping local fenced Claude/GPT verdicts into attributable checks is therefore an unresolved **PROPOSAL**, not a design installed by this screen. The source supports neither equating two review counts with two model families nor treating a shared workflow token as family provenance. Required-check names and existing ruleset interactions are target-repository inputs, left unchanged.

The inventory carries Claude Code Action and the Codex-for-Claude bridge. Both remain INCOMPLETE for the requested full local fenced-review integration: the action restores only a fixed configuration list and merges MCP configuration; the bridge documents read-only review but does not thereby prove an independent clean fence or compatibility with current clients. Muse is absent from these 30 inventory entries and belongs to the held Meta lane; no Meta table or additional reviewer candidate is manufactured. This PR requests the co-op's GPT read and CC's Claude read; a Muse trial read is outside this lane and only routed if separately requested.

## Inputs

Paths below are relative to the private coordination root. Only identities/hashes are retained here; no private direction text is reproduced.

| Input | SHA-256 |
| --- | --- |
| `ns2604-coop/screens-20261015/inventory-8053f14e7.json` | `a95affd3270f14f737a1efa63cc4d184f5475b019c162a9e70034d4550139dc5` |
| `ns2604-coop/screens-20261015/gh-facts-20261015T2003Z.json` | `06ba47908d8506a777478d9331da7a2487225c555addd9519510a550fd07140c` |
| `ns2604-coop/notes/screens-plan-20261015T2007Z.md` | `7da92c9717f1c10df3b4a373bc76684fc07e1b3a6d5df61b607c968e9186cea0` |
| `ns2604-coop/notes/screens-plan-20261015T2007Z.addendum-01.md` | `742481e59cf025805926df0d91f2692e58fc615e25bc43eca6304d649d573c82` |
| `ns2604-coop/notes/screens-plan-20261015T2007Z.addendum-02.md` | `ef2d3259b403fb0883b79e01bd18386d7c6f216ddfbcad45a8fcb58b7b697283` |
| `command-center/ROW-cc-20261015T2048Z-correction-practice-by-convergence.md` | `c75fd83da2664e94ff3064ff9d938ac36b9bde85a733803c3f0ebe4b6d98455c` |
| `command-center/ROW-cc-20261015T2048Z-correction-practice-by-convergence.addendum-01.md` | `10ca572d6ab73d3be54c4dafd5d487941efceb964113a07a8189069c12cde3d6` |
| `command-center/ROW-cc-20261015T2048Z-correction-practice-by-convergence.addendum-02.md` | `bf91dd21113dadb4401be1905a310621f79859e9fcfef8ac3b66e6351db648a0` |
| `command-center/research-cc-role-20261008/direction-cc-20261015T1912Z-new-wsl-harness-first.md` | `464f655d433817e25349ec7cbe335d6d4b3793b0c08a39c9a0fb2697d823b6f9` |
| `command-center/research-cc-role-20261008/direction-cc-20261015T1912Z-new-wsl-harness-first.addendum-03.md` | `bcf3b0ae2e721778ffb49d01edb6201fc12832a253e3d8e6d569521d86b2f044` |
| `command-center/research-cc-role-20261008/direction-cc-20261015T1912Z-new-wsl-harness-first.addendum-04.md` | `7ddd99fb5d9a50367062f854deb3b071077dc5de123b2b2a5270a4e24e01913d` |
| `command-center/research-cc-role-20261008/direction-cc-20261015T1912Z-new-wsl-harness-first.addendum-05.md` | `66cae758e0416f1951f065363b685aa687f3b09fc8af3968e4e7e3e5efbaa438` |

## Validation and handoff

The required pre-commit command is `python3 scripts/validate.py`; its completed result is retained in the PR description. A focused integrity audit checks exact inventory coverage, nine JSON/Markdown pairs, all full source/action pins, required fields, source-versus-estimate labels, no Meta output, and byte-identical readiness copies. These checks validate this evidence artifact; they do not execute or qualify a candidate.

Each layer's six table files has been copied under the same names to the readiness table directory and sent as R LAYER-DONE with SHA-256. The shared facts file is copied alongside them so JSON references resolve. Each new repository evidence file is registered through `scripts.host_receipts.register_file`; that callable updates only the evidence registry. No new `scripts/*.py` is added.
