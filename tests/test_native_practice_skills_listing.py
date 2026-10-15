"""The skills-library row of the claude-native-practice skill records the 2026-10-15 plugin dispositions and states what
`syncClaudeAiSkills` does.

Before this change the row's notes ended at the 2026-10-13 plugin exception, and its first rejection read
"`syncClaudeAiSkills: true` (synced skills bypass the pinned manifest)", as if `true` turned the sync on. The settings
reference (`syncClaudeAiSkills`, client 2.1.300, fetched 2026-10-15) says `true` is the same as unset and that unset
syncs; only `false` turns it off. Each check pins one fact on both surfaces a session reads, reference/slots.json and
its layer page instructions-skills.md, and checks it against the repository file it rests on where there is one:
the agent definition that preloads typesafe-ai, the settings template, and the dated measurements under
evidence/artifacts/skills-listing-20261015. Repository-text checks only: no client runs here.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".claude/skills/claude-native-practice/reference"
ARTIFACTS = ROOT / "evidence/artifacts/skills-listing-20261015"
SYNC_REJECTION = ("Leaving `syncClaudeAiSkills` unset or `true` (both sync the claude.ai account's skills, which bypass the pinned "
                  "manifest; settings-reference `syncClaudeAiSkills`, client 2.1.300); the template and user settings set `false`")
CHANGELOG_PIN = "anthropics/claude-code CHANGELOG.md at 94506ff0d3bd9185f1752da36e968775021fb48f"


def flat(text: str) -> str:
    return " ".join(text.split())


class SkillsLibraryRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slot = next(slot for slot in json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]
                        if slot["id"] == "skills-library")
        page = (REFERENCE / "instructions-skills.md").read_text(encoding="utf-8")
        section = page.split("\n## skills-library\n", 1)[1].split("\n## ", 1)[0]
        cls.page_lines = {match.group(1): match.group(2) for match in re.finditer(r"^- \*\*(.+?):\*\* (.*)$", section, re.M)}
        cls.notes = flat(cls.slot["notes"])

    def test_the_layer_page_mirrors_the_row(self):
        self.assertEqual(self.page_lines["Notes"], self.slot["notes"])
        self.assertEqual(self.page_lines["Rejected"], "; ".join(self.slot["rejections"]))

    def test_a_the_built_in_claude_api_skill_supersedes_the_plugin_copy(self):
        for needle in ("The built-in claude-api skill supersedes the claude-api@anthropic-agent-skills plugin copy, disabled 2026-10-15T05:07Z",
                       CHANGELOG_PIN, "L7009, 2.1.69: \"Added the `/claude-api` skill\"",
                       "L3528, 2.1.234: its load cut to ~25k tokens by loading reference docs on demand"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.notes)

    def test_b_the_typesafe_plugin_duplicate_is_off_and_the_preloaded_user_skill_stays(self):
        self.assertIn("The typesafe@typesafe-ai plugin, a duplicate of the manifest-pinned user skill typesafe-ai (15 uses against the "
                      "plugin copy's 0), was disabled the same day; typesafe-ai stays, because semantic-evidence-reviewer preloads it.",
                      self.notes)
        agent = (ROOT / ".claude/agents/semantic-evidence-reviewer.md").read_text(encoding="utf-8")
        frontmatter = agent.split("---\n", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^skills:\n  - typesafe-ai$")
        manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text(encoding="utf-8"))
        self.assertIn("typesafe-ai", {skill["name"] for skill in manifest["skills"]})

    def test_c_the_synced_plugins_are_off(self):
        self.assertIn("The claude.ai synced plugins bigdata-com, lseg, daloopa and cowork-plugin-management were disabled "
                      "(#1138: 8,450 of the table's 16,490 context tokens, 0 uses).", self.notes)

    def test_d_the_double_row_is_one_listing_recorded_and_rechecked(self):
        attachments = json.loads((ARTIFACTS / "listing-attachments.json").read_text(encoding="utf-8"))
        clients = sorted(attachments["by_client"])
        for client in clients:
            with self.subTest(client=client):
                counts = attachments["by_client"][client]
                self.assertGreater(counts["initial_listings"], 0)
                self.assertEqual(counts["naming_it_once"], counts["initial_listings"])
                self.assertEqual(counts["names_unique"], counts["initial_listings"])
        total = sum(counts["initial_listings"] for counts in attachments["by_client"].values())
        named = ", ".join(clients[:-1]) + f" and {clients[-1]}"
        for needle in ("/skill-doctor prints claude-native-practice twice, from userSettings and from projectSettings, at ~130 context "
                       "tokens on each row (measured 2026-10-15)",
                       "the 2.1.300 client builds the skill listing unique by name and prints the name's one estimate on every row",
                       f"all {total} initial skill_listing attachments of this repository's sessions since the personal copy appeared "
                       f"(clients {named}) name it once, so the second row costs no listing tokens",
                       "evidence/artifacts/skills-listing-20261015",
                       "option (a) stands: no setting change, ~130 tokens/turn for the one listing, re-checked each release."):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.notes)
        rows = json.loads((ARTIFACTS / "skill-doctor-rows.json").read_text(encoding="utf-8"))
        listed = [(row["source"], row["context_tokens"]) for row in rows["rows"] if row["skill"] == "claude-native-practice"]
        self.assertEqual(listed, [("userSettings", 130), ("projectSettings", 130)])
        self.assertEqual([entry["name"] for entry in rows["derived"]["duplicate_listings"]], ["claude-native-practice"])

    def test_the_sync_rejection_states_what_the_setting_does(self):
        self.assertEqual(self.slot["rejections"][0], SYNC_REJECTION)
        self.assertFalse([item for item in self.slot["rejections"] if "`syncClaudeAiSkills: true`" in item])
        template = json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8"))
        self.assertIs(template["syncClaudeAiSkills"], False)


if __name__ == "__main__":
    unittest.main()
