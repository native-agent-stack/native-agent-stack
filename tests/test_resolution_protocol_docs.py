"""Pin the CC-approved W6 session rule at its documentation boundary.

These checks protect agent-facing text; they do not execute research, certify a
layer FINAL, or enforce the future final-stack generator's lifecycle checks.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECORD = "docs/decisions/2026-10-11-layer-resolution-protocol.md"


class ResolutionProtocolDocsTests(unittest.TestCase):
    def record(self):
        return " ".join((ROOT / RECORD).read_text(encoding="utf-8").split())

    def assert_phrases(self, phrases, text=None):
        if text is None:
            text = self.record()
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_agents_rule_is_a_bounded_pointer_under_this_repository(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        rules = [line for line in text.splitlines()
                 if line.startswith("- **Layer resolution:**")]
        self.assertEqual(len(rules), 1, "AGENTS.md needs the W6 layer-resolution rule")
        rule = rules[0]
        section = text.partition("## This repository\n")[2].split("\n## ", 1)[0]
        self.assertIn(rule, section, "The pointer must be a repository rule")
        self.assertLessEqual(len((rule + "\n").encode("utf-8")), 283)
        for phrase in (
            "Before any research dispatch or comparison",
            "follow the",
            f"[resolution protocol]({RECORD})",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)
        self.assertTrue((ROOT / RECORD).is_file(), "The rule's decision record must resolve")

    def test_record_pins_dispatch_reopening_and_pending_sweep_append(self):
        decision = self.record().partition("## Decision")[2].partition("## Terminal states")[0]
        self.assert_phrases((
            "Before any research dispatch or comparison",
            "layer's catalog verdict",
            "latest sweep's survivors",
            "latest sweep covering the `(catalog, layer_id)`",
            "completed sweep awaiting its ledger append",
            "read its retained manifest and returns",
            "record that the ledger append is pending",
            "record an unresolved latest-sweep gap",
            "bound recovery to retaining and registering them",
            "An older ledger row cannot be treated as the latest sweep",
            "Reconstruct each candidate's latest adjudication from all prior sweeps",
            "Carry forward every unresolved survivor",
            "later omission and missing return do not clear it",
            "Dispatch only the delta",
            "FINAL layer reopens only when a sweep detects a change",
        ), decision)

    def test_final_requires_all_four_evidence_conditions(self):
        final = self.record().partition("## Terminal states and evidence")[2].partition("**SCHEDULED:**")[0]
        self.assert_phrases((
            "A layer is FINAL only when all of the following hold",
            "evidence class, verdict wave and `next_review`",
            "run pin in `catalogs/landscape/final-stack.json` `runs[]`",
            "upstream's own install and test path, at that pin",
            "Invoke evidence in the measured window",
            "or a recorded reason it isn't invoked",
            "wiring defect to fix, or a role to retire",
        ), final)

    def test_terminal_and_non_terminal_states_follow_the_cc_ruling(self):
        terminal = self.record().partition("## Terminal states and evidence")[2].partition("## Alternatives")[0]
        self.assert_phrases((
            "**Terminal states:** FINAL, SCHEDULED, RETIRED",
            "**SCHEDULED:** no winner",
            "**RETIRED:** the role is retired with a recorded reason",
            "**Non-terminal:** everything else",
        ), terminal)
        scheduled = terminal.partition("**SCHEDULED:**")[2].partition("**RETIRED:**")[0]
        self.assert_phrases((
            "ONE preregistered comparison with a date and a fixed decision rule",
            "comparison id, preregistration hash, run date and fixed decision rule",
            "becomes FINAL or RETIRED when the comparison runs and its rule applies",
            "A comparison that misses its date is a defect to fix",
        ), scheduled)
        non_terminal = terminal.partition("**Non-terminal:**")[2]
        self.assert_phrases((
            "`no_selection` must name its comparison in `open_gaps`",
            "comparison id, preregistration hash, run date and fixed decision rule",
            "No-winner without a scheduled comparison is not allowed",
            "still undecided cannot be a terminal state",
        ), non_terminal)

    def test_record_dates_the_authority_and_names_existing_harnesses(self):
        self.assert_phrases((
            "CC-approved W6 plan",
            "retained W6 snapshot",
            "fb4a95b19a00335c5831bce913cbf177f90d5bd2c17819013b6021d2dc585e5c",
            "after W4 PR 2",
            "promptfoo",
            "token-e2e",
            "cc-native-practice paired runs",
            "landscape-sweep comparisons",
        ))
        self.assertNotIn("Review of this PR requires", self.record())
        self.assertNotRegex(self.record().lower(), r"\bowner\b")
        self.assertNotIn("22b9f43b62cfeb458c25be0b4ccaf27601e78c71316aecdcded696d66afa5ea7", self.record())


if __name__ == "__main__":
    unittest.main()
