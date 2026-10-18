"""Model-free tests of the saved lane's return, using the existing envelope seam.

No native Workflow or model is launched. agent/parallel/log are injected stubs,
as in examples/claude-native/workflows/test-envelope.mjs at NAS 6f57256a.
"""
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "examples/claude-native/workflows/layer-verdict-lane.js"
DRIVER = r"""
const fs = require('node:fs')
const input = JSON.parse(fs.readFileSync(0, 'utf8'))
const body = fs.readFileSync(process.argv[1], 'utf8').replace(/^export const meta/m, 'const meta')
const calls = []
const agent = (prompt, opts) => {
  calls.push({label: opts.label, prompt, schema: opts.schema})
  const key = opts.label.startsWith('propose:revise:') ? 'revision'
    : opts.label.startsWith('propose:') ? 'proposal'
    : (opts.label.includes(':recheck:') ? 'revision_' : '')
      + (opts.label.includes(':evidence:') ? 'evidence' : 'challenger')
  const value = input.returns[key]
  if (value && value.sync_throw) throw new Error(value.sync_throw)
  if (value && value.throw) return Promise.reject(new Error(value.throw))
  return Promise.resolve(value === undefined ? null : value)
}
let groups = 0
const parallel = async (thunks) => {
  const fault = ++groups === (input.returns._parallel_round || 1) ? input.returns._parallel : null
  if (fault === 'before') throw new Error('synthetic parallel failure before calls')
  const got = await Promise.all(thunks.map((t) => t().catch(() => null)))
  if (fault === 'after') throw new Error('synthetic parallel failure after calls')
  return fault === 'null_after' ? null : got
}
const run = new Function('args', 'agent', 'parallel', 'log', 'return (async () => {\n' + body + '\n})()')
run(input.args, agent, parallel, () => {}).then((result) => {
  process.stdout.write(JSON.stringify({result, calls}))
}).catch((e) => { console.error(e.stack); process.exitCode = 1 })
"""
PACKET = {"catalog": "foundation", "layer_id": "fixture-layer", "path": "packets/fixture.json", "sha256": "a" * 64}
ARGS = {"repo": "fixture-view", "packets": [PACKET], "prompt": "Read {PACKET_PATH} under {REPO_ROOT} for {LANE}."}
PROPOSAL = {"fixture": "original"}
REVISION = {"fixture": "revised"}
MAJOR = {"claim": "challenger evidence omitted", "evidence": "fixtures/challenger.json:1", "severity": "major"}


def vote(*, refuted=False, findings=None, resolutions=None):
    return {"refuted": refuted, "reason": "fixture evidence checked", "findings": findings or [],
            "paths_checked": ["fixtures/challenger.json"], "resolutions": resolutions or []}


