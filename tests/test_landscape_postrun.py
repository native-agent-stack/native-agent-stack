"""Public CLI regressions for explicit resume accounting, without model calls."""

import copy
import hashlib
import json
import re
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_landscape_sweep_harness import HARNESS, child_usage_raw


class CompletedSupersessionTests(unittest.TestCase):
    def test_public_postrun_record_omits_private_journal_digest_prefix(self):
        record = HARNESS.parents[2] / "docs/decisions/2026-10-11-landscape-postrun-accounting.md"
        text = record.read_text(encoding="utf-8")
        # A shortened authentication token still confirms a guessed private preimage.
        self.assertIsNone(re.search(r"historically cited\s*[0-9a-fA-F]{7,}", text),
                          "private journal digest prefix remains in the public citation")

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
    def test_receipt_proof_digest_binds_published_redacted_proof_not_private_original(self):
        identity = "digest-fixture-" + self.work.name + "@" + "example.org"
        self.proof["private_note"] = identity
        self.write("proof.json", self.proof)
        private_digest = self.sha("proof.json")
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        published = (self.work / "usage.json").read_text()
        self.assertNotIn(identity, published)
        provenance = json.loads(published)["measurement"]["post_processing"]["explicit_supersession"]
        self.assertNotEqual(provenance["proof_sha256"], private_digest)
        redacted = provenance["proof"]
        self.assertEqual(redacted, {
            "status": "proved-actual-resumed-run",
            "nativeRun": {"runId": "wf_fixture-1", "status": "completed"},
            "originalPrefix": {"byteEqual": True},
            "reexecutedResultEqualsNative": True,
            "supersessionPairs": [{field: pair[field] for field in
                                   ("label", "superseded_agent_id", "superseded_by_agent_id")}
                                  for pair in self.proof["supersessionPairs"]],
        })
        published_preimage = (json.dumps(redacted, indent=1, ensure_ascii=False) + "\n").encode()
        self.assertEqual(provenance["proof_sha256"], hashlib.sha256(published_preimage).hexdigest())
        self.assertNotIn(private_digest, published)

    def test_public_cli_omits_unvalidated_metadata_inside_supersession_pairs(self):
        identity = "pair-fixture-" + self.work.name + "@" + "example.org"
        self.proof["supersessionPairs"][0]["capture_metadata"] = {
            "nested": [{"contact": identity, "private_note": "synthetic pair capture"}]}
        self.write("proof.json", self.proof)
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        receipt = (self.work / "usage.json").read_text()
        with self.subTest(publication="receipt"):
            self.assertFalse(identity in receipt, "unvalidated pair metadata reaches the receipt")
        with self.subTest(publication="cli"):
            self.assertFalse(identity in done.stdout + done.stderr, "unvalidated pair metadata reaches CLI output")
        provenance = json.loads(receipt)["measurement"]["post_processing"]["explicit_supersession"]
        fields = {"label", "superseded_agent_id", "superseded_by_agent_id"}
        for location in ("pairs", "proof"):
            pairs = provenance["pairs"] if location == "pairs" else provenance["proof"]["supersessionPairs"]
            with self.subTest(publication=location):
                self.assertTrue(all(set(pair) == fields for pair in pairs), "published pairs exceed validated fields")
        self.assertEqual(provenance["proof"]["supersessionPairs"], provenance["pairs"])
        preimage = (json.dumps(provenance["proof"], indent=1, ensure_ascii=False) + "\n").encode()
        self.assertEqual(provenance["proof_sha256"], hashlib.sha256(preimage).hexdigest())

    def test_public_cli_omits_private_raw_contract_and_journal_seals_and_prefixes(self):
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        receipt = (self.work / "usage.json").read_text()
        publications = {"receipt": receipt, "stdout": done.stdout, "stderr": done.stderr}
        for source, field in (("raw.json", "raw_output_sha256"), ("contract.json", "contract_sha256"),
                              ("journal.jsonl", "journal_sha256")):
            digest = self.sha(source)
            for location, text in publications.items():
                with self.subTest(source=source, publication=location):
                    self.assertFalse(digest[:7] in text.lower(), "private input seal or prefix reaches publication")
                    self.assertNotIn(field, text)
        provenance = json.loads(receipt)["measurement"]["post_processing"]["explicit_supersession"]
        self.assertEqual(set(provenance), {"proof", "proof_sha256", "processor_sha256", "pairs"})
        processor = HARNESS / "usage_record.py"
        self.assertEqual(provenance["processor_sha256"], hashlib.sha256(processor.read_bytes()).hexdigest())

    def test_public_cli_digest_audit_accepts_only_known_public_authentication(self):
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        pairs = [{field: pair[field] for field in
                  ("label", "superseded_agent_id", "superseded_by_agent_id")}
                 for pair in self.proof["supersessionPairs"]]
        public_proof = {"status": "proved-actual-resumed-run",
                        "nativeRun": {"runId": "wf_fixture-1", "status": "completed"},
                        "originalPrefix": {"byteEqual": True}, "reexecutedResultEqualsNative": True,
                        "supersessionPairs": pairs}
        public_bytes = (json.dumps(public_proof, indent=1, ensure_ascii=False) + "\n").encode()
        root = Path(__file__).resolve().parents[1]
        known_public = {hashlib.sha256(public_bytes).hexdigest(),
                        hashlib.sha256((HARNESS / "usage_record.py").read_bytes()).hexdigest(),
                        hashlib.sha256((root / "examples/claude-native/workflows/child-usage.mjs").read_bytes()).hexdigest(),
                        subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()}
        for location, text in (("receipt", (self.work / "usage.json").read_text()),
                               ("stdout", done.stdout), ("stderr", done.stderr)):
            with self.subTest(publication=location):
                tokens = set(re.findall(r"(?:v2:)?[0-9a-fA-F]{7,}", text))
                unknown = tokens - known_public
                native_keys = sum(token.startswith("v2:") for token in unknown)
                self.assertEqual(len(unknown), 0,
                                 f"{len(unknown)} unknown authentication tokens, including {native_keys} native keys")

    def test_public_cli_output_allowlist_withholds_unknown_nested_native_fields(self):
        private = "v2:" + hashlib.sha256(b"synthetic unpublished native prompt").hexdigest()
        self.raw["private_capture"] = {"key": private}
        self.raw["children"][0]["final_return"] = {"prompt_key": private}
        self.raw["children"][0]["usage"] = {"output_tokens": 5, "private_capture": private}
        self.raw["children"][0]["web_search"]["private_capture"] = private
        self.raw["by_resolved_model"]["fixture"]["private_capture"] = private
        self.raw["web_search"]["private_capture"] = private
        self.raw["effort_mismatches"][0]["private_capture"] = private
        self.write("raw.json", self.raw)
        done = self.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        receipt = (self.work / "usage.json").read_text()
        for location, text in (("receipt", receipt), ("stdout", done.stdout), ("stderr", done.stderr)):
            with self.subTest(publication=location):
                self.assertFalse(private[3:10] in text, "non-allowlisted native metadata reaches publication")
        value = json.loads(receipt)
        self.assertEqual(set(value), {"schema_version", "measurement", "child_usage"})
        self.assertEqual(set(value["measurement"]),
                         {"tool", "tool_sha256", "processor_sha256", "exit_code", "post_processing"})
        self.assertEqual(value["child_usage"]["by_resolved_model"]["fixture"]["output_tokens"], 4321)
        old = next(x for x in value["child_usage"]["superseded_attempts"] if x["agent_id"] == "old0")
        self.assertEqual(set(old["usage"]), {"output_tokens"})
        self.assertEqual(old["usage"]["output_tokens"], 5)

    def test_explicit_supersession_never_accepts_a_nonmax_required_effort(self):
        for child in self.raw["children"]:
            child["efforts"] = ["high"]
        self.raw["effort_mismatches"] = []
        self.write("raw.json", self.raw)
        done = self.run_usage(explicit=True, required="high")
        self.assertEqual(done.returncode, 2)
        self.assertIn("max effort", done.stderr)
        self.assertFalse((self.work / "usage.json").exists())

    def test_native_authentication_cannot_be_relabelled_as_a_public_status_or_label(self):
        private = "v2:" + hashlib.sha256(b"synthetic private prompt identity").hexdigest()
        for field, explicit in (("status", True), ("label", False)):
            with self.subTest(field=field):
                raw = copy.deepcopy(self.raw)
                if field == "status":
                    raw["status"] = private
                else:
                    raw["children"][0]["label"] = private
                self.write("raw.json", raw)
                done = self.run_usage(explicit=explicit)
                self.assertEqual(done.returncode, 2)
                self.assertEqual(done.stdout, "")
                self.assertFalse(private[3:10] in done.stderr)
                self.assertFalse((self.work / "usage.json").exists())

    def test_unhashable_native_journal_identities_refuse_without_a_traceback(self):
        original = (self.work / "journal.jsonl").read_text()
        for row_type in ("started", "result"):
            for field in ("agentId", "key"):
                for invalid in ([], {}):
                    with self.subTest(row_type=row_type, field=field, value_type=type(invalid).__name__):
                        rows = [json.loads(line) for line in original.splitlines()]
                        next(row for row in rows if row.get("type") == row_type)[field] = invalid
                        (self.work / "journal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                        proof = copy.deepcopy(self.proof)
                        proof["finalJournalSha256"] = self.sha("journal.jsonl")
                        self.write("proof.json", proof)
                        done = self.run_usage(explicit=True)
                        self.assertEqual(done.returncode, 2)
                        self.assertIn("invalid native identity", done.stderr)
                        self.assertNotIn("Traceback", done.stderr)
                        self.assertFalse((self.work / "usage.json").exists())

    def test_nontext_measured_agent_ids_refuse_on_explicit_and_ordinary_paths(self):
        for explicit in (False, True):
            for invalid in ([], {}):
                for prior_receipt in (False, True):
                    with self.subTest(explicit=explicit, value_type=type(invalid).__name__, prior=prior_receipt):
                        raw = copy.deepcopy(self.raw)
                        raw["children"][0]["agent_id"] = invalid
                        self.write("raw.json", raw)
                        path = self.work / "usage.json"
                        if prior_receipt:
                            path.write_text("previous receipt stays unchanged\n")
                        else:
                            path.unlink(missing_ok=True)
                        done = self.run_usage(explicit=explicit)
                        self.assertEqual(done.returncode, 2)
                        self.assertNotIn("Traceback", done.stderr)
                        self.assertEqual(done.stdout, "")
                        if prior_receipt:
                            self.assertEqual(path.read_text(), "previous receipt stays unchanged\n")
                        else:
                            self.assertFalse(path.exists())

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
                    self.assertNotIn("raw_output_sha256", receipt["measurement"])
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
        self.assertNotIn("raw_output_sha256", document["measurement"])
        provenance = document["measurement"]["post_processing"]["explicit_supersession"]
        proof_bytes = (json.dumps(provenance["proof"], indent=1, ensure_ascii=False) + "\n").encode()
        self.assertEqual(provenance["proof_sha256"], hashlib.sha256(proof_bytes).hexdigest())
        self.assertNotIn("contract_sha256", provenance)
        self.assertNotIn("journal_sha256", provenance)
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
