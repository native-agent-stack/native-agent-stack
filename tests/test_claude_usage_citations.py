"""Source contracts for #954's public symbol citations and private marker.

Git 2.53.0 v2.53.0 (67ad42147a7acc2af6074753ebd03d904476118f),
Documentation/merge-options.adoc:119-127, explains why --squash does not
preserve a PR source commit as a merge parent. Symbol references remain
checkable from the landed source without depending on a PR-only object.
"""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECORD = "docs/decisions/2026-10-06-native-lane-invocation-observability.md"
RENDERER = "observability/lanes_dashboard.py"


class ClaudeUsageCitationTests(unittest.TestCase):
    def assert_query_references(self, record, source):
        lines = record.splitlines()
        tokens = next(line for line in lines if line.startswith("| tokens |"))
        mcp = next(line for line in lines if line.startswith("The Lanes ") and "MCP" in line)
        self.assertNotRegex(tokens + mcp, r"/blob/[a-f0-9]{40}/observability/lanes_dashboard\.py")
        for line, symbols in ((tokens, ("dashboard", "usage")), (mcp, ("dashboard", "records"))):
            self.assertIn(RENDERER, line)
            for name in symbols:
                self.assertIn("`" + name + "()`", line)
        functions = {node.name: node for node in ast.parse(source).body
                     if isinstance(node, ast.FunctionDef)}
        self.assertTrue({"dashboard", "usage", "records"} <= functions.keys())
        dashboard = ast.get_source_segment(source, functions["dashboard"])
        for panel in ("Codex request usage by native conversation",
                      "Claude request usage by native session",
                      "Per-session MCP server and tool results"):
            self.assertIn(panel, tokens + mcp)
            self.assertIn(panel, dashboard)
        self.assertIn("observed", mcp)
        self.assertIn("observed =", dashboard)

    def test_public_query_references_resolve_to_renderer_symbols(self):
        self.assert_query_references((ROOT / RECORD).read_text(), (ROOT / RENDERER).read_text())

    def test_missing_query_symbol_is_rejected(self):
        record = (ROOT / RECORD).read_text().replace("`usage()`", "`missing_symbol()`")
        with self.assertRaises(AssertionError):
            self.assert_query_references(record, (ROOT / RENDERER).read_text())

    def test_private_guard_reference_publishes_only_its_marker(self):
        record = (ROOT / "docs/decisions/2026-10-10-claude-usage-observability.md").read_text()
        lines = record.splitlines()
        index = next(i for i, line in enumerate(lines) if "w5_guard.py" in line)
        entry = "\n".join(lines[index:index + 2])
        # Never include an unapproved digest in a failure diagnostic.
        self.assertTrue("private, not published (host state)" in entry, "private guard marker required")
        self.assertFalse(re.search(r"\b[a-f0-9]{64}\b", entry), "private guard digest must be omitted")

