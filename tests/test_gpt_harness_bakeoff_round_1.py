"""The GPT-lane harness bake-off, round 1: the decision record, the scores and the ranking agree.

docs/decisions/2026-10-17-gpt-harness-bakeoff-round-1.md carries the measured table; evidence/artifacts/gpt-harness-bakeoff-20261017/
holds the scores and ranking it is derived from. The fold tests also bind the cache-normalized
figures to a public usage extract and reject incomplete runs or stale aggregates.
These are publication checks: they do not re-run a harness or qualify a runtime profile.
"""
import copy
import hashlib
import json
import math
import re
import runpy
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/artifacts/gpt-harness-bakeoff-20261017"
DECISION = ROOT / "docs/decisions/2026-10-17-gpt-harness-bakeoff-round-1.md"
ORDER = ["codex-exec", "pi", "opencode", "kilo", "oh-my-pi", "goose", "openhands", "deerflow"]
# Shapes of private locators, case-insensitive: home, scratch and run-time paths (the repository's host-name scan, validate.py
# --scan-file, covers the names themselves).
PRIVATE = re.compile(r"/(?:home|Users)/\S|/(?:var/)?tmp/|/run/user/\d", re.I)
# A scheduling date in a comparison's readiness trigger would break the protocol's no-date rule.
SCHEDULING_DATES = re.compile(
    r"(?i)\b(?:run|due|target|scheduled|execution|start|end|comparison)\s+dates?\b|\bdeadlines?\b|\bwith a date\b|\bdated comparison\b")


def half_up(value):
    return math.floor(value + 0.5)


def scores():
    return json.loads((EVIDENCE / "SCORES.json").read_text(encoding="utf-8"))


def checker():
    return runpy.run_path(str(EVIDENCE / "recompute.py"))


def table_rows(text):
    return [line for line in text.splitlines() if line.startswith("| ")]


