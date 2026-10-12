# MCP templates and live registrations: reconciliation, 2026-10-12

Status: decided by the command center's ruling of 2026-10-12 after the measurement below. This record carries the evidence for it; the stored client configuration of the host is changed by the command center on a reviewed diff, never by this change.

## Context

On 2026-10-12 `claude mcp list` (Claude Code 2.1.296) on the first host of the new distribution showed 14 servers, all connected: the 13 user-scope servers of `~/.claude.json` and `plugin:context-mode:context-mode`. The committed templates render nine servers for Claude Code (`adoption/mcp/claude-user.json` plus the distribution's additions, merged only by `tools/adoption/new_wsl_client_config.py`) and ten for Codex. The two sets differed in names (four servers only the host registered, one server under another name) and in values (a port, a launch command, a version, an environment). A generator that reads the render, the runtime profiles of pi and OpenCode, inherited the gap: its first native `mcp list` found `ai-memory` on a port the host does not run and the SocratiCode entry point absent.

`tools/adoption/mcp_template_drift.py` is the new read-only report of that gap. It renders the templates in process with the same functions as `new_wsl_client_config.py --render`, reads the user scope of Claude Code and the `[mcp_servers.*]` tables of Codex, and prints one row per client and server: SAME, DIFFERS (with the fields), TEMPLATE-ONLY or LIVE-ONLY. It prints no value of a registration (it shows environment and header names, a URL as `scheme://host` unless the URL holds an `@`, a command as its file name, the transport from a fixed set (stdio, http, sse) and the number of arguments, never which; the host label and the command's file name are printed as names, not as values; the values are compared in memory, and a field of an unexpected shape ends the run with exit 2 and a message that names the server only), writes nothing and starts nothing. `adoption/new-wsl/mcp-drift-acknowledged.json` lists the differences this record accepts, each with a reason; an entry that no longer matches a row fails the run, so an exception cannot outlive its cause. On the first host, `python3 tools/adoption/mcp_template_drift.py --with-authorization-settings --acknowledged adoption/new-wsl/mcp-drift-acknowledged.json` exits 0.

## Decision

1. **The code graph server is `codebase-memory-mcp`** in both clients' templates and in every current contract that names its tools (`mcp__codebase-memory-mcp__*`). The vendor's own registration is that key (DeusData/codebase-memory-mcp v0.11.0, commit `8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798`, `README.md` L450-460: `"mcpServers": {"codebase-memory-mcp": {"command": "/path/to/codebase-memory-mcp", "args": []}}`), and both clients on the host show it. The change is the rename of draft #834 (commit `6c6d8179f`) carried onto current main; that draft is superseded. Its separate four-byte trim (RULING-Q26) is not carried: the trim offset the bytes the rename added to the Codex startup text, and the instruction sources no longer name the server (the philosophy-only sources of [2026-10-08](2026-10-08-philosophy-only-rules.md)), so the rename adds none. The MCPorter example (`examples/mcporter.json.example`) registers the server under the same key, so every published `mcporter ... call` selects `codebase-memory-mcp.<tool>`: MCPorter takes the text before the first `.` of the selector as the server and looks it up by exact name (openclaw/mcporter@`e4cb002200e44460279d414b0d1dec597b978f06`, `src/cli/call-command.ts` L309-346 and `src/runtime.ts` L229-235, `Unknown MCP server '<name>'`). The short selector `codebase-memory.<tool>` stays only in the transcript classifiers, which still read sessions recorded before the rename; `tests/test_mcporter_selectors.py` resolves each published selector against the example.
2. **promptfoo is wired for Claude Code** in the distribution's additions (`claude/mcp/server/promptfoo`, slot `promptfoo`, see below).
3. **The other live-only servers and values stay out of the templates** and are accepted one by one in the acknowledged file (below).
4. **jcodemunch stays stdio** in the committed templates. The shared-service trial failed the admission gate (below), and the command center returned the live registration to the committed stdio form at 06:01Z.
5. **Two loopback routes that accept any Origin get research rows** for their owners (below). This change touches neither server.

## promptfoo

`promptfoo mcp --transport stdio`, from the installed global package of the manifest's `promptfoo` slot (pinned at Promptfoo 0.123.1, `promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8`; the first host runs 0.124.0, which has the same 14 tool names and the same `mcp --transport` command, so the drift between the pin and the install is a currency item for the version owner, not a reason to change this entry): the documentation's client entry is `site/docs/integrations/mcp-server.md` L49-52 and says stdio is the transport of desktop AI tools (L169); `src/commands/mcp/server.ts` L94-112 registers the server's 14 tools. The entry runs the installed binary, not `npx promptfoo@latest`, so the version is the installed one and never a floating one. Its state directory is the distribution's own and its telemetry and update check are off, exactly as the host's registration has them (`PROMPTFOO_CONFIG_DIR`, `PROMPTFOO_DISABLE_TELEMETRY=1`, `PROMPTFOO_DISABLE_UPDATE=1`).

Four of the 14 tools only read local state (`get_evaluation_details`, `list_evaluations`, `list_logs`, `read_logs`). Two more look read-only and are not: `run_assertion` runs content checks locally and also runs javascript, python and webhook assertions (`src/commands/mcp/tools/runAssertion.ts` L19-24; a provider is needed only for the model-graded ones, L43 and L166), and `validate_promptfoo_config` resolves configurations through `resolveConfigs` (`validatePromptfooConfig.ts` L5 and L62), which imports a JavaScript configuration as code (`src/util/config/load.ts` L383-385). The other eight call model providers or upload results. The tool classes are the basis of the read-only fence the runtime-profile generator applies; this change registers the server and sets no permission.

The Codex entry on the host forwards a gateway key by name (`env_vars`) and is left to its own decision: the ruling names the Claude template, and a template that forwards a credential variable is a separate choice. It is an acknowledged LIVE-ONLY row.

## Servers that stay out of the templates

| Server | Where | Why it stays out |
| --- | --- | --- |
| agentsview | Claude Code | the command center ruled it out of the templates on 2026-10-12 |
| grafana | Claude Code | until draft #807 decides the Grafana server's slot; registered with `--disable-write` |
| hindsight | both clients | the research-memory unit of this host; its loopback route accepts any Origin (below) |
| promptfoo | Codex | see above |

## Values that differ

| Server | Client | Fields | Reason |
| --- | --- | --- | --- |
| headroom | both | args | the template's `--proxy-url http://127.0.0.1:1` is a closed-port placeholder; the live proxy port is a host value |
| socraticode | both | args, env (Claude also command) | the host runs SocratiCode 1.16.0 (Claude Code through npx, Codex through node) with an auto-resume and a collection prefix; the environment names that differ in both clients are `QDRANT_COLLECTION_PREFIX`, `SOCRATICODE_AUTO_RESUME`, `SOCRATICODE_WATCHER` and `TMPDIR`; the template names 1.15.0; versions stay with the version owner. The `claude mcp list` warning about whitespace in its two embedding prefix variables is expected: the committed templates give them the values `query: ` and `passage: `, each with a trailing space on purpose |
| chrome-devtools | Codex | enabled | the live Codex entry is disabled |
| codebase-memory-mcp | Codex | env_vars | the live entry forwards `CBM_CACHE_DIR` and `CBM_RUNTIME_DIR` by name; the host owns the values |
| jcodemunch | Codex | enabled_tools | the template limits Codex to `menu`, `order` and `route`; the live entry lists none and exposes every tool |

The tool approval modes the host applies (`default_tools_approval_mode = "approve"` on five Codex servers) are authorization settings: the report renders them with `--with-authorization-settings`, as `new_wsl_client_config.py --render` does, and without the option they are the expected difference.

## Gate evidence

The `mcp-shared-servers` slot of the Claude Code practice page (`.claude/skills/claude-native-practice/reference/mcp-surfaces.md` L24-32; its pilot is [the QMD record](2026-10-08-qmd-shared-mcp.md)) admits one shared HTTP service per server only when it binds 127.0.0.1 only, rejects an invalid `Origin` with 403 and authenticates where the vendor supports it, through `headersHelper`; it then measures proportional set size before and after and checks tool-surface parity. Measured on 2026-10-12 against the jcodemunch service the host had registered (127.0.0.1:21852):

| Gate | Result |
| --- | --- |
| bind | loopback only (`127.0.0.1:21852`) |
| invalid `Origin` | HTTP 200, not 403 (no Origin: 200) |
| tool parity | stdio 6 tools, HTTP 6 tools, same names, same description and schema hashes |
| proportional set size | a fresh stdio child after the handshake 45.3 MiB; the shared service 47.8 MiB; break-even at 1.1 stdio sessions (at 5, 10 and 20 concurrent sessions stdio costs 226, 453 and 906 MiB) |

The service fails the Origin gate, so the registration went back to the committed stdio form. The memory case for sharing stands for the day a version of the service validates `Origin`.

Four loopback MCP routes, each probed with an `initialize` request only (no tool call, no data read) with no `Origin`, with `Origin: http://evil.example` and with `Host: evil.example`:

| Route | No Origin | Invalid Origin | Foreign Host |
| --- | --- | --- | --- |
| jcodemunch (21852) | 200 | 200 | 200 |
| qmd (21851) | 200 | 403 | 403 |
| ai-memory (29374) | 200 | 200 | 403 |
| hindsight (8888, `/mcp/trading-research/`) | 200 | 200 | 200 |

The specification of the Streamable HTTP transport requires the check: servers **MUST** validate the `Origin` header on all incoming connections to prevent DNS rebinding (modelcontextprotocol/modelcontextprotocol@`1f520964b295d58494d944f2aea8a5ab51c79f77`, `docs/specification/2025-06-18/basic/transports.mdx` L76), and an invalid `Origin` **MUST** get HTTP 403 (`docs/specification/2025-11-25/basic/transports.mdx` L78-79; `docs/specification/2026-07-28/basic/transports/streamable-http.mdx` L58-61). qmd passes. ai-memory validates `Host` but not `Origin`; hindsight validates neither. Both routes are loopback-only, which narrows the exposure and does not remove the requirement. Research rows go to the owners of the two units: whether the vendor has an allowed-origins setting (and if so, its documented key), else whether a stdio or socket form is the supported way to reach the unit from a client. No server was changed here.

## Alternatives

- **Rebase #834 onto this change** instead of folding it: the rename would stay a separate pull request on the co-op's branch, and the registry, checksum inventories and instruction copies it touches would conflict twice. Not chosen.
- **Put the four live-only servers into the shared templates:** each has a ruling or an open decision of its own (above), and a template entry makes a server part of every host's registration. Not chosen.
- **Keep the short code graph key:** it disagrees with the vendor's registration and with the names both clients show, so every tool id in a contract would have to be aliased. Not chosen.
- **Fix the host's stored configuration from this change:** stored client configuration is the command center's act on a reviewed diff. The report names the differences; it does not change them.

## Overturn conditions

- The vendor of the code graph server documents another registration key, or a client stops showing `codebase-memory-mcp`.
- A promptfoo release changes the `mcp` command or its transport flag, or the manifest's `promptfoo` slot stops installing it.
- A released version of the jcodemunch service answers an invalid `Origin` with 403 and authenticates, and the memory case still holds on the host: reopen the shared-service trial.
- The command center rules a Codex promptfoo entry, a template for `hindsight`, `grafana` or `agentsview`, or a different headroom proxy value: remove the matching acknowledgement in the same change, and the report fails until it is gone.
