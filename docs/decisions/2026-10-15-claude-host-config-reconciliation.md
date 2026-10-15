# Record: Claude Code host configuration against the new-WSL clean render (2026-10-15)

**Status:** DRAFT for review. Every row carries its evidence; a row with no decisive record reads UNRESOLVED or "host retire, pending CC", never a generated fix. All `path:line` locators are at `origin/main` `8053f14e7`.

## Trigger and scope

On 2026-10-15 the owner asked for the Claude Code configuration in a clean, SOTA-aligned form and a new WSL setup carrying
it (paraphrased, dated). This record compares the live host's Claude Code user configuration with the clean form the
repository already generates. It authors no new clean form and applies nothing to the host: host changes are the command
center's act, handed over as a reviewed diff.

Out of scope, owned elsewhere:

- The practice skill's currency at Claude Code 2.1.300: #1171 classifies the 357 CHANGELOG entries of 2.1.296, 2.1.299
  and 2.1.300 and overturns no default.
- The 96 repository surfaces of the continuity design's section 6 (R4), owned by that lane.
- The client floor (#1128), the surface watch (#1131, #1155) and the gap-ledger rows (#1147, #1157, #1158, #1160, #1169).

## Method (reproducible)

- Base: `origin/main` at `8053f14e7`. Client: Claude Code 2.1.300 (`npm view @anthropic-ai/claude-code dist-tags`:
  latest 2.1.300, next 2.1.301, stable 2.1.292).
- Clean form: `python3 tools/adoption/new_wsl_client_config.py --check` (passed: 403 pieces, 363 wired lines, two
  warnings for `MCP_AUTO_OPEN_ENABLED`, whose slot the manifest installs and the install plan does not), then
  `--render --host example --out <dir> [--with-authorization-settings]`.
- Comparison: names only (keys, hook identities, plugin, marketplace and MCP server names, counts). No env value,
  permission rule text or credential-bearing field is printed or recorded.
- Tag per row, from the render's `wiring.json`: `practice`, `slot:<name>`, `authorization`, `not_wired` (the map names the
  piece and leaves it out), or `no piece` (the map, a closed world, does not name it).
- The render used the example host value file. That file holds nine placeholders (paths and URLs) and no Claude setting, so every scalar row's render value is a template literal or a map override, not a host fill.

## Rows

Direction is the question each row answers: **template behind** (a landed record adopted the piece after the 2026-10-01
definitive manifest, so the map and template must gain it) or **host retire** (no record adopts it) or a **host fix**
(the template already has the converged value).

