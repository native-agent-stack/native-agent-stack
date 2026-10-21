"""Operator-side class, replacement integrity and vacated-container regressions."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.test_blind_readset_v3 import ROOT, blind, redaction
import readset_audit as audit
import winner_asymmetry as asym


class WinnerAsymmetryTests(unittest.TestCase):
    candidates = [
        {"key": "C01", "name": "Cedar", "repository": "https://github.com/example/cedar",
         "component_id": "cedar", "pin": "1.2.3", "adopted": True},
        {"key": "C02", "name": "Birch", "repository": "https://github.com/example/birch",
         "component_id": "birch", "adopted": True},
    ]

    def result(self, node, installer=False):
        return asym.audit_layer(self.candidates, [("example/cedar", "cedar", "cedar")],
                                {"probe": list(asym.bindings(node, installer=installer))}, {"probe"})

    def test_each_binding_form_separates_and_balanced_controls_do_not(self):
        cases = {
            "slot": {"slot": "layer/cedar", "disposition": "not_counted_ready", "exit_code": 0},
            "cross-slot": {"slot": "cross:layer/cedar", "exit_code": 0},
            "default": {"settings": {"default": "Cedar"}},
            "interim": {"interim": {"repository": "example/cedar"}},
            "decided_by": {"decided_by": "Cedar"},
            "canonical": {"role": "frontend", "canonical": {"source": "example/cedar"}},
            "primary": {"primary": "Cedar"},
            "choice": {"choice": "Cedar"},
            "selection": {"selection": "Cedar"},
            "selected": {"selected": "Cedar"},
            "installed-owner": {"installed_owner": "Cedar"},
            "alternatives": {"alternatives": ["An alternative to Cedar remains unqualified"]},
            "owner": {"slot": "probe", "owner": "Cedar", "installed": "1.2.3"},
            "roadmap": {"slots": [{"slot_id": "layer/cedar", "status": "READY"}]},
            "pinned": {"pinned_requirements": {"probe": [{"owner": "layer", "name": "Cedar"}]}},
            "correction": "Cedar stays the selection and is the baseline of a comparison.",
            "installed": "The interim keeps its install gate. Cedar needs a store; the installed package serves nothing.",
            "function": "cedar() { printf 'scope'; }",
            "command": "npm install --global cedar@1.2.3",
            "dispatch": 'run_slot cedar',
        }
        for form, node in cases.items():
            with self.subTest(form=form):
                result = self.result(node, form in ("function", "command", "dispatch"))
                self.assertTrue(result["scored"])
                self.assertTrue(result["separating"])
                self.assertTrue(result["correlating"])
        self.assertFalse(self.result({"slots": [
            {"slot_id": "layer/cedar", "status": "READY"},
            {"slot_id": "layer/birch", "status": "READY"}]})["correlating"])
        self.assertFalse(self.result({"observations": [
            {"package": "Cedar", "installed": "1.2.3", "exit_code": 0} ]})["correlating"])
        self.assertFalse(self.result("Measured Cedar latency: 2 ms; Birch latency: 4 ms.")["correlating"])
        self.assertFalse(self.result("Cedarwood is the default value of a test parameter.")["correlating"])
        self.assertFalse(self.result({"selection": "Sum Cedar and Birch rows by their timestamp."})["correlating"])
        self.assertFalse(self.result("check() { cedar measure; }", True)["correlating"])
        self.assertFalse(self.result("Cedar's live-but-unreachable owner keeps its PID file.")["correlating"])
        self.assertFalse(self.result("Cedar logs do not prove every installed component is active.")["correlating"])

    def test_equal_presence_but_different_density_is_not_a_clean_result(self):
        self.assertTrue(self.result({"slots": [
            {"slot_id": "layer/cedar", "status": "READY"},
            {"slot_id": "layer/cedar", "status": "READY"},
            {"slot_id": "layer/birch", "status": "READY"}]})["correlating"])

    def test_closure_expands_directories_paths_embedded_json_and_links_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "docs/one.json").write_text(json.dumps({
                "wrapped": json.dumps({"link": "docs/two.md"})}))
            (root / "docs/two.md").write_text("[next](../third.md)")
            (root / "third.md").write_text("Uncited second-level link.")
            files = {"docs/one.json", "docs/two.md", "third.md"}
            self.assertEqual(asym.closure({"arbitrary": "docs/one.json"}, root, files),
                             {"docs/one.json", "docs/two.md"})
            self.assertEqual(asym.closure({"arbitrary": "docs"}, root, files), files)


class ReplacementAndNormalizationTests(unittest.TestCase):
    def test_selection_bearing_m1_unit_cannot_be_a_data_exception(self):
        exceptions = {(item["path"], item["sha256"])
                      for item in json.loads(audit.RULES.read_text())["data"]}
        self.assertNotIn((
            "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json",
            "9e1c81da8a380ad6fc1289e099e8981c9f2cbe75b025727ae8a8e66f23f9480d"),
            exceptions)

    def test_original_install_owner_span_works_without_a_parent_rewrite(self):
        relative = "evidence/artifacts/new-wsl-install-plan-20261002/owners.json"
        source = json.loads((ROOT / relative).read_text())
        source_digest = "84061872d94e9ab1f25df24f2d1a5c2819e20496136efc07fcda03517c8e4c8e"
        fragment = next(value for text in asym.strings(source)
                        for _, _, value in redaction.statements(text)
                        if redaction.digest(value) == source_digest)
        spans = {s["sha256"]: s for s in json.loads(redaction.CLASSIFICATION.read_text())["spans"]
                 if s["path"] == relative}
        records = []
        masked = redaction.redact_text(fragment, relative, "", records, b"k" * 32,
                                      redaction.classification(relative), spans)
        self.assertNotEqual(masked, fragment)
        self.assertTrue(records)
        self.assertTrue(all(len(row["old_sha256"]) == 64 for row in records))

    def test_real_residual_forms_are_masked_and_measurements_survive(self):
        base = "evidence/artifacts/"
        manifest = base + "new-wsl-definitive-defaults-20261001/definitive-manifest.json"
        plan = base + "new-wsl-install-plan-20261002/install-plan.json"
        measured = base + "env-freshness-20260924/wsl-ubuntu-main.json"
        practice = "catalogs/landscape/native-practice.json"
        paths = [manifest, plan, measured, practice] + [
            base + "ns2604-requalification-20261005/" + name + ".json"
            for name in ("review-715-corrections", "roadmap-tools", "roadmap-dispositions",
                         "roadmap-memory-skills", "roadmap-observation", "dated-readiness-rulings", "slots")]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            self.assertEqual(audit.audit_readset(root, paths)["findings"], [])
            original = json.loads((ROOT / manifest).read_text())
            masked = json.loads((root / manifest).read_text())
            self.assertEqual([s["measurement"] for s in masked["slots"]],
                             [s["measurement"] for s in original["slots"]])
            self.assertEqual((root / measured).read_bytes(), (ROOT / measured).read_bytes())
            self.assertNotIn("needs a Qdrant store", (root / manifest).read_text())
            self.assertNotIn("promptfoo follows the written manifest", (root / plan).read_text())
            self.assertNotIn("alternatives", json.loads((root / practice).read_text()))
            tokens = {"socraticode", "markitdown", "serena", "nautilustrader", "rtk",
                      "codex", "qmd", "promptfoo", "openhands"}
            contexts = asym.scan_files(root, paths)
            self.assertEqual([(relative, b.pointer, b.kind) for relative, values in contexts.items()
                              for b in values if asym.named(b.text, tokens)], [])
            for relative in paths:
                if "ns2604-requalification" in relative:
                    # A single-field re-exposure must fail even when its old
                    # verdict and decision keywords remain absent.
                    self.assertFalse(any(b.kind == "slot" for b in
                                         asym.bindings(json.loads((root / relative).read_text()))),
                                     relative)

    def test_every_replacement_is_bound_to_independently_reviewed_bytes(self):
        registry = json.loads(redaction.CLASSIFICATION.read_text())
        allowed = json.loads(audit.RULES.read_text())["replacement_sha256"]
        for span in registry["spans"]:
            if "replacement" in span:
                with self.subTest(path=span["path"], source=span["sha256"]):
                    self.assertEqual(hashlib.sha256(span["replacement"].encode()).hexdigest(),
                                     allowed[span["path"] + "/" + span["sha256"]])

    def test_installer_is_withheld_with_a_keyed_record_not_selection_commands(self):
        relative = "evidence/artifacts/new-wsl-install-plan-20261002/install.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / relative, target)
            manifest = blind.strip_worktree(root, b"k" * 32)
            self.assertFalse(target.exists())
            self.assertTrue(any(row["path"] == relative and len(row["old_sha256"]) == 64
                                for row in manifest["stripped_fields"]))
            self.assertNotIn("qmd", json.dumps(manifest))

    def test_newly_empty_lists_objects_and_list_elements_disappear(self):
        cue = "Cedar is the current choice."
        node = {"before": {"exit": 0}, "new_list": [{"choice": cue}],
                "new_object": {"choice": cue}, "already_empty": [], "measurement": {}}
        redaction.redact_document(node, "probe.json", "", [], b"k" * 32,
                                  {redaction.digest(cue): "choice"}, {}, {})
        self.assertEqual(node, {"before": {"exit": 0}, "already_empty": [], "measurement": {}})

    def test_audit_collection_form_does_not_need_slot_or_layer_keys(self):
        self.assertTrue(any("selection of record" in value for value in
                            audit.units(json.dumps({"slots": [{"label": "Cedar"}]}))))
        self.assertFalse(any("selection of record" in value for value in
                             audit.units(json.dumps({"measurements": [{"label": "Cedar", "ms": 2}]}))))

    def test_both_missing_choice_word_orders_and_negative_controls(self):
        for positive in ("OpenHands software-agent-sdk 1.50.1 stays the selection and is the baseline of a comparison.",
                         "The owner's order installs Cedar by default.",
                         "The selected 2.0.0rc5."):
            with self.subTest(text=positive):
                self.assertIsNotNone(audit.CHOICE.search(positive))
        for negative in ("Measured software-agent-sdk 1.50.1: 18 tests passed.",
                         "Cedar's install command exited 0 in the measurement.",
                         "The user selected a date in a native UI control.",
                         "A version 2.0.0rc5 was measured without an adoption decision."):
            with self.subTest(text=negative):
                self.assertIsNone(audit.CHOICE.search(negative))


if __name__ == "__main__":
    unittest.main()
