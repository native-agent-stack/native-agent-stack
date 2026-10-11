"""Public CLI regressions for explicit resume accounting, without model calls."""

import copy
import hashlib
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_landscape_sweep_harness import HARNESS, child_usage_raw


class CompletedSupersessionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        labels = ["discover:quality-evaluation:followup", "refute-fit:quality-evaluation:followup",
                  *[f"fixture:{index}" for index in range(10)]]
        raw = json.loads(child_usage_raw("wf_fixture-1", labels))
        originals, reruns, pairs, calls, journal = [], [], [], [], [{"type": "launched"}]
        for index, child in enumerate(raw["children"]):
            old, new = f"old{index}", f"new{index}"
            old_key, new_key = "v2:" + f"{index:064x}", "v2:" + f"{index + 100:064x}"
            originals.append(dict(child, agent_id=old, efforts=["max", "low"] if index < 2 else ["max"]))
            reruns.append(dict(child, agent_id=new))
            pairs.append({"label": child["label"], "superseded_agent_id": old, "superseded_key": old_key,
                          "superseded_by_agent_id": new, "superseded_by_key": new_key})
            calls.append({"label": child["label"], "original_agent_id": old, "original_key": old_key,
                          "approved_rerun_key": new_key, "new_key_must_be_computed_from_actual_max_discovery": False})
            for agent_id, key in [(old, old_key), (new, new_key)]:
                journal.extend([{"type": "started", "agentId": agent_id, "key": key, "label": child["label"]},
                                {"type": "result", "agentId": agent_id, "key": key, "result": {"fixture": True}}])
        others = json.loads(child_usage_raw("wf_fixture-1", [f"other:{i}" for i in range(94)]))["children"]
        raw["children"] = originals + [dict(c, agent_id=f"other{i}") for i, c in enumerate(others)] + reruns
        raw["by_resolved_model"] = {"fixture": {"children": 126, "output_tokens": 4321}}
        raw["superseded_attempts"] = [{"label": "other:0", "agent_id": f"killed{i}", "complete": False,
                                       "efforts": ["max"], "requests": 1, "unknown_effort_requests": 0,
                                       "superseded_by": "other0"} for i in range(8)]
        raw["effort_mismatches"] = [{"child": labels[i], "efforts": ["max", "low"]} for i in range(2)]
        self.raw = raw
        self.write("raw.json", raw)
        contract = {"schema_version": 1, "workflow": "wf_fixture-1", "calls": calls}
        self.write("contract.json", contract)
        journal_bytes = "".join(json.dumps(row) + "\n" for row in journal).encode()
        (self.work / "journal.jsonl").write_bytes(journal_bytes)
        self.proof = {"status": "proved-actual-resumed-run", "nativeRun": {"runId": "wf_fixture-1", "status": "completed"},
                      "contractSha256": self.sha("contract.json"), "finalJournalSha256": self.sha("journal.jsonl"),
                      "originalPrefix": {"byteEqual": True}, "reexecutedResultEqualsNative": True,
                      "supersessionPairs": pairs,
                      "reruns": [{"label": p["label"], "agentId": p["superseded_by_agent_id"],
                                  "key": p["superseded_by_key"], "supersedesAgentId": p["superseded_agent_id"],
                                  "supersedesKey": p["superseded_key"], "keyKind": "approved-equal",
                                  "transcriptPromptEqual": True, "nativeResultPresent": True} for p in pairs]}
        self.write("proof.json", self.proof)

    def write(self, name, value):
        (self.work / name).write_text(json.dumps(value), encoding="utf-8")

    def sha(self, name):
        return hashlib.sha256((self.work / name).read_bytes()).hexdigest()

    def run_usage(self, explicit=False, required=None):
        args = [sys.executable, str(HARNESS / "usage_record.py"), "--raw-output", str(self.work / "raw.json"),
                "--exit-code", "1", "--out", str(self.work / "usage.json")]
        if explicit:
            args += ["--supersession-proof", str(self.work / "proof.json"),
                     "--supersession-contract", str(self.work / "contract.json"),
                     "--supersession-journal", str(self.work / "journal.jsonl")]
        if required:
            args += ["--require-effort", required]
        return subprocess.run(args, capture_output=True, text=True)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_native_cli_requires_every_request_effort_to_be_known(self):
        run = self.work / "native"
        run.mkdir()
        (run / "journal.jsonl").write_text("\n".join(json.dumps(row) for row in [
            {"type": "started", "agentId": "native", "label": "fixture", "key": "v2:fixture"},
            {"type": "result", "agentId": "native", "key": "v2:fixture", "result": {"ok": True}}]) + "\n")
        (run / "agent-native.meta.json").write_text(json.dumps({"model": "opus"}))
        adapter = HARNESS.parents[2] / "examples/claude-native/workflows/child-usage.mjs"
        for effort in ("max", None, "", " "):
            with self.subTest(effort=effort):
                rows = [{"type": "assistant", "effort": value, "message": {
                    "id": f"message-{i}", "model": "claude-opus-5-5",
                    "usage": {"input_tokens": 2, "output_tokens": 3}}}
                        for i, value in enumerate(("max", effort))]
                (run / "agent-native.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                done = subprocess.run([shutil.which("node"), str(adapter), str(run), "--require-effort", "max"],
                                      capture_output=True, text=True)
                report = json.loads(done.stdout)
                child = report["children"][0]
                self.assertEqual(done.returncode, 0 if effort == "max" else 1, done.stderr)
                self.assertEqual(child["requests"], 2)
                self.assertEqual(child["usage"]["input_tokens"], 4)
                self.assertEqual(child["usage"]["output_tokens"], 6)
                self.assertEqual(child["unknown_effort_requests"], 0 if effort == "max" else 1)
                self.assertEqual(bool(report["effort_mismatches"]), effort != "max")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_native_unknown_request_effort_cannot_cover_a_completed_attempt(self):
        adapter = HARNESS.parents[2] / "examples/claude-native/workflows/child-usage.mjs"
        program = """
import { summarizeChild } from ADAPTER;
const rows = EFFORTS.map((effort, i) => ({type: 'assistant', effort,
  message: {id: 'msg' + i, model: 'claude-opus-5-5', usage: {input_tokens: 2, output_tokens: 3}}}));
console.log(JSON.stringify(summarizeChild({agentId: 'fixture', label: 'fixture'},
  {result: {ok: true}}, {model: 'opus'}, rows)));
"""
        def native(efforts):
            done = subprocess.run([shutil.which("node"), "--input-type=module", "-e",
                                   program.replace("ADAPTER", json.dumps(adapter.as_uri()))
                                   .replace("EFFORTS", json.dumps(efforts))], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(done.stdout)

        # Actual adapter output at the public CLI, with a successful measured-max control.
        for case, efforts in (("all_measured", ["max", "max"]),
                              ("unknown_terminal", ["max", None]), ("unknown_original", [None])):
            with self.subTest(case=case):
                raw = copy.deepcopy(self.raw)
                index = 0 if case == "unknown_original" else -12
                raw["children"][index].update(native(efforts))
                raw["children"][index].update(agent_id="old0" if index == 0 else "new0",
                                               label=self.raw["children"][0]["label"])
                if case == "unknown_original":
                    raw["effort_mismatches"][0]["efforts"] = []
                self.write("raw.json", raw)
                (self.work / "usage.json").unlink(missing_ok=True)
                done = self.run_usage(explicit=True)
                if case == "all_measured":
                    self.assertEqual(done.returncode, 0, done.stderr)
                    receipt = json.loads((self.work / "usage.json").read_text())
                    self.assertEqual(next(c for c in receipt["child_usage"]["children"]
                                          if c["agent_id"] == "new0")["unknown_effort_requests"], 0)
                    self.assertEqual(receipt["measurement"]["raw_output_sha256"], self.sha("raw.json"))
                    self.assertEqual(receipt["child_usage"]["by_resolved_model"], raw["by_resolved_model"])
                else:
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertIn("effort", done.stderr)
                    self.assertFalse((self.work / "usage.json").exists())

    def test_completed_changed_key_attempts_need_proven_pairs_and_keep_all_counters(self):
        baseline = self.run_usage()
        self.assertEqual(baseline.returncode, 1, baseline.stderr)
        before = json.loads((self.work / "usage.json").read_text())
        self.assertEqual(len(before["child_usage"]["children"]), 118)
        self.assertEqual(len(before["child_usage"]["effort_mismatches"]), 2)
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        document = json.loads((self.work / "usage.json").read_text())
        usage = document["child_usage"]
        self.assertEqual(len(usage["children"]), 106)
        self.assertEqual(len(usage["superseded_attempts"]), 20)
        self.assertEqual(usage["effort_mismatches"], [])
        self.assertEqual(usage["by_resolved_model"], self.raw["by_resolved_model"])
        self.assertEqual(usage["web_search"], self.raw["web_search"])
        self.assertEqual(document["measurement"]["exit_code"], 1)
        self.assertEqual(document["measurement"]["raw_output_sha256"], self.sha("raw.json"))
        provenance = document["measurement"]["post_processing"]["explicit_supersession"]
        self.assertEqual(provenance["proof_sha256"], self.sha("proof.json"))
        self.assertEqual(provenance["contract_sha256"], self.sha("contract.json"))
        by_id = {c["agent_id"]: c for c in usage["superseded_attempts"]}
        for child in self.raw["children"][:12]:
            retained = copy.deepcopy(by_id[child["agent_id"]])
            retained.pop("superseded_by")
            retained.pop("reason")
            self.assertEqual(retained, child)

    def test_bound_results_must_follow_their_own_starts(self):
        original = (self.work / "journal.jsonl").read_text()
        self.assertEqual(self.run_usage(explicit=True).returncode, 0)
        prior_receipt = (self.work / "usage.json").read_bytes()
        for agent_id in ("old0", "new0"):
            for existing_receipt in (False, True):
                with self.subTest(agent_id=agent_id, existing_receipt=existing_receipt):
                    rows = [json.loads(line) for line in original.splitlines()]
                    start = next(i for i, row in enumerate(rows) if row.get("agentId") == agent_id and row["type"] == "started")
                    result = next(i for i, row in enumerate(rows) if row.get("agentId") == agent_id and row["type"] == "result")
                    rows[start], rows[result] = rows[result], rows[start]
                    (self.work / "journal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                    proof = copy.deepcopy(self.proof)
                    proof["finalJournalSha256"] = self.sha("journal.jsonl")
                    self.write("proof.json", proof)
                    if existing_receipt:
                        (self.work / "usage.json").write_bytes(prior_receipt)
                    else:
                        (self.work / "usage.json").unlink(missing_ok=True)
                    done = self.run_usage(explicit=True)
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertIn("supersession result did not follow its started identity", done.stderr)
                    if existing_receipt:
                        self.assertEqual((self.work / "usage.json").read_bytes(), prior_receipt)
                    else:
                        self.assertFalse((self.work / "usage.json").exists())

    def test_completed_same_label_children_must_belong_to_the_explicit_chain(self):
        from tests.test_landscape_sweep_harness import convert
        self.assertEqual(self.run_usage(explicit=True).returncode, 0)
        receipt = json.loads((self.work / "usage.json").read_text())
        label = self.raw["children"][0]["label"]
        self.assertEqual(convert.usage_children(receipt)[label]["agent_id"], "new0")
        original_journal = (self.work / "journal.jsonl").read_text()
        for position in ("before_terminal", "after_terminal"):
            with self.subTest(position=position):
                raw = copy.deepcopy(self.raw)
                child = dict(raw["children"][-12], agent_id="unpaired")
                if position == "before_terminal":
                    raw["children"].insert(len(raw["children"]) - 12, child)
                else:
                    raw["children"].append(child)
                self.write("raw.json", raw)
                rows = [{"type": "started", "agentId": "unpaired", "key": "v2:" + "f" * 64, "label": label},
                        {"type": "result", "agentId": "unpaired", "key": "v2:" + "f" * 64, "result": {"ok": True}}]
                (self.work / "journal.jsonl").write_text(original_journal + "".join(json.dumps(row) + "\n" for row in rows))
                proof = copy.deepcopy(self.proof)
                proof["finalJournalSha256"] = self.sha("journal.jsonl")
                self.write("proof.json", proof)
                (self.work / "usage.json").unlink()
                done = self.run_usage(explicit=True)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn("completed same-label child is outside the proven supersession chain", done.stderr)
                self.assertFalse((self.work / "usage.json").exists())
                # Reset a previous valid artifact to verify that refusal leaves it untouched as well.
                self.write("usage.json", receipt)
                previous = (self.work / "usage.json").read_bytes()
                done = self.run_usage(explicit=True)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertEqual((self.work / "usage.json").read_bytes(), previous)

    def test_duplicate_or_unbound_journal_and_summary_identities_are_refused(self):
        original = (self.work / "journal.jsonl").read_text()
        self.assertEqual(self.run_usage(explicit=True).returncode, 0)
        previous = (self.work / "usage.json").read_bytes()
        cases = {"duplicate_result": "supersession journal repeats a result identity",
                 "orphan_result": "supersession result did not follow its started identity",
                 "wrong_key": "supersession result did not follow its started identity",
                 "overlap": "supersession rerun did not start after its completed original",
                 "duplicate_summary": "supersession summary repeats a measured child identity"}
        for case, diagnostic in cases.items():
            with self.subTest(case=case):
                rows = [json.loads(line) for line in original.splitlines()]
                raw = copy.deepcopy(self.raw)
                if case == "duplicate_result":
                    rows.append(copy.deepcopy(rows[2]))
                elif case == "orphan_result":
                    rows.append(dict(rows[2], agentId="orphan"))
                elif case == "wrong_key":
                    rows[2]["key"] = "v2:" + "f" * 64
                elif case == "overlap":
                    rows[2], rows[3] = rows[3], rows[2]
                else:
                    raw["children"].append(copy.deepcopy(raw["children"][-12]))
                (self.work / "journal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                proof = copy.deepcopy(self.proof)
                proof["finalJournalSha256"] = self.sha("journal.jsonl")
                self.write("proof.json", proof)
                self.write("raw.json", raw)
                done = self.run_usage(explicit=True)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn(diagnostic, done.stderr)
                self.assertEqual((self.work / "usage.json").read_bytes(), previous)

    def test_terminal_effort_needs_affirmative_request_accounting(self):
        for field, value in (("unknown_effort_requests", None), ("unknown_effort_requests", False),
                             ("unknown_effort_requests", 1), ("requests", 0), ("requests", True)):
            with self.subTest(field=field, value=value):
                raw = copy.deepcopy(self.raw)
                terminal = raw["children"][-12]
                if value is None:
                    terminal.pop(field)
                else:
                    terminal[field] = value
                self.write("raw.json", raw)
                done = self.run_usage(explicit=True)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn("supersession chain does not end at measured required effort", done.stderr)
                self.assertFalse((self.work / "usage.json").exists())

    def test_completed_mixed_effort_chain_is_covered_only_by_its_proven_max_terminal(self):
        raw = copy.deepcopy(self.raw)
        raw["children"][-12]["efforts"] = ["max", "low"]
        terminal = dict(raw["children"][-12], agent_id="terminal", efforts=["max"])
        raw["children"].append(terminal)
        raw["effort_mismatches"].append(copy.deepcopy(raw["effort_mismatches"][0]))
        raw["by_resolved_model"] = {"fixture": {"children": 127, "output_tokens": 4338}}
        self.write("raw.json", raw)
        label, old_key, new_key = terminal["label"], "v2:" + f"{100:064x}", "v2:" + f"{200:064x}"
        with (self.work / "journal.jsonl").open("a", encoding="utf-8") as stream:
            for row in [{"type": "started", "agentId": "terminal", "key": new_key, "label": label},
                        {"type": "result", "agentId": "terminal", "key": new_key, "result": {"fixture": True}}]:
                stream.write(json.dumps(row) + "\n")
        contract = json.loads((self.work / "contract.json").read_text())
        contract["calls"].append({"label": label, "original_agent_id": "new0", "original_key": old_key,
                                  "approved_rerun_key": new_key, "new_key_must_be_computed_from_actual_max_discovery": False})
        self.write("contract.json", contract)
        proof = copy.deepcopy(self.proof)
        proof["contractSha256"], proof["finalJournalSha256"] = self.sha("contract.json"), self.sha("journal.jsonl")
        proof["supersessionPairs"].append({"label": label, "superseded_agent_id": "new0", "superseded_key": old_key,
                                           "superseded_by_agent_id": "terminal", "superseded_by_key": new_key})
        proof["reruns"].append({"label": label, "agentId": "terminal", "key": new_key,
                                "supersedesAgentId": "new0", "supersedesKey": old_key, "keyKind": "approved-equal",
                                "transcriptPromptEqual": True, "nativeResultPresent": True})
        self.write("proof.json", proof)
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        document = json.loads((self.work / "usage.json").read_text())
        usage = document["child_usage"]
        self.assertEqual(usage["effort_mismatches"], [])
        self.assertEqual(len(usage["children"]), 106)
        self.assertEqual(len(usage["superseded_attempts"]), 21)
        self.assertEqual(next(c for c in usage["superseded_attempts"] if c["agent_id"] == "new0")["efforts"],
                         ["max", "low"])
        self.assertEqual(usage["by_resolved_model"], raw["by_resolved_model"])

    def test_dynamic_rerun_keys_require_the_actual_recomputed_proof(self):
        contract = json.loads((self.work / "contract.json").read_text())
        contract["calls"][0]["approved_rerun_key"] = None
        contract["calls"][0]["new_key_must_be_computed_from_actual_max_discovery"] = True
        self.write("contract.json", contract)
        proof = copy.deepcopy(self.proof)
        proof["contractSha256"] = self.sha("contract.json")
        proof["reruns"][0]["keyKind"] = "dynamic-recomputed"
        self.write("proof.json", proof)
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        prior = (self.work / "usage.json").read_bytes()
        proof["reruns"][0]["keyKind"] = "approved-equal"
        self.write("proof.json", proof)
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 2)
        self.assertEqual((self.work / "usage.json").read_bytes(), prior)

    def test_cli_effort_cannot_weaken_the_bound_contract(self):
        contract = json.loads((self.work / "contract.json").read_text())
        contract["calls"][0]["require_actual_later_complete_max_child"] = True
        self.write("contract.json", contract)
        proof = copy.deepcopy(self.proof)
        proof["contractSha256"] = self.sha("contract.json")
        self.write("proof.json", proof)
        raw = copy.deepcopy(self.raw)
        for child in [*raw["children"], *raw["superseded_attempts"]]:
            child["efforts"] = ["high"]
        raw["children"][0]["efforts"] = ["max", "low"]
        raw["children"][1]["efforts"] = ["max", "low"]
        self.write("raw.json", raw)
        done = self.run_usage(explicit=True, required="high")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("the bound supersession contract requires max effort", done.stderr)
        self.assertFalse((self.work / "usage.json").exists())
        self.write("raw.json", self.raw)
        control = self.run_usage(explicit=True)
        self.assertEqual(control.returncode, 0, control.stderr)

    def test_unbound_or_invalid_supersession_is_refused_before_writing(self):
        cases = {"contract_hash": "supersession proof contract or journal hash mismatch",
                 "journal_hash": "supersession proof contract or journal hash mismatch",
                 "run": "supersession proof does not establish this completed resumed run",
                 "key": "supersession pair is absent from the contract or proved reruns",
                 "duplicate": "supersession pairs repeat an identity or do not change the call key",
                 "effort": "supersession chain does not end at measured required effort",
                 "mixed_effort": "supersession chain does not end at measured required effort",
                 "label": "supersession needs measured complete same-label children and a later rerun",
                 "missing_result": "supersession pair is absent from the contract or proved reruns"}
        for case, diagnostic in cases.items():
            with self.subTest(case=case):
                proof, raw = copy.deepcopy(self.proof), copy.deepcopy(self.raw)
                if case == "contract_hash":
                    proof["contractSha256"] = "0" * 64
                elif case == "journal_hash":
                    proof["finalJournalSha256"] = "0" * 64
                elif case == "run":
                    proof["nativeRun"]["runId"] = "wf_other"
                elif case == "key":
                    proof["supersessionPairs"][0]["superseded_by_key"] = "v2:" + "f" * 64
                elif case == "duplicate":
                    proof["supersessionPairs"][1] = copy.deepcopy(proof["supersessionPairs"][0])
                elif case == "effort":
                    raw["children"][-12]["efforts"] = ["low"]
                elif case == "mixed_effort":
                    raw["children"][-12]["efforts"] = ["max", "low"]
                elif case == "label":
                    raw["children"][-12]["label"] = "other"
                elif case == "missing_result":
                    proof["reruns"][0]["nativeResultPresent"] = False
                self.write("proof.json", proof)
                self.write("raw.json", raw)
                (self.work / "usage.json").unlink(missing_ok=True)
                done = self.run_usage(explicit=True)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn(diagnostic, done.stderr)
                self.assertFalse((self.work / "usage.json").exists())


if __name__ == "__main__":
    unittest.main()