| # | Family | Piece | Live | Clean render | Tag | Landed record | In-flight PR | Proposed disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | MCP | agentsview | user scope | absent | no piece | `adoption/new-wsl/mcp-drift-acknowledged.json:9` (the CC ruled on 2026-10-12 that it stays out of the templates); `2026-10-12-mcp-template-live-reconciliation.md:31` | none edits the map or a template | host keep by ruling (a recorded template hold-out) |
| 2 | MCP | grafana | user scope | absent | no piece | `mcp-drift-acknowledged.json:16` (out until #807 decides the server's slot; read-only on this host); reconciliation record `:32` | #807 adds a CC-only template | host keep by ruling; follow #807 |
| 3 | MCP | hindsight | user scope | absent | no piece | `mcp-drift-acknowledged.json:23` (the host's research-memory unit stays out of the templates); reconciliation record `:33` | none edits the map or a template | host keep by ruling |
| 4 | plugin | codex@openai-codex | enabled | absent | not_wired | the map leaves it out by decision (`client-config-map.json:252-264`; `2026-10-04-new-wsl-changelog-parity.md:31`); `claude.settings.template.json:345` still enables it | #1092 pins it in a new plugin pins file | UNRESOLVED: the map and the template disagree; one of them is corrected by PR |
| 5 | plugin | diagram-design@diagram-design | enabled | absent | no piece | none | none edits the map or a template; usage records only in #1138 and #1153 | UNRESOLVED: no record; host retire or adoption by the CC |
| 6 | plugin | socraticode@socraticode | enabled | absent (the server is wired, slot:code-search) | no piece (plugin) | `2026-10-07-clean-upstream-install-finalizes-a-candidate.md:151-152` (SocratiCode takes its vendor's plugin with one user-scope server entry) | #901 adds the plugin, its marketplace and a map entry | template behind; follow #901 |
| 7 | plugin | worktrunk@worktrunk | enabled | absent | no piece | `2026-10-04-2604-e2e-fix-wave-g7-git.md:11-13` (the upstream plugin installation); the install plan's worktrunk row runs the vendor's plugin install | none | template behind: the install plan installs it, the map does not name it |
| 8 | marketplace | anthropic-agent-skills | present | absent | no piece | `adoption/skills/manifest.json:66` (trial); `2026-10-13-plugin-skill-identity.md:63` (which copy a host has is the host's) | #1153 records the built-in skill superseding this plugin copy, disabled 2026-10-15 | host retire after #1153, pending CC |
| 9 | marketplace | diagram-design | present | absent | no piece | none | none | as row 5 |
| 10 | marketplace | openai-codex | present | absent | not_wired | as row 4; `claude.settings.template.json:361` holds the marketplace | #1092 | as row 4 |
| 11 | marketplace | socraticode | present | absent | no piece | as row 6 | #901 | template behind; follow #901 |
| 12 | marketplace | trailofbits | present | absent | no piece | `2026-10-01-new-wsl-definitive-defaults.md:58` (definitive slot); the install plan adds the marketplace; `adoption/skills/manifest.json` (eight trial rows) | none | template behind: the install plan adds it, the map does not name it |
| 13 | marketplace | typesafe-ai | present | absent | no piece | `2026-10-13-plugin-skill-identity.md:9-10, 119-120` (the vendor's plugin route); `adoption/skills/manifest.json:96` | #1153 disables the plugin copy | follow #1153; the skill is the layer candidate |
| 14 | marketplace | worktrunk | present | absent | no piece | as row 7 | none | template behind, as row 7 |
| 15 | hook | codebase-memory-mcp: PostToolUse Read, PreToolUse Grep/Glob/Bash, SessionStart startup/resume/clear/compact, SubagentStart (7) | present | absent (server wired, slot:code-graph) | no piece | none adopts them; pre-manifest hold-outs: `2026-09-25-codex-mcp-scope.md:75-76` (never run the vendor's `install` subcommand, which edits client configs) | #776 records the 2026-10-06 vendor install run that wrote them, with no map entry | host retire, pending CC (written by the vendor installer against the hold-out) |
| 16 | hook | serena-hooks: SessionStart activate, SessionEnd cleanup (2) | present | absent (server wired, slot:serena) | no piece | hold-outs: `2026-09-27-claude-harness-settings.md:47` (the optional hooks are not added to the template); `2026-10-02-new-wsl-client-configuration.md:737-738` (not wired) | none | host retire, pending CC (writer not identified) |
| 17 | hook | context-mode-cache-heal.mjs: SessionStart | present | absent | not_wired | `client-config-map.json:163-168`: the context-mode plugin writes this hook and deploys its file itself; a second writer would compete | none | host keep (the plugin's own entry; never a template piece) |
| 18 | hook | cc-clock-context: PreToolUse (write tools, SendMessage), UserPromptSubmit (2) | present | absent | no piece | none; a host-authored script in no repository, informational only | #955 mentions it only | UNRESOLVED: no record; the CC decides record-and-template or retire |
| 19 | hook | ai-memory: UserPromptSubmit command hook | present | absent (eight other ai-memory events wired, slot:memory-owner) | no piece | hold-out: `docs/token-efficiency-stack.json:3409` (prompt capture off by design) | #800 records the CC's 2026-10-06 run of the vendor's hook installer with prompt capture on | UNRESOLVED: owned by #800 |
| 20 | hook | Notification matcher | live lacks `auth_storage_failure` | adds `auth_storage_failure` | practice | #790; `2026-10-06-auth-storage-failure-notification.md:11` | none | host fix, pending CC (the record says live application is the CC's) |
| 21 | env | CLAUDE_CODE_TMPDIR | set | absent | no piece | `upstream-surface-dispositions.json:527-536` (enabled: applied on NativeStack2604 by the CC on 2026-10-10 after the `/tmp` tmpfs filled; template unchanged) | none | host choice, carried to the new distribution as one |
| 22 | env | SEMBLE_CACHE_LOCATION, SEMBLE_MODEL_NAME | in the Claude settings `env` | in the Claude `semble` server env | slot:code-search | `client-config-map.json:445`; `2026-10-07-foundation-finalization.md:470-471` (per-client server entries) | #1051 moves the semble env | host fix, pending CC (scope: server env, not settings env) |
| 23 | env | SOCRATICODE_SPEC | set | absent | no piece | none names it as a host variable | #901 adds it to the template | follow #901 |
| 24 | setting | autoDreamEnabled | `false` | absent | no piece | none; name only in `catalogs/foundation/upstream-surface-baseline.json` | #1149 says the CC set `true` on 2026-10-15 at 00:45 ET; the file reads `false` | UNRESOLVED: the live value contradicts #1149; ask the CC |
| 25 | setting | enableArtifact | `false` | absent | no piece | none | #1169 records it as a host choice that the template leaves out; #1131 | host choice (as #1169 records), not a template piece |
| 26 | setting | feedbackDrafts | `"off"` | absent | no piece | `2026-10-04-new-wsl-changelog-parity.md:32` (NativeStack2604 keeps the client default); `upstream-surface-dispositions.json:1597` (declined, no ruling or upstream advice to turn it off) | none | host retire, pending CC (the records keep the default) |
| 27 | setting | crossSessionInbound | absent | `"accept"` (authorization; written only with `--with-authorization-settings`) | authorization | `client-config-map.json:345`; dispositions `:1393` (enabled) | #1111 removes it from the map and additions ("no template sets it") | follow #1111 (in flight); no host change now |
| 28 | setting | ultracode | user `false`, project `true`, local `false` | `true` (template) | practice | dispositions `:2281` (enabled, set on both hosts, read 2026-10-04); `2026-10-09-claude-code-gap-resolution.md:159-164` (local file turns it off; input to the G6 settings-drift inventory) | #829 (opt-in; open since 2026-10-07) | UNRESOLVED: owned by the G6 inventory and #829 |
| 29 | setting | verbose | `false` | `true` (template) | practice | dispositions `:2293` (enabled, set on both hosts, read 2026-10-04); `2026-09-28-community-sweep.md:360` | none | host fix, pending CC (no record adopts `false`) |
| 30 | setting | model | alias `opus` | `claude-opus-5-5` (map override) | practice | `client-config-map.json:297-298` (the owner's choice of Opus 5.5, 2026-10-04); dispositions `:1741` (the model choice is the owner's) | none | equivalent today; owner's choice; no change |
| 31 | setting | advisorModel | `fable` | `opus` | practice | `2026-10-04-coordinator-dispatch-and-spend.md:68` (the owner chose Opus 5.5); dispositions `:1153` (adopt-pending: the other value observed since 2026-10-06 21:28Z, actor unknown) | none | owner item, open in dispositions `:1153`; not decided here |
| 32 | skillOverrides | domain-modeling, setup-matt-pocock-skills (`off`) | present | absent | no piece | installed by the plan's mattpocock row (`2026-10-02-new-wsl-client-configuration.md:160-161`), excluded by `adoption/skills/manifest.json`, removed by `install.sh`; neither skill is installed on the host | none | host retire, pending CC (entries for skills that are not installed) |
| 33 | skillOverrides | claude-native-practice, hcom-agent-messaging, loki, promptfoo-evals (`on`) | absent | present | practice | #852, `2026-10-08-skills-cc-lanes-picks.md:3`; #972, `2026-10-10-skills-claude-native-practice-row.md:49` | none | host fix, pending CC (the template already holds them) |
| 34 | permissions | allow rules | 19 | 2 (17 live-only) | none of the 17 mapped | none for any of the 17 (eleven MCP tool names, six read-path grants for host state and worktree roots); dispositions `:1825` (baseline-unreviewed) | none | UNRESOLVED: host-only grants; the CC decides keep or retire; the paths are not restated here |
| 35 | permissions | deny rules | 138 | 133 (5 live-only, 0 clean-only) | none of the 5 mapped | none: five credential-file read denies (certificate and key extensions, a credentials file name); dispositions `:1873` (defer-user: whether the template's rules replace them is the owner's) | #1100 adds two different denies to a new sandbox overlay | UNRESOLVED: owner item per `:1873`; deny-first practice favors keeping them |

Same on both sides: the other 14 scalar keys, 16 of the live hook identities, 10 MCP servers, 3 plugins, the status line
command and `permissions.defaultMode`.

## Summary of dispositions

| Disposition | Rows |
| --- | --- |
| template behind: the map and template gain the piece by PR | 7, 12, 14 (the install plan installs them; the map does not name them) |
| follow an open PR | 6, 11, 23 (#901); 13 and 8 (#1153); 27 (#1111); 2 (#807); 19 (#800); 28 (#829 and the G6 inventory) |
| host keep by ruling or as a recorded host choice | 1, 2, 3, 17, 21, 25 |
| host fix, pending CC | 20, 22, 29, 33 |
| host retire, pending CC | 15, 16, 26, 32 |
| owner item | 31, 35 |
| UNRESOLVED | 4 and 10 (the map and the template disagree), 5 and 9, 18, 24, 34 |
| equivalent today; no change | 30 |

For the new distribution, rows 7, 12 and 14 are the only template gap that changes what the clean render installs.

## Next actions

1. Template-behind rows (7, 12, 14): one map and template change, sequenced against the open PRs that touch
   `adoption/new-wsl/client-config-map.json` (#1051, #1089, #1109, #1111, #1151 and older ones from 2026-10-06 to 10-09).
2. Host rows: a reviewed diff for the command center. NativeStack2604 keeps account C, so its configuration stays the
   command center's.
3. New WSL distribution: built from the clean render through the recipe
   (`adoption/platforms/linux-wsl2-new-distro.md`), up to the owner's sign-ins
   ([install plan record](2026-10-15-new-wsl-clean-install-plan.md)).
