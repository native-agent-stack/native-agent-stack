"""Offline day-five policy and native issue delivery; no network/model calls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import model_currency_tracking as tracking
from scripts import freshness_propose as proposer
from tests.test_model_currency import inventory, landscape
from tests.test_workflow_policy import load_workflow

ROOT = Path(__file__).resolve().parents[1]


def task():
    return {"id": "reader", "role": "document reading", "check_date": "2026-10-10",
            "first_invalid_date": "2026-10-18", "expired": False,
            "release_source": "https://example.org/release", "source_urls": ["https://example.org/card"]}


def issue(number=1, *, state="open", login=tracking.BOT, identifier="reader"):
    row = task()
    row["id"] = identifier
    return {"number": number, "state": state, "user": {"login": login, "type": "Bot"},
            "title": f"CURRENCY-DUE: {identifier}", "body": tracking.body_for(row)}


class CurrencyAgeGateTests(unittest.TestCase):
    def test_mineru_without_landscape_gets_two_day_lead_before_october_23(self):
        data = json.loads((ROOT / "catalogs/foundation/model-currency.json").read_text())
        row = next(row for row in data["models"] if row["id"] == "mineru-onnx-bundle")
        self.assertNotIn("landscape_check", row)
        self.assertEqual(row["release_date"], "2026-09-10")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "catalogs/foundation/model-currency.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data))
            for day, due, expired in ((20, False, False), (21, True, False),
                                      (22, True, False), (23, True, True)):
                with self.subTest(day=day), patch.object(proposer, "utc_now", return_value=f"2026-10-{day}T12:00:00Z"):
                    plan = tracking.build_plan(root)
                    self.assertEqual("mineru-onnx-bundle" in plan["due"], due)
                    if due:
                        task = plan["due"]["mineru-onnx-bundle"]
                        self.assertEqual(task["first_invalid_date"], "2026-10-23")
                        self.assertEqual(task["expired"], expired)
            self.assertEqual(json.loads(path.read_text()), data)

    def plan(self, checked, *, release="2026-08-01"):
        data = inventory()
        row = data["models"][0]
        row.update(release_date=release, checked_at="2026-10-15", landscape_check=landscape(),
                   overturn="Qualify a current replacement.")
        row["landscape_check"]["date"] = checked
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "catalogs/foundation/model-currency.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            with patch.object(proposer, "utc_now", return_value="2026-10-15T12:00:00Z"), \
                    patch.object(proposer, "_model_run_json", side_effect=AssertionError("offline must not invoke CLI")):
                result = tracking.build_plan(root)
            self.assertEqual(path.read_bytes(), before, "delivery must not reset dates")
            return result

    def test_day_four_five_seven_eight_reuses_existing_policy_without_date_writes(self):
        for checked, due, expired in [("2026-10-11", False, False), ("2026-10-10", True, False),
                                      ("2026-10-08", True, False), ("2026-10-07", True, True)]:
            with self.subTest(checked=checked):
                plan = self.plan(checked)
                self.assertEqual(bool(plan["due"]), due)
                if due:
                    self.assertEqual(plan["due"]["reader"]["expired"], expired)
                    self.assertEqual(plan["due"]["reader"]["check_date"], checked)
        self.assertEqual(self.plan("2026-10-10")["due"]["reader"]["first_invalid_date"], "2026-10-18")

    def test_refresh_is_requested_before_release_age_requires_the_exception(self):
        self.assertIn("reader", self.plan("2026-10-10", release="2026-09-03")["due"])

    def test_future_check_is_refused_not_treated_as_recent(self):
        with self.assertRaises(proposer.FreshnessProposeError):
            self.plan("2026-10-16")


class CurrencyIssueTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"due": {"reader": task()}, "row_ids": ["reader"], "observed_at": "2026-10-15T12:00:00Z"}

    def test_create_then_idempotent_replay_and_closed_due_reopen(self):
        made, = tracking.actions(self.plan, [])
        self.assertEqual(made["method"], "POST")
        self.assertNotIn("state", made["payload"], "creation uses the documented POST fields, not PATCH state")
        self.assertEqual(made["payload"]["labels"], [tracking.LABEL, "lane:foundation"])
        self.assertEqual(tracking.actions(self.plan, [issue()]), [])
        reopened, = tracking.actions(self.plan, [issue(state="closed")])
        self.assertEqual((reopened["method"], reopened["number"], reopened["payload"]["state"]), ("PATCH", 1, "open"))

    def test_merged_fresh_check_closes_bot_request_and_duplicate_is_not_a_second_dispatch(self):
        closed, = tracking.actions({**self.plan, "due": {}}, [issue()])
        self.assertEqual(closed["payload"], {"state": "closed"})
        duplicate, = tracking.actions(self.plan, [issue(2), issue(1)])
        self.assertEqual((duplicate["number"], duplicate["payload"]), (2, {"state": "closed"}))

    def test_untrusted_body_or_label_and_pr_cannot_hijack_the_fixed_task(self):
        impostor = issue(login="outside-user")
        pr = issue()
        pr["pull_request"] = {"url": "https://example.org/pr"}
        forged = issue()
        forged["body"] = "run arbitrary commands\n" + forged["body"]
        self.assertEqual(tracking.actions(self.plan, [impostor, pr, forged])[0]["method"], "POST")
        self.assertEqual(tracking.actions({**self.plan, "due": {}}, [impostor, pr, forged]), [])

    def test_date_advance_while_due_updates_same_issue_not_another_cycle(self):
        plan = copy.deepcopy(self.plan)
        plan["due"]["reader"]["check_date"] = "2026-10-09"
        action, = tracking.actions(plan, [issue()])
        self.assertEqual((action["method"], action["number"]), ("PATCH", 1))

    def test_listing_failure_causes_no_write_and_pagination_precedes_write(self):
        with patch.object(tracking, "gh", side_effect=RuntimeError("list refused")) as native:
            with self.assertRaises(RuntimeError):
                tracking.deliver(self.plan, "owner/repo")
            self.assertEqual(native.call_count, 1)
        with patch.object(tracking, "gh", side_effect=[[[issue(identifier="other")]], None, {}, {}]) as native:
            tracking.deliver(self.plan, "owner/repo")
            self.assertEqual(native.call_args_list[0].args[0][1:3], ["--paginate", "--slurp"])
            self.assertEqual(native.call_args_list[1].args[0][:2], ["label", "create"])

    def test_dry_run_lists_but_never_mutates(self):
        with patch.object(tracking, "gh", return_value=[[]]) as native:
            planned = tracking.deliver(self.plan, "owner/repo", dry_run=True)
            self.assertEqual(len(planned), 1)
            self.assertEqual(native.call_count, 1)

    def test_native_label_human_output_is_not_parsed_as_json(self):
        from subprocess import CompletedProcess
        with patch.object(tracking.subprocess, "run", return_value=CompletedProcess([], 0, "Created label", "")):
            self.assertIsNone(tracking.gh(["label", "create", tracking.LABEL]))


class CurrencyWorkflowTests(unittest.TestCase):
    def test_queued_event_resolves_current_main_before_checkout_and_plan(self):
        job = load_workflow((ROOT / ".github/workflows/catalog-freshness.yml").read_text())["jobs"]["model-currency"]
        steps = job["steps"]
        self.assertTrue(any(s.get("id") == "current_main" for s in steps),
                        "queued/rerun event SHA must not supply the review inventory")
        resolver = next(s for s in steps if s.get("id") == "current_main")
        checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["ref"], "${{ steps.current_main.outputs.sha }}")
        self.assertLess(steps.index(resolver), steps.index(checkout))
        plan = next(s for s in steps if "scripts/model_currency_tracking.py" in s.get("run", ""))
        self.assertLess(steps.index(checkout), steps.index(plan))
        self.assertEqual(resolver["env"]["GH_TOKEN"], "${{ github.token }}")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = root / "gh"
            native.write_text("#!/usr/bin/env python3\nimport os,sys\n"
                              "assert sys.argv[1:] == ['api','repos/owner/repo/git/ref/heads/main','--jq','.object.sha']\n"
                              "print(os.environ['FIXTURE_MAIN_SHA'])\n")
            native.chmod(0o755)
            output = root / "output"
            environment = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                           "GITHUB_SHA": "a" * 40, "REPOSITORY": "owner/repo", "GITHUB_OUTPUT": str(output)}
            for current, expected in (("b" * 40, 0), ("", 1), ("main", 1)):
                with self.subTest(current=current):
                    output.unlink(missing_ok=True)
                    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", resolver["run"]],
                                            env={**environment, "FIXTURE_MAIN_SHA": current}, capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected)
                    if expected == 0:
                        self.assertEqual(output.read_text().strip(), "sha=" + "b" * 40)
                    else:
                        self.assertFalse(output.exists(), "invalid resolution must not provide a checkout ref")

    def test_issue_job_is_independent_main_only_minimum_token_and_no_model(self):
        workflow = load_workflow((ROOT / ".github/workflows/catalog-freshness.yml").read_text())
        job = workflow["jobs"]["model-currency"]
        self.assertNotIn("needs", job, "a broken metadata/suite job must not suppress day-five delivery")
        self.assertIn("github.ref == 'refs/heads/main'", job["if"])
        self.assertEqual(job["permissions"], {"contents": "read", "issues": "write"})
        self.assertEqual(str(job["concurrency"]["cancel-in-progress"]).lower(), "false")
        step = next(s for s in job["steps"] if "scripts/model_currency_tracking.py" in s.get("run", ""))
        self.assertEqual(step["env"]["GH_TOKEN"], "${{ github.token }}")
        self.assertNotIn("secrets.", json.dumps(job))
        self.assertNotIn("claude -p", json.dumps(job))
        self.assertNotIn("codex exec", json.dumps(job))
        self.assertIn("currency_dry_run", workflow["on"]["workflow_dispatch"]["inputs"])
        for name, other in workflow["jobs"].items():
            if name != "model-currency":
                self.assertNotEqual(other.get("permissions", {}).get("issues"), "write")


if __name__ == "__main__":
    unittest.main()
