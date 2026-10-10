"""Every cell of the Claude column of reference/cross-client.md names the documentation pages it rests on, each page's recorded capture and
the line it was read at (the command center's read of #958 at 8ca5d825, P3), and every citation of a cell is validated on its own.

The capture hashes and fetch times are the locators of evidence/artifacts/claude-native-practice-20261009/claims.json, so a cell that
cites a page, hash or fetch time the claims never recorded fails here without the retained page copies, which are not in the repository.
Repository-text checks only: no page is fetched.

The first version parsed a cell with `findall` and asked for one recognised citation, so a corrupted citation disappeared whenever another one of
the cell stayed valid (the GPT read of #986 at 428fcb19, P2: removing only the hooks.md line-2587 citation, or giving it a hash that is not hex, a
fetch time without seconds or another host, still passed). Now each citation is split out of its cell and must match the whole citation form, the
citations a need rests on are listed here (`EXPECTED`), and the mutation test changes or removes each citation of each cell by itself.
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
CITATION = re.compile(r"\[([a-z-]+)\]\((https://code\.claude\.com/docs/en/([a-z-]+)\.md)\) line (\d+), sha256 `([0-9a-f]{16})`, "
                      r"fetched (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) \((.+)\)")
SEPARATOR = re.compile(r";\s+(?=\[)")
# The citations each need of the mechanism table rests on, in the order its cell lists them: (page, line). A cell that loses, gains, reorders or
# moves one of them fails, so removing one of several citations is detected, not only removing all of them.
EXPECTED = {
    "Delegation with fresh context": (("sub-agents", 11), ("sub-agents", 492), ("workflows", 204)),
    "Completion gate": (("hooks", 2587), ("hooks", 2655)),
    "Structured headless result": (("cli-reference", 103),),
    "Machine-readable event stream": (("cli-reference", 112),),
    "Packaged capability": (("plugins", 9),),
    "Native review": (("commands", 71),),
    "Clean-context run for an eval": (("headless", 17), ("sub-agents", 11)),
}


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


def split_cell(cell: str) -> list[str]:
    """The citations of a cell as written: each starts at a link, and the text between two links belongs to the citation before it."""
    return SEPARATOR.split(cell.strip())


def violations(cells: dict, needs: list, captures: dict) -> list:
    found = [f"no source cell for {need!r}" for need in needs if need not in cells]
    found += [f"a source cell for {need!r}, which is not a need of the mechanism table" for need in cells if need not in needs]
    found += [f"no expected citations for {need!r}" for need in needs if need not in EXPECTED]
    found += [f"expected citations for {need!r}, which is not a need of the mechanism table" for need in EXPECTED if need not in needs]
    for need, cell in cells.items():
        cited = []
        for position, segment in enumerate(split_cell(cell), 1):
            match = CITATION.fullmatch(segment)
            if match is None:
                found.append(f"{need!r}: citation {position} is not a well-formed citation: {segment[:70]!r}")
                continue
            name, url, page, line, prefix, fetched, _note = match.groups()
            if name != page:
                found.append(f"{need!r}: link text {name!r} is not the page {url}")
            if int(line) < 1:
                found.append(f"{need!r}: line {line}")
            if not any(sha.startswith(prefix) and time == fetched for sha, time in captures.get(url, ())):
                found.append(f"{need!r}: {url} sha256 {prefix} fetched {fetched} is not a capture the claims record")
            cited.append((page, int(line)))
        if need in EXPECTED and cited != list(EXPECTED[need]):
            found.append(f"{need!r}: cites {cited}, the need rests on {list(EXPECTED[need])}")
    return found


def mutants_of(segment: str) -> list[tuple[str, str | None]]:
    """Single corruptions of one citation: a field changed to a malformed or to a wrong but well-formed value, text added, or the citation removed (None)."""
    name, url, page, line, prefix, fetched, _note = CITATION.fullmatch(segment).groups()
    other_digit = "1" if prefix[-1] == "0" else "0"
    return [
        ("hash with a character that is not hex", segment.replace(f"`{prefix}`", f"`{prefix[:-1]}g`")),
        ("hash of another capture's digits", segment.replace(f"`{prefix}`", f"`{prefix[:-1]}{other_digit}`")),
        ("hash one character short", segment.replace(f"`{prefix}`", f"`{prefix[:-1]}`")),
        ("fetch time without seconds", segment.replace(fetched, fetched[:-4] + "Z")),
        ("fetch time one second off", segment.replace(fetched, fetched[:-3] + ("00" if fetched[-3:-1] != "00" else "01") + "Z")),
        ("another host", segment.replace("code.claude.com", "invalid.example")),
        ("another page", segment.replace(f"/{page}.md", f"/{page}-guide.md")),
        ("another link text", segment.replace(f"[{name}]", "[docs]")),
        ("line 0", segment.replace(f" line {line},", " line 0,")),
        ("line moved by one", segment.replace(f" line {line},", f" line {int(line) + 1},")),
        ("line word removed", segment.replace(f" line {line},", ",")),
        ("text before the link", "see " + segment),
        ("text after the note", segment + " and more"),
        ("citation removed", None),
    ]


class CrossClientClaudeSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.needs, cls.cells = page_rows()
        cls.captures = recorded_captures()

    def test_every_need_of_the_mechanism_table_has_a_cited_source_cell(self):
        self.assertEqual(len(self.needs), 7, self.needs)
        self.assertEqual(violations(self.cells, self.needs, self.captures), [])
        self.assertEqual(sorted(self.cells), sorted(self.needs))
        self.assertEqual(sorted(EXPECTED), sorted(self.needs))

    def test_each_cited_page_has_exactly_one_recorded_capture(self):
        for need, cell in self.cells.items():
            for segment in split_cell(cell):
                url = CITATION.fullmatch(segment).group(2)
                with self.subTest(need=need, url=url):
                    self.assertEqual(len(self.captures[url]), 1, self.captures[url])

    def test_every_citation_of_every_cell_is_caught_when_changed_or_removed_by_itself(self):
        checked = 0
        for need, cell in self.cells.items():
            segments = split_cell(cell)
            for index, segment in enumerate(segments):
                for label, mutated in mutants_of(segment):
                    with self.subTest(need=need, citation=index + 1, change=label):
                        rest = segments[:index] + ([] if mutated is None else [mutated]) + segments[index + 1:]
                        self.assertNotEqual(rest, segments)
                        changed = {**self.cells, need: "; ".join(rest)}
                        self.assertNotEqual(violations(changed, self.needs, self.captures), [])
                        checked += 1
        self.assertEqual(checked, 14 * sum(len(split_cell(cell)) for cell in self.cells.values()))
        self.assertEqual(sum(len(split_cell(cell)) for cell in self.cells.values()), 11)

    def test_the_probes_of_the_review_of_428fcb19_are_caught(self):
        # Each changed only the first hooks.md citation of the Completion gate cell, and each passed the first version of this module.
        need = "Completion gate"
        first, second = split_cell(self.cells[need])
        self.assertIn("line 2587", first)
        probes = {
            "that citation removed": second,
            "its hash not hex": "; ".join([first.replace("3bd21d31955304d9", "3bd21d31955304dg"), second]),
            "its fetch time without seconds": "; ".join([first.replace("2026-10-09T03:38:41Z", "2026-10-09T03:38Z"), second]),
            "its host another": "; ".join([first.replace("code.claude.com", "invalid.example"), second]),
        }
        for label, cell in probes.items():
            with self.subTest(probe=label):
                self.assertNotEqual(cell, self.cells[need])
                self.assertNotEqual(violations({**self.cells, need: cell}, self.needs, self.captures), [])

    def test_a_missing_cell_a_new_need_and_a_reordered_cell_are_caught(self):
        removed = dict(self.cells)
        del removed["Completion gate"]
        self.assertNotEqual(violations(removed, self.needs, self.captures), [])
        self.assertNotEqual(violations(self.cells, self.needs + ["A need nobody cited"], self.captures), [])
        need = "Delegation with fresh context"
        segments = split_cell(self.cells[need])
        reordered = {**self.cells, need: "; ".join(reversed(segments))}
        self.assertNotEqual(violations(reordered, self.needs, self.captures), [])


if __name__ == "__main__":
    unittest.main()
