"""PR registration continuity through real Git fixtures and the supported writer."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.host_receipts import register_file
from scripts.validate import InvalidPublication, validate_registration_rows
from tests import test_validate

ROOT = Path(__file__).resolve().parents[1]
AGENT = ".claude/agents/registry-fixture.md"
NEW_AGENT = ".claude/agents/registry-new-fixture.md"


class RegistryRowsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_validate.PublicationValidationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.fixture.write(AGENT, "Fixture agent version 1.\n")
        register_file(self.root, AGENT)
        self.git("init", "-q")
        self.base = self.commit()

    def git(self, *args):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        result = subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", *args], env=environment,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "Fixture revision")
        return self.git("rev-parse", "HEAD")

    def drop(self, path):
        manifest = self.root / "manifests/evidence.json"
        evidence = json.loads(manifest.read_text())
        evidence["files"] = [row for row in evidence["files"] if row["path"] != path]
        manifest.write_text(json.dumps(evidence, indent=2) + "\n")

    def check(self, *, before=None, base=None):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment["NATIVE_AGENT_REGISTRATION_BASE"] = base or self.base
        environment["NATIVE_AGENT_REGISTRATION_BEFORE"] = before or ""
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate.py"), "--root", str(self.root)],
            env=environment, capture_output=True, text=True, timeout=60)

    def test_a_changed_registered_path_losing_its_row_fails(self):
        self.fixture.write(AGENT, "Fixture agent version 2.\n")
        self.drop(AGENT)
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(AGENT + ": required registration row missing", result.stdout)

    def test_a_previously_pr_registered_new_path_survives_a_registry_rebase(self):
        self.fixture.write(NEW_AGENT, "New fixture agent.\n")
        register_file(self.root, NEW_AGENT)
        before = self.commit()
        self.git("reset", "--hard", self.base)  # Only this isolated fixture repository.
        self.fixture.write(NEW_AGENT, "New fixture agent.\n")
        self.commit()
        result = self.check(before=before)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(NEW_AGENT + ": required registration row missing", result.stdout)

    def test_an_unchanged_base_file_cannot_lose_only_its_row(self):
        self.drop(AGENT)
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(AGENT + ": required registration row missing", result.stdout)

    def test_hash_mismatch_fails(self):
        self.fixture.write(AGENT, "Changed fixture agent.\n")
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("SHA-256 mismatch", result.stdout)

    def test_byte_count_mismatch_fails(self):
        manifest = self.root / "manifests/evidence.json"
        evidence = json.loads(manifest.read_text())
        next(row for row in evidence["files"] if row["path"] == AGENT)["bytes"] += 1
        manifest.write_text(json.dumps(evidence, indent=2) + "\n")
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("byte count mismatch", result.stdout)

    def test_supported_registration_of_changed_and_new_files_passes(self):
        self.fixture.write(AGENT, "Changed fixture agent.\n")
        self.fixture.write(NEW_AGENT, "New fixture agent.\n")
        register_file(self.root, AGENT)
        register_file(self.root, NEW_AGENT)
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_deleted_files_may_remove_their_rows(self):
        self.drop(AGENT)
        (self.root / AGENT).unlink()
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_main_with_itself_as_base_passes(self):
        result = self.check(base=self.base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_never_registered_non_evidence_files_are_not_blanket_required(self):
        self.fixture.write("scripts/unregistered-fixture.txt", "Optional source fixture.\n")
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unavailable_before_revision_fails_closed(self):
        result = self.check(before="f" * 40)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("PR registration Git inputs unavailable", result.stdout)

    def test_a_second_push_cannot_forget_a_prior_ancestor_registration(self):
        self.fixture.write(NEW_AGENT, "New fixture agent.\n")
        register_file(self.root, NEW_AGENT)
        self.commit()
        self.drop(NEW_AGENT)
        self.commit()
        self.fixture.write("scripts/unrelated-fixture.txt", "Unrelated change.\n")
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(NEW_AGENT + ": required registration row missing", result.stdout)

    def test_a_second_push_after_rebase_keeps_force_pushed_registration_intent(self):
        self.fixture.write(NEW_AGENT, "New fixture agent.\n")
        register_file(self.root, NEW_AGENT)
        original = self.commit()
        self.git("reset", "--hard", self.base)
        self.fixture.write(NEW_AGENT, "New fixture agent.\n")
        missing = self.commit()
        self.fixture.write("scripts/unrelated-fixture.txt", "Unrelated change.\n")
        self.commit()
        result = self.check(before=original + " " + missing)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(NEW_AGENT + ": required registration row missing", result.stdout)
        register_file(self.root, NEW_AGENT)
        self.commit()
        repaired = self.check(before=original + " " + missing)
        self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)

    def test_registry_integrity_uses_committed_head_bytes_not_a_restored_worktree(self):
        self.fixture.write(AGENT, "Changed committed agent.\n")
        self.commit()
        self.fixture.write(AGENT, "Fixture agent version 1.\n")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("SHA-256 mismatch at Git head", result.stdout)

    def test_new_evidence_requires_a_row_without_a_previous_registration(self):
        self.fixture.write("evidence/artifacts/new-fixture.txt", "New evidence.\n")
        self.commit()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("evidence file is not hash-listed", result.stdout)

    def test_repaired_historical_invalid_manifests_warn_and_do_not_poison_the_pr(self):
        manifest = self.root / "manifests/evidence.json"
        valid = manifest.read_text()
        for bad in ("not JSON", '{"files":[],"files":[]}',
                    json.dumps({"files": [{"path": AGENT}, {"path": AGENT}]})):
            with self.subTest(kind=bad[:12]):
                manifest.write_text(bad)
                bad_head = self.commit()
                manifest.write_text(valid)
                self.commit()
                result = self.check(before=bad_head)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(bad_head + ":manifests/evidence.json", result.stderr)
                self.assertIn("skipped invalid historical manifest", result.stderr)

    def test_an_accidental_historical_manifest_self_row_can_be_removed(self):
        register_file(self.root, "manifests/evidence.json")
        accidental = self.commit()
        self.drop("manifests/evidence.json")
        self.commit()
        result = self.check(before=accidental)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_direct_rule_rejects_stale_committed_hash_and_bytes(self):
        for field in ("sha256", "bytes"):
            with self.subTest(field=field):
                manifest = self.root / "manifests/evidence.json"
                valid = manifest.read_text()
                document = json.loads(valid)
                row = next(row for row in document["files"] if row["path"] == AGENT)
                row[field] = "0" * 64 if field == "sha256" else row[field] + 1
                manifest.write_text(json.dumps(document, indent=2) + "\n")
                self.commit()

                # Bare publication validation sees repaired working bytes; only
                # the new committed-head rule can reject this fixture.
                manifest.write_text(valid)
                test_validate.validate(self.root)
                with self.assertRaisesRegex(InvalidPublication, "mismatch at Git head"):
                    validate_registration_rows(self.root, self.base)
                self.commit()

    def test_invalid_current_manifest_keeps_its_commit_and_path_diagnostic(self):
        manifest = self.root / "manifests/evidence.json"
        manifest.write_text("invalid current JSON")
        current = self.commit()
        with self.assertRaisesRegex(
                InvalidPublication, current + ":manifests/evidence.json: invalid current registration manifest"):
            validate_registration_rows(self.root, self.base)

    def test_removing_the_continuity_rule_is_caught_by_the_existing_missing_row_case(self):
        from unittest import mock
        from scripts import validate as validator_module

        self.fixture.write(AGENT, "Changed registered agent.\n")
        self.drop(AGENT)
        self.commit()
        test_validate.validate(self.root)  # Existing integrity checks accept it.
        with self.assertRaisesRegex(InvalidPublication, "required registration row missing"):
            validate_registration_rows(self.root, self.base)
        with mock.patch.object(validator_module, "validate_registration_rows", return_value=None):
            with self.assertRaises(AssertionError):
                with self.assertRaises(InvalidPublication):
                    validator_module.validate_registration_rows(self.root, self.base)


class RegistryWorkflowTests(unittest.TestCase):
    def test_private_history_fetch_authentication_is_command_scoped_and_never_persisted(self):
        import base64
        import hashlib
        import shutil
        from tests.test_workflow_policy import load_workflow

        workflow = load_workflow((ROOT / ".github/workflows/validate.yml").read_text())
        step = next(step for step in workflow["jobs"]["validate"]["steps"]
                    if step.get("id") == "registry_history")
        fake_token = "fixture-read-only-job-token"
        expected = "AUTHORIZATION: basic " + base64.b64encode(
            ("x-access-token:" + fake_token).encode()).decode()
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            real_git = shutil.which("git")
            subprocess.run([real_git, "init", "-q", str(root)], check=True)
            config = root / ".git/config"
            original = hashlib.sha256(config.read_bytes()).hexdigest()
            (root / "gh").write_text("#!/bin/bash\nprintf '%s\\n' '" + "a" * 40 + "'\n")
            # Exercise actual Git's environment config reader under the stubbed
            # fetch boundary; no real token, private repository or network.
            (root / "git").write_text(
                "#!" + sys.executable + "\n"
                "import os, subprocess, sys\n"
                "assert sys.argv[1:4] == ['fetch', '--no-tags', 'origin']\n"
                "result = subprocess.run([" + repr(real_git) +
                ", 'config', '--get', 'http.https://github.com/.extraheader'], "
                "capture_output=True, text=True)\n"
                "if result.returncode or result.stdout.strip() != " + repr(expected) + ":\n"
                "    print('fixture private fetch refused unauthenticated request', file=sys.stderr)\n"
                "    sys.exit(3)\n"
                "assert os.environ['GIT_CONFIG_COUNT'] == '1'\n"
                "assert all(" + repr(fake_token) + " not in arg for arg in sys.argv)\n")
            for name in ("gh", "git"):
                (root / name).chmod(0o700)
            output = root / "output"
            environment = {"PATH": str(root) + ":" + os.defpath,
                           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                           "GH_TOKEN": fake_token, "PR_HISTORY_REPOSITORY": "fixture/private",
                           "PR_HISTORY_NUMBER": "1", "REGISTRATION_BEFORE": "",
                           "GITHUB_OUTPUT": str(output)}
            result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(hashlib.sha256(config.read_bytes()).hexdigest(), original)
            self.assertNotIn(fake_token, result.stdout + result.stderr + output.read_text())
            probe = subprocess.run([real_git, "config", "--get", "http.https://github.com/.extraheader"],
                                   cwd=root, env={"PATH": os.defpath, "GIT_CONFIG_GLOBAL": os.devnull,
                                                  "GIT_CONFIG_NOSYSTEM": "1"}, capture_output=True)
            self.assertEqual(probe.returncode, 1, "authentication leaked past the fetch command")

    def test_timeline_reads_have_only_the_needed_read_permissions(self):
        from tests.test_workflow_policy import load_workflow

        job = load_workflow((ROOT / ".github/workflows/validate.yml").read_text())["jobs"]["validate"]
        self.assertEqual(job["permissions"], {"contents": "read", "pull-requests": "read"})

    def test_graphql_variables_are_literal_without_shellcheck_single_quote_warning(self):
        from tests.test_workflow_policy import load_workflow

        workflow = load_workflow((ROOT / ".github/workflows/validate.yml").read_text())
        step = next(step for step in workflow["jobs"]["validate"]["steps"]
                    if step.get("id") == "registry_history")
        self.assertNotIn("-f query='query($", step["run"])
        self.assertIn('-f query="query(\\$owner:', step["run"])

    def test_force_push_count_uses_only_the_filtered_nodes(self):
        from tests.test_workflow_policy import load_workflow

        job = load_workflow((ROOT / ".github/workflows/validate.yml").read_text())["jobs"]["validate"]
        step = next(step for step in job["steps"] if step.get("id") == "registry_history")
        self.assertNotIn("totalCount", step["run"])
        self.assertIn("timeline_count", step["run"])
        self.assertIn("timeline nodes: %s", step["run"])

    def test_prior_heads_are_scoped_to_the_validator_step_and_paginated(self):
        from tests.test_workflow_policy import load_workflow

        workflow = load_workflow((ROOT / ".github/workflows/validate.yml").read_text())
        steps = workflow["jobs"]["validate"]["steps"]
        history = next(step for step in steps if step.get("id") == "registry_history")
        validation = next(step for step in steps if step.get("name") == "Validate manifests and evidence integrity")
        self.assertEqual(history["if"], "matrix.shard == 0 && github.event_name == 'pull_request'")
        self.assertLess(steps.index(history), steps.index(validation))
        self.assertIn("gh api graphql --paginate", history["run"])
        self.assertIn("beforeCommit { oid }", history["run"])
        self.assertIn("--full-history", (ROOT / "scripts/validate.py").read_text())
        self.assertNotIn("GITHUB_ENV", history["run"], "prior refs must not leak into test subprocesses")
        self.assertEqual(validation["env"]["NATIVE_AGENT_REGISTRATION_BEFORE"],
                         "${{ steps.registry_history.outputs.before_refs }}")

    def test_native_history_step_fetches_all_refs_and_fails_on_incomplete_inputs(self):
        from tests.test_workflow_policy import load_workflow

        workflow = load_workflow((ROOT / ".github/workflows/validate.yml").read_text())
        step = next(step for step in workflow["jobs"]["validate"]["steps"]
                    if step.get("id") == "registry_history")
        before, first, second = "d" * 40, "a" * 40, "b" * 40
        for mode in ("complete", "partial", "null", "empty-timeline", "trailing-null", "git-failure"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
                root = Path(directory)
                (root / "gh").write_text(
                    "#!/bin/bash\n"
                    "if [[ $FIXTURE_MODE == null ]]; then printf '\\n'; exit 0; fi\n"
                    "if [[ $FIXTURE_MODE == empty-timeline ]]; then exit 0; fi\n"
                    f"if [[ $FIXTURE_MODE == trailing-null ]]; then printf '%s\\n' '{first}' '' '{second}' ''; exit 0; fi\n"
                    f"printf '%s\\n' '{first}' '{second}'\n"
                    "if [[ $FIXTURE_MODE == partial ]]; then exit 2; fi\n")
                (root / "git").write_text(
                    "#!/bin/bash\n"
                    "printf '%s\\n' \"$*\" >> \"$FIXTURE_FETCHES\"\n"
                    "if [[ $FIXTURE_MODE == git-failure ]]; then exit 3; fi\n")
                for name in ("gh", "git"):
                    (root / name).chmod(0o700)
                output, fetches = root / "output", root / "fetches"
                environment = {"PATH": str(root) + ":" + os.defpath,
                               "GH_TOKEN": "fixture-read-only-job-token",
                               "PR_HISTORY_REPOSITORY": "fixture/repository", "PR_HISTORY_NUMBER": "1",
                               "REGISTRATION_BEFORE": before, "GITHUB_OUTPUT": str(output),
                               "FIXTURE_MODE": mode, "FIXTURE_FETCHES": str(fetches)}
                result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=root,
                                        env=environment, capture_output=True, text=True, timeout=30)
                if mode in ("complete", "null", "empty-timeline", "trailing-null"):
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    expected = (before, first, second) if mode in ("complete", "trailing-null") else (before,)
                    self.assertEqual(output.read_text(), "before_refs=" + " ".join(expected) + "\n")
                    self.assertEqual(fetches.read_text().splitlines(),
                                     [f"fetch --no-tags origin {ref}" for ref in expected])
                    if mode in ("null", "trailing-null"):
                        self.assertIn("skipped inaccessible empty historical timeline node", result.stderr)
                    else:
                        self.assertNotIn("skipped inaccessible empty historical timeline node", result.stderr)
                    count = {"complete": 2, "null": 1, "empty-timeline": 0, "trailing-null": 4}[mode]
                    self.assertIn("timeline nodes: " + str(count), result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists(), "never publish partial registration inputs")
