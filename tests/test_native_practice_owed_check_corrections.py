"""The two corrections from the command center's 2.1.302 owed checks (F1.1 and F2.1) stay corrected.

Each check pins one claim that was wrong at 728141f2 and is mirrored on its layer page, so a later edit cannot silently
restore it:

- settings-permissions (reference/native-clients.md and its slots.json row), F1.1: CHANGELOG@v2.1.302 L245 (2.1.299)
  fixes rm prompts on shell `-c` scripts; it changes a built-in prompt, not how permission rules are evaluated. The row
  filed it with L373 as a rule-evaluation change, in its evidence ("L373 and L245 (2.1.299, rule evaluation)") and in
  its note ("Rule evaluation changed in 2.1.299 (CHANGELOG@v2.1.302 L373, L280 and L245)").
- subagent-definitions (reference/workers.md and its slots.json row), F2.1: the note said four host copies differ from
  adoption/agents/claude, four host-only definitions exist and 4 user-scope copies are stale. `diff -rq` of
  adoption/agents/claude and of .claude/agents against ~/.claude/agents exited 0 on 2026-10-17, and
  docs/decisions/2026-10-13-claude-agent-drift-check.md had already recorded the note as stale. The corrected note's
  count and its locator into that record are checked against the repository; the host folder itself is not readable
  here.

These are repository-text checks, not a run of Claude Code or a read of the host's agent folder.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"


def row(slot_id: str) -> dict:
    slots = json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"]
    return next(slot for slot in slots if slot["id"] == slot_id)


def section(page: str, slot_id: str) -> str:
    """The slot's section of its layer page, from its heading to the next one."""
    return (REF / page).read_text(encoding="utf-8").split(f"\n## {slot_id}\n", 1)[1].split("\n## ", 1)[0]


class SettingsPermissionsRmPromptTests(unittest.TestCase):
    """F1.1: L245 is cited as the rm-prompt change, apart from the 2.1.299 rule-evaluation lines L373 and L280."""

    WRONG = ("L373 and L245 (2.1.299, rule evaluation)", "(CHANGELOG@v2.1.302 L373, L280 and L245)")

    def setUp(self):
        self.row = row("settings-permissions")

    def test_the_row_files_l245_as_a_prompt_change_not_rule_evaluation(self):
        cited = [item for item in self.row["evidence"] if "L245" in item]
        self.assertEqual(cited, ["L245 (2.1.299, rm prompts on shell `-c` scripts)"])
        self.assertIn("CHANGELOG@v2.1.302 L373 (2.1.299, MCP allow rules reach only the named server)",
                      self.row["evidence"])
        notes = self.row["notes"]
        self.assertIn("Rule evaluation changed in 2.1.299 (CHANGELOG@v2.1.302 L373 and L280): ", notes)
        rule_sources = notes.split("Rule evaluation changed in 2.1.299 (", 1)[1].split("):", 1)[0]
        self.assertNotIn("L245", rule_sources)
        self.assertIn("The same release changed a built-in prompt, not rule evaluation (L245): an rm built at run time",
                      notes)

    def test_the_page_carries_the_corrected_row(self):
        text = section("native-clients.md", "settings-permissions")
        for wrong in self.WRONG:
            self.assertNotIn(wrong, text)
        self.assertIn(f"- **Evidence:** {'; '.join(self.row['evidence'])}\n", text)
        self.assertIn(f"- **Notes:** {self.row['notes']}\n", text)


class SubagentDefinitionsDriftNoteTests(unittest.TestCase):
    """F2.1: the subagent-definitions note no longer reports host drift that `diff -rq` showed gone."""

    STALE = ("Four host copies differ from adoption/agents/claude", "four host-only definitions exist",
             "where 4 are stale")
    MATCH = re.compile(r"The host copies match adoption/agents/claude: ~/\.claude/agents and \.claude/agents hold the "
                       r"same (\d+) definitions byte for byte and no host-only one "
                       r"\(`diff -rq`, exit 0, \d{4}-\d{2}-\d{2}\), which settles the stale note recorded in "
                       r"(docs/decisions/2026-10-13-claude-agent-drift-check\.md):(\d+)\.")

    def setUp(self):
        self.row = row("subagent-definitions")

    def test_the_row_states_the_copies_match(self):
        for stale in self.STALE:
            self.assertNotIn(stale, self.row["notes"])
        self.assertRegex(self.row["notes"], self.MATCH)

    def test_the_page_carries_the_corrected_row(self):
        text = section("workers.md", "subagent-definitions")
        for stale in self.STALE:
            self.assertNotIn(stale, text)
        self.assertIn(f"- **Notes:** {self.row['notes']}\n", text)

    def test_the_note_agrees_with_the_repository_copies_and_the_record_it_cites(self):
        found = self.MATCH.search(self.row["notes"])
        self.assertIsNotNone(found, "the corrected sentence is missing")
        count, record, line = int(found.group(1)), found.group(2), int(found.group(3))
        adopted = sorted(path.name for path in (ROOT / "adoption/agents/claude").iterdir() if path.is_file())
        project = sorted(path.name for path in (ROOT / ".claude/agents").iterdir() if path.is_file())
        self.assertEqual(adopted, project)
        self.assertEqual(len(adopted), count)
        for name in adopted:
            with self.subTest(definition=name):
                self.assertEqual((ROOT / "adoption/agents/claude" / name).read_bytes(),
                                 (ROOT / ".claude/agents" / name).read_bytes())
        cited = (ROOT / record).read_text(encoding="utf-8").split("\n")[line - 1]
        self.assertIn('"four host copies differ") is stale', cited)


if __name__ == "__main__":
    unittest.main()
