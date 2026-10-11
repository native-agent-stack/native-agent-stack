"""The RTK 0.51.0 qualification receipt's locators name the lines that check the replay prerequisite, at the commit they are pinned to.

evidence/receipts/rtk-051-qualification-20261004.json (data.compatibility_review.replay_prerequisite) cites the three places that require `rtk 0.50.0` before the kernel
replays RTK calls: the kernel's own check and the two test gates. A locator written without a commit names a line of whatever the file is now: #973 added two imports to
tests/test_skill_usage.py and the unqualified `tests/test_skill_usage.py:33` then named PARSER_DIR instead of the regex line it named when the receipt was written. Each
locator is `<commit>:<path>:<line>`, pinned to the commit that added the receipt (14048b840425c2569e0df60a6596e94e601da15b, where all three resolve); this test reads the line
at the pin through Git and requires the prerequisite's version regex on it. A locator without a pin must resolve in the working tree. It skips where the history lacks the pin.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
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


def read(sha: str | None, path: str) -> str | None:
    if sha is None:
        return (ROOT / path).read_text(encoding="utf-8") if (ROOT / path).is_file() else None
    shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{sha}:{path}"], capture_output=True, text=True)
    return shown.stdout if shown.returncode == 0 else None


def has_commit(sha: str) -> bool:
    return subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode == 0


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
                if sha is not None and not has_commit(sha):
                    self.skipTest(f"the history of this checkout does not hold {sha}")
                text = read(sha, match.group("path"))
                self.assertIsNotNone(text, f"{match.group('path')} does not exist at {sha or 'the working tree'}")
                line = line_at(text, int(match.group("line")))
                self.assertTrue(names_the_prerequisite(line), f"line {match.group('line')} of {match.group('path')} at {sha or 'the working tree'} is {line.strip()[:80]!r}")

    def test_the_check_can_fail(self):
        # the defect this test exists for: after two lines are added above it, the unqualified line number names an unrelated line
        before = 'import os\nRTK_REPLAY_SUPPORTED = (x and re.fullmatch(\n    r"rtk 0\\.50\\.0\\s*", run()))\n'
        after = "import ntpath\nimport types\n" + before
        self.assertTrue(names_the_prerequisite(line_at(before, 3)))
        self.assertFalse(names_the_prerequisite(line_at(after, 3)))
        self.assertFalse(names_the_prerequisite(line_at(after, 99)), "a line past the end names nothing")


if __name__ == "__main__":
    unittest.main()
