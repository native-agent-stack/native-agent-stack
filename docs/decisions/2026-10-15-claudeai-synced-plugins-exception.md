# claude.ai synced plugins: an owner-synced exception to the pin policy (2026-10-15)

**Status:** superseded in part on 2026-10-15T05:07Z. On the owner's direction of 2026-10-15 (01:05 ET, paraphrased by the command center: resolve the synced plugins cleanly with current practice), after the listing-cost measurement below, the command center disabled each of the four plugins with the native CLI, `claude plugin disable <id> --scope user`. That wrote `"<name>@synced": false` into `enabledPlugins` in user settings for bigdata-com, lseg, daloopa and cowork-plugin-management, and `claude plugin list` shows them disabled. The keep decision below is superseded. The sync itself stays on, because `syncClaudeAiPlugins` stays unset, so a plugin the account adds later still arrives and is caught by the trigger. Inverse: `claude plugin enable <id> --scope user`.

**Corrects:** the `claude:setting:syncClaudeAiPlugins` row in `catalogs/foundation/upstream-surface-dispositions.json`. On 2026-10-04 that row said "off on both hosts". In fact the settings template has never set the key, and Claude Code honours only `false`, so the sync was on. The row is now `default-on` and cites this record: the sync stays on (the key unset), and since 2026-10-15T05:07Z each synced plugin is disabled per plugin, which supersedes the keep decision below. `tests/test_claudeai_synced_plugins_exception.py` fails on the old row.

**Refines:** [2026-09-25-skills-trial-and-usage.md](2026-09-25-skills-trial-and-usage.md), line 381. It said the key stays unset because no claude.ai plugin had appeared, and that is no longer true. The key still stays unset, now for the exception below.

## What is synced

The inventory is [evidence/artifacts/claudeai-synced-plugins-20261015/inventory.json](../../evidence/artifacts/claudeai-synced-plugins-20261015/inventory.json), read on the 2604 host with Claude Code 2.1.300.

- **Location:** one of the ten account buckets in `~/.claude/plugins/synced/` holds four plugins from the `knowledge-work-plugins` marketplace:
  - `cowork-plugin-management`: 2 skills;
  - `lseg`: 8 skills, MCP server `lseg`;
  - `daloopa`: 23 skills, MCP servers `daloopa` and `daloopa-docs`;
  - `bigdata-com`: 27 skills, MCP server `bigdata.com`.
- **Loading sessions:**
  - 30 sessions loaded the plugins on 2026-10-09T07:11Z-07:15Z: the `.in_use` markers, matched by 30 Loki sessions on 2.1.295.
  - The bucket last synced at 2026-10-10T01:57:26Z.
  - A session signed in with that account loads each plugin as `<name>@synced`.
- **Invocations:** 0 skill activations and 0 MCP calls, counted from Loki's first Claude Code event (2026-10-04) to 2026-10-15T02:48:30Z with the [count of record](2026-09-26-tool-invoke-rates.md).
- **Catalog:** none of the four synced plugins is pinned. Their source repository, anthropics/knowledge-work-plugins, has four grand-catalog rows (`catalogs/landscape/grand-catalog-20261008.json`, rows 447-450):
  - 447, durable-memory: WATCH (SOURCE-REVIEW), pinned to the repository at `ae1513ea`;
  - 448, instructions-skills, and 449, mcp-surfaces: PENDING, PROPOSED provisional WATCH, no pin;
  - 450, token-efficiency: PENDING, PROPOSED provisional OUT-OF-SCOPE, no pin.
  No row pins an individual synced plugin.

## Decision

The four plugins stay synced as an **owner-synced exception** to the rule that skills and plugins load from a pinned catalog.
- They are the owner's own claude.ai integrations, and three are financial data providers.
- Unused, they still cost context: their 66 skills add about 8,450 tokens of skill listing to the system prompt of every turn (bigdata-com 6,360, lseg 1,230, daloopa 620, cowork-plugin-management 240), about half of the 16,490 listing tokens of all loaded skills, measured with /skill-doctor at 2.1.300 on 2026-10-15T04:55:55Z ([listing-cost.json](../../evidence/artifacts/claudeai-synced-plugins-20261015/listing-cost.json)). This corrects the first version of this record, which claimed no measurable cost; a single plugin can be dropped with `"<name>@synced": false` in `enabledPlugins` (settings reference, `syncClaudeAiPlugins`).
- Turning the sync off would move them to `~/.claude/plugins/.trash/` for every CLI session.

The template and the host settings stay unchanged.

**Trigger:** the exception ends at the first hit for any of the four, whichever surfaces it:
- a `skill_activated` event naming one of their skills, or a `tool_result` event naming one of their MCP servers, in the count of record;
- or a call in the lane's transcript scan.

At that point, one of two changes follows, by pull request:
- a catalog pin for the plugin that was hit, at a commit of its source, with a measured trial;
- or `"syncClaudeAiPlugins": false` in the template, with the host key set by the command center.

**If the owner chooses off:** a follow-up pull request sets the template key, maps it in `adoption/new-wsl/client-config-map.json` and pins it with a test. The command center applies the host line.

## Upstream source

Claude Code settings reference, `syncClaudeAiPlugins` (<https://code.claude.com/docs/en/settings-reference>, read 2026-10-14 for client 2.1.300):
- Claude Code downloads the account's plugins at the start of signed-in terminal sessions and loads each one as `<name>@synced`.
- `false` stops the download and the loading. In user settings, it also moves the synced plugins to `~/.claude/plugins/.trash/`.
- Only `false` is honoured; `true` is the same as unset.
- `"<name>@synced": false` in `enabledPlugins` turns off a single plugin.

`anthropics/claude-code` CHANGELOG at `7779afb12e36`, 2.1.275, added the sync with this opt-out.
