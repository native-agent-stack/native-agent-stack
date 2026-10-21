"""Real-data preservation and independent blind-readset regression contracts."""
import hashlib
import hmac
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools/sota-convergence"
sys.path.insert(0, str(TOOLS))
import blind_checkout as blind
import readset_redaction as redaction


def walk_strings(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from walk_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_strings(value)
    elif isinstance(node, str):
        yield node


class IndependentAuditTests(unittest.TestCase):
    def test_redacted_table_column_does_not_reintroduce_a_choice_heading(self):
        import export_isolation_check as isolation
        relative = "docs/foundation-closure-20260921.md"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            rows = [(text, headed) for text, headed in isolation.prose_statements(target.read_text())
                    if "developers.openai.com/codex/sdk" in text]
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0][1], rows[0])
            self.assertIn("0.155.1", rows[0][0])

    def test_every_text_encoding_and_json_keys_are_scanned(self):
        cases = [
            "The current\nchoice is Cedar.",
            "The **current** choice is Cedar.",
            "current_choice: Cedar",
            '{"current_choice": "Cedar"}',
            "Cedar is the default.",
            "We keep Cedar.",
            "Cedar won.",
            "Cedar is the winner.",
            "Host receipts do not bind to that winner.",
            "The selected [Cedar source](https://example.org/source).",
            "Native acceptance for the Cedar selected path.",
            "Cedar remains the frozen historical comparator.",
            "Cedar took the slot.",
            "Native Codex SDK remains the incumbent.",
        ]
        suffixes = [".md", ".txt", ".json", ".out", ".stderr", ".py", ".0472177", ""]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, text in enumerate(cases):
                for suffix in suffixes:
                    name = f"{index}{suffix}"
                    (root / name).write_text(text)
                    with self.subTest(case=index, suffix=suffix):
                        self.assertTrue(redaction.content_findings(root, {name}))
            (root / "binary.txt").write_bytes(b"\x00\xffThe current choice is Cedar.")
            self.assertEqual(redaction.content_findings(root, {"binary.txt"}), [])

    def test_history_without_json_suffix_is_redacted_and_audited(self):
        relative = "blueprints/convergence-practice/application-delivery/history/experiment.json.0472177"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            document = json.loads(target.read_text())
            self.assertEqual(document.get("discovery_provenance"), [])
            self.assertEqual(redaction.content_findings(root, {relative}), [])

    def test_real_source_twin_is_redacted_and_restoring_it_fails_audit(self):
        relative = ("evidence/artifacts/omniroute-sdk-worker-0160-20261003/historical/"
                    "omniroute-runtime-workers-experiment.json.source.txt")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / relative
            target.parent.mkdir(parents=True)
            original = (ROOT / relative).read_bytes()
            target.write_bytes(original)
            blind.strip_worktree(root, b"k" * 32)
            self.assertNotEqual(target.read_bytes(), original)
            self.assertEqual(redaction.content_findings(root, {relative}), [])
            target.write_bytes(original)
            self.assertTrue(redaction.content_findings(root, {relative}))

    def test_no_lane_file_carries_withheld_routes(self):
        relative = "evidence/artifacts/landscape-sweep-20260926/returns.json"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            target = root / relative
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"discovery": {"count": 1},
                                          "votes": {"proof": "evidence/measurement.json"}}))
            (root / "evidence/measurement.json").write_text('{"exit_code": 0}')
            manifest = blind.strip_worktree(root, b"k" * 32)
            (root / "BLIND-MANIFEST.json").write_text(json.dumps(manifest))
            packets = Path(temporary) / "packets"
            packets.mkdir()
            (packets / "foundation__fixture.json").write_text(json.dumps(
                {"candidates": [{"evidence_refs": [relative]}]}))
            export = Path(temporary) / "export"
            blind.export_tree(root, export, allow_from_packets=packets)
            self.assertTrue((export / "evidence/measurement.json").is_file())
            for path in export.rglob("*"):
                if path.is_file():
                    self.assertNotIn(b"withheld_choice_evidence_refs", path.read_bytes())
            self.assertNotIn("withheld_choice_evidence_refs", json.loads(target.read_text()))


