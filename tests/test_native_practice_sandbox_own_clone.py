"""The isolation and client-core rows carry the command center's 2026-10-15 rulings on the vendor sandbox's side effects.

On 2026-10-14/15 sandboxed Claude Code runs in worktrees of the shared repository left `.git/config.lock`, an empty read-only
placeholder that bwrap creates for a write-protected path that does not exist, in the shared `.git`. While it existed every
lane's git config writes failed (`could not lock config file`). The 2.1.300 binary's sandbox write-protects `.git/config`,
`.git/config.lock`, `.git/config.worktree(.lock)`, `.git/hooks`, `.git/worktrees` and more, and a worktree's common directory
is the main `.git`. The command center adopted the own-clone rule; the same runs left placeholders under
C:\\Program Files\\ClaudeCode, which the client-core row watches. CHANGELOG 2.1.98 adds a PID-namespace subprocess sandbox
when CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set, which a measured run showed independent of sandbox.enabled. These checks pin
that the rows say so, on both surfaces a session reads (slots.json and the layer page).
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".claude/skills/claude-native-practice/reference"


def page_notes(page: str, slot_id: str) -> str:
    section = page.split(f"\n## {slot_id}\n", 1)[1].split("\n## ", 1)[0]
    notes = [line[len("- **Notes:** "):] for line in section.splitlines() if line.startswith("- **Notes:** ")]
    assert len(notes) == 1, (slot_id, len(notes))
    return notes[0]


class SandboxSideEffectRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slots = {s["id"]: s for s in json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]}

    def test_the_sandbox_row_carries_the_own_clone_rule_on_both_surfaces(self):
        notes = self.slots["sandbox"]["notes"]
        self.assertEqual(notes, page_notes((REFERENCE / "isolation.md").read_text(encoding="utf-8"), "sandbox"))
        for phrase in ("own clone", "never in the shared main checkout or one of its worktrees", ".git/config.lock",
                       "removed with its stat recorded", "persists more than 10 minutes"):
            self.assertIn(phrase, notes)

    def test_the_sandbox_row_names_the_env_scrub_subprocess_sandbox(self):
        notes = self.slots["sandbox"]["notes"]
        self.assertIn("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", notes)
        self.assertIn("CHANGELOG 2.1.98", notes)
        self.assertRegex(notes, r"whatever sandbox\.enabled says")

    def test_the_client_core_row_watches_the_windows_placeholders(self):
        notes = self.slots["client-core"]["notes"] or ""
        self.assertEqual(notes, page_notes((REFERENCE / "native-clients.md").read_text(encoding="utf-8"), "client-core"))
        self.assertIn("managed-settings.d", notes)
        self.assertTrue(re.search(r"re-check when the Windows client is next upgraded", notes), notes)


if __name__ == "__main__":
    unittest.main()
