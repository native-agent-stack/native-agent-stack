"""The claude.ai plugin sync row agrees with the template and names its exception record.

docs/decisions/2026-10-15-claudeai-synced-plugins-exception.md: the 2026-10-04 row said the sync was "off on both
hosts", but the template never set syncClaudeAiPlugins, and Claude Code honours only false (settings reference,
syncClaudeAiPlugins), so the sync was on and four plugins loaded. The row must say what the template does.
"""
import json
import string
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPOSITIONS = ROOT / "catalogs/foundation/upstream-surface-dispositions.json"
TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"
DECISION = "docs/decisions/2026-10-15-claudeai-synced-plugins-exception.md"
INVENTORY = ROOT / "evidence/artifacts/claudeai-synced-plugins-20261015/inventory.json"


class SyncedPluginsRowTests(unittest.TestCase):
    def row(self):
        rows = json.loads(DISPOSITIONS.read_text(encoding="utf-8"))["rows"]
        (row,) = [r for r in rows if r["key"] == "claude:setting:syncClaudeAiPlugins"]
        return row

    def template_sets_off(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        # Placeholder values do not matter here; safe_substitute leaves the JSON shape intact.
        settings = json.loads(string.Template(text).safe_substitute())
        return settings.get("syncClaudeAiPlugins") is False

    def test_the_row_says_off_only_when_the_template_sets_false(self):
        row = self.row()
        claims_off = row["disposition"] == "declined" or "off on both hosts" in row["reason"]
        self.assertEqual(claims_off, self.template_sets_off(), row)

    def test_an_unset_key_is_the_recorded_owner_synced_exception(self):
        if self.template_sets_off():
            self.skipTest("the template turns the sync off; the exception no longer applies")
        row = self.row()
        # 2026-10-15T05:07Z: the keep decision was superseded; the sync stays on by default and each plugin is disabled.
        self.assertEqual(row["disposition"], "default-on")
        self.assertIn("superseded in part on 2026-10-15T05:07Z", (ROOT / DECISION).read_text(encoding="utf-8"))
        self.assertIn("claude plugin disable <id> --scope user", (ROOT / DECISION).read_text(encoding="utf-8"))
        self.assertEqual(row["source"].rsplit(":", 1)[0], DECISION)
        decision = (ROOT / DECISION).read_text(encoding="utf-8")
        for plugin in json.loads(INVENTORY.read_text(encoding="utf-8"))["plugins"]:
            self.assertIn(f"`{plugin['name']}`", decision)
        self.assertIn("**Trigger:**", decision)


    def test_the_decision_states_the_measured_listing_cost(self):
        # Correction (2026-10-15T04:52Z, /skill-doctor at 2.1.300): the four synced plugins add about 8,450 tokens of skill
        # listing to every turn with 0 uses, so "nothing measurable" was wrong.
        decision = (ROOT / DECISION).read_text(encoding="utf-8")
        self.assertNotIn("cost nothing measurable", decision)
        cost = json.loads((INVENTORY.parent / "listing-cost.json").read_text(encoding="utf-8"))
        synced = sum(cost["by_source"][p]["listing_tokens"] for p in ("bigdata-com", "lseg", "daloopa", "cowork-plugin-management"))
        self.assertEqual(synced, cost["synced_total_tokens"])
        self.assertIn(f"{synced:,}", decision)

if __name__ == "__main__":
    unittest.main()
