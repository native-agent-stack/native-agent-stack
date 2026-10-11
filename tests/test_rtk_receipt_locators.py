"""The RTK 0.51.0 qualification receipt's locators name the lines that check the replay prerequisite, at the commit they are pinned to.

evidence/receipts/rtk-051-qualification-20261004.json (data.compatibility_review.replay_prerequisite) cites the three places that require `rtk 0.50.0` before the kernel
replays RTK calls: the kernel's own check and the two test gates. A locator written without a commit names a line of whatever the file is now: #973 added two imports to
tests/test_skill_usage.py and the unqualified `tests/test_skill_usage.py:33` then named PARSER_DIR instead of the regex line it named when the receipt was written. Each
locator is `<commit>:<path>:<line>`, pinned to the commit that added the receipt (14048b840425c2569e0df60a6596e94e601da15b, where all three resolve); this test reads the line
at the pin through Git and requires the prerequisite's version regex on it. A locator without a pin must resolve in the working tree. It skips where the history lacks the pin, and where
a checkout keeps the pinned commit but not its tree (a treeless partial clone with no network: the Codex review in GitHub of #1005 at bf864c370, P2): `git cat-file -e <sha>^{tree}` fails there
while `<sha>^{commit}` still passes, and a bad path with the tree present is still a failure.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "evidence/receipts/rtk-051-qualification-20261004.json"
LOCATOR = re.compile(r"^(?:(?P<sha>[0-9a-f]{40}):)?(?P<path>[\w./-]+):(?P<line>[1-9][0-9]*)$")
PREREQUISITE = re.compile(r"rtk 0\\?\.50\\?\.0")


def line_at(text: str, number: int) -> str:
    lines = text.splitlines()
    return lines[number - 1] if 1 <= number <= len(lines) else ""


def names_the_prerequisite(line: str) -> bool:
    return bool(PREREQUISITE.search(line))


def read(sha: str | None, path: str, repo: Path = ROOT) -> str | None:
    if sha is None:
        return (repo / path).read_text(encoding="utf-8") if (repo / path).is_file() else None
    shown = subprocess.run(["git", "-C", str(repo), "show", f"{sha}:{path}"], capture_output=True, text=True)
    return shown.stdout if shown.returncode == 0 else None


def has_commit(sha: str, repo: Path = ROOT) -> bool:
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode == 0


def has_tree(sha: str, repo: Path = ROOT) -> bool:
    """False in a checkout that keeps the commit object but not the tree it points at."""
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{tree}}"], capture_output=True).returncode == 0


def unavailable(sha: str | None, repo: Path = ROOT, path: str | None = None) -> str | None:
    """Why a pinned locator cannot be read in this checkout (None when it can, or when it has no pin). With a path: the trees on the way to it and its blob have to be there too, and a path that is not in the
    tree at the pin is not a reason to skip (the Codex review in GitHub of #1005 at 5c5eecaad, P2, line 60: in a blobless partial clone the commit and its root tree are present and the blob is not)."""
    if sha is None:
        return None
    if not has_commit(sha, repo):
        return f"the history of this checkout does not hold {sha}"
    if not has_tree(sha, repo):
        return f"this checkout holds the commit {sha} but not its tree (a partial clone)"
    if path is None:
        return None
    listed = subprocess.run(["git", "-C", str(repo), "ls-tree", "-z", sha, "--", path], capture_output=True)
    if listed.returncode != 0:
        return f"this checkout holds {sha} but not every tree on the way to {path} (a partial clone)"
    entry = listed.stdout.split(b"\0")[0].decode("utf-8", "replace")
    if not entry:
        return None  # the path is not in the tree at the pin: the locator is wrong and the test has to fail
    blob = entry.split()[2]
    if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", blob], capture_output=True).returncode != 0:
        return f"this checkout holds the tree of {sha} but not the blob of {path} (a blobless partial clone)"
    return None


def locator_unavailable(locator: str, repo: Path = ROOT) -> str | None:
    """Why the line a locator names cannot be read in this checkout (None when it can): its pin, the trees on the way to its path and its blob have to be there."""
    match = LOCATOR.match(locator)
    return unavailable(match.group("sha"), repo, match.group("path")) if match else None


class ReceiptLocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(RECEIPT.read_text(encoding="utf-8"))["data"]["compatibility_review"]["replay_prerequisite"]
        cls.locators = [data["kernel_source"]] + list(data["gate_sources"])

    def test_the_receipt_cites_three_locators_and_each_is_pinned(self):
        self.assertEqual(len(self.locators), 3)
        for locator in self.locators:
            with self.subTest(locator=locator):
                match = LOCATOR.match(locator)
                self.assertIsNotNone(match, "a locator is <commit>:<path>:<line>")
                self.assertIsNotNone(match.group("sha"), "an unpinned locator names a line of whatever the file is now")

    def test_each_locator_names_the_line_that_requires_the_version(self):
        for locator in self.locators:
            with self.subTest(locator=locator):
                match = LOCATOR.match(locator)
                self.assertIsNotNone(match)
                sha = match.group("sha")
                reason = locator_unavailable(locator)
                if reason is not None:
                    self.skipTest(reason)
                text = read(sha, match.group("path"))
                self.assertIsNotNone(text, f"{match.group('path')} does not exist at {sha or 'the working tree'}")
                line = line_at(text, int(match.group("line")))
                self.assertTrue(names_the_prerequisite(line), f"line {match.group('line')} of {match.group('path')} at {sha or 'the working tree'} is {line.strip()[:80]!r}")

    def test_a_pin_whose_tree_is_missing_is_skipped_and_a_bad_path_with_the_tree_present_is_not(self):
        # The Codex review in GitHub of #1005 at bf864c370 (P2, line 67): in a checkout that keeps the pinned commit but not its tree, has_commit() was true, read() returned None and every locator failed.
        def git(repo, *args):
            return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args], capture_output=True, text=True, check=True).stdout.strip()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-q")
            (repo / "a.txt").write_text("line 1\nrtk 0.50.0\n", encoding="utf-8")
            git(repo, "add", "a.txt")
            git(repo, "commit", "-q", "-m", "pin")
            sha = git(repo, "rev-parse", "HEAD")
            self.assertIsNone(unavailable(sha, repo))
            self.assertTrue(names_the_prerequisite(line_at(read(sha, "a.txt", repo), 2)))
            self.assertIsNone(read(sha, "missing.txt", repo), "a bad path with the tree present is a failure to report, not a skip")
            self.assertIsNone(unavailable(sha, repo))
            self.assertIsNone(unavailable(None, repo))
            tree = git(repo, "rev-parse", f"{sha}^{{tree}}")
            (repo / ".git/objects" / tree[:2] / tree[2:]).unlink()
            self.assertTrue(has_commit(sha, repo), "the commit object is still there: the check that was used before cannot tell")
            self.assertIsNone(read(sha, "a.txt", repo), "which made every locator fail")
            self.assertFalse(has_tree(sha, repo))
            self.assertIn("not its tree", unavailable(sha, repo))
            self.assertIn("does not hold", unavailable("0" * 40, repo))

    def test_a_blob_that_is_missing_is_skipped_and_a_path_that_is_not_in_the_tree_is_not(self):
        # The Codex review in GitHub of #1005 at 5c5eecaad (P2, line 60): deleting only the referenced blob leaves the commit and its root tree, so the check on the tree could not tell.
        def git(repo, *args):
            return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args], capture_output=True, text=True, check=True).stdout.strip()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-q")
            (repo / "a.txt").write_text("line 1\nrtk 0.50.0\n", encoding="utf-8")
            (repo / "d").mkdir()
            (repo / "d" / "b.txt").write_text("rtk 0.50.0\n", encoding="utf-8")
            git(repo, "add", "a.txt", "d/b.txt")
            git(repo, "commit", "-q", "-m", "pin")
            sha = git(repo, "rev-parse", "HEAD")
            self.assertIsNone(unavailable(sha, repo, "a.txt"))
            self.assertIsNone(unavailable(sha, repo, "d/b.txt"))
            blob = git(repo, "rev-parse", f"{sha}:a.txt")
            (repo / ".git/objects" / blob[:2] / blob[2:]).unlink()
            self.assertTrue(has_tree(sha, repo), "the root tree is still there: the check on the tree cannot tell")
            self.assertIsNone(read(sha, "a.txt", repo), "which made the locator fail instead of skip")
            self.assertIn("not the blob of a.txt", unavailable(sha, repo, "a.txt"))
            self.assertIsNone(unavailable(sha, repo, "d/b.txt"), "the other blobs are there")
            self.assertIsNone(unavailable(sha, repo, "missing.txt"), "a path that is not in the tree at the pin is a wrong locator: the test fails, it does not skip")
            self.assertIsNone(read(sha, "missing.txt", repo))
            subtree = git(repo, "rev-parse", f"{sha}:d")
            (repo / ".git/objects" / subtree[:2] / subtree[2:]).unlink()
            self.assertIn("not every tree on the way to d/b.txt", unavailable(sha, repo, "d/b.txt"))
            # the locator form the receipt uses asks the same questions
            self.assertIn("not the blob of a.txt", locator_unavailable(f"{sha}:a.txt:2", repo))
            self.assertIsNone(locator_unavailable(f"{sha}:missing.txt:1", repo))
            self.assertIsNone(locator_unavailable("a.txt:2", repo), "a locator without a pin is read in the working tree")

    def test_the_locator_test_skips_where_the_checkout_cannot_read_the_locator(self):
        # the wiring of the call that decides between a skip and a failure: with a checkout that cannot read any locator the test skips each of the three and fails none
        with mock.patch.object(sys.modules[__name__], "locator_unavailable", return_value="a partial clone") as asked:
            result = unittest.TestResult()
            ReceiptLocatorTests("test_each_locator_names_the_line_that_requires_the_version").run(result)
        self.assertEqual((result.failures, result.errors, len(result.skipped), asked.call_count), ([], [], 3, 3))

    def test_the_check_can_fail(self):
        # the defect this test exists for: after two lines are added above it, the unqualified line number names an unrelated line
        before = 'import os\nRTK_REPLAY_SUPPORTED = (x and re.fullmatch(\n    r"rtk 0\\.50\\.0\\s*", run()))\n'
        after = "import ntpath\nimport types\n" + before
        self.assertTrue(names_the_prerequisite(line_at(before, 3)))
        self.assertFalse(names_the_prerequisite(line_at(after, 3)))
        self.assertFalse(names_the_prerequisite(line_at(after, 99)), "a line past the end names nothing")


if __name__ == "__main__":
    unittest.main()
