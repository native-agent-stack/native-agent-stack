"""Offline checks at the recipe's documented Claude command boundary; no model dispatch."""

from pathlib import Path
import re
import shlex
import unittest


REPO = Path(__file__).resolve().parents[1]


class BlindLaneLaunchTests(unittest.TestCase):
    def commands(self):
        recipe = (REPO / "recipes/sota-convergence-practice.md").read_text(encoding="utf-8")
        return re.findall(r'^\(cd "\$BLIND_DIR/export" && (.*?) > "\$WORK_DIR/[^"\n]+"\)',
                          recipe.replace("\\\n", " "), re.S | re.M)

    def check_controls(self, command):
        argv = shlex.split(command)
        at = argv.index("claude")
        with self.subTest(control="advisor"):
            self.assertIn("CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1", argv[:at])
        with self.subTest(control="MCP"):
            self.assertIn("--strict-mcp-config", argv[at + 1:])
            self.assertNotIn("--mcp-config", argv[at + 1:])

    def test_lane_launch_disables_advisor_and_loads_no_mcp(self):
        self.check_controls(self.commands()[0])

    def test_adjudication_launch_disables_advisor_and_loads_no_mcp(self):
        commands = self.commands()
        self.assertEqual(len(commands), 2, "lane and adjudication must both have concrete launch commands")
        self.check_controls(commands[1])


if __name__ == "__main__":
    unittest.main()
