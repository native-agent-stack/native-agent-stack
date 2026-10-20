"""Table integrity, preservation and independent cue regressions for v6."""
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
