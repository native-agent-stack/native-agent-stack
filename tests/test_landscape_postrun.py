"""Public CLI regressions for explicit resume accounting, without model calls."""

import copy
import hashlib
import json
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
                                       "efforts": ["max"], "superseded_by": "other0"} for i in range(8)]
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
        self.assertFalse((self.work / "usage.json").exists())

    def test_unbound_or_invalid_supersession_is_refused_before_writing(self):
        cases = ("contract_hash", "journal_hash", "run", "key", "duplicate", "effort", "mixed_effort", "label", "missing_result")
        for case in cases:
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
                self.assertFalse((self.work / "usage.json").exists())


if __name__ == "__main__":
    unittest.main()
