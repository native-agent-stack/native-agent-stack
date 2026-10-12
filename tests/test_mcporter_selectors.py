"""Every `mcporter ... call SERVER.TOOL` that the repository publishes with the example configuration (${MCPORTER_CONFIG}) names a server that examples/mcporter.json.example registers.

MCPorter (openclaw/mcporter@e4cb002200e44460279d414b0d1dec597b978f06, the pin of MIRRORS.json, v0.13.13; the installed 0.14.2 behaves the same) takes the text before the first `.` of the selector
as the server (src/cli/call-command.ts:309-346, resolveCallTarget and splitServerToolSelector) and looks it up by exact name (src/runtime.ts:229-235: `Unknown MCP server '<name>'.`). The check reads
files and a configuration; it starts no server. Dated records (docs/decisions/, evidence/) and tests are not scanned: they quote what ran or what a classifier must still recognise, not what to run.
"""

import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "mcporter.json.example"
SKIPPED_DIRECTORIES = {".git", "node_modules", "__pycache__", "evidence", "tests"}
SKIPPED_PREFIXES = ("docs/decisions/",)
SUFFIXES = {".md", ".json", ".txt", ".yaml", ".yml", ".sh", ".toml", ".mjs", ".py"}
SELECTOR = re.compile(r"\bmcporter\b[^\n]*?\bcall\s+([A-Za-z0-9_-]+)\.([A-Za-z0-9_]+)")


def registered_servers() -> set:
    return set(json.loads(EXAMPLE.read_text(encoding="utf-8"))["mcpServers"])


def selectors_of(text: str) -> list:
    """(line number, server, tool) of each `mcporter ... call SERVER.TOOL` on a line that selects the example configuration; the server is the text before the first dot."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if "MCPORTER_CONFIG" not in line:
            continue
        for match in SELECTOR.finditer(line):
            found.append((number, match.group(1), match.group(2)))
    return found


def published_selectors() -> list:
    found = []
    for directory, names, files in os.walk(ROOT):
        names[:] = sorted(name for name in names if name not in SKIPPED_DIRECTORIES)
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix not in SUFFIXES or relative.startswith(SKIPPED_PREFIXES) or path.stat().st_size > 8_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "MCPORTER_CONFIG" in text:
                found += [(relative, *item) for item in selectors_of(text)]
    return found


class McporterSelectorTests(unittest.TestCase):
    def test_the_example_registers_the_code_graph_server_under_the_vendors_name(self):
        servers = registered_servers()
        self.assertIn("codebase-memory-mcp", servers)
        self.assertNotIn("codebase-memory", servers, "MCPorter finds a server by exact name: a second name would start a second process on the same index")

    def test_every_published_call_names_a_server_the_example_registers(self):
        servers = registered_servers()
        found = published_selectors()
        unknown = [f"{path}:{line} {server}.{tool}" for path, line, server, tool in found if server not in servers]
        self.assertEqual(unknown, [], "MCPorter answers `Unknown MCP server` for each of these; the example registers " + ", ".join(sorted(servers)))
        self.assertGreaterEqual(len(found), 20, "the scan finds the published calls (a pattern that matches nothing proves nothing)")
        self.assertIn("codebase-memory-mcp", {server for _, _, server, _ in found})

    def test_the_check_flags_a_selector_the_example_does_not_register(self):
        servers = registered_servers()
        old = 'mcporter --config "${MCPORTER_CONFIG}" call codebase-memory.search_graph --args "${GRAPH_QUERY_ARGS}" --output json --no-oauth'
        new = old.replace("codebase-memory.", "codebase-memory-mcp.")
        self.assertEqual([server for _, server, _ in selectors_of(old)], ["codebase-memory"])
        self.assertNotIn("codebase-memory", servers)
        self.assertEqual([server for _, server, _ in selectors_of(new)], ["codebase-memory-mcp"])
        self.assertIn("codebase-memory-mcp", servers)
        self.assertEqual(selectors_of('mcporter --config "$OTHER" call codebase-memory.search_graph'), [], "only calls that select the example configuration are in scope")
        self.assertEqual(selectors_of("a.b mcporter call x"), [])


if __name__ == "__main__":
    unittest.main()
