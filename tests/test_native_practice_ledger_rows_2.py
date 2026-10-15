"""Practice rows from the 2026-10-15 guide screen (items 15, 35, 60) and the effortLevel origin record (item 42).

Sources at client 2.1.300: CHANGELOG 2.1.288 (`/code-review --max-findings`, reused until `default`), 2.1.296
(`CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL`), settings-reference `extraKnownMarketplaces` (trust-gated in a repository;
`autoUpdate` defaults true for official Anthropic marketplaces and false for third-party ones), and PR #479 (squash
ba31dcd02, 2026-09-29) for the project settings' effortLevel xhigh.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"


def row(slot_id):
    return next(s for s in json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"] if s["id"] == slot_id)


class LedgerRowsWave2(unittest.TestCase):
    def test_code_review_runs_pass_max_findings_explicitly(self):
        self.assertIn("--max-findings", row("pr-review-pre-cue")["notes"])
        self.assertIn("CHANGELOG 2.1.288", row("pr-review-pre-cue")["notes"])

    def test_marketplace_autoupdate_and_trust_are_recorded(self):
        notes = row("plugin-marketplaces")["notes"]
        self.assertIn("autoUpdate", notes)
        self.assertIn("third-party marketplaces default to false", notes)
        self.assertIn("workspace trust", notes)

    def test_the_workflow_subagent_model_override_stays_unset(self):
        route = row("model-effort-routing")["route"]
        self.assertIn("CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL", route)

    def test_the_project_effort_level_origin_is_recorded(self):
        notes = row("model-effort-routing")["notes"]
        self.assertIn("#479", notes)
        self.assertIn("docs/decisions/2026-09-29-sonnet-5-5-dispatch.md", notes)

    def test_the_pages_render_the_rows(self):
        for slot_id, page in (("pr-review-pre-cue", "git-github-automation.md"), ("plugin-marketplaces", "instructions-skills.md"),
                              ("model-effort-routing", "native-clients.md")):
            text = (REF / page).read_text(encoding="utf-8")
            with self.subTest(slot=slot_id):
                self.assertIn(f"- **Notes:** {row(slot_id)['notes']}\n", text)
                self.assertIn(f"- **Route:** {row(slot_id)['route']}\n", text)


if __name__ == "__main__":
    unittest.main()
