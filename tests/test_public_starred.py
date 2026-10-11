"""Public metadata boundary, age retention, and retryable weekly notification."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import public_starred as stars


NOW = datetime(2026, 10, 10, 17, tzinfo=timezone.utc)
ENDPOINT = "https://api.github.com/users/example/starred?per_page=100"


def api_row(repo="example/project", **extra):
    return {"full_name": repo, "html_url": "https://github.com/" + repo,
            "private": False, "visibility": "public", "archived": False,
            "fork": False, "default_branch": "main", "description": "public description",
            "topics": ["python"], "license": {"spdx_id": "MIT"},
            "pushed_at": "2026-10-09T00:00:00Z", **extra}


class PublicStarredTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "checkout"
        self.canonical = self.root / stars.STARS
        self.canonical.parent.mkdir(parents=True)
        self.state = self.base / "state"
        self.questions = self.base / "lane.questions.md"
        self.questions.write_text("# Lane questions\n", encoding="utf-8")
        self.baseline = {"schema_version": 1, "kind": "public_starred", "endpoint": ENDPOINT,
                         "convergence_manifest": "catalogs/example.json",
                         "retrieved_at": "2026-10-01", "count": 1, "repositories": [
                             {"repository": "example/project", "disposition": "IN-SCOPE: parsing",
                              "disposition_status": "SOURCE-REVIEW", "layer_keys": ["parsing"],
                              "seed_refs": [{"source": "catalogs/example.json#/seeds/0"}],
                              "verdict_refs": [], "verdict_follow_up": "await recorded verdict",
                              "reason": "source review recorded in the linked evidence",
                              "convergence_manifest": "catalogs/example.json#/repositories/0"}]}
        self.save_baseline()

    def save_baseline(self):
        self.canonical.write_text(json.dumps(self.baseline), encoding="utf-8")

    def api(self, pages):
        return patch.object(stars.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["gh"], 0, json.dumps(pages), ""))

    def refresh_state(self):
        return stars.refresh_public_stars(self.root, state_dir=self.state,
                                          questions=self.questions, now=NOW)

    def test_paginated_metadata_is_allowlisted_and_public_only(self):
        private = api_row("private/hidden", private=True, owner={"unrecorded": "account field"})
        internal = api_row("internal/hidden", visibility="internal")
        public = api_row(owner={"unrecorded": "account field"}, permissions={"admin": True},
                         watchers_count=100, license={"spdx_id": "MIT", "url": "unused"})
        with self.api([[public, private], [internal, api_row("example/new")]]) as fetch:
            result = stars.refresh_public_stars(self.root, output=stars.STARS, now=NOW)
        snapshot = json.loads(self.canonical.read_text())
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["new_count"], 1)
        self.assertEqual(snapshot["filtered_nonpublic_count"], 2)
        self.assertEqual(set(snapshot["repositories"][1]), set(stars.PUBLIC_FIELDS) | {
            "disposition", "disposition_status", "first_observed_at"})
        self.assertEqual(snapshot["repositories"][0]["license_metadata"], "MIT")
        serialized = self.canonical.read_text()
        for unwanted in ("permissions", "watchers_count", "unrecorded", "private/hidden", "internal/hidden"):
            self.assertNotIn(unwanted, serialized)
        args = fetch.call_args.args[0]
        for flag in ("--paginate", "--slurp", "--hostname"):
            self.assertIn(flag, args)
        self.assertEqual(args[2], "users/example/starred?per_page=100")

    def test_rebuild_keeps_top_level_convergence_status_and_exact_canonical_bytes(self):
        self.baseline["convergence_status"] = "SOURCE-SCOPED; recorded tier verdicts pending"
        self.save_baseline()
        with self.api([[api_row()]]):
            stars.refresh_public_stars(self.root, output=stars.STARS, now=NOW)
        first = self.canonical.read_bytes()
        self.assertEqual(json.loads(first).get("convergence_status"), self.baseline["convergence_status"])
        rebuilt = stars._build(json.loads(first), [api_row()], NOW)
        stars._write_json(self.canonical, rebuilt)
        self.assertEqual(self.canonical.read_bytes(), first)

    def test_duplicate_or_malformed_page_does_not_replace_snapshot(self):
        original = self.canonical.read_bytes()
        for pages in ([[api_row()], [api_row("EXAMPLE/project")]], [api_row()], {"message": "error"}, []):
            with self.subTest(pages_type=type(pages).__name__), self.api(pages):
                with self.assertRaises(ValueError):
                    stars.refresh_public_stars(self.root, output=stars.STARS, now=NOW)
            self.assertEqual(self.canonical.read_bytes(), original)

    def test_failed_cli_never_echoes_unallowlisted_error_data(self):
        error_result = subprocess.CompletedProcess(["gh"], 1, "", "UNALLOWLISTED ERROR DATA")
        with patch.object(stars.subprocess, "run", return_value=error_result):
            with self.assertRaisesRegex(ValueError, r"failed \(exit 1\)") as raised:
                stars.refresh_public_stars(self.root, output=stars.STARS, now=NOW)
        self.assertNotIn("UNALLOWLISTED", str(raised.exception))

    def test_missing_cli_reports_gh_without_replacing_snapshots_or_notifications(self):
        original = self.canonical.read_bytes()
        questions = self.questions.read_bytes()
        for arguments in ({"output": stars.STARS},
                          {"state_dir": self.state, "questions": self.questions}):
            with self.subTest(mode=next(iter(arguments))):
                with patch.dict(os.environ, {"PATH": str(self.base / "empty-cli-path")}):
                    with self.assertRaisesRegex(ValueError, r"GitHub CLI \(gh\) was not found on PATH"):
                        stars.refresh_public_stars(self.root, now=NOW, **arguments)
                self.assertEqual(self.canonical.read_bytes(), original)
                self.assertEqual(self.questions.read_bytes(), questions)
                self.assertFalse((self.state / stars.SNAPSHOT_NAME).exists())
                self.assertFalse((self.state / stars.JOURNAL_NAME).exists())

    def test_public_endpoint_cannot_redirect_cli_or_change_api_surface(self):
        for endpoint in ("https://example.invalid/users/example/starred?per_page=100",
                         "https://api.github.com/user/starred?per_page=100",
                         "https://api.github.com/users/example/starred?per_page=100&extra=1"):
            with self.subTest(endpoint=endpoint):
                self.baseline["endpoint"] = endpoint
                self.save_baseline()
                with patch.object(stars.subprocess, "run") as fetch:
                    with self.assertRaises(ValueError):
                        stars.refresh_public_stars(self.root, output=stars.STARS, now=NOW)
                fetch.assert_not_called()

    def test_weekly_state_preserves_age_and_takes_current_canonical_review(self):
        original = self.canonical.read_bytes()
        with self.api([[api_row(), api_row("example/new")]]):
            first = self.refresh_state()
        self.assertEqual(first["queued_count"], 1)
        self.assertEqual(self.canonical.read_bytes(), original)
        path = self.state / stars.SNAPSHOT_NAME
        snapshot = json.loads(path.read_text())
        snapshot["repositories"][0]["disposition"] = "STALE SCRATCH DECISION"
        snapshot["repositories"][1]["disposition"] = "UNREVIEWED SCRATCH DECISION"
        path.write_text(json.dumps(snapshot))
        self.baseline["retrieved_at"] = "2026-10-10"
        self.baseline["repositories"][0]["disposition"] = "OUT-OF-SCOPE: recorded current review"
        self.save_baseline()
        with self.api([[api_row(), api_row("example/new")]]):
            second = stars.refresh_public_stars(self.root, state_dir=self.state,
                                                questions=self.questions, now=NOW + timedelta(days=7))
        refreshed = json.loads(path.read_text())["repositories"]
        self.assertEqual(refreshed[0]["disposition"], "OUT-OF-SCOPE: recorded current review")
        self.assertEqual(refreshed[0]["first_observed_at"], "2026-10-01T00:00:00Z")
        self.assertEqual(refreshed[0]["reason"], self.baseline["repositories"][0]["reason"])
        self.assertEqual(refreshed[0]["convergence_manifest"], "catalogs/example.json#/repositories/0")
        self.assertEqual(json.loads(path.read_text())["convergence_manifest"], "catalogs/example.json")
        self.assertTrue(refreshed[1]["disposition"].startswith("NEEDS-EVIDENCE"))
        self.assertEqual(refreshed[1]["first_observed_at"], "2026-10-10T17:00:00Z")
        self.assertFalse(second["newstars_posted"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)

    def test_notification_append_failure_remains_retryable_after_snapshot_write(self):
        with self.api([[api_row(), api_row("example/new")]]), patch.object(
                stars, "_notify", side_effect=OSError("simulated append failure")):
            with self.assertRaises(OSError):
                self.refresh_state()
        self.assertTrue((self.state / stars.SNAPSHOT_NAME).is_file())
        journal = json.loads((self.state / stars.JOURNAL_NAME).read_text())
        self.assertEqual(journal["notification_state"], "prepared")
        self.assertEqual(journal["pending_repositories"], ["example/new"])
        with self.api([[api_row(), api_row("example/new")]]):
            receipt = self.refresh_state()
        self.assertTrue(receipt["newstars_posted"])
        with self.api([[api_row(), api_row("example/new")]]):
            self.assertFalse(self.refresh_state()["newstars_posted"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)

    def test_queue_clears_only_after_canonical_disposition_arrives(self):
        with self.api([[api_row(), api_row("example/new")]]):
            self.refresh_state()
        self.baseline["count"] = 2
        self.baseline["repositories"].append({"repository": "example/new", "disposition": "PENDING"})
        self.save_baseline()
        with self.api([[api_row(), api_row("example/new")]]):
            self.assertEqual(self.refresh_state()["queued_count"], 1)
        self.baseline["repositories"][1]["disposition"] = "OUT-OF-SCOPE: recorded review"
        self.save_baseline()
        with self.api([[api_row(), api_row("example/new")]]):
            receipt = self.refresh_state()
        self.assertEqual(receipt["queued_count"], 0)
        self.assertIn("## NEWSTARS 0", self.questions.read_text())

    def test_unresolved_queue_survives_missing_live_repository_until_review(self):
        with self.api([[api_row(), api_row("example/new")]]):
            first = self.refresh_state()
        for pages in ([[api_row()]], [[]]):
            with self.api(pages):
                receipt = self.refresh_state()
            self.assertEqual(receipt["queued_count"], 1)
            self.assertEqual(receipt["notification_id"], first["notification_id"])
            journal = json.loads((self.state / stars.JOURNAL_NAME).read_text())
            self.assertEqual(journal["pending_repositories"], ["example/new"])
            retained = journal["pending_observations"]["example/new"]
            self.assertEqual(retained["repository"], "example/new")
            self.assertEqual(retained["first_observed_at"], "2026-10-10T17:00:00Z")
        self.baseline["count"] = 2
        self.baseline["repositories"].append({"repository": "example/new",
                                             "disposition": "OUT-OF-SCOPE: recorded review"})
        self.save_baseline()
        with self.api([[]]):
            self.assertEqual(self.refresh_state()["queued_count"], 0)

    def test_reopened_canonical_review_has_fresh_notification_and_retry_deduplicates(self):
        with self.api([[api_row(), api_row("example/new")]]):
            first = self.refresh_state()
        self.baseline["count"] = 2
        self.baseline["retrieved_at"] = "2026-10-10T17:00:00Z"
        self.baseline["repositories"].append({"repository": "example/new",
                                             "first_observed_at": "2026-10-10T17:00:00Z",
                                             "disposition": "OUT-OF-SCOPE: recorded review"})
        self.save_baseline()
        with self.api([[api_row(), api_row("example/new")]]):
            self.assertEqual(self.refresh_state()["queued_count"], 0)
        self.baseline["repositories"][1]["disposition"] = "NEEDS-EVIDENCE: review reopened"
        self.save_baseline()
        with self.api([[api_row(), api_row("example/new")]]):
            reopened = self.refresh_state()
        self.assertNotEqual(reopened["notification_id"], first["notification_id"])
        self.assertTrue(reopened["newstars_posted"])
        with self.api([[api_row(), api_row("example/new")]]):
            retry = self.refresh_state()
        self.assertEqual(retry["notification_id"], reopened["notification_id"])
        self.assertFalse(retry["newstars_posted"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 2)

    def test_each_queue_clearance_is_observable_and_its_retry_deduplicates(self):
        with self.api([[api_row()]]):
            initial = self.refresh_state()
        with self.api([[api_row(), api_row("example/new")]]):
            self.refresh_state()
        self.baseline["count"] = 2
        self.baseline["repositories"].append({"repository": "example/new",
                                             "disposition": "OUT-OF-SCOPE: recorded review"})
        self.save_baseline()
        with self.api([[api_row()]]):
            cleared = self.refresh_state()
        self.assertNotEqual(cleared["notification_id"], initial["notification_id"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 0"), 2)
        with self.api([[api_row()]]):
            retry = self.refresh_state()
        self.assertEqual(retry["notification_id"], cleared["notification_id"])
        self.assertFalse(retry["newstars_posted"])
        self.baseline["repositories"][1]["disposition"] = "NEEDS-EVIDENCE: review reopened"
        self.save_baseline()
        with self.api([[api_row()]]):
            self.refresh_state()
        self.baseline["repositories"][1]["disposition"] = "OUT-OF-SCOPE: second recorded review"
        self.save_baseline()
        with self.api([[api_row()]]):
            second_clearance = self.refresh_state()
        self.assertNotEqual(second_clearance["notification_id"], cleared["notification_id"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 0"), 3)

    def test_observation_must_not_be_newer_than_containing_snapshot(self):
        self.baseline["repositories"][0].update(disposition="PENDING",
                                               first_observed_at="2026-10-09T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "newer than.*snapshot"):
            stars.validate_pending_age(self.baseline, NOW)
        self.save_baseline()
        with self.api([[api_row()]]) as fetch:
            with self.assertRaisesRegex(ValueError, "newer than.*snapshot"):
                self.refresh_state()
        fetch.assert_not_called()

    def test_snapshot_write_failure_window_retains_new_work_when_live_row_disappears(self):
        original_write = stars._write_json
        def stop_before_journal(path, value):
            if Path(path).name == stars.JOURNAL_NAME:
                raise OSError("simulated stop before journal prepare")
            original_write(path, value)
        with self.api([[api_row(), api_row("example/new")]]), patch.object(
                stars, "_write_json", side_effect=stop_before_journal):
            with self.assertRaises(OSError):
                self.refresh_state()
        with self.api([[api_row()]]):
            receipt = self.refresh_state()
        self.assertEqual(receipt["queued_count"], 1)
        self.assertIn("Repositories: example/new", self.questions.read_text())

    def test_stop_after_append_replays_marker_once_and_retains_missing_live_work(self):
        original_write = stars._write_json
        def stop_after_append(path, value):
            if Path(path).name == stars.JOURNAL_NAME and value.get("notification_state") == "posted":
                raise OSError("simulated stop after append")
            original_write(path, value)
        with self.api([[api_row(), api_row("example/new")]]), patch.object(
                stars, "_write_json", side_effect=stop_after_append):
            with self.assertRaises(OSError):
                self.refresh_state()
        with self.api([[api_row()]]):
            receipt = self.refresh_state()
        self.assertEqual(receipt["queued_count"], 1)
        self.assertFalse(receipt["newstars_posted"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)

    def test_consecutive_journal_failures_retain_unresolved_identity_and_first_observation(self):
        original_write = stars._write_json

        def fail_journal(path, value):
            if Path(path).name == stars.JOURNAL_NAME:
                raise OSError("simulated journal write failure")
            original_write(path, value)

        for rows in ([api_row(), api_row("example/new")], [api_row()]):
            with self.api([rows]), patch.object(stars, "_write_json", side_effect=fail_journal):
                with self.assertRaisesRegex(OSError, "simulated journal write failure"):
                    self.refresh_state()
        self.assertNotIn("## NEWSTARS", self.questions.read_text())
        with self.api([[api_row()]]):
            report = stars.refresh_public_stars(self.root, state_dir=self.state,
                                               questions=self.questions, now=NOW + timedelta(days=1))
        journal = json.loads((self.state / stars.JOURNAL_NAME).read_text())
        self.assertEqual(journal["pending_repositories"], ["example/new"])
        self.assertEqual(journal["pending_observations"]["example/new"]["first_observed_at"],
                         "2026-10-10T17:00:00Z")
        self.assertEqual(report["queued_count"], 1)
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)
        self.assertIn("Repositories: example/new", self.questions.read_text())

    def test_prepared_snapshot_is_published_before_notification_or_next_fetch(self):
        original_write = stars._write_json

        def fail_snapshot(path, value):
            if Path(path).name == stars.SNAPSHOT_NAME:
                raise OSError("simulated snapshot write failure")
            original_write(path, value)

        with self.api([[api_row(), api_row("example/new")]]), patch.object(
                stars, "_write_json", side_effect=fail_snapshot):
            with self.assertRaisesRegex(OSError, "simulated snapshot write failure"):
                self.refresh_state()
        self.assertNotIn("## NEWSTARS", self.questions.read_text())
        with self.api([[api_row()]]), patch.object(stars, "_write_json", side_effect=fail_snapshot), \
                patch.object(stars, "_fetch", wraps=stars._fetch) as fetch, \
                patch.object(stars, "_notify", wraps=stars._notify) as notify:
            with self.assertRaisesRegex(OSError, "simulated snapshot write failure"):
                self.refresh_state()
            fetch.assert_not_called()
            notify.assert_not_called()

        original_notify = stars._notify

        def require_published_snapshot(*args, **kwargs):
            if args[5] == NOW:
                snapshot = json.loads((self.state / stars.SNAPSHOT_NAME).read_text())
                self.assertIn("example/new", stars._rows(snapshot))
                self.assertEqual(snapshot["retrieved_at"], "2026-10-10T17:00:00Z")
            return original_notify(*args, **kwargs)

        with self.api([[api_row()]]), patch.object(stars, "_notify", side_effect=require_published_snapshot):
            report = stars.refresh_public_stars(self.root, state_dir=self.state,
                                               questions=self.questions, now=NOW + timedelta(days=1))
        self.assertEqual(report["queued_count"], 1)
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)
        snapshot = json.loads((self.state / stars.SNAPSHOT_NAME).read_text())
        self.assertNotIn("example/new", stars._rows(snapshot))

    def test_missing_live_canonical_unreviewed_row_retains_legacy_observation(self):
        self.baseline["repositories"][0]["disposition"] = "NEEDS-EVIDENCE: review missing"
        self.save_baseline()
        with self.api([[]]):
            receipt = self.refresh_state()
        self.assertEqual(receipt["queued_count"], 1)
        journal = json.loads((self.state / stars.JOURNAL_NAME).read_text())
        self.assertEqual(journal["pending_observations"]["example/project"]["first_observed_at"],
                         "2026-10-01T00:00:00Z")

    def test_stop_after_notification_before_publication_marker_replays_once(self):
        original_write = stars._write_json

        def stop_before_marker(path, value):
            if Path(path).name == stars.PREPARED_NAME and value.get("publication_state") == "posted":
                raise OSError("simulated stop before publication marker")
            original_write(path, value)

        with self.api([[api_row(), api_row("example/new")]]), patch.object(
                stars, "_write_json", side_effect=stop_before_marker):
            with self.assertRaisesRegex(OSError, "simulated stop before publication marker"):
                self.refresh_state()
        with self.api([[api_row()]]):
            report = self.refresh_state()
        self.assertEqual(report["queued_count"], 1)
        self.assertFalse(report["newstars_posted"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)
        prepared = json.loads((self.state / stars.PREPARED_NAME).read_text())
        self.assertEqual(prepared["publication_state"], "posted")
        self.assertEqual(prepared["journal"]["pending_repositories"], ["example/new"])

    def test_preparation_failure_preserves_previous_snapshot_and_pending_observations(self):
        with self.api([[api_row(), api_row("example/new")]]):
            first = self.refresh_state()
        before = {name: (self.state / name).read_bytes() for name in
                  (stars.SNAPSHOT_NAME, stars.JOURNAL_NAME, stars.PREPARED_NAME)}
        original_write = stars._write_json

        def fail_preparation(path, value):
            if Path(path).name == stars.PREPARED_NAME:
                raise OSError("simulated preparation failure")
            original_write(path, value)

        with self.api([[api_row()]]), patch.object(stars, "_write_json", side_effect=fail_preparation):
            with self.assertRaisesRegex(OSError, "simulated preparation failure"):
                self.refresh_state()
        for name, original in before.items():
            self.assertEqual((self.state / name).read_bytes(), original)
        with self.api([[api_row()]]):
            report = self.refresh_state()
        self.assertEqual(report["queued_count"], 1)
        self.assertEqual(report["notification_id"], first["notification_id"])

    def test_legacy_prepared_journal_without_publication_record_still_replays(self):
        with self.api([[api_row(), api_row("example/new")]]), patch.object(
                stars, "_notify", side_effect=OSError("simulated append failure")):
            with self.assertRaises(OSError):
                self.refresh_state()
        (self.state / stars.PREPARED_NAME).unlink()
        with self.api([[api_row()]]):
            report = self.refresh_state()
        self.assertEqual(report["queued_count"], 1)
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)

    def test_prepared_notification_survives_review_landing_before_retry(self):
        with self.api([[api_row(), api_row("example/new")]]), patch.object(
                stars, "_notify", side_effect=OSError("simulated append failure")):
            with self.assertRaises(OSError):
                self.refresh_state()
        self.baseline["count"] = 2
        self.baseline["repositories"].append({"repository": "example/new",
                                             "disposition": "OUT-OF-SCOPE: recorded review"})
        self.save_baseline()
        with self.api([[api_row(), api_row("example/new")]]):
            receipt = self.refresh_state()
        text = self.questions.read_text()
        self.assertEqual(text.count("## NEWSTARS 1"), 1)
        self.assertEqual(text.count("## NEWSTARS 0"), 1)
        self.assertLess(text.index("## NEWSTARS 1"), text.index("## NEWSTARS 0"))
        self.assertEqual(receipt["queued_count"], 0)

    def test_repository_casing_change_does_not_repeat_semantic_notification(self):
        with self.api([[api_row(), api_row("example/new")]]):
            self.refresh_state()
        with self.api([[api_row(), api_row("Example/New")]]):
            self.assertFalse(self.refresh_state()["newstars_posted"])
        self.assertEqual(self.questions.read_text().count("## NEWSTARS 1"), 1)

    def test_external_mode_rejects_checkout_state_and_requires_questions(self):
        for kwargs in ({"state_dir": self.root / "scratch", "questions": self.questions},
                       {"state_dir": self.state, "questions": self.root / "questions.md"},
                       {"state_dir": self.state},
                       {"output": self.canonical, "state_dir": self.state, "questions": self.questions}):
            with self.subTest(kwargs_keys=list(kwargs)):
                with self.assertRaises(ValueError):
                    stars.refresh_public_stars(self.root, now=NOW, **kwargs)

    def test_state_questions_collisions_fail_before_fetch_or_directory_creation(self):
        for index, suffix in enumerate((None, stars.SNAPSHOT_NAME, stars.JOURNAL_NAME,
                                        stars.PREPARED_NAME, ".public-starred.lock")):
            with self.subTest(suffix=suffix):
                state = self.base / f"collision-{index}"
                questions = state if suffix is None else state / suffix
                error = None
                with self.api([[api_row()]]) as fetch:
                    try:
                        stars.refresh_public_stars(self.root, state_dir=state, questions=questions, now=NOW)
                    except Exception as received:
                        error = received
                self.assertIsInstance(error, ValueError, "colliding inputs must fail at validation")
                fetch.assert_not_called()
                self.assertFalse(state.exists())

    def test_existing_runtime_path_types_fail_before_fetch(self):
        question_directory = self.base / "not-a-questions-file"
        question_directory.mkdir()
        state_file = self.base / "not-a-state-directory"
        state_file.write_text("harmless sentinel\n")
        for state, questions in ((self.state, question_directory), (state_file, self.questions)):
            with self.subTest(state_is_file=state == state_file):
                error = None
                with self.api([[api_row()]]) as fetch:
                    try:
                        stars.refresh_public_stars(self.root, state_dir=state, questions=questions, now=NOW)
                    except Exception as received:
                        error = received
                self.assertIsInstance(error, ValueError, "invalid runtime path types must fail at validation")
                fetch.assert_not_called()
        self.assertFalse(self.state.exists())
        self.assertEqual(state_file.read_text(), "harmless sentinel\n")

    def test_state_resource_symlinks_are_rejected_before_read_or_fetch(self):
        sentinel = self.root / "harmless-review-fixture.json"
        sentinel.write_text(json.dumps(self.baseline))
        original = sentinel.read_bytes()
        for index, filename in enumerate((stars.SNAPSHOT_NAME, stars.JOURNAL_NAME,
                                          stars.PREPARED_NAME, ".public-starred.lock")):
            with self.subTest(filename=filename):
                state = self.base / f"redirect-{index}"
                state.mkdir()
                (state / filename).symlink_to(sentinel)
                error = None
                with self.api([[api_row()]]) as fetch, patch.object(stars, "_read", wraps=stars._read) as reads:
                    try:
                        stars.refresh_public_stars(self.root, state_dir=state, questions=self.questions, now=NOW)
                    except Exception as received:
                        error = received
                self.assertIsInstance(error, ValueError, "redirected state resources must fail at validation")
                fetch.assert_not_called()
                self.assertNotIn(state / filename, [call.args[0] for call in reads.call_args_list])
                self.assertEqual(sentinel.read_bytes(), original)

    def test_broken_lock_symlink_cannot_create_a_checkout_file(self):
        self.state.mkdir()
        sentinel = self.root / "must-remain-absent.txt"
        (self.state / ".public-starred.lock").symlink_to(sentinel)
        with self.api([[api_row()]]) as fetch:
            with self.assertRaises(ValueError):
                self.refresh_state()
        fetch.assert_not_called()
        self.assertFalse(sentinel.exists())

    def test_questions_symlink_cannot_read_or_append_a_different_external_file(self):
        sentinel = self.base / "harmless-external-sentinel.md"
        sentinel.write_text("harmless fixture\n")
        alias = self.base / "questions-alias.md"
        alias.symlink_to(sentinel)
        error = None
        with self.api([[api_row()]]) as fetch:
            try:
                stars.refresh_public_stars(self.root, state_dir=self.state, questions=alias, now=NOW)
            except Exception as received:
                error = received
        self.assertIsInstance(error, ValueError, "questions symlink must fail before opening its target")
        fetch.assert_not_called()
        self.assertEqual(sentinel.read_text(), "harmless fixture\n")
        self.assertFalse(self.state.exists())

    def test_first_state_queues_existing_canonical_unreviewed_rows(self):
        self.baseline["count"] = 3
        self.baseline["repositories"].extend([
            {"repository": "example/needs", "disposition": "NEEDS-EVIDENCE: source review missing"},
            {"repository": "example/pending", "disposition": "PENDING"},
        ])
        self.save_baseline()
        with self.api([[api_row(), api_row("example/needs"), api_row("example/pending")]]):
            receipt = self.refresh_state()
        self.assertEqual(receipt["new_count"], 0)
        self.assertEqual(receipt["queued_count"], 2)
        journal = json.loads((self.state / stars.JOURNAL_NAME).read_text())
        self.assertEqual(journal["pending_repositories"], ["example/needs", "example/pending"])
        self.assertIn("## NEWSTARS 2", self.questions.read_text())

    def test_later_canonical_unreviewed_rows_queue_without_prior_newstar_record(self):
        with self.api([[api_row()]]):
            self.assertEqual(self.refresh_state()["queued_count"], 0)
        self.baseline["repositories"][0]["disposition"] = "NEEDS-EVIDENCE: updated primary evidence required"
        self.save_baseline()
        with self.api([[api_row()]]):
            receipt = self.refresh_state()
        self.assertEqual(receipt["new_count"], 0)
        self.assertEqual(receipt["queued_count"], 1)
        self.assertIn("## NEWSTARS 1", self.questions.read_text())

    def test_pending_age_is_measured_from_first_seen_not_refresh_time(self):
        snapshot = {"count": 1, "retrieved_at": "2026-10-10T17:00:00Z", "repositories": [
            {"repository": "example/project", "disposition": "PENDING",
             "first_observed_at": "2026-10-01T00:00:00Z"}]}
        with self.assertRaisesRegex(ValueError, "older than 7 days"):
            stars.validate_pending_age(snapshot, now=NOW)
        snapshot["repositories"][0]["first_observed_at"] = "2026-10-03T17:00:00Z"
        stars.validate_pending_age(snapshot, now=NOW)
        with self.assertRaises(ValueError):
            stars.validate_pending_age(snapshot, now=NOW + timedelta(seconds=1))

    def test_missing_legacy_first_seen_uses_retained_snapshot_date(self):
        snapshot = {"count": 1, "retrieved_at": "2026-09-30", "repositories": [
            {"repository": "example/project", "disposition": "PENDING"}]}
        with self.assertRaisesRegex(ValueError, "older than 7 days"):
            stars.validate_pending_age(snapshot, now=NOW)

    def test_malformed_or_future_dates_fail_closed_including_month_boundary(self):
        snapshot = {"count": 1, "retrieved_at": "2026-10-10", "repositories": [
            {"repository": "example/project", "disposition": "PENDING"}]}
        for observed in ("2026-10-11", "2026-09-31", "2026-10-10T10:00:00", "2026-10-01T00:00:00-04:00"):
            with self.subTest(observed=observed):
                snapshot["repositories"][0]["first_observed_at"] = observed
                with self.assertRaises(ValueError):
                    stars.validate_pending_age(snapshot, now=NOW)
        snapshot["repositories"][0]["first_observed_at"] = "2026-09-30T23:59:59Z"
        with self.assertRaisesRegex(ValueError, "older than 7 days"):
            stars.validate_pending_age(snapshot, now=NOW)


if __name__ == "__main__":
    unittest.main()
