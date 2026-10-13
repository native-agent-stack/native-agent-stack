"""W1b advisory workflow: trusted base, read-only API and frozen CLI contract."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_workflow_policy import load_workflow, violations

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/source-citations-report.yml"
FIXTURE = ROOT / "tests/fixtures/source-citations-report/verifier.py"
FIXTURE_SHA256 = "3e02319fba3f95ea51c3d7894f80e6c8e4ffe82082d3e67026518e4bee85ddd8"


class SourceCitationsReportWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = load_workflow(cls.text)
        cls.job = cls.workflow["jobs"]["source-citations"]
        cls.step = cls.job["steps"][1]

    def test_event_and_trusted_base_exclude_pr_head_execution(self):
        self.assertEqual(set(self.workflow["on"]), {"pull_request"})
        self.assertEqual(self.workflow["on"]["pull_request"]["branches"], ["main"])
        self.assertEqual(set(self.workflow["on"]["pull_request"]["types"]),
                         {"opened", "synchronize", "reopened", "edited", "ready_for_review"})
        self.assertEqual(self.job["steps"][0]["with"]["ref"], "${{ github.event.pull_request.base.sha }}")
        self.assertEqual(self.job["steps"][0]["with"]["persist-credentials"], "false")
        self.assertEqual(len(self.job["steps"]), 2)
        self.assertNotIn("head.sha", self.text)
        self.assertNotIn("pull_request_target", self.text)

    def test_permissions_and_actions_follow_the_report_only_boundary(self):
        self.assertEqual(self.workflow["permissions"], {})
        self.assertEqual(self.job["permissions"], {"contents": "read", "pull-requests": "read"})
        self.assertEqual(self.workflow["cache-mode"], "none")
        self.assertEqual(self.job["continue-on-error"], "true")
        self.assertEqual(self.step["if"], "always()")
        self.assertEqual(violations(WORKFLOW.name, self.text), [])
        action = self.job["steps"][0]["uses"]
        self.assertRegex(action, r"\Aactions/checkout@[a-f0-9]{40}\Z")
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("${{", self.step["run"])

    def test_contract_fixture_is_frozen_and_not_a_repository_revision_pin(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), FIXTURE_SHA256)

    def run_report(self, status=0, summary=True, installed=True, pr="42"):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            if installed:
                destination = directory / "tools/sota-sources/verify_sources.py"
                destination.parent.mkdir(parents=True)
                shutil.copyfile(FIXTURE, destination)
            summary_path = directory / "summary.md"
            environment = {"PATH": os.environ.get("PATH", ""),
                           "GITHUB_STEP_SUMMARY": str(summary_path), "RUNNER_TEMP": str(directory),
                           "SOURCE_REPOSITORY": "example/project", "SOURCE_PR": pr,
                           "FIXTURE_EXIT": str(status), "FIXTURE_SUMMARY": "yes" if summary else "no"}
            result = subprocess.run(["bash", "--noprofile", "--norc", "-c", self.step["run"]],
                                    cwd=directory, env=environment, capture_output=True, text=True, timeout=20)
            text = summary_path.read_text() if summary_path.exists() else ""
            report_path = directory / "source-citations-report.json"
            report = json.loads(report_path.read_text()) if report_path.exists() else None
            self.assertFalse((directory / "injected").exists())
            return result, text, report

    def test_findings_use_report_mode_and_write_the_cli_summary(self):
        result, summary, report = self.run_report()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["mode"], "report")
        self.assertEqual(report["source"], {"repo": "example/project", "pr": 42})
        self.assertIn("line-range-out-of-bounds", summary)
        self.assertIn("## Verified sources", summary)

    def test_cli_failures_are_reported_without_failing_the_step(self):
        for status in (1, 2, 3, 7):
            for summary_written in (True, False):
                with self.subTest(status=status, summary=summary_written):
                    result, summary, _ = self.run_report(status=status, summary=summary_written)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("report unavailable", summary)
                    self.assertIn(f"exited {status};", summary)

    def test_missing_dependency_reports_the_trusted_base_gap(self):
        result, summary, report = self.run_report(installed=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(report)
        self.assertIn("trusted PR base", summary)
        self.assertIn("#1003", summary)

    def test_pr_input_is_an_argument_and_never_shell_source(self):
        result, summary, _ = self.run_report(pr="42; touch injected")
        self.assertEqual(result.returncode, 0)
        self.assertIn("report unavailable", summary)


if __name__ == "__main__":
    unittest.main()
