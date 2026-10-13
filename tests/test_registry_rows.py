"""PR registration continuity through real Git fixtures and the supported writer."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.host_receipts import register_file
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


class RegistryWorkflowTests(unittest.TestCase):
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
        for mode in ("complete", "partial", "null", "git-failure"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
                root = Path(directory)
                (root / "gh").write_text(
                    "#!/bin/bash\n"
                    "if [[ $FIXTURE_MODE == null ]]; then echo null; exit 0; fi\n"
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
                               "PR_HISTORY_REPOSITORY": "fixture/repository", "PR_HISTORY_NUMBER": "1",
                               "REGISTRATION_BEFORE": before, "GITHUB_OUTPUT": str(output),
                               "FIXTURE_MODE": mode, "FIXTURE_FETCHES": str(fetches)}
                result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=root,
                                        env=environment, capture_output=True, text=True, timeout=30)
                if mode == "complete":
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(output.read_text(), f"before_refs={before} {first} {second}\n")
                    self.assertEqual(fetches.read_text().splitlines(),
                                     [f"fetch --no-tags origin {ref}" for ref in (before, first, second)])
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists(), "never publish partial registration inputs")
