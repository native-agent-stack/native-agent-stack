"""The protected-capture producer covers citations, workflow pins and package pins."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.starred_protected import capture, source_kind, witnesses


class ProtectedCaptureTests(unittest.TestCase):
    def test_bare_and_url_citations_have_repository_boundaries(self):
        names = {"actions/checkout", "pytest-dev/pytest"}
        rows = list(witnesses("`Actions/Checkout` https://github.com/pytest-dev/pytest\n"
                              "other-actions/checkout actions/checkout-extra", "decision_record", names))
        self.assertEqual([(name, row["line"]) for name, row in rows],
                         [("actions/checkout", 1), ("pytest-dev/pytest", 1)])

    def test_workflow_action_subpath_and_python_dependency_pin(self):
        names = {"actions/checkout", "pytest-dev/pytest"}
        rows = list(witnesses("- uses: actions/checkout/subpath@" + "a" * 40,
                              "workflow_pin", names))
        self.assertEqual(rows[0][0], "actions/checkout")
        self.assertEqual(rows[0][1]["match"], "uses_pin")
        rows = list(witnesses('dev = ["pytest==9.1.1"]', "dependency_or_runtime_manifest", names))
        self.assertEqual(rows[0][0], "pytest-dev/pytest")
        self.assertEqual(source_kind("uv.lock"), "dependency_or_runtime_manifest")
        self.assertEqual(source_kind("package-lock.json"), "dependency_or_runtime_manifest")

    def test_capture_reads_named_tree_instead_of_changed_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", "-C", directory, *args], stderr=subprocess.DEVNULL)
            git("init", "-q")
            path = root / "pyproject.toml"
            path.write_text('dependencies = ["pytest==9.1.1"]\n')
            git("add", "pyproject.toml")
            fixture_identity = "fixture" + "@" + "users.noreply.github.com"
            git("-c", "user.name=Fixture", "-c", "user.email=" + fixture_identity,
                "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
            address = git("show", "-s", "--format=%ae", "HEAD").decode().strip()
            self.assertEqual(address.rpartition("@")[2], "users.noreply.github.com",
                             "fixture commits require a public no-reply identity")
            head = git("rev-parse", "HEAD").decode().strip()
            path.write_text('dependencies = []\n')
            trees = [("fixture", root, head)]
            result = capture({"pytest-dev/pytest"}, trees, [], "a" * 64)
            witness = result["repositories"]["pytest-dev/pytest"][0]
            self.assertEqual(witness["head"], head)
            self.assertEqual(witness["source"], "fixture:pyproject.toml")
            self.assertEqual(result, capture({"pytest-dev/pytest"}, trees, [], "a" * 64))


if __name__ == "__main__":
    unittest.main()
