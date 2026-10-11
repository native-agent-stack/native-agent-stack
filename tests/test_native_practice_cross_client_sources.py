"""Every cell of the Claude column of reference/cross-client.md names the documentation pages it rests on, each page's recorded capture and
the line it was read at (the command center's read of #958 at 8ca5d825, P3), and every citation of a cell is validated on its own.

The capture hashes and fetch times are the locators of evidence/artifacts/claude-native-practice-20261009/claims.json, so a cell that
cites a page, hash or fetch time the claims never recorded fails here without the retained page copies, which are not in the repository.
Repository-text checks only: no page is fetched.

The first version parsed a cell with `findall` and asked for one recognised citation, so a corrupted citation disappeared whenever another one of
the cell stayed valid (the GPT read of #986 at 428fcb19, P2: removing only the hooks.md line-2587 citation, or giving it a hash that is not hex, a
fetch time without seconds or another host, still passed). Now each citation is split out of its cell and must match the whole citation form, the
citations a need rests on are listed here (`EXPECTED`), and the mutation test changes or removes each citation of each cell by itself.

The second version still let a note swallow what followed it (the GPT read of #986 at cc454f7f, P2): `re.fullmatch` demands only that the whole input match the
pattern, and its final `(.+)` was free to consume the note's closing parenthesis, trailing text and another note's opening parenthesis, so a citation added after `; see `,
or after a space, or with no separator, counted as part of the previous note and the cell still listed its expected citations. The note group now excludes parentheses,
brackets and newlines, so a note ends at its own closing parenthesis. Upstream mechanism, read at the interpreter this was measured on: CPython 3.13.16,
Lib/re/__init__.py lines 169-172 (`fullmatch` returns `_compile(pattern, flags).fullmatch(string)` and its docstring "Try to apply the pattern to all of the string"; file sha256
dbe158a677c6aaacf717ea2abc23c56233453d38024aef75b7c3d93612cabb93), and its documentation, https://docs.python.org/3.13/library/re.html (`re.fullmatch`, and the entries for
`.` and the greedy `+`), fetched 2026-10-11T03:48:42Z, sha256 19195ec76056c9b8088394ba81014ff47e1d4040a8eae092e450412f75f5c378: neither bounds what a greedy `.+` consumes,
so the boundary has to be in the pattern. Fails before, passes after: the five probes of `test_the_probes_of_the_review_of_cc454f7f_are_caught` and the five new mutation kinds
(55 more mutants) are all accepted by the unfixed guard, so these tests fail on it, and all are rejected by the fixed one.

The third version let the page claim what the artifact does not hold (the Codex review in GitHub of #986 at f085a62b, P2, thread on the page's Claude column sources paragraph): the page said that the URL, the capture's sha256 and the
line a citation was read at are the locators of claims.json. At f085a62b that file (blob cb0fe6c39497d0f5c6261cd97315d1117acc3a86) holds 256 documentation locators (type `url`, code.claude.com) and 253 of them
carry a `lines` field, but only 2 of the page's 11 citations (the two cli-reference.md lines, 103 and 112) fall inside a range recorded for the same capture. Each cited line is now recorded in
cross-client-lines.json with the capture it was read from and the sha256 of its text, read from the retained copies of the captures (checked against the page's 16-hex prefixes and against claims.json), and
`test_every_cited_line_is_recorded_with_its_capture_and_a_line_hash` and the `lines` check of `violations()` fail on a page whose line, capture or fetch time the artifact does not hold. A host that has the
captures sets CLAUDE_DOCS_CAPTURES to their directory and `test_the_recorded_line_hashes_match_the_captures_where_they_are_available` recomputes every hash from the bytes.

The fourth version still lost a row before any check saw it (the GPT micro of #986 at f085a62b, P2, review-output/VERDICT.md of fix2-pr986-f085a62b2): `page_rows()` stored `cells[need] = cell`, and
a later row with the same need replaced the earlier one, so a malformed row placed before the valid one left all six tests green (a wrong host or trailing prose: 0 violations for the pair, 2 for the corrupt row
alone). Python's mapping assignment does exactly that: "d[key] = value: Set d[key] to value" (https://docs.python.org/3.13/library/stdtypes.html, Mapping Types, fetched 2026-10-11T08:50:50Z, sha256
3b6ac10c7354317fa42ed1253bf3e400c2f62af139da4a5a53ec56159d0ae763). The rows are now kept in page order, `violations()` reports a need written twice and checks every row, and
`test_a_duplicate_source_row_is_caught_in_either_order_whatever_it_holds` inserts a corrupt or exact duplicate before and after the valid row (six pages) and shows that collapsing by need, as before, reports
nothing for the corrupt-first pages. Fails before, passes after: on the guard of f085a62b the corrupt-first pages pass the whole module (the co-op's probe), and the new tests fail on it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / ".claude/skills/claude-native-practice/reference/cross-client.md"
CLAIMS = ROOT / "evidence/artifacts/claude-native-practice-20261009/claims.json"
LINES = ROOT / "evidence/artifacts/claude-native-practice-20261009/cross-client-lines.json"
BASE = "https://code.claude.com/docs/en/"
CITATION = re.compile(r"\[([a-z-]+)\]\((https://code\.claude\.com/docs/en/([a-z-]+)\.md)\) line (\d+), sha256 `([0-9a-f]{16})`, "
                      r"fetched (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) \(([^()\[\]\n]+)\)")
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


def page_rows(text: str | None = None) -> tuple[list[str], list[tuple[str, str]]]:
    """The needs of the mechanism table, and the rows of the Claude source table as (need, cell) in the order they are written, duplicates kept (a mapping keyed by need let a later row replace an
    earlier one before any check saw it: the GPT micro of #986 at f085a62b, P2)."""
    text = PAGE.read_text(encoding="utf-8") if text is None else text
    mechanism = text.split("## Native mechanism per client", 1)[1].split("Claude column sources", 1)[0]
    needs = [line.split("|")[1].strip() for line in mechanism.splitlines()
             if line.startswith("| ") and not line.startswith(("| Need", "| ---"))]
    sources = text.split("Claude column sources", 1)[1]
    rows = []
    for line in sources.splitlines():
        if line.startswith("| ") and not line.startswith(("| Need", "| ---")):
            need, cell = (part.strip() for part in line.strip().strip("|").split("|", 1))
            rows.append((need, cell))
    return needs, rows


def recorded_captures() -> dict:
    captures = {}
    for claim in json.loads(CLAIMS.read_text(encoding="utf-8"))["claims"]:
        for locator in claim.get("locators", []):
            if locator.get("type") == "url" and locator.get("url", "").startswith(BASE) and "capture_sha256" in locator:
                captures.setdefault(locator["url"], set()).add((locator["capture_sha256"], locator.get("fetched_utc")))
    return captures


def recorded_lines() -> dict:
    """(url, line) -> (capture sha256, fetch time, line sha256) as cross-client-lines.json records them; a line recorded twice fails loudly."""
    lines = {}
    for entry in json.loads(LINES.read_text(encoding="utf-8"))["lines"]:
        key = (entry["url"], entry["line"])
        assert key not in lines, f"line recorded twice: {key}"
        lines[key] = (entry["capture_sha256"], entry["fetched_utc"], entry["line_sha256"])
    return lines


def line_digest(capture: bytes, number: int) -> str:
    """The recorded hash of a line: the sha256 of its bytes followed by a newline, lines counted by newline; `sed -n '<number>p' <capture> | sha256sum` prints the same."""
    return hashlib.sha256(capture.split(b"\n")[number - 1] + b"\n").hexdigest()


def split_cell(cell: str) -> list[str]:
    """The citations of a cell as written: each starts at a link, and the text between two links belongs to the citation before it."""
    return SEPARATOR.split(cell.strip())


def violations(cells, needs: list, captures: dict, lines: dict | None = None) -> list:
    """`cells` is the rows of the source table as (need, cell) pairs in page order, or a dict need -> cell. A need written twice is a violation and every row is checked, not only the last one."""
    rows = list(cells.items()) if isinstance(cells, dict) else list(cells)
    lines = recorded_lines() if lines is None else lines
    names = [need for need, _ in rows]
    found = [f"more than one source row for {need!r}" for need in dict.fromkeys(names) if names.count(need) > 1]
    found += [f"no source cell for {need!r}" for need in needs if need not in names]
    found += [f"a source cell for {need!r}, which is not a need of the mechanism table" for need in dict.fromkeys(names) if need not in needs]
    found += [f"no expected citations for {need!r}" for need in needs if need not in EXPECTED]
    found += [f"expected citations for {need!r}, which is not a need of the mechanism table" for need in EXPECTED if need not in needs]
    for need, cell in rows:
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
            recorded = lines.get((url, int(line)))
            if recorded is None:
                found.append(f"{need!r}: line {line} of {url} is not recorded in the lines artifact")
            elif not (recorded[0].startswith(prefix) and recorded[1] == fetched):
                found.append(f"{need!r}: line {line} of {url} is recorded with another capture or fetch time")
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
        ("parenthesised prose after the note", segment + " (extra prose)"),
        ("the citation repeated after a space", segment + " " + segment),
        ("the citation repeated with no separator", segment + segment),
        ("a second citation after '; see '", segment + "; see " + segment),
        ("a second citation after '; see ' on another host", segment + "; see " + segment.replace("code.claude.com", "invalid.example")),
        ("citation removed", None),
    ]


class CrossClientClaudeSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.needs, cls.rows = page_rows()
        cls.cells = dict(cls.rows)
        cls.captures = recorded_captures()

    def test_every_need_of_the_mechanism_table_has_a_cited_source_cell(self):
        self.assertEqual(len(self.needs), 7, self.needs)
        self.assertEqual(len(set(self.needs)), len(self.needs), "a need is written twice in the mechanism table")
        self.assertEqual(violations(self.rows, self.needs, self.captures), [])
        self.assertEqual(len(self.rows), len(self.cells), "a need has two source rows")
        self.assertEqual(sorted(self.cells), sorted(self.needs))
        self.assertEqual(sorted(EXPECTED), sorted(self.needs))

    def test_each_cited_page_has_exactly_one_recorded_capture(self):
        for need, cell in self.rows:
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
        self.assertEqual(checked, 19 * sum(len(split_cell(cell)) for cell in self.cells.values()))
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

    def test_the_probes_of_the_review_of_cc454f7f_are_caught(self):
        # Each appended to the unchanged Completion gate cell and passed the second version of this module, whose note group was `(.+)`: it swallowed the closing
        # parenthesis, the trailing text and the opening parenthesis of another note, so an extra citation counted as part of the previous note.
        need = "Completion gate"
        first, second = split_cell(self.cells[need])
        unchanged = self.cells[need]
        probes = {
            "parenthesised prose": unchanged + " (extra prose)",
            "the first citation after a space": unchanged + " " + first,
            "the first citation after '; see '": unchanged + "; see " + first,
            "the same on another host": unchanged + "; see " + first.replace("code.claude.com", "invalid.example"),
            "the first citation with no separator": unchanged + first,
        }
        for label, cell in probes.items():
            with self.subTest(probe=label):
                self.assertNotEqual(violations({**self.cells, need: cell}, self.needs, self.captures), [])
        # the boundary itself: a note ends at its own closing parenthesis and holds no parenthesis or bracket
        self.assertIsNone(CITATION.fullmatch(second + " (extra prose)"))
        self.assertIsNone(CITATION.fullmatch(second + " " + second))
        self.assertIsNotNone(CITATION.fullmatch(second))

    def test_a_duplicate_source_row_is_caught_in_either_order_whatever_it_holds(self):
        # The GPT micro of #986 at f085a62b (P2): a corrupt Completion gate row placed before the valid one was replaced by it in the mapping, and all six tests stayed green.
        text = PAGE.read_text(encoding="utf-8")
        head, sources = text.split("Claude column sources", 1)  # the mechanism table above has a Completion gate row too
        original = next(line for line in sources.splitlines() if line.startswith("| Completion gate |"))
        need, cell = (part.strip() for part in original.strip().strip("|").split("|", 1))
        modify = lambda pair: head + "Claude column sources" + sources.replace(original, pair, 1)  # noqa: E731
        corruptions = {"a wrong host": cell.replace("code.claude.com", "invalid.example", 1), "trailing prose": cell + " (extra prose)", "an exact copy": cell}
        for label, bad_cell in corruptions.items():
            self.assertTrue(label == "an exact copy" or bad_cell != cell)
            bad = f"| {need} | {bad_cell} |"
            for order, pair in (("the duplicate before the valid row", bad + "\n" + original), ("the duplicate after the valid row", original + "\n" + bad)):
                with self.subTest(duplicate=label, order=order):
                    needs, rows = page_rows(modify(pair))
                    self.assertEqual(len(rows), len(self.rows) + 1)
                    found = violations(rows, needs, self.captures)
                    self.assertIn(f"more than one source row for {need!r}", found)
                    if label != "an exact copy":
                        self.assertGreater(len(found), 1, "the corrupt row is checked on its own")
            if label != "an exact copy":
                needs, rows = page_rows(modify(bad + "\n" + original))
                self.assertEqual(violations(dict(rows), needs, self.captures), [], "collapsing the rows by need, as the earlier versions did, hides the corrupt row placed first")
        needs, rows = page_rows(text)
        self.assertEqual(violations(rows, needs, self.captures), [], "the page as written has no duplicate row")

    def test_every_cited_line_is_recorded_with_its_capture_and_a_line_hash(self):
        # The Codex review in GitHub of #986 at f085a62b (P2): the page called the line of each citation a locator of claims.json, which holds a covering range for 2 of the 11.
        lines = recorded_lines()
        cited = {}
        for _need, cell in self.rows:
            for segment in split_cell(cell):
                _name, url, _page, line, prefix, fetched, _note = CITATION.fullmatch(segment).groups()
                cited[(url, int(line))] = (prefix, fetched)
        self.assertEqual(len(cited), 10)
        self.assertEqual(sorted(lines), sorted(cited), "the lines artifact records exactly the lines the page cites")
        for key, (sha, fetched, digest) in lines.items():
            with self.subTest(line=key):
                self.assertEqual((sha[:16], fetched), cited[key])
                self.assertIn((sha, fetched), self.captures[key[0]])
                self.assertRegex(digest, r"^[0-9a-f]{64}$")
        for entry in json.loads(LINES.read_text(encoding="utf-8"))["lines"]:
            self.assertTrue(entry["line_head"].strip())
            self.assertLessEqual(len(entry["line_head"]), 80)

    def test_a_line_that_is_not_recorded_or_recorded_with_another_capture_is_caught(self):
        lines = recorded_lines()
        key = ("https://code.claude.com/docs/en/hooks.md", 2587)
        sha, fetched, digest = lines[key]
        self.assertEqual(violations(self.rows, self.needs, self.captures, lines), [])
        for label, changed in {"the line missing": {k: v for k, v in lines.items() if k != key}, "another fetch time": {**lines, key: (sha, fetched[:-3] + "59Z", digest)},
                               "another capture": {**lines, key: ("0" * 64, fetched, digest)}}.items():
            with self.subTest(change=label):
                self.assertNotEqual(violations(self.rows, self.needs, self.captures, changed), [])

    def test_the_line_hash_is_the_hash_of_the_line_and_its_newline(self):
        capture = b"first\nsecond\nthird"
        self.assertEqual(line_digest(capture, 1), hashlib.sha256(b"first\n").hexdigest())
        self.assertEqual(line_digest(capture, 2), hashlib.sha256(b"second\n").hexdigest())
        self.assertEqual(line_digest(capture, 3), hashlib.sha256(b"third\n").hexdigest(), "the last line without a newline is hashed with one added, as `sed -n 3p | sha256sum` prints it")

    @unittest.skipUnless(os.environ.get("CLAUDE_DOCS_CAPTURES"), "set CLAUDE_DOCS_CAPTURES to the directory that holds the captured documentation pages (<page>.md)")
    def test_the_recorded_line_hashes_match_the_captures_where_they_are_available(self):
        directory = Path(os.environ["CLAUDE_DOCS_CAPTURES"])
        for (url, number), (sha, _fetched, digest) in recorded_lines().items():
            with self.subTest(line=(url, number)):
                capture = (directory / (url.rsplit("/", 1)[1])).read_bytes()
                self.assertEqual(hashlib.sha256(capture).hexdigest(), sha)
                self.assertEqual(line_digest(capture, number), digest)

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
