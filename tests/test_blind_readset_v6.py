"""Table integrity, preservation and independent cue regressions for v6."""
from pathlib import Path
import json
import re
import shutil
import tempfile
import unittest

from tests.test_blind_readset_v3 import ROOT, blind, redaction
import export_isolation_check as isolation
import readset_audit as audit


class TableIntegrityTests(unittest.TestCase):
    def test_real_masked_tables_keep_delimiters_and_measured_cells(self):
        paths = [
            "docs/foundation-closure-20260921.md",
            "docs/candidate-quality-review-20260921.md",
            "docs/foundation-rd-readiness.md",
            "docs/memory-landscape-maintenance.md",
            "evidence/artifacts/gap-wave2-20260923/"
            "us-equities__security-supply-chain/README.md",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            originals = {}
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
                originals[relative] = target.read_text()
            blind.strip_worktree(root, b"k" * 32)
            for relative in paths:
                before = [line for line in originals[relative].splitlines()
                          if line.lstrip().startswith("|")]
                after = [line for line in (root / relative).read_text().splitlines()
                         if line.lstrip().startswith("|")]
                with self.subTest(path=relative):
                    self.assertEqual([line.count("|") for line in after],
                                     [line.count("|") for line in before])
            closure = (root / paths[0]).read_text()
            ecc = next(line for line in closure.splitlines() if "missing worker context" in line)
            self.assertIn("bounded refinement of missing worker context", ecc.split("|")[2])
            self.assertEqual(ecc.split("|")[3].strip(), "[withheld]")
            memory = (root / paths[3]).read_text()
            self.assertIn("One adopted project, allowlisted lifecycle capture", memory)
            security = (root / paths[4]).read_text()
            openbao = next(line for line in security.splitlines() if line.startswith("| 6 |"))
            self.assertEqual(openbao.split("|")[4].strip(), "Dev mode only.")

    def test_every_registered_table_keeps_each_nondecision_cell(self):
        import json
        registry = json.loads(redaction.CLASSIFICATION.read_text())
        key = b"k" * 32
        for relative, tables in registry["tables"].items():
            original = (ROOT / relative).read_text()
            masked = redaction.redact_tables(original, relative, [], key)
            spans = {span["sha256"]: span for span in registry["spans"] if span["path"] == relative}
            columns = []
            for before, after in zip(original.splitlines(), masked.splitlines(), strict=True):
                if not before.lstrip().startswith("|"):
                    columns = []
                    continue
                signature = redaction.digest(before)
                if signature in tables:
                    columns = tables[signature]
                reviewed = redaction.redact_text(before, relative, "", [], key, {}, spans)
                old_cells, new_cells = reviewed.split("|"), after.split("|")
                with self.subTest(path=relative, row=signature):
                    self.assertEqual(len(old_cells), len(new_cells))
                    self.assertTrue(after.lstrip().startswith("|"))
                    for column, cell in enumerate(old_cells):
                        if column not in columns:
                            self.assertEqual(new_cells[column], cell)

    def test_row_after_a_malformed_table_body_is_still_scored(self):
        text = ("| Tool | Scope |\n| --- | --- |\n| Cedar | measured |\n"
                "broken body |\n| Cedar | current choice |\n")
        rows = list(isolation.prose_statements(text))
        self.assertIn(("| Cedar | current choice |", False), rows)


class AdjacentPreservationTests(unittest.TestCase):
    def test_vacated_middle_list_item_keeps_both_measured_neighbors(self):
        cue = "Cedar is the current choice."
        node = ["before: exit 0", cue, "after: 18 samples"]
        redaction.redact_document(node, "probe.json", "", [], b"k" * 32,
                                  {redaction.digest(cue): "choice"}, {}, {})
        self.assertEqual(node, ["before: exit 0", "after: 18 samples"])

    def test_unchanged_measured_whitespace_is_byte_exact(self):
        cue = "Cedar is the current choice."
        node = {"measured": "  tab\t\tand  double space  ", "choice": cue}
        redaction.redact_document(node, "probe.json", "", [], b"k" * 32,
                                  {redaction.digest(cue): "choice"}, {}, {})
        self.assertEqual(node["measured"], "  tab\t\tand  double space  ")

    def test_vacated_dict_value_is_removed_without_losing_measurements(self):
        cue = "Cedar is the current choice."
        node = {"before": {"exit": 0}, "choice": cue, "after": "18 samples",
                "already_empty": ""}
        redaction.redact_document(node, "probe.json", "", [], b"k" * 32,
                                  {redaction.digest(cue): "choice"}, {}, {})
        self.assertEqual(node, {"before": {"exit": 0}, "after": "18 samples",
                                "already_empty": ""})

    def test_singular_lifecycle_stage_cue_needs_no_copula(self):
        self.assertTrue(isolation._states_selection("Cedar lifecycle stage: bounded.", []))

    def test_cut_leading_sentence_leaves_no_new_markdown_indent(self):
        cue = "Cedar is the current choice."
        source = cue + " Native measurement: 18 samples."
        after = redaction.redact_text(source, "probe.md", "", [], b"k" * 32,
                                      {redaction.digest(cue): "choice"}, {})
        self.assertEqual(after, "Native measurement: 18 samples.")


class SelectionCueTests(unittest.TestCase):
    def test_reviewed_selection_clauses_keep_their_measured_neighbors(self):
        cases = [
            ("docs/github-automation.md", "selection of record", "decision M45"),
            ("catalogs/landscape/candidate-quality-review.json",
             "selection remains", "held-out recall"),
            ("blueprints/convergence-practice/omniroute-runtime-workers/"
             "experiment-sdk-0160-20261003.json", "Selected source remains", "a956835d"),
            ("docs/foundation-closure-20260921.md", "selected ECC", "persistent native settings"),
            ("evidence/receipts/foundation-closure-20260921.json",
             "selected ECC", "six connected MCP servers"),
            ("catalogs/foundation/community-practice-20260920.json",
             "for this selection", "executable eval framework"),
            ("evidence/receipts/native-claude-profile-20260920.json",
             "Selected skill file", "do not establish improved task performance"),
            ("evidence/artifacts/new-wsl-definitive-defaults-20261001/"
             "definitive-manifest.json", "Its interim, semble", "needs a Qdrant store"),
            ("blueprints/us-equities/catalyst-provenance/"
             "native-network-edgartools-5600-20261004.json", "selection moves", "5.60.0"),
            ("blueprints/us-equities/runtime-2604/README.md",
             "bundle selected **EdgarTools", "25/25 offline checks passed"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, _, _ in cases:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            for relative, cue, measured in cases:
                with self.subTest(path=relative):
                    text = (root / relative).read_text()
                    self.assertFalse(cue in text, (relative, cue))
                    self.assertTrue(measured in text, (relative, measured))

    def test_new_selection_forms_have_data_negative_controls(self):
        cases = [
            ("Cedar selection remains bounded.", "File selection returns 18 rows."),
            ("Cedar is the selection of record.", "The selection of records took 4 ms."),
            ("The catalog selection moves to Cedar 2.", "Selection movement is measured in pixels."),
            ("The bundle selected Cedar 2.", "The query selected five rows."),
            ("Cedar (selected for this catalog).", "The measured count (selected_rows=5)."),
            ("Do not install Cedar for this selection.", "Use the column for this selection_count."),
            ("Selected source remains example/Cedar.", "The selected source files contain 18 samples."),
            ("Its interim, under the dated ruling, adds Cedar.", "Its interim measurement records 4 ms."),
            ("The catalog selection stays Cedar.", "Selection stability is measured, not adoption."),
        ]
        for positive, negative in cases:
            with self.subTest(cue=positive):
                self.assertIsNotNone(audit.CHOICE.search(positive))
                self.assertIsNone(audit.CHOICE.search(negative))


class V7SelectionBoundaryTests(unittest.TestCase):
    def test_memory_and_interim_forms_distinguish_records_from_data(self):
        cases = [
            ("Cedar is the memory of record.", "The memory of records is 18 bytes."),
            ("Retain ai-memory 2.3.2 as the shared store.", "Retain five rows as the sample."),
            ("The interim install uses Cedar.", "The interim installation time was 4 ms."),
            ("The interim installs both arms.", "Interim installment counts are measured."),
            ("It overlaps the selected `dagu-org/dagu`.", "The selected source files hold 18 rows."),
            ("The current host uses ai-memory.", "The current host measures 18 samples."),
        ]
        for positive, negative in cases:
            with self.subTest(cue=positive):
                plain = re.sub(r"[`*]", "", positive)
                self.assertIsNotNone(audit.CHOICE.search(plain))
                self.assertIsNone(audit.CHOICE.search(negative))

    def test_key_borne_slot_decisions_are_audited_without_matching_ui_defaults(self):
        selected = {"layer_id": "native-clients", "default": "Cedar",
                    "definitive": True, "state": "definitive",
                    "resolution": {"outcome": "final", "by": "both families"}}
        data = {"ui": {"default": "Cedar"}, "measurement": {"returned": True}}
        self.assertTrue(any(audit.CHOICE.search(unit) for unit in audit.units(json.dumps(selected))))
        self.assertFalse(any(audit.CHOICE.search(unit) for unit in audit.units(json.dumps(data))))

    def test_cited_memory_records_keep_measurements_but_not_selection(self):
        cases = [
            ("evidence/artifacts/memory-rag-lifecycle-20260921/native-client.json",
             "memory of record", "384-dimensional"),
            ("docs/dashboard-rendered-acceptance.md", "memory of record", "Zero Serena memories"),
            ("docs/memory-landscape-maintenance.md", "the current host uses", "vLLM 0.30.0"),
            ("docs/token-practice.md", "durable decisions with scoped ai-memory", "2,731"),
            ("evidence/artifacts/sdk-runtime-coverage-20260922/durable-runtimes.json",
             "the selected `dagu-org/dagu`", "nine retained runs"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, _, _ in cases:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            for relative, cue, measured in cases:
                with self.subTest(path=relative):
                    text = (root / relative).read_text()
                    self.assertFalse(cue in text, (relative, cue))
                    self.assertIn(measured, text)

    def test_slot_fields_are_withheld_but_measurements_and_sources_survive(self):
        relative = ("evidence/artifacts/new-wsl-definitive-defaults-20261001/"
                    "definitive-manifest.json")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / relative, target)
            original = json.loads(target.read_text())
            blind.strip_worktree(root, b"k" * 32)
            masked = json.loads(target.read_text())
            for before, after in zip(original["slots"], masked["slots"], strict=True):
                with self.subTest(slot=before["slot_id"]):
                    for field in ("default", "definitive", "state"):
                        self.assertFalse(field in after, (before["slot_id"], field))
                    self.assertEqual(after["measurement"], before["measurement"])
                    self.assertEqual(after["repository"], before["repository"])
            self.assertFalse("interim install on the owner's decisions" in target.read_text().lower())

    def test_each_pin_note_is_audited_when_restored_and_keeps_inventory_when_masked(self):
        paths = [
            "evidence/receipts/edgartools-5600-pin-move-20261004.json",
            "evidence/artifacts/edgartools-5600-20261004/pin-site-classification.json",
        ]
        digest = "6fbe4ab1bb0bbc07dae70094a32b463a5c2661268c2b7efd6e7ebea5ee8c5789"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            for relative in paths:
                with self.subTest(path=relative):
                    target = root / relative
                    view = target.read_text()
                    self.assertFalse("are live selection mirrors" in view)
                    for retained in ("5.60.0", "95cf94ca4", "29da752f5",
                                     "saturation-audit.json:3209", "upstream-snapshot.json:3524"):
                        self.assertIn(retained, view)
                    original = json.loads((ROOT / relative).read_text())
                    note = next(value for value in original.values() if isinstance(value, str)
                                and "five sites previously" in value)
                    target.write_text(json.dumps({"restored": note}))
                    findings = audit.audit_readset(root, [relative])["findings"]
                    self.assertIn(digest, [finding["sha256"] for finding in findings])
                    target.write_text(view)

    def test_new_masks_leave_no_trailing_comma_or_lost_noun_artifacts(self):
        paths = ["docs/github-automation.md",
                 "evidence/artifacts/sdk-runtime-coverage-20260922/durable-runtimes.json"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            blind.strip_worktree(root, b"k" * 32)
            markdown = (root / paths[0]).read_text()
            original = (ROOT / paths[0]).read_text()
            self.assertEqual(sum(line.endswith(" ") for line in markdown.splitlines()),
                             sum(line.endswith(" ") for line in original.splitlines()))
            text = (root / paths[1]).read_text()
            self.assertNotIn("dagu-org/dagu ,", text)
            self.assertNotIn("Omitting a from", text)


if __name__ == "__main__":
    unittest.main()
