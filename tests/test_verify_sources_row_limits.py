"""Final-round report amplification regressions; synthetic inputs, no network."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_verify_sources import V, AT_FORM, Fake, recorded_routes, run_main


class RowLimitTests(unittest.TestCase):
    def setUp(self):
        # create=True lets these exact assertions replay on the unchanged old
        # source, which ignores the new budgets rather than raising AttributeError.
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(V, "MAX_ROWS", 4, create=True).start()
        mock.patch.object(V, "MAX_ENTRY_CHARS", 32, create=True).start()
        mock.patch.object(V, "MAX_ROW_FIELD_CHARS", 64, create=True).start()

    def rows(self, content, routes=None):
        return V.verify_body("## SOTA sources\n\n" + content, V.GitHub(fetch=Fake(routes or {})))[1]

    def assert_omitted(self, rows, count):
        self.assertLessEqual(len(rows), 5)
        self.assertEqual(rows[-1]["omitted_rows"], count)
        self.assertEqual(rows[-1]["status"], V.UNAVAILABLE)
        self.assertEqual(V.exit_code(rows, "enforce"), 3)

    def test_diagnostics_have_one_exact_omission_row(self):
        self.assert_omitted(self.rows("a/b@x " * 1000), 996)

    def test_recognized_occurrences_stop_verification_at_the_row_budget(self):
        with mock.patch.object(V, "verify_citation", wraps=V.verify_citation) as checked:
            rows = self.rows("\n".join("- " + AT_FORM for _ in range(8)), recorded_routes())
        self.assert_omitted(rows, 4)
        self.assertEqual(checked.call_count, 4)
        self.assertEqual([row["status"] for row in rows[:-1]], ["ok"] * 4)

    def test_candidate_free_entries_are_also_bounded(self):
        self.assert_omitted(self.rows("\n".join("- plain source " + str(i) for i in range(9))), 5)

    def test_entry_and_other_repeated_display_fields_are_truncated(self):
        rows = self.rows("[exception:" + "r" * 1000 + "] a/b@x")
        self.assertLessEqual(len(rows[0]["entry"]), 32)
        self.assertTrue(rows[0]["entry"].endswith("…"))
        self.assertTrue(all(len(value) <= 64 for value in rows[0].values() if isinstance(value, str)))
        self.assertTrue(rows[0]["notes"])

    def test_actual_cli_records_limits_and_keeps_the_report_small(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "body.md"
            path.write_text("## SOTA sources\n\n" + "a/b@x " * 1000, encoding="utf-8")
            code, out, err, fake = run_main(["--body-file", str(path), "--mode", "enforce"],
                                           environment={"GITHUB_TOKEN": "", "GITHUB_STEP_SUMMARY": ""})
        report = json.loads(out)
        self.assertLess(len(out.encode()), 30_000)
        self.assert_omitted(report["rows"], 996)
        self.assertEqual(code, 3)
        self.assertEqual(report["omitted_rows"], 996)
        self.assertEqual({key: report["limits"][key] for key in
                          ("rows", "omission_rows", "entry_characters", "row_field_characters")},
                         {"rows": 4, "omission_rows": 1, "entry_characters": 32, "row_field_characters": 64})
        self.assertIn("0 code citations", err)
        self.assertIn("996", V.markdown(report))
        self.assertEqual(fake.calls, [])

    def test_citation_budget_is_preserved_inside_the_row_budget(self):
        with mock.patch.object(V, "MAX_CITATIONS", 2):
            rows = self.rows("\n".join("- " + AT_FORM for _ in range(8)), recorded_routes())
        self.assert_omitted(rows, 4)
        self.assertEqual([row["status"] for row in rows[:-1]], ["ok", "ok", V.NOT_CHECKED, V.NOT_CHECKED])

    def test_exact_row_boundary_has_no_omission_and_keeps_every_entry(self):
        rows = self.rows("\n".join("- plain source " + str(i) for i in range(4)))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(not row.get("omitted_rows") for row in rows))
        self.assertEqual(V.exit_code(rows, "enforce"), 0)
