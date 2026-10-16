# Start-up context, measured per role launch

`startup_context.py` measures how many tokens a Claude Code launch starts with, using the client's own `/context` report,
at no model cost. It runs one role's launch as a control (the launch without the components under test) and then as the
control plus one component at a time, and reports each component's start-up tokens over the control.

```sh
python3 tools/startup-context/startup_context.py measure --launch tools/startup-context/launches/CC.json --out <dir>
python3 tools/startup-context/startup_context.py parse <saved stream result>
```

## How it measures

- **The report:** `/context` shows current context usage (`commands.md:75` in the Claude Code documentation, fetched
  2026-10-15T20:05:21Z, sha256 `3857d8e6782aab33`). Run headless as `claude -p "/context"`, it answers without a model turn:
  `num_turns` 0 and `total_cost_usd` 0 at 2.1.301 (measured 2026-10-16). The tool refuses any run where either is not 0,
  so a measurement never spends.
- **What loaded:** each run uses `--output-format stream-json --verbose`, whose `system/init` event lists every MCP server
  with its `status` and the loaded plugins (`headless.md:253-255`, `:279`, fetched 2026-10-15T20:05:20Z, sha256
  `fe8a1d507c57c816`). A component's tokens over the control are reported only when it loaded (its server `connected`, or
  its plugin listed); otherwise the summary says it did not load.
- **What counts:** the report's total is the start-up context. MCP tool definitions are deferred under tool search: their
  names are listed and their schemas load on demand (`context-window.md:43-47`, sha256 `78bf25a505d7563d`), so the per-server
  tool tokens are recorded but are outside the total.
- **The launch:** a variant's MCP servers come from the repository's template `adoption/mcp/claude-user.json`, rendered as
  the installer renders it (`tools/adoption/install_claude_profile.py`, `render_servers` and `default_eco_root`), written to a
  scratch file and passed with `--strict-mcp-config --mcp-config`. Plugins are switched with `--settings`
  (`enabledPlugins`). User and project settings, hooks and other plugins are the same in every variant.

## What a receipt holds

Names, token counts, each server's status, the loaded plugins and the variant's flags. Never an absolute home path (a
path under home is shown as `~/...`, the dash-encoded home in a project directory as `-~-`), an environment value or a
host name. Values of 1,000 tokens and more are the client's own rounding to the nearest 100.

## Tests

`python3 -m unittest tests.test_startup_context` (a stand-in client; synthetic reports).
