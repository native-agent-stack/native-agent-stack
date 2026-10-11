# Landscape judgment workers preserve scratch ownership

Decision date: 2026-10-10. Correction #138. Base: `9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`.

A fit refuter issued a wildcard delete against its session's shared scratchpad. The role inherited shell and arbitrary-code tools, so a research worker could remove files another worker had created. The role now uses Claude Code's supported explicit `tools` list: local source readers, WebSearch, ToolSearch when exposed, and the three named context-mode fetch/index/search tools. The coordinator and command-only GPT wrappers own scratch preparation and cleanup.

The native Skill tool also leaves this role. Reading the named installed SKILL.md files preserves their research instructions without running their dynamic shell context. Future sweep templates describe that route; Codex skill invocation and the frozen scripts of existing runs are unchanged. `skills_used` means instructions actually applied, not merely a file mentioned.

## Primary sources

- Anthropic Claude Code **2.1.296**, public release repository [anthropics/claude-code@2301018b](https://github.com/anthropics/claude-code/tree/2301018b1f61073c501a8e7a4813ef48c239163b), [CHANGELOG.md](https://github.com/anthropics/claude-code/blob/2301018b1f61073c501a8e7a4813ef48c239163b/CHANGELOG.md). The installed vendor executable reports 2.1.296 and has SHA256 `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de`.
- Official [subagent available-tools documentation](https://code.claude.com/docs/en/sub-agents#available-tools), observed 2026-10-10. The installed binary's frontmatter schema near byte 216026220 says `tools` replaces the default tool set. Its role resolver `HC` near byte 223508340 selects the named native/MCP tools. These are installed-client source observations, not a claim that the public repository ships that implementation.
- Official [subagent-frontmatter hooks](https://code.claude.com/docs/en/sub-agents#hooks-in-subagent-frontmatter) and [PreToolUse decisions](https://code.claude.com/docs/en/hooks#pretooluse-decision-control). A hook matching `Bash(rm *)` controls that shell command; it does not control a different MCP execution tool.
- Official [skills dynamic context](https://code.claude.com/docs/en/skills#inject-dynamic-context). In installed 2.1.296, a Skill containing dynamic shell context deleted a foreign scratch file even when Bash was absent from the role's tool list; the native regression below reproduces it.
- [Context-mode v1.0.169@589d8214](https://github.com/mksglu/context-mode/tree/589d8214d56740a28b5f7bf63167743d586b0b40), [src/server.ts](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts): `ctx_fetch_and_index`, `ctx_index`, `ctx_search` gather/index/retrieve source data; `ctx_execute`, `ctx_execute_file` and `ctx_batch_execute` run caller-supplied code/commands and are outside the list. The three admitted MCP names match the installed sweep's actual native tool-use records.
- Official [CLI reference](https://code.claude.com/docs/en/cli-reference): the regression uses native `--agents`/`--agent` and, for the direct-tool cases, `--bare`. Fresh `CLAUDE_CONFIG_DIR`, explicit MCP fixtures and an allowlist of environment keys keep real credentials and existing host state outside the fixture. The Skill cases use isolated normal mode because bare mode omits Skill.

## Measured regression

Evidence class: **local_integration**. The real installed Claude client admits or rejects each call. A loopback Anthropic streaming-response fixture requests the exact tool action, including actions absent from the advertised tool list; a tiny MCP fixture reports whether dispatch reached its handler. The model/provider responses are synthetic. No paid model, real authentication, live Workflow, or production scratch directory participates.

Before the fix, this command ran against the inherited role and failed on the user's exact symptom:

```text
python3 -m unittest tests.test_landscape_sweep_worker_boundary.NativeToolAdmissionTests.test_wildcard_delete_preserves_foreign_scratch_files -v
1 test; exit 1; 1.131 s
AssertionError: worker deleted a foreign scratch file
```

The native client executed `rm -f <fixture-scratch>/*.py .../*.md .../*.toml .../*.txt`; all four operator-created foreign files disappeared. Its own `.keep` file remained.

The first tool-list candidate excluded Bash but retained Skill. An additional native regression failed in 1.218 s: an installed fixture Skill with dynamic shell context deleted `foreign.py`. Excluding native Skill closed this observed bypass; source-only skill reading leaves the dynamic text inert.

The final native suite checks wildcard and interpreter deletion, all three context execution entry points, an unlisted MCP mutator, an attempted deferred-tool load, Skill permission grants, and Skill dynamic context. Positive controls require actual dispatch for native Read and context fetch/index/search, and reading SKILL.md without executing its dynamic text. Every negative case checks file hashes and native error/dispatch results. The deferred check does not claim ToolSearch is active when the native client eagerly exposes the three exact MCP definitions instead.

## Review correction (2026-10-11)

The first GPT read of #987 at `4a1e5b7d079c7a2d327f022dc0f702963a190bb5` found that
`adoption/hooks/claude/token-lanes-subagent-start.py` still sent this restricted role the default carrier.
That carrier requested ungranted memory, code-execution and shell tools. The unchanged full token-lanes
module reproduced two failures: the ungranted-tool assertion and the restricted-role count (`11 != 10`).

The role body already supplies primary-page fetch/index/search, bounded local source reads and installed
SKILL.md reading. The hook now classifies the exact `landscape-sweep-worker` name as silent, supplying no
additional carrier. This follows Claude Code 2.1.296's supported [SubagentStart context
output](https://code.claude.com/docs/en/hooks#subagentstart) and preserves the native `tools` allowlist;
hook guidance does not grant tools. The official hook and [available-tools
documentation](https://code.claude.com/docs/en/sub-agents#available-tools) were rechecked on 2026-10-11,
and the installed client still reports 2.1.296. A separate carrier would duplicate guidance already in
the role body.

The regression now requires zero injection for this worker, removes it from the default-context cases,
keeps exact-name controls, and checks all eleven shipped restricted roles. With those expectations
changed before the hook fix, the full 23-test module failed three assertions, including the worker's
zero-injection case. These hook subprocess checks are **local_integration**; they use no paid model call.
The README also corrects the `stack-researcher` comparison: its Bash and code-execution grants distinguish
it from this worker. Both roles can read installed skill source without the native Skill tool.

After the hook fix, `python3 -m unittest tests.test_token_lanes_subagent_start
tests.test_landscape_sweep_worker_boundary` passed all **34 tests** (23 hook tests and 11 native boundary
tests) in 19.932 seconds. The native boundary suite still uses the installed 2.1.296 executable with
SHA256 `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de` and synthetic loopback responses;
no authenticated provider call participates.

## Alternatives and practical limits

- Cleanup-only prose leaves the unsafe tool available; the original native regression demonstrates the consequence.
- A Bash-only delete hook leaves interpreter and MCP execution routes. Blocking only the three known context execution names would also leave other inherited mutators, so the boundary uses an explicit allowlist rather than a growing command blacklist.
- Keeping native Skill with a read-only tool list failed the measured dynamic-context regression.
- Workflow `bashCommandClamp` is a supported call option in 2.1.296, not a supported role-frontmatter field. Its native activation removes MCP tools, losing the required primary-page route. The role allowlist retains the selected read surfaces.

Public GitHub REST GET/page retrieval replaces authenticated `gh api` in this role; anonymous limits or inaccessible fields must remain unknown/pending, not invented evidence. Research quality and throughput under this narrower surface have not been benchmarked. The native fixture proves admission and preservation, not model research quality.

This is the judgment worker's tool boundary, not an OS filesystem sandbox. Trusted client/MCP implementations may maintain their own caches. The coordinator, native job runners and command-only wrappers retain their existing capabilities and remain responsible for their owned writes. No host installation, active role mutation, catalog change, frozen-run rewrite or rebase is part of this PR.

Reconsider this decision if an upstream supported role-scoped filesystem or read-only execution boundary passes the same foreign-file regressions, including MCP execution and dynamic Skill context, while retaining authenticated research or computation. Adopt that supported mechanism after a measured comparison.
