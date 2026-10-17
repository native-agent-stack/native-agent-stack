"""The headless-sdk row does not offer the fork toggle as a fan-out control (the GPT read of #1234 at 887f929c, P1).

CHANGELOG@v2.1.302 L35: `CLAUDE_CODE_FORK_SUBAGENT=0` turns off fork subagents (`subagent_type: "fork"`); it does not
turn off named subagents. So a worker that must not fan out keeps Agent out of `--tools`, and the toggle is described as
fork-only. The page's Route line must mirror the slots.json row.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"


class ForkToggleScope(unittest.TestCase):
    def setUp(self):
        slots = json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"]
        self.route = next(s for s in slots if s["id"] == "headless-sdk")["route"]

    def test_the_toggle_is_not_an_alternative_to_removing_agent(self):
        self.assertNotIn("or set `CLAUDE_CODE_FORK_SUBAGENT=0` for a worker that must not fan out", self.route)
        self.assertIn("a worker that must not fan out keeps Agent out of `--tools`", self.route)
        self.assertIn("`CLAUDE_CODE_FORK_SUBAGENT=0` turns off fork subagents only (L35), not named subagents", self.route)

    def test_the_page_mirrors_the_row(self):
        self.assertIn(f"- **Route:** {self.route}\n", (REF / "agent-sdks.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
