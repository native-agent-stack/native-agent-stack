"""Every cell of the Claude column of reference/cross-client.md names the documentation page it rests on, the page's recorded capture and
the line it was read at (the command center's read of #958 at 8ca5d825, P3).

The capture hashes and fetch times are the locators of evidence/artifacts/claude-native-practice-20261009/claims.json, so a cell that
cites a page, hash or fetch time the claims never recorded fails here without the retained page copies, which are not in the repository.
Repository-text checks only: no page is fetched.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / ".claude/skills/claude-native-practice/reference/cross-client.md"
CLAIMS = ROOT / "evidence/artifacts/claude-native-practice-20261009/claims.json"
BASE = "https://code.claude.com/docs/en/"
CITATION = re.compile(r"\[([a-z-]+)\]\((https://code\.claude\.com/docs/en/[a-z-]+\.md)\) line (\d+), sha256 `([0-9a-f]{16})`, "
                      r"fetched (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)")


def page_rows() -> tuple[list[str], dict]:
    """The needs of the mechanism table, and need -> the cell of the Claude source table."""
    text = PAGE.read_text(encoding="utf-8")
    mechanism = text.split("## Native mechanism per client", 1)[1].split("Claude column sources", 1)[0]
    needs = [line.split("|")[1].strip() for line in mechanism.splitlines()
             if line.startswith("| ") and not line.startswith(("| Need", "| ---"))]
    sources = text.split("Claude column sources", 1)[1]
    cells = {}
    for line in sources.splitlines():
        if line.startswith("| ") and not line.startswith(("| Need", "| ---")):
            need, cell = (part.strip() for part in line.strip().strip("|").split("|", 1))
            cells[need] = cell
    return needs, cells


def recorded_captures() -> dict:
    captures = {}
    for claim in json.loads(CLAIMS.read_text(encoding="utf-8"))["claims"]:
        for locator in claim.get("locators", []):
            if locator.get("type") == "url" and locator.get("url", "").startswith(BASE) and "capture_sha256" in locator:
                captures.setdefault(locator["url"], set()).add((locator["capture_sha256"], locator.get("fetched_utc")))
    return captures


def violations(cells: dict, needs: list, captures: dict) -> list:
    found = [f"no source cell for {need!r}" for need in needs if need not in cells]
    for need, cell in cells.items():
        citations = CITATION.findall(cell)
        if not citations:
            found.append(f"{need!r}: no citation")
        for name, url, line, prefix, fetched in citations:
            if not url.endswith(f"/{name}.md"):
                found.append(f"{need!r}: link text {name!r} is not the page {url}")
            if int(line) < 1:
                found.append(f"{need!r}: line {line}")
            matching = [capture for capture in captures.get(url, ()) if capture[0].startswith(prefix) and capture[1] == fetched]
            if not matching:
                found.append(f"{need!r}: {url} sha256 {prefix} fetched {fetched} is not a capture the claims record")
    return found


class CrossClientClaudeSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.needs, cls.cells = page_rows()
        cls.captures = recorded_captures()

    def test_every_need_of_the_mechanism_table_has_a_cited_source_cell(self):
        self.assertEqual(len(self.needs), 7, self.needs)
        self.assertEqual(violations(self.cells, self.needs, self.captures), [])
        self.assertEqual(sorted(self.cells), sorted(self.needs))

    def test_each_cited_page_has_exactly_one_recorded_capture(self):
        for need, cell in self.cells.items():
            for _, url, _, _, _ in CITATION.findall(cell):
                with self.subTest(need=need, url=url):
                    self.assertEqual(len(self.captures[url]), 1, self.captures[url])

    def test_a_changed_citation_is_caught(self):
        need = "Completion gate"
        cell = self.cells[need]
        for label, changed in (("hash", cell.replace("3bd21d31955304d9", "3bd21d31955304d8")),
                               ("fetch time", cell.replace("2026-10-09T03:38:41Z", "2026-10-09T03:38:42Z")),
                               ("page", cell.replace("/hooks.md", "/hooks-guide.md")),
                               ("citation removed", re.sub(r"\[hooks\]\([^)]*\) line \d+, sha256 `[0-9a-f]+`, fetched \S+", "hooks", cell))):
            with self.subTest(change=label):
                self.assertNotEqual(changed, cell)
                self.assertNotEqual(violations({**self.cells, need: changed}, self.needs, self.captures), [])
        removed = dict(self.cells)
        del removed[need]
        self.assertNotEqual(violations(removed, self.needs, self.captures), [])


if __name__ == "__main__":
    unittest.main()
