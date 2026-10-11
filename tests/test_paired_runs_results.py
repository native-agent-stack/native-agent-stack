"""The paired-run results of 2026-10-10 recompute from their artifact, and the skill's rows say what the artifact shows.

evidence/artifacts/native-practice-paired-runs-20261010/paired-runs.json holds the per-run rows of each paired run (hidden-test result, sessions, cost, lost-work count), the
decision rule's inputs and the sha256 of every private paper the results rest on. The rows of the claude-native-practice skill (reference/slots.json) and the record's addendum
(docs/decisions/2026-10-09-claude-code-native-practice.md) state the decisions; each statement here is derived from the artifact, so a row that drifts from the data, or an artifact
whose rows no longer give the decision it records, fails. Repository-text checks only: the private papers and transcripts are not in the repository.
"""

from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_REL = "evidence/artifacts/native-practice-paired-runs-20261010/paired-runs.json"
SLOTS = ROOT / ".claude/skills/claude-native-practice/reference/slots.json"
RECORD = ROOT / "docs/decisions/2026-10-09-claude-code-native-practice.md"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CELLS = [("F5", 1), ("F6", 1), ("F5", 2), ("F6", 2)]


def decision_from_runs(runs: list[dict]) -> dict:
    """The preregistered rule of paired run 2b, from the per-run rows alone: B or C replaces A only when it passes at least as many runs as A and uses fewer sessions or less cost in a
    majority of the counted fixture-trial cells (a cell counts when at least one of the two compared runs passes), with no more lost-work events than A."""
    by = {(r["fixture"], r["trial"], r["arm"]): r for r in runs}
    out = {}
    for arm in "BC":
        wins, counted, won_cells = 0, 0, []
        for fixture, trial in CELLS:
            a, other = by[(fixture, trial, "A")], by[(fixture, trial, arm)]
            if not (a["resolved"] or other["resolved"]):
                continue
            counted += 1
            if other["sessions_used"] < a["sessions_used"] or other["cost_usd_list_equivalent"] < a["cost_usd_list_equivalent"]:
                wins += 1
                won_cells.append(f"{fixture}-t{trial}")
        mine = [r for r in runs if r["arm"] == arm]
        a_runs = [r for r in runs if r["arm"] == "A"]
        out[arm] = {"passes": sum(r["resolved"] for r in mine), "a_passes": sum(r["resolved"] for r in a_runs), "counted_cells": counted, "cell_wins": wins,
                    "won_cells": won_cells, "majority": wins * 2 > counted, "lost_work_events": sum(r["lost_work_events"] for r in mine),
                    "a_lost_work_events": sum(r["lost_work_events"] for r in a_runs)}
        out[arm]["replaces_a"] = (out[arm]["passes"] >= out[arm]["a_passes"] and out[arm]["majority"]
                                  and out[arm]["lost_work_events"] <= out[arm]["a_lost_work_events"])
    return out


FIXTURES = ["F1", "F2", "F3", "F4", "F5", "F6"]
PRIMARY = ["F3", "F4", "F5", "F6"]
VOID_PAIRS = [("F3", "AC"), ("F3", "BC")]


def orchestration_rule(o: dict, fixtures: list) -> dict:
    """The preregistered rule of paired run 1, from the per-run rows and the pairwise judgements alone: an orchestrated arm (B or C) clears only when it resolves at least 2 more of the fixtures that count than A, or the
    judges' counted preference puts it over A on at least 4 of them, at no more than twice A's mean cost over those fixtures. A void pair carries no preference."""
    runs = {(r["fixture"], r["arm"]): r for r in o["runs"]}
    pairs = {(p["fixture"], p["pair"]): p for p in o["judging"]["pairs"]}
    resolved = {a: sum(1 for f in fixtures if runs[(f, a)]["resolved"]) for a in "ABC"}
    mean = {a: sum(runs[(f, a)]["cost_usd_list_equivalent"] for f in fixtures) / len(fixtures) for a in "ABC"}
    out = {"resolved": resolved, "mean_cost": mean}
    for arm, pair in (("B", "AB"), ("C", "AC")):
        wins = sum(1 for f in fixtures if pairs[(f, pair)]["counted_preference"] == arm)
        within = mean[arm] <= 2 * mean["A"]
        extra = resolved[arm] - resolved["A"]
        out[arm] = {"extra_resolved": extra, "judge_wins": wins, "cost_within_2x": within, "clears_rule": within and (extra >= 2 or wins >= 4)}
    return out


class PlanningRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads((ROOT / ARTIFACT_REL).read_text(encoding="utf-8"))
        cls.plan = cls.artifact["planning_2b"]
        cls.runs = cls.plan["runs"]
        cls.slots = {slot["id"]: slot for slot in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"]}

    def test_the_artifact_names_its_schema_and_says_the_papers_are_private(self):
        self.assertEqual(self.artifact["schema"], "claude-native-practice-paired-runs/1")
        self.assertIn("private working papers", self.artifact["root"])

    def test_the_grid_is_complete_and_every_run_carries_a_hash_of_its_result(self):
        self.assertEqual(sorted((r["fixture"], r["trial"], r["arm"]) for r in self.runs), sorted((f, t, a) for f, t in CELLS for a in "ABC"))
        for run in self.runs:
            with self.subTest(run=run["run"]):
                self.assertEqual(run["run"], f"{run['fixture']}-{run['arm']}-{run['trial']}")
                self.assertRegex(run["result_sha256"], SHA256)
                if run["sessions_used"] > 1:
                    self.assertTrue(all(SHA256.match(h) for h in run["lost_work_readers"].values()))
                else:
                    self.assertNotIn("lost_work_readers", run)

    def test_a_run_that_did_not_declare_done_used_every_session_of_the_design(self):
        limit = self.plan["design"]["max_sessions"]
        for run in self.runs:
            if not run["declared_done"]:
                with self.subTest(run=run["run"]):
                    self.assertEqual(run["sessions_used"], limit)

    def test_the_recorded_decision_is_what_the_runs_give(self):
        recomputed = decision_from_runs(self.runs)
        for arm in "BC":
            recorded = self.plan["decision"][arm]
            for key in ("passes", "a_passes", "counted_cells", "cell_wins", "majority", "lost_work_events", "a_lost_work_events", "replaces_a"):
                with self.subTest(arm=arm, field=key):
                    self.assertEqual(recorded[key], recomputed[arm][key])
        self.assertEqual(self.plan["outcome"], "A stays the default" if not any(recomputed[a]["replaces_a"] for a in "BC") else "an arm replaces A")
        self.assertEqual(self.plan["outcome"], "A stays the default")

    def test_the_decision_is_live_not_typed_in(self):
        flipped = copy.deepcopy(self.runs)
        for run in flipped:
            if run["run"] in ("F5-B-1", "F5-B-2"):  # make the task list cheaper than A on both F5 cells: it would then win four of four
                run["cost_usd_list_equivalent"] = 1.0
        self.assertTrue(decision_from_runs(flipped)["B"]["replaces_a"])
        self.assertFalse(decision_from_runs(self.runs)["B"]["replaces_a"])
        failed = copy.deepcopy(self.runs)
        for run in failed:
            if run["arm"] == "B":
                run["resolved"] = False
        self.assertFalse(decision_from_runs(failed)["B"]["replaces_a"], "an arm that passes fewer runs than A cannot replace it")

    def test_lost_work_adds_up_and_the_single_session_run_has_no_readers(self):
        self.assertEqual(self.plan["lost_work"]["total_events"], sum(r["lost_work_events"] for r in self.runs))
        self.assertEqual(self.plan["lost_work"]["runs_with_one_session"], [r["run"] for r in self.runs if r["sessions_used"] == 1])
        self.assertNotEqual(self.plan["lost_work"]["first_reader_model"], self.plan["lost_work"]["second_reader_model"])

    def test_the_papers_the_results_rest_on_are_hashed(self):
        papers = list(self.plan["papers"].values()) + [self.plan["lost_work"][k] for k in ("protocol", "counts", "table")]
        for paper in papers:
            with self.subTest(path=paper["path"]):
                self.assertRegex(paper["sha256"], SHA256)
                self.assertGreater(paper["bytes"], 0)
                self.assertNotIn("/home/", paper["path"])

    def test_the_planning_rows_state_what_the_artifact_shows(self):
        recomputed = decision_from_runs(self.runs)
        planning, loops = self.slots["planning-persistence"], self.slots["loops-completion"]
        task_list = planning["alternatives"][0]
        self.assertTrue(task_list.startswith("Native Task tools with `CLAUDE_CODE_TASK_LIST_ID`: ranked second"))
        self.assertIn(f"won {recomputed['B']['cell_wins']} of {recomputed['B']['counted_cells']} cells", task_list)
        self.assertEqual(sorted(recomputed["B"]["won_cells"]), ["F6-t1", "F6-t2"])
        self.assertIn("both on the smaller F6 fixture", task_list)
        self.assertIn("`--allowedTools`", task_list)
        self.assertIn("ran all 8 sessions without declaring TASK-DONE", task_list)
        self.assertIn("ranked third, for fallback only", planning["alternatives"][1])
        self.assertIn(f"task list {recomputed['B']['cell_wins']} of {recomputed['B']['counted_cells']}, loop {recomputed['C']['cell_wins']} of {recomputed['C']['counted_cells']}", planning["notes"])
        self.assertIn("0 events in all twelve runs", planning["notes"])
        self.assertEqual(planning["default"].split(" per ")[0], "Repository-resident task state")

    def test_the_ralph_row_carries_the_rulings_three_statements(self):
        loops = self.slots["loops-completion"]
        ralph = next(alt for alt in loops["alternatives"] if alt.startswith("Ralph-style headless loops"))
        self.assertNotIn("candidate until", ralph)
        for needle in ("third behind repository state files and the native task list", "for fallback only", "when neither can be used",
                       "An external done check is required", "never with the session cap alone",
                       "post hoc and provisional", "the preregistration named no criterion",
                       "preregisters its criterion before its first session", "ranked if it wins at least one cell, or ties repository state files on sessions and cost in some cell; else rejected"):
            with self.subTest(statement=needle):
                self.assertIn(needle, ralph)
        recomputed = decision_from_runs(self.runs)
        self.assertEqual(recomputed["C"]["cell_wins"], 0)
        self.assertIn("won no cell", ralph)
        self.assertEqual(recomputed["C"]["passes"], 4)
        self.assertIn("passed 4 of 4 runs", ralph)
        self.assertIn("with 0 lost work", ralph)

    def test_the_rows_cite_the_hashes_of_the_artifact(self):
        papers = self.plan["papers"]
        cited = {"RESULT.md": papers["result"]["sha256"], "analysis.txt": papers["analysis"]["sha256"], "lost_work.json": self.plan["lost_work"]["counts"]["sha256"]}
        for slot_id in ("planning-persistence", "loops-completion"):
            text = " ".join(self.slots[slot_id]["evidence"])
            self.assertIn(ARTIFACT_REL, text)
            for name, full in cited.items():
                with self.subTest(slot=slot_id, paper=name):
                    match = re.search(re.escape(name) + r"(?: sha256)? ([0-9a-f]{12})", text)
                    self.assertIsNotNone(match, f"{slot_id} does not cite {name}")
                    self.assertTrue(full.startswith(match.group(1)))

    def test_the_record_addendum_cites_the_artifact_and_states_the_decision(self):
        record = RECORD.read_text(encoding="utf-8")
        addendum = record.split("## Addendum (2026-10-10): paired-run results", 1)[1]
        self.assertIn(f"../../{ARTIFACT_REL}", addendum)
        self.assertTrue((ROOT / ARTIFACT_REL).is_file())
        for needle in ("All 12 runs passed the hidden tests", "the task list won 2 of 4 cells (both F6) and the loop none", "Lost work: 0 events in all 12 runs",
                       "third behind repository state files and the native task list and for fallback only", "post hoc and provisional"):
            with self.subTest(statement=needle):
                self.assertIn(needle, " ".join(addendum.split()))


class OrchestrationRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads((ROOT / ARTIFACT_REL).read_text(encoding="utf-8"))
        cls.o = cls.artifact["orchestration_1"]
        cls.runs = {r["run"]: r for r in cls.o["runs"]}
        cls.slots = {slot["id"]: slot for slot in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"]}

    def test_the_grid_is_complete_and_every_run_carries_a_hash_of_its_result(self):
        self.assertEqual(sorted(self.runs), sorted(f"{f}-{a}-1" for f in FIXTURES for a in "ABC"))
        for name, run in self.runs.items():
            with self.subTest(run=name):
                self.assertEqual(name, f"{run['fixture']}-{run['arm']}-1")
                self.assertRegex(run["result_sha256"], SHA256)
                self.assertEqual(run["void_in_primary"], run["fixture"] in ("F1", "F2"))
                if run["arm"] == "B":
                    self.assertRegex(run["workflow"]["journal_sha256"], SHA256)
                if run["arm"] == "C":
                    self.assertTrue(run["cost_is_estimate"])

    def test_the_recorded_rule_is_what_the_runs_and_the_pairs_give(self):
        for name, fixtures in (("primary_f3_to_f6", PRIMARY), ("sensitivity_all_six_regraded", FIXTURES)):
            recomputed, recorded = orchestration_rule(self.o, fixtures), self.o["analysis"][name]
            self.assertEqual(recorded["fixtures"], fixtures)
            self.assertEqual(recorded["resolved"], recomputed["resolved"])
            for arm in "ABC":
                self.assertAlmostEqual(recorded["mean_cost_usd_list_equivalent_not_billed"][arm], recomputed["mean_cost"][arm], places=2)
            for arm in "BC":
                with self.subTest(analysis=name, arm=arm):
                    self.assertEqual(recorded[f"{arm}_vs_A"], recomputed[arm])
                    self.assertFalse(recomputed[arm]["clears_rule"], "an orchestrated arm clears the rule: the rows say none does")

    def test_the_rule_is_live_not_typed_in(self):
        wins = copy.deepcopy(self.o)
        for pair in wins["judging"]["pairs"]:
            if pair["pair"] == "AB" and pair["fixture"] in PRIMARY:
                pair["counted_preference"] = "B"  # the judges prefer the Workflow on all four fixtures that count
        self.assertTrue(orchestration_rule(wins, PRIMARY)["B"]["clears_rule"])
        fails = copy.deepcopy(self.o)
        for run in fails["runs"]:
            if run["arm"] == "A" and run["fixture"] in ("F3", "F4"):
                run["resolved"] = False  # the single session fails two fixtures that B and C pass
        self.assertTrue(orchestration_rule(fails, PRIMARY)["B"]["clears_rule"])
        cheap = copy.deepcopy(self.o)
        for pair in cheap["judging"]["pairs"]:
            if pair["pair"] == "AC" and pair["fixture"] in PRIMARY:
                pair["counted_preference"] = "C"
        self.assertFalse(orchestration_rule(cheap, PRIMARY)["C"]["clears_rule"], "four judge wins do not clear a rule whose cost bound the team misses")
        for run in cheap["runs"]:
            if run["arm"] == "C":
                run["cost_usd_list_equivalent"] = run["cost_usd_list_equivalent"] / 4
        self.assertTrue(orchestration_rule(cheap, PRIMARY)["C"]["clears_rule"])

    def test_the_pairs_are_consistent_and_exactly_the_uncaptured_ones_are_void(self):
        pairs = self.o["judging"]["pairs"]
        self.assertEqual(sorted((p["fixture"], p["pair"]) for p in pairs), sorted((f, q) for f in FIXTURES for q in ("AB", "AC", "BC")))
        for p in pairs:
            with self.subTest(pair=f"{p['fixture']}-{p['pair']}"):
                self.assertEqual(sorted((p["x"], p["y"])), sorted(p["pair"]))
                self.assertIn(p["first_judge_prefers"], (p["x"], p["y"], "tie"))
                self.assertRegex(p["judge_sha256"], SHA256)
                self.assertRegex(p["refute_sha256"], SHA256)
                void = (p["fixture"], p["pair"]) in VOID_PAIRS
                self.assertEqual(p["void"], void)
                expected = None if (void or not p["refuter_holds"]) else p["first_judge_prefers"]
                self.assertEqual(p["counted_preference"], expected)
        self.assertEqual(sorted(name for name, run in self.runs.items() if not run["diff_captured"]), ["F3-C-1"])
        self.assertTrue(self.runs["F3-C-1"]["resolved"], "the hidden-test result of the run whose diff was not captured stands")

    def test_the_papers_the_orchestration_result_rests_on_are_hashed(self):
        for name, paper in self.o["papers"].items():
            with self.subTest(paper=name):
                self.assertRegex(paper["sha256"], SHA256)
                self.assertGreater(paper["bytes"], 0)
                self.assertNotIn("/home/", paper["path"])

    def test_the_orchestration_rows_state_what_the_artifact_shows(self):
        runs, o = self.runs, self.o
        mean = {a: sum(runs[f"{f}-{a}-1"]["cost_usd_list_equivalent"] for f in FIXTURES) / 6 for a in "ABC"}
        pairs = {(p["fixture"], p["pair"]): p for p in o["judging"]["pairs"]}
        a_over_b = sum(1 for f in FIXTURES if pairs[(f, "AB")]["counted_preference"] == "A")
        a_over_c = sum(1 for f in FIXTURES if pairs[(f, "AC")]["counted_preference"] == "A")
        b_over_a = sum(1 for f in FIXTURES if pairs[(f, "AB")]["counted_preference"] == "B")
        c_over_a = sum(1 for f in FIXTURES if pairs[(f, "AC")]["counted_preference"] == "C")
        c_runs = [runs[f"{f}-C-1"] for f in FIXTURES]
        b_wf = [runs[f"{f}-B-1"]["workflow"] for f in FIXTURES]
        returned = sum(w["verifier_returned"] for w in b_wf)
        cut = sum(1 for w in b_wf if w["verifier_started"] and not w["verifier_returned"])
        never = sum(1 for w in b_wf if not w["verifier_started"])
        orch, teams, workflow = self.slots["orchestration-frameworks"], self.slots["agent-teams"], self.slots["background-workflows"]
        evidence = next(e for e in orch["evidence"] if e.startswith("Paired run 1, 2026-10-10"))
        for needle in (f"the single session cost ${mean['A']:.2f} on average", f"the verify Workflow {mean['B'] / mean['A']:.1f}x and the agent team {mean['C'] / mean['A']:.1f}x",
                       f"on {a_over_b} of 6 fixtures and to the team's on {a_over_c} of the 5 where the team's diff was captured", "every mode passed 6 of 6"):
            with self.subTest(statement=needle):
                self.assertIn(needle, evidence)
        self.assertIn(evidence, teams["evidence"])
        self.assertIn(evidence, workflow["evidence"])
        for key, label in (("result", "RESULT.md"), ("score", "score.json")):
            match = re.search(re.escape(label) + r"(?: sha256)? ([0-9a-f]{12})", evidence)
            self.assertIsNotNone(match, f"the row does not cite {label}")
            self.assertTrue(o["papers"][key]["sha256"].startswith(match.group(1)))
        self.assertIn(f"(Workflow {b_over_a} of 6, team {c_over_a} of 5 comparable)", orch["notes"])
        self.assertIn(f"{mean['B'] / mean['A']:.1f}x and {mean['C'] / mean['A']:.1f}x its mean cost", orch["notes"])
        self.assertIn(f"it reached TEAM-DONE in {sum(r['team_done'] for r in c_runs)} of 6 runs, hit its $30 cap in {sum(r['capped_at_30_usd'] for r in c_runs)}", teams["notes"])
        self.assertIn(f"the verifier returned in {returned} of 6 runs ({sum(1 for w in b_wf if w['verifier_refuted'])} refuted), was cut by the 45-minute wait ceiling of `claude -p` in {cut}, and in {never} the implementer itself ran to the ceiling", workflow["notes"])
        self.assertEqual((returned, cut, never), (2, 3, 1))
        self.assertIn("not found by name in 6 of 6 headless runs", workflow["notes"])

    def test_the_record_addendum_states_the_orchestration_decision(self):
        record = " ".join(RECORD.read_text(encoding="utf-8").split())
        paragraph = record.split("**Orchestration (paired run 1).**", 1)[1].split("**", 1)[0]
        for needle in ("Every run passed the hidden tests in both analyses (18 of 18)", "F3's two pairs with the team are void: its diff was not captured", "Neither orchestrated arm clears the rule",
                       "the routing guidance for bounded fixes on north-star code names the single session", "Four defects of the measurement were found during the run"):
            with self.subTest(statement=needle):
                self.assertIn(needle, paragraph)
        self.assertIn("18 of 18 verdicts held", paragraph)


if __name__ == "__main__":
    unittest.main()
