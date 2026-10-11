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

    def test_terminal_section_is_pinned_exactly(self):
        terminal = self.record().partition("## Terminal states and evidence")[2].partition("## Alternatives")[0]
        expected = """
**Terminal states:** FINAL, SCHEDULED, RETIRED.

Before choosing a terminal state, record the disposition of the cumulative
unresolved survivor set: adjudicate it, include it in the frozen comparison, or
record the reason its role is retired. A later sweep's omission cannot provide
that disposition.

A layer is FINAL only when all of the following hold for each of its winners:

1. A recorded verdict with its evidence class, verdict wave and `next_review`.
2. Each winner has a run pin in `catalogs/landscape/final-stack.json` `runs[]`.
3. An E2E receipt through the upstream's own install and test path, at that pin.
4. Invoke evidence in the measured window (adoption-now), or a recorded reason
   it isn't invoked. A zero-call tool is a wiring defect to fix, or a role to
   retire; installation alone is not invoke evidence.

**SCHEDULED:** no winner because evidence cannot settle the layer; commit to
ONE preregistered comparison with a readiness trigger and a fixed decision rule. Retain its
comparison id, preregistration hash, readiness trigger and fixed decision rule, plus the
frozen scope, before the run. SCHEDULED is terminal for the wave: its decision
procedure is fixed, so the layer waits for its named inputs rather than being relaunched.
A readiness trigger names the inputs whose existence starts the run, with no date.
The comparison starts as soon as those inputs exist.
A comparison whose inputs exist and has not run is a defect.
This is not a reason to re-research.
The term SCHEDULED stays for compatibility and means a comparison pending its named inputs.
It becomes FINAL or RETIRED when the comparison runs and its rule applies.
Preregistered protocol windows, including the holdout boundary and the model seal
before forward scoring, are data-range rules, not schedules.
Use the existing W5 harnesses: promptfoo, token-e2e, cc-native-practice paired runs
and landscape-sweep comparisons; introduce another only through its adoption
decision.

**RETIRED:** the role is retired with a recorded reason (condition 4); retirement
does not claim a qualified winner or an E2E adoption.

**Non-terminal:** everything else, including pending lanes, reopened, unswept,
`no_selection` or no-winner without a scheduled comparison, and still undecided.
`no_selection` must name its comparison in `open_gaps`, including the comparison
id, preregistration hash, readiness trigger and fixed decision rule above, to qualify as
SCHEDULED. No-winner without a scheduled comparison is not allowed;
still undecided cannot be a terminal state. A catalog status alone is not a
terminal state.

The W6 plan assigns machine enforcement of FINAL to a follow-up
`scripts/final_stack.py --check` after W4 PR 2. At this base those files
are not present; this decision does not claim that generator has run or that
any layer is FINAL. The existing catalog statuses (`pending_lanes`, `recorded`,
`no_selection`) retain their meanings and are not aliases for FINAL.
K=3 saturation remains a separate sweep count, not a FINAL verdict or a claim
that this wave reached saturation.
"""
        self.assertEqual(terminal.strip(), " ".join(expected.split()))

    def test_record_rejects_scheduling_dates(self):
        self.assertNotRegex(
            self.record(),
            r"(?i)\b(?:run|due|target|scheduled|execution|start|end|comparison)\s+dates?\b"
            r"|\bdeadlines?\b|\bwith a date\b|\bmisses its date\b|\bdated comparison\b",
        )

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
