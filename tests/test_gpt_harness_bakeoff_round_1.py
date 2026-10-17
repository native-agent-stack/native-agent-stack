"""The GPT-lane harness bake-off, round 1: the decision record, the scores and the ranking agree.

docs/decisions/2026-10-17-gpt-harness-bakeoff-round-1.md carries the measured table; evidence/artifacts/gpt-harness-bakeoff-20261017/
holds the scores and ranking it is derived from. Every test here fails on the base commit, where none of the three files exists.
The tests pin the record to the data, not the data to the world: they do not re-run a harness.
"""
import json
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/artifacts/gpt-harness-bakeoff-20261017"
DECISION = ROOT / "docs/decisions/2026-10-17-gpt-harness-bakeoff-round-1.md"
ORDER = ["codex-exec", "pi", "opencode", "kilo", "oh-my-pi", "goose", "openhands", "deerflow"]
# Shapes of private locators, case-insensitive: home, scratch and run-time paths (the repository's host-name scan, validate.py
# --scan-file, covers the names themselves).
PRIVATE = re.compile(r"/home/\S|/var/tmp/|/tmp/claude-\d|/run/user/\d", re.I)
# A scheduling date in a comparison's readiness trigger would break the protocol's no-date rule.
SCHEDULING_DATES = re.compile(
    r"(?i)\b(?:run|due|target|scheduled|execution|start|end|comparison)\s+dates?\b|\bdeadlines?\b|\bwith a date\b|\bdated comparison\b")


def half_up(value):
    return math.floor(value + 0.5)


def scores():
    return json.loads((EVIDENCE / "SCORES.json").read_text(encoding="utf-8"))


def table_rows(text):
    return [line for line in text.splitlines() if line.startswith("| ")]


class GptHarnessBakeoffRound1Tests(unittest.TestCase):
    def setUp(self):
        self.decision = DECISION.read_text(encoding="utf-8")
        self.flat = " ".join(self.decision.split())
        self.scores = scores()

    def test_the_published_files_exist_and_carry_no_private_locator(self):
        for path in (EVIDENCE / "SCORES.json", EVIDENCE / "RANKING.md", DECISION):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                self.assertIsNone(PRIVATE.search(path.read_text(encoding="utf-8")), path.name)

    def test_every_decision_table_row_is_derived_from_the_scores(self):
        rows = table_rows(self.decision)
        for harness in ORDER:
            t1, t2 = self.scores["harnesses"][harness]["T1"], self.scores["harnesses"][harness]["T2"]
            label = harness + (" (baseline)" if harness == "codex-exec" else "")
            expected = (f"| {label} | {t1['correct']}/{t1['of']} | {t1['median_wall_s']:.1f} | "
                        f"{half_up(t1['median_tokens_in_plus_out']):,} | {t2['correct']}/{t2['of']} | "
                        f"{t2['t2_file_and_tests_ok']}/{t2['of']} | {t2['median_wall_s']:.1f} | "
                        f"{half_up(t2['median_tokens_in_plus_out']):,} |")
            with self.subTest(harness=harness):
                self.assertIn(expected, rows)

    def test_the_ranking_table_rows_agree_with_the_scores(self):
        ranking = (EVIDENCE / "RANKING.md").read_text(encoding="utf-8")
        for harness in ORDER:
            for task in ("T1", "T2"):
                run = self.scores["harnesses"][harness][task]
                label = harness + (" (baseline)" if harness == "codex-exec" else "")
                cell = f"| {label} | {run['correct']}/{run['of']} | {run['median_wall_s']:.1f} | {half_up(run['median_tokens_in_plus_out']):,}"
                self.assertIn(cell, ranking, (harness, task))

    def test_all_sixteen_edit_and_test_clones_were_correct(self):
        for harness in ORDER:
            t2 = self.scores["harnesses"][harness]["T2"]
            self.assertEqual(t2["t2_file_and_tests_ok"], 2, harness)
            self.assertTrue(all(run["state_and_tests_ok"] for run in t2["per_run"]), harness)
        self.assertIn("All 16 edit-and-test clones were correct", self.flat)

    def test_the_wrong_reply_count_matches_the_runs(self):
        wrong = sum(1 for harness in ORDER for run in self.scores["harnesses"][harness]["T2"]["per_run"] if not run["reply_correct"])
        self.assertEqual(wrong, 8)
        self.assertIn("Eight of the 16 T2 replies", self.flat)
        self.assertIn("The eight wrong T2 replies left a correct file", self.flat)

    def test_goose_has_exactly_one_failed_run(self):
        failed = [(harness, task, run["rep"]) for harness in ORDER for task in ("T1", "T2")
                  for run in self.scores["harnesses"][harness][task]["per_run"] if run["exit"] != 0]
        self.assertEqual(failed, [("goose", "T1", 1)])

    def test_the_record_names_each_caveat_and_each_untested_boundary(self):
        for phrase in ("n = 2 per task per harness", "indicative only", "`thinkingLevelMap`", "`--no-extensions --no-mcp --no-skills --no-context-files`",
                       "directly rather than through `codex_call.sh`", "Effort is verified for pi only", "stream-decode failure",
                       "multi-file edits, long runs, tool-heavy tasks, failure recovery, concurrency, sandbox"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.flat)

    def test_the_outcome_is_a_proposal_that_changes_no_default(self):
        for phrase in ("Status: measurement recorded; the outcome is a **proposal**", "`codex exec` (through the Codex runner",
                       "stays the default and the fallback", "pi is a measured fast-path candidate for bounded read-and-edit jobs",
                       "may not become a default", "`AGENTS.md:7` requires a converged harness with its full layers",
                       "not a preregistered comparison"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.flat)

    def test_round_two_has_a_dateless_trigger_a_fixed_rule_and_the_agreed_design(self):
        round_two = " ".join(self.decision.split("## Round 2 (the delta)", 1)[1].split("\n## ", 1)[0].split())
        self.assertIsNone(SCHEDULING_DATES.search(round_two))
        self.assertIsNone(re.search(r"\b20\d\d-\d\d-\d\d\b", round_two))
        for phrase in ("**Readiness trigger (named inputs, no date):**", "tools/adoption/runtime_profiles.py", "multi-file edit",
                       "long tool-heavy task", "concurrency task", "n of at least 3", "Uniform token accounting", "Effort verified per runtime",
                       "**Fixed decision rule:**"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, round_two)

    def test_the_cited_profile_code_still_admits_only_the_old_pins(self):
        source = (ROOT / "tools/adoption/runtime_profiles.py").read_text(encoding="utf-8")
        self.assertIn('{"pi": "1.1.0", "opencode": "1.18.35"}[runtime]', source)

    def test_the_cited_decision_links_resolve(self):
        for target in re.findall(r"\]\(([^)#]+\.md)\)", self.decision):
            with self.subTest(target=target):
                self.assertTrue((DECISION.parent / target).is_file(), target)


if __name__ == "__main__":
    unittest.main()
