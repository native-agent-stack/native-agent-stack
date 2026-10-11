"""Pin the CC-approved W6 session rule at its documentation boundary.

These checks protect agent-facing text; they do not execute research, certify a
layer FINAL, or enforce the future final-stack generator's lifecycle checks.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECORD = "docs/decisions/2026-10-11-layer-resolution-protocol.md"


class ResolutionProtocolDocsTests(unittest.TestCase):
    def test_agents_rule_pins_the_pre_dispatch_and_reopen_contract(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        rules = [line for line in text.splitlines()
                 if line.startswith("- **Layer resolution:**")]
        self.assertEqual(len(rules), 1, "AGENTS.md needs the W6 layer-resolution rule")
        rule = rules[0]
        for phrase in (
            "Before any research dispatch or comparison",
            "layer's catalog verdict",
            "latest sweep's survivors",
            "dispatch only the delta",
            "FINAL layer reopens only when a sweep detects a change",
            f"[resolution protocol]({RECORD})",
            "terminal states",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)
        self.assertTrue((ROOT / RECORD).is_file(), "The rule's decision record must resolve")


if __name__ == "__main__":
    unittest.main()
