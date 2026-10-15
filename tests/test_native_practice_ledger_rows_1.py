"""Gap-ledger first wave (2026-10-15): rows whose practice text the ledger found missing or stale.

A4-0079: a Workflow child's or -p child's frontmatter Stop hook from a project .claude/agents file is skipped until that
folder is trusted, and a -p session does not count as trusted (sub-agents.md:757, client 2.1.300; since 2.1.218). The
loops-completion row must say so and route those hooks through user-scope or --agents definitions.
CLAUDE_CODE_TMPDIR: the 2026-10-04 disposition said "off on both hosts"; the command center applied it on 2604 on
2026-10-10, so the row must record it as applied there.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ROOT / ".claude/skills/claude-native-practice/reference/slots.json"
PAGE = ROOT / ".claude/skills/claude-native-practice/reference/workers.md"
DISPOSITIONS = ROOT / "catalogs/foundation/upstream-surface-dispositions.json"


class LedgerRowsWave1(unittest.TestCase):
    def test_loops_completion_routes_child_hooks_outside_project_agent_frontmatter(self):
        row = next(s for s in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"] if s["id"] == "loops-completion")
        notes = row["notes"]
        self.assertIn("sub-agents.md:757", notes)
        self.assertIn("--agents", notes)
        self.assertIn("~/.claude/agents", notes)
        self.assertIn("a -p session does not count as trusted", notes)
        self.assertIn(f"- **Notes:** {notes}\n", PAGE.read_text(encoding="utf-8"))

    def test_the_tmpdir_row_records_the_2604_application(self):
        rows = json.loads(DISPOSITIONS.read_text(encoding="utf-8"))["rows"]
        (row,) = [r for r in rows if r["key"] == "claude:env:CLAUDE_CODE_TMPDIR"]
        self.assertEqual((row["disposition"], row["value"], row["carrier"]), ("enabled", "/var/tmp/claude-tmp", "host user settings"))
        self.assertNotIn("off on both hosts", row["reason"])


    def test_the_advisor_row_records_the_observed_host_value_without_changing_the_default(self):
        # 2026-10-15: 2604 reads fable since a 2026-10-06 window with no recorded actor, against the 10-04 rule (fable only
        # when truly needed); the template and the row's value stay opus until the owner confirms.
        rows = json.loads(DISPOSITIONS.read_text(encoding="utf-8"))["rows"]
        (row,) = [r for r in rows if r["key"] == "claude:setting:advisorModel"]
        self.assertEqual(row["value"], "opus")
        self.assertIn("fable observed on 2604 since the 2026-10-06T21:28Z", row["reason"])
        self.assertIn("confirms fable as the standing advisor", row["overturn"])

if __name__ == "__main__":
    unittest.main()