class GptHarnessBakeoffRound1Tests(unittest.TestCase):
    def setUp(self):
        self.decision = DECISION.read_text(encoding="utf-8")
        self.flat = " ".join(self.decision.split())
        self.scores = scores()

    def test_the_published_files_exist_and_carry_no_private_locator(self):
        for path in (EVIDENCE / "SCORES.json", EVIDENCE / "RANKING.md", EVIDENCE / "T2-USAGE.json",
                     EVIDENCE / "ROUND2-PREREGISTRATION.json", EVIDENCE / "recompute.py", DECISION):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                self.assertIsNone(PRIVATE.search(path.read_text(encoding="utf-8")), path.name)

    def test_every_decision_table_row_is_derived_from_the_scores(self):
        derived = checker()["validate_scores"](self.scores)
        rows = table_rows(self.decision)
        for harness in ORDER:
            t1, t2 = derived[harness]["T1"], derived[harness]["T2"]
            label = harness + (" (baseline)" if harness == "codex-exec" else "")
            expected = (f"| {label} | {t1['correct']}/{t1['of']} | {t1['median_wall_s']:.1f} | "
                        f"{half_up(t1['median_tokens_in_plus_out']):,} | {t2['correct']}/{t2['of']} | "
                        f"{t2['t2_file_and_tests_ok']}/{t2['of']} | {t2['median_wall_s']:.1f} | "
                        f"{half_up(t2['median_tokens_in_plus_out']):,} |")
            with self.subTest(harness=harness):
                self.assertIn(expected, rows)

    def test_the_ranking_table_rows_agree_with_the_scores(self):
        derived = checker()["validate_scores"](self.scores)
        ranking = (EVIDENCE / "RANKING.md").read_text(encoding="utf-8")
        for harness in ORDER:
            for task in ("T1", "T2"):
                run = derived[harness][task]
                label = harness + (" (baseline)" if harness == "codex-exec" else "")
                cell = f"| {label} | {run['correct']}/{run['of']} | {run['median_wall_s']:.1f} | {half_up(run['median_tokens_in_plus_out']):,}"
                self.assertIn(cell, ranking, (harness, task))

    def test_all_sixteen_edit_and_test_clones_were_correct(self):
        derived = checker()["validate_scores"](self.scores)
        for harness in ORDER:
            t2 = derived[harness]["T2"]
            self.assertEqual(t2["t2_file_and_tests_ok"], 2, harness)
        self.assertEqual(sum(derived[h]["T2"]["of"] for h in ORDER), 16)
        self.assertIn("All 16 edit-and-test clones were correct", self.flat)

    def test_the_wrong_reply_count_matches_the_runs(self):
        usage = json.loads((EVIDENCE / "T2-USAGE.json").read_text(encoding="utf-8"))
        checker()["validate_usage"](self.scores, usage)
        wrong = sum(1 for harness in ORDER for run in self.scores["harnesses"][harness]["T2"]["per_run"] if not run["reply_correct"])
        self.assertEqual(wrong, 8)
        for harness in ORDER:
            wrong_reps = [run["rep"] for run in usage["harnesses"][harness]["per_run"]
                          if run["reply"]["changed_line"] == 141]
            self.assertEqual(wrong_reps, {"opencode": [2], "kilo": [1, 2], "oh-my-pi": [1, 2],
                                         "openhands": [2], "deerflow": [1, 2]}.get(harness, []))
        self.assertIn("Eight of the 16 T2 replies", self.flat)
        self.assertIn("The eight wrong T2 replies left a correct file", self.flat)

    def test_missing_or_duplicate_runs_cannot_certify_sixteen_clones(self):
        validate = checker()["validate_scores"]
        for task in ("T1", "T2"):
            for mutation in ("empty", "missing", "duplicate", "wrong_of"):
                broken = copy.deepcopy(self.scores)
                record = broken["harnesses"]["pi"][task]
                if mutation == "empty":
                    record["per_run"] = []
                elif mutation == "missing":
                    record["per_run"].pop()
                elif mutation == "duplicate":
                    record["per_run"][1]["rep"] = 1
                else:
                    record["of"] = 1
                with self.subTest(task=task, mutation=mutation), self.assertRaises(ValueError):
                    validate(broken)

    def test_stale_aggregates_and_changed_measurements_are_rejected(self):
        validate = checker()["validate_scores"]
        for field in ("wall_s", "tokens_in", "tokens_out", "reply_correct", "state_and_tests_ok"):
            broken = copy.deepcopy(self.scores)
            task = "T2" if field == "state_and_tests_ok" else "T1"
            run = broken["harnesses"]["pi"][task]["per_run"][0]
            run[field] = False if isinstance(run[field], bool) else 10000
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(broken)

    def test_cache_normalized_medians_and_accounting_are_published(self):
        usage = json.loads((EVIDENCE / "T2-USAGE.json").read_text(encoding="utf-8"))
        medians = checker()["validate_usage"](self.scores, usage)
        inclusive = {"codex-exec", "goose", "openhands", "deerflow"}
        for harness in ORDER:
            with self.subTest(harness=harness):
                record = usage["harnesses"][harness]
                self.assertEqual(record["input_includes_cached"], harness in inclusive)
                self.assertIn(f"| {harness} | {medians[harness]:,.1f} |", self.decision)
        self.assertEqual(sorted(medians, key=medians.get)[:4], ["deerflow", "goose", "kilo", "pi"])
        note = self.scores["notes"][2]
        ranking = (EVIDENCE / "RANKING.md").read_text(encoding="utf-8")
        for text in (note, ranking, self.flat):
            self.assertIn("codex-exec, deerflow, goose and OpenHands include cached input", text)
            self.assertIn("pi, OpenCode, Kilo and oh-my-pi report uncached input", text)

    def test_prose_time_figures_are_derived_and_t1_cache_cause_is_unconfirmed(self):
        derived = checker()["validate_scores"](self.scores)
        for task in ("T1", "T2"):
            pi = derived["pi"][task]["median_wall_s"]
            baseline = derived["codex-exec"][task]["median_wall_s"]
            self.assertIn(f"{task} {pi:.1f} s against {baseline:.1f} s", self.flat)
        self.assertIn("T1 baseline event logs are not retained", self.flat)
        self.assertIn("cold-then-warm cache is an untested explanation", self.flat)
        self.assertIn("T2 only", self.flat)
        ranking = (EVIDENCE / "RANKING.md").read_text(encoding="utf-8")
        self.assertIn("cold-cache attribution is unconfirmed", ranking)

    def test_resolution_records_the_survivors_refutations_and_missing_wave(self):
        ledger = json.loads((ROOT / "catalogs/saturation/ledger.json").read_text(encoding="utf-8"))
        sweep = next(s for s in ledger["sweeps"] if s["sweep_id"] == "landscape-sweep-20260929")
        layer = next(row for row in sweep["layers"] if row["layer_id"] == "agent-sdks" and row["catalog"] == "foundation")
        for key in ("survived", "refuted"):
            for repo in (["github/copilot-sdk", "agentproto/ts"] if key == "survived"
                         else ["earendil-works/pi", "openhands/software-agent-sdk"]):
                self.assertIn("https://github.com/" + repo, [r["repo"] for r in layer[key]])
                self.assertIn(f"`{repo}`", self.flat)
        self.assertIn("`layer-verdict-waves.json` has no `agent-sdks` entry", self.flat)
        self.assertIn("requires the protocol's reopen on this new evidence", self.flat)

    def test_upstream_citations_do_not_overstate_pi_or_omit_runner_flags(self):
        for phrase in ("--skip-git-repo-check", '-c web_search="live"', "host-observed only",
                       "does not ask for approval before every tool call", "no built-in sandbox",
                       "protocol.rs:1357"):
            self.assertIn(phrase, self.flat)
        self.assertNotIn("no OS sandbox or approval gate", self.flat)
        self.assertNotIn("reasoning` marks a model that thinks", self.flat)

    def test_t1_alternates_and_durable_decision_sections_are_complete(self):
        proposal = self.flat.split("## Proposal (not adopted)", 1)[1].split("## Round 2", 1)[0]
        for harness in ("opencode", "kilo", "oh-my-pi", "deerflow", "OpenHands"):
            self.assertIn(harness, proposal)
        for heading in ("## Alternatives considered", "## Inverse", "## Overturn condition"):
            self.assertIn(heading, self.decision)

    def test_substitutions_are_declared_for_the_corrected_evidence(self):
        privacy = self.flat.split("## Public copies and privacy", 1)[1].split("## Verification", 1)[0]
        for phrase in ("`notes[2]`", "token-accounting bullet", "cold-cache attribution", "host-observed"):
            self.assertIn(phrase, privacy)

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
        for phrase in ("write-capable baseline", "edit-and-test smoke", "profile-adoption decision",
                       "preregistration hash", "frozen scope", "not SCHEDULED"):
            self.assertIn(phrase, round_two)
        path = EVIDENCE / "ROUND2-PREREGISTRATION.json"
        registration = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn(registration["comparison_id"], round_two)
        self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), round_two)
        self.assertEqual(set(registration["scope"]["arms"]), set(ORDER))
        for arm in registration["scope"]["arms"].values():
            self.assertTrue(arm["write_mode_path"])
            self.assertIn("edit-and-test smoke", arm["readiness"])

    def test_the_cited_profile_code_still_admits_only_the_old_pins(self):
        source = (ROOT / "tools/adoption/runtime_profiles.py").read_text(encoding="utf-8")
        self.assertIn('{"pi": "1.1.0", "opencode": "1.18.35"}[runtime]', source)

    def test_the_cited_decision_links_resolve(self):
        for target in re.findall(r"\]\(([^)#]+\.md)\)", self.decision):
            with self.subTest(target=target):
                self.assertTrue((DECISION.parent / target).is_file(), target)


if __name__ == "__main__":
    unittest.main()