class PreservationTests(unittest.TestCase):
    def test_source_hash_binding_stays_original_and_operator_binds_the_view(self):
        relative = "docs/memory-landscape-maintenance.md"
        original = (ROOT / relative).read_bytes()
        key = b"k" * 32
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            target = root / relative
            target.parent.mkdir(parents=True)
            target.write_bytes(original)
            binder = root / "evidence/binding.json"
            binder.parent.mkdir()
            binding = {"path": relative, "sha256": hashlib.sha256(original).hexdigest()}
            binder.write_text(json.dumps(binding))
            manifest = blind.strip_worktree(root, key)
            (root / "BLIND-MANIFEST.json").write_text(json.dumps(manifest))
            changed = next(item for item in manifest["rewritten_files"] if item["path"] == relative)
            self.assertEqual(changed["original_hmac_sha256"],
                             hmac.new(key, original, hashlib.sha256).hexdigest())
            self.assertEqual(changed["view_hmac_sha256"],
                             hmac.new(key, target.read_bytes(), hashlib.sha256).hexdigest())
            self.assertNotEqual(changed["original_hmac_sha256"], changed["view_hmac_sha256"])
            packets = Path(temporary) / "packets"
            packets.mkdir()
            (packets / "foundation__fixture.json").write_text(json.dumps(
                {"candidates": [{"evidence_refs": [relative, "evidence/binding.json"]}]}))
            export = Path(temporary) / "export"
            blind.export_tree(root, export, allow_from_packets=packets)
            self.assertEqual(json.loads((export / "evidence/binding.json").read_text()), binding)
            self.assertFalse((export / "BLIND-MANIFEST.json").exists())
            for name in blind.ROOT_INSTRUCTION_STUBS:
                self.assertEqual((export / name).read_text(), blind.EXPORT_INSTRUCTION_STUB)

    def test_inspect_measured_dispositions_remain_exact(self):
        base = ROOT / "evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/raw"
        total = 0

        def outcomes(node, path=""):
            found = {}
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "disposition" and value in ("advisory_insufficient", "reject_evidence"):
                        found[path + "/" + key] = value
                    found.update(outcomes(value, path + "/" + key))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    found.update(outcomes(value, path + "/" + str(index)))
            return found

        for path in base.rglob("*.json"):
            document = json.loads(path.read_text())
            expected = outcomes(document)
            if expected:
                total += len(expected)
                blind.strip_evidence_verdicts(document, path.relative_to(ROOT).as_posix(), [], b"k" * 32)
                with self.subTest(path=path.name):
                    self.assertEqual(outcomes(document), expected)
        self.assertEqual(total, 125)

    def test_data_table_and_single_word_are_not_adoption(self):
        relatives = [
            "blueprints/us-equities/point-in-time/README.md",
            "blueprints/us-equities/adaptive-paper/trials/mac-2026-09-24-mover-a/README.md",
            "evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/raw/7-AcctAppMarginAndCustAgmt.pypdf.txt",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in relatives:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            for relative in relatives:
                with self.subTest(path=relative):
                    self.assertEqual((root / relative).read_bytes(), (ROOT / relative).read_bytes())

    def test_all_reviewed_spans_preserve_every_byte_outside_the_span(self):
        registry = json.loads(redaction.CLASSIFICATION.read_text())
        for span in registry["spans"]:
            text = (ROOT / span["path"]).read_text()
            try:
                values = list(walk_strings(json.loads(text)))
            except ValueError:
                values = [text]
            if span.get("unit") == "line":
                source = next(line for text in values for line in text.splitlines()
                              if redaction.digest(line) == span["sha256"])
            elif span.get("unit") == "paragraph":
                source = next(part.group() for text in values
                              for part in re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*", text)
                              if redaction.digest(part.group()) == span["sha256"])
            else:
                source = next(value for text in values for _, _, value in redaction.statements(text)
                              if redaction.digest(value) == span["sha256"])
            stripped = []
            after = redaction.redact_text(source, span["path"], "", stripped, b"k" * 32,
                                          redaction.classification(span["path"]), {span["sha256"]: span})
            ranges = span.get("ranges", [[span["start"], span["end"]]])
            expected = source
            for start, end in sorted(ranges, reverse=True):
                left, right = expected[:start], expected[end:]
                if not right or right.startswith(("\n", ",", ".", ";", ":")):
                    left = left.rstrip(" \t")
                if not left or left.endswith("\n"):
                    right = right.lstrip(" \t")
                if left.endswith((" ", "\t")) and right.startswith((" ", "\t")):
                    right = right.lstrip(" \t")
                expected = left + right
            with self.subTest(path=span["path"]):
                self.assertEqual(after, expected)
                self.assertEqual(len(stripped), len(ranges))

    def test_field_hash_mismatch_preserves_a_new_measured_value(self):
        field = next(item for item in json.loads(redaction.CLASSIFICATION.read_text())["fields"]
                     if item["sha256"] and item["pointer"].count("/") == 1)
        name = field["pointer"][1:]
        document = {name: {"observed_at": "2026-10-20", "exit_code": 0}}
        expected = json.loads(json.dumps(document))
        redaction.redact_document(document, field["path"], "", [], b"k" * 32, {},
                                  {field["path"] + field["pointer"]: field["sha256"]}, {})
        self.assertEqual(document, expected)

    def test_whitespace_variants_do_not_escape_known_choice_redaction(self):
        registry = json.loads(redaction.CLASSIFICATION.read_text())
        entry = next(item for item in registry["statements"]
                     if item["disposition"] == "choice" and item["path"].endswith(".md"))
        text = (ROOT / entry["path"]).read_text()
        source = next(value for _, _, value in redaction.statements(text)
                      if redaction.digest(value) == entry["sha256"])
        variant = source.replace(" ", "  ")
        result = redaction.redact_text(variant, entry["path"], "", [], b"k" * 32,
                                      redaction.classification(), {})
        self.assertNotEqual(result, variant)


if __name__ == "__main__":
    unittest.main(verbosity=2)