class LayerVerdictWorkflowTests(unittest.TestCase):
    maxDiff = 500
    def run_lane(self, *, args=None, **returns):
        result = subprocess.run(["node", "-e", DRIVER, str(WORKFLOW)],
                                input=json.dumps({"args": ARGS if args is None else args, "returns": returns}),
                                text=True, capture_output=True, timeout=15, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def major_run(self, **overrides):
        returns = {"proposal": PROPOSAL, "evidence": vote(findings=[MAJOR]), "challenger": vote(),
                   "revision": REVISION, "revision_evidence": vote(), "revision_challenger": vote()}
        returns.update(overrides)
        return self.run_lane(**returns)

    def test_required_revision_never_falls_back_to_the_major_bearing_proposal(self):
        for name, overrides in [
            ("null revision", {"revision": None}),
            ("unknown recheck", {"revision_evidence": None}),
            ("refuted recheck", {"revision_evidence": vote(refuted=True)}),
        ]:
            with self.subTest(case=name):
                row = self.major_run(**overrides)["result"]["layers"][0]
                self.assertIsNone(row["final"])
                self.assertIsNone(row["final_source"])
                self.assertEqual(row["refutation"]["status"], "unknown")
                self.assertEqual(row["proposal"], PROPOSAL)
                self.assertEqual(row["votes"][0]["findings"], [MAJOR])

    def test_remaining_major_or_blocking_findings_prevent_sealing_a_revision(self):
        for severity in ("major", "blocking"):
            with self.subTest(severity=severity):
                finding = {**MAJOR, "severity": severity}
                row = self.major_run(revision_evidence=vote(findings=[finding]))["result"]["layers"][0]
                self.assertIsNone(row["final"])
                self.assertEqual(row["refutation"]["status"], "unknown")
                self.assertEqual(row["revision_votes"][0]["findings"], [finding])

    def test_clean_recheck_needs_explicit_evidence_backed_closure_of_prior_majors(self):
        row = self.major_run()["result"]["layers"][0]
        self.assertIsNone(row["final"])
        self.assertEqual(row["refutation"]["status"], "unknown")
        self.assertEqual(row["votes"][0]["findings"], [MAJOR])

    def test_original_proposal_can_complete_with_two_clean_votes(self):
        got = self.run_lane(proposal=PROPOSAL, evidence=vote(), challenger=vote())
        row = got["result"]["layers"][0]
        self.assertEqual(row["final"], PROPOSAL)
        self.assertEqual(row["final_source"], "proposal")
        self.assertEqual(len(got["calls"]), 3)

    def test_revision_can_complete_only_with_explicit_originating_lens_closure(self):
        resolution = {"finding_id": "proposal:evidence:0", "disposition": "resolved",
                      "evidence": "fixtures/challenger.json:1 now cited in revision alternatives"}
        got = self.major_run(revision_evidence=vote(resolutions=[resolution]))
        row = got["result"]["layers"][0]
        self.assertEqual(row["final"], REVISION)
        self.assertEqual(row["final_source"], "revision")
        self.assertEqual(row["votes"][0]["findings"], [MAJOR])
        self.assertEqual(row["revision_votes"][0]["resolutions"], [resolution])
        recheck = next(c for c in got["calls"] if c["label"].startswith("refute:recheck:evidence:"))
        self.assertIn("proposal:evidence:0", recheck["prompt"])
        self.assertIn(MAJOR["claim"], recheck["prompt"])

    def test_invalid_dispositions_cannot_close_a_prior_finding(self):
        resolution = {"finding_id": "proposal:evidence:0", "disposition": "resolved", "evidence": "fixtures/fix.json:1"}
        for entries in ([{**resolution, "evidence": " "}], [{**resolution, "disposition": "unresolved"}],
                        [{**resolution, "finding_id": "unknown"}], [resolution, resolution]):
            with self.subTest(entries=entries):
                row = self.major_run(revision_evidence=vote(resolutions=entries))["result"]["layers"][0]
                self.assertIsNone(row["final"])
                self.assertEqual(row["refutation"]["status"], "unknown")

    def test_admission_rejects_every_input_except_one_valid_raw_packet(self):
        invalid = [
            {**ARGS, "packets": [PACKET, None]}, {**ARGS, "packets": [PACKET, PACKET]},
            {**ARGS, "packets": []}, {**ARGS, "packets": PACKET}, {**ARGS, "packets": [None]},
            {**ARGS, "packets": [{**PACKET, "sha256": ["a" * 64]}]},
            {**ARGS, "packets": [{**PACKET, "catalog": "unrecognized"}]},
            {**ARGS, "packets": [{**PACKET, "path": " "}]},
            {**ARGS, "packets": [{**PACKET, "sha256": "A" * 64}]},
            {**ARGS, "docs": ["arbitrary.md"]}, {**ARGS, "docs": []},
            {"repo": "fixture-view", "docs": ["arbitrary.md"]},
            {**ARGS, "repo": " "}, {**ARGS, "prompt": " "},
            {**ARGS, "launch": {"repo": "different-view"}},
        ]
        for args in invalid:
            with self.subTest(args=args):
                got = self.run_lane(args=args)
                self.assertEqual(len(got["calls"]), 0)
                self.assertEqual(got["result"]["status"], "incomplete")
                self.assertEqual(got["result"]["stop_cause"], "argument_rejected")
                self.assertTrue(got["result"]["argument_issues"])

    def test_exceptions_keep_the_failed_stage_and_all_earlier_judgments(self):
        for stage in ("proposal", "evidence", "challenger", "revision", "revision_evidence", "revision_challenger"):
            with self.subTest(stage=stage):
                got = self.major_run(**{stage: {"throw": "synthetic " + stage + " failure"}})["result"]
                self.assertEqual(got.get("status"), "incomplete")
                self.assertTrue(got["stop_cause"])
                row = got["layers"][0]
                failure = next(s for s in row["stage_results"] if s["status"] == "error")
                self.assertEqual(failure["error"], {"name": "Error", "message": "synthetic " + stage + " failure"})
                self.assertIsNone(row["final"])
                if stage.startswith("revision"):
                    self.assertEqual(row["proposal"], PROPOSAL)
                    self.assertEqual(row["votes"][0]["findings"], [MAJOR])
                if stage.startswith("revision_"):
                    self.assertEqual(row["revised"], REVISION)

    def test_malformed_votes_are_retained_but_never_count_as_a_success(self):
        for raw in ({"findings": [MAJOR]}, {**vote(), "findings": "not an array"},
                    {**vote(), "refuted": "false"}, {**vote(), "findings": [{**MAJOR, "severity": "unknown"}]}):
            with self.subTest(raw=raw):
                got = self.major_run(evidence=raw)["result"]
                self.assertEqual(got.get("status"), "incomplete")
                self.assertEqual(got["stop_cause"], "proposal_votes_incomplete")
                row = got["layers"][0]
                self.assertIsNone(row["final"])
                malformed = next(s for s in row["stage_results"] if s["status"] == "invalid")
                self.assertEqual(malformed["returned"], raw)

    def test_top_level_status_distinguishes_closed_judgment_from_partial_run(self):
        complete = self.run_lane(proposal=PROPOSAL, evidence=vote(), challenger=vote())["result"]
        self.assertEqual(complete.get("status"), "complete")
        self.assertIsNone(complete["stop_cause"])
        partial = self.major_run(revision=None)["result"]
        self.assertEqual(partial.get("status"), "incomplete")
        self.assertEqual(partial["stop_cause"], "revision_missing")
        row = partial["layers"][0]
        self.assertEqual(row["expected_roles"], ["proposal", "proposal:evidence", "proposal:challenger",
                                                 "revision", "revision:evidence", "revision:challenger"])
        self.assertEqual(row["returned_roles"], ["proposal", "proposal:evidence", "proposal:challenger"])
        self.assertEqual(row["not_started_roles"], ["revision:evidence", "revision:challenger"])

    def test_synchronous_agent_errors_preserve_the_partial_chain(self):
        for stage in ("proposal", "evidence", "revision"):
            with self.subTest(stage=stage):
                got = self.major_run(**{stage: {"sync_throw": "synthetic synchronous failure"}})["result"]
                self.assertEqual(got["status"], "incomplete")
                self.assertEqual(len(got["layers"]), 1)
                row = got["layers"][0]
                self.assertTrue(any(s.get("error", {}).get("message") == "synthetic synchronous failure"
                                    for s in row["stage_results"]))
                if stage == "revision":
                    self.assertEqual(row["votes"][0]["findings"], [MAJOR])

    def test_orchestration_faults_keep_completed_votes_and_never_complete(self):
        for round_number in (1, 2):
            for fault in ("before", "after", "null_after"):
                with self.subTest(round=round_number, fault=fault):
                    got = self.major_run(_parallel=fault, _parallel_round=round_number)["result"]
                    self.assertEqual(got["status"], "incomplete")
                    self.assertEqual(len(got["layers"]), 1)
                    row = got["layers"][0]
                    self.assertIsNone(row["final"])
                    self.assertEqual(row["proposal"], PROPOSAL)
                    self.assertTrue(any(s["role"].endswith(":parallel") and s["status"] == "error"
                                        for s in row["stage_results"]))
                    if round_number == 2:
                        self.assertEqual(row["revised"], REVISION)
                        self.assertEqual(row["votes"][0]["findings"], [MAJOR])
                    if fault != "before":
                        votes = row["votes"] if round_number == 1 else row["revision_votes"]
                        self.assertTrue(all(v["refuted"] is False for v in votes))

    def test_packet_label_suffix_cannot_change_the_recorded_lens(self):
        args = {**ARGS, "packets": [{**PACKET, "layer_id": "x:evidence:y"}]}
        row = self.run_lane(args=args, proposal=PROPOSAL, evidence=vote(), challenger=vote())["result"]["layers"][0]
        self.assertEqual(row["returned_roles"], ["proposal", "proposal:evidence", "proposal:challenger"])
        self.assertEqual(row["not_started_roles"], [])


if __name__ == "__main__":
    unittest.main()
