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
line a citation was read at are the locators of claims.json. At f085a62b that file (blob cb0fe6c39497d0f5c6261cd97315d1117acc3a86) holds 257 documentation locators (type `url`, code.claude.com), 256 of them with a capture hash (the one without is the skills.md locator) and 253 of them
carry a `lines` field, but only 2 of the page's 11 citations (the two cli-reference.md lines, 103 and 112) fall inside a range recorded for the same capture. Each cited line is now recorded in
cross-client-lines.json with the capture it was read from and the sha256 of its text, read from the retained copies of the captures (checked against the page's 16-hex prefixes and against claims.json), and
`test_every_cited_line_is_recorded_with_its_capture_and_a_line_hash` and the `lines` check of `violations()` fail on a page whose line, capture or fetch time the artifact does not hold. A host that has the
captures sets CLAUDE_DOCS_CAPTURES to their directory and `test_the_recorded_line_hashes_match_the_captures_where_they_are_available` recomputes every hash from the bytes.

The fourth version still lost a row before any check saw it (the GPT micro of #986 at f085a62b, P2, review-output/VERDICT.md of fix2-pr986-f085a62b2): `page_rows()` stored `cells[need] = cell`, and
a later row with the same need replaced the earlier one, so a malformed row placed before the valid one left all six tests green (a wrong host or trailing prose: 0 violations for the pair, 2 for the corrupt row
alone). Python's mapping assignment does exactly that: "d[key] = value: Set d[key] to value" (https://docs.python.org/3.13/library/stdtypes.html, Mapping Types, fetched 2026-10-11T08:50:50Z, sha256
3b6ac10c7354317fa42ed1253bf3e400c2f62af139da4a5a53ec56159d0ae763), and the language reference says what it does to an existing key (https://docs.python.org/3.13/reference/simple_stmts.html, Assignment statements: a mapping "is then asked to create
a key/value pair which maps the subscript to the assigned object. This can either replace an existing key/value pair with the same key value, or insert a new key/value pair"; fetched 2026-10-11T09:47:16Z,
sha256 1f9cff2314892731150c210ba7e14ce362500767439d073fbb842b13c4f804b5) and the interpreter does it: CPython v3.13.16 Objects/dictobject.c (sha256 60ff1a61f3e8a6fdea5e645aa9343a87aa1aea24464159c6c965ef56c3106695),
`dict_ass_sub` (line 3400) calls `PyDict_SetItem` (2578), which calls `_PyDict_SetItem_Take2` (2562) and `insertdict` (2558, defined at 1832); `insertdict` finds the existing key (`old_value`, 1859 to 1875) and
stores the new value over the entry with `STORE_VALUE(ep, value)` (1885, 1890). The rows are now kept in page order, `violations()` reports a need written twice and checks every row, and
`test_a_duplicate_source_row_is_caught_in_either_order_whatever_it_holds` inserts a corrupt or exact duplicate before and after the valid row (six pages) and shows that collapsing by need, as before, reports
nothing for the corrupt-first pages. Fails before, passes after: on the guard of f085a62b the corrupt-first pages pass the whole module (the co-op's probe), and the new tests fail on it.

The fifth version still read only the physical lines that start with "| " (the Claude micro of #986 at be54c82e, P2, command-center/research-cc-role-20261008/pr986-claude-micro-be54c82e.md): a corrupt copy of a
source row written with one to three leading spaces, with no space or a tab after the leading pipe, with no trailing pipe or with no outer pipes is a table row for GitHub's renderer and was invisible to `page_rows()`
(each spelling placed before the valid row: 11 tests, OK). `table_rows()` now reads a table the way the GFM specification does (https://github.github.com/gfm/, version 0.29-gfm of 2019-04-06, section 4.10
Tables (extension), fetched 2026-10-11T09:47:16Z, sha256 b153d814fdfc8624bb6da7449162c1cd707a637f7d1c1b636eb44b9cf63fa220): "The header row must match the delimiter row in the number of cells. If not, a table will
not be recognized", "The table is broken at the first empty line, or beginning of another block-level structure" (examples 201 and 202: a block quote ends it, a line of plain text is a row), and every other line is a
row, whatever its pipes and spaces; a line is cut at a newline or a carriage return only (section 2.1, "A line ending is a newline (U+000A), a carriage return (U+000D) not followed by a newline, or a carriage return
and a following newline"), not at the other characters `str.splitlines()` cuts at. A line that starts with a pipe outside any table is reported, because GitHub renders it as text. What GitHub's renderer does with each
shape was measured with `gh api markdown -f mode=gfm` on the header, the delimiter, the valid row and one line of the shape before it and after it (measurement file sha256 a6e5a13dae945734eac60beba901e28f33b4659cf436a4b2f86509dc3bf3e4ba): the spellings of a row in
ROW_SHAPES and ODD_ROWS are rows; the shapes in BREAK_SHAPES (a block quote, a heading, a list item, a fence, an HTML block, a thematic break, a line indented four columns, a lone pipe, a blank line) end the table and
take every row after them out of it. `test_the_reading_agrees_with_the_rows_github_renders` repeats the measurement where GFM_RENDER_CHECK is set. Fails before, passes after: the unfixed reading (`unfixed_rows()`
below, the reading of be54c82e) finds no extra row for the spellings that do not start with "| " and keeps reading rows after a line that ends the table; the new tests fail on it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
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


# How GitHub Flavored Markdown reads a table (spec 0.29-gfm, section 4.10), as GitHub's renderer was measured to apply it (fifth version above): a header row and a delimiter row with the same number of cells
# start a table; the table is broken at the first blank line or the beginning of another block-level structure; every other line is a row, whatever its pipes and spaces.
DELIMITER = re.compile(r" {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*")
OTHER_BLOCK = re.compile(r" {0,3}(?:>|#{1,6}(?:[ \t]|$)|[-+*](?:[ \t]|$)|\d{1,9}[.)](?:[ \t]|$)|`{3,}|~{3,}|<[A-Za-z/!?]|([-*_])(?:[ \t]*\1){2,}[ \t]*$)")
ROW_LIKE = re.compile(r" {0,3}\|[ \t]*\S")
LINE_ENDING = re.compile(r"\r\n|\r|\n")
SPACES = " \t"
OUTSIDE = "outside a table: "
# A line of each shape built from a source row ({need} and {cell}); the renderer's reading of each was measured (the hash is in the docstring).
ROW_SHAPES = {  # rows
    "the canonical row": "| {need} | {cell} |",
    "one leading space": " | {need} | {cell} |",
    "two leading spaces": "  | {need} | {cell} |",
    "three leading spaces": "   | {need} | {cell} |",
    "no space after the leading pipe": "|{need} | {cell} |",
    "a tab after the leading pipe": "|\t{need} | {cell} |",
    "no space before the closing pipe": "| {need} | {cell}|",
    "no trailing pipe": "| {need} | {cell}",
    "no leading pipe": "{need} | {cell} |",
    "no outer pipes": "{need} | {cell}",
    "a third, empty cell": "| {need} | {cell} | |",
    "the need alone": "{need}",
}
ODD_ROWS = {  # rows with another first cell, which the renderer also reads as rows
    "an empty cell": "| |",
    "two pipes": "||",
    "three pipes": "|||",
    "a heading marker with no space": "#{need}",
    "an ordered marker with no space": "1.{need}",
    "a dash with no space": "-{need}",
    "text ending in a backslash": "{need} \\",
}
BREAK_SHAPES = {  # lines that end the table
    "an empty line": "",
    "a line of spaces": "   ",
    "four leading spaces": "    | {need} | {cell} |",
    "a leading tab": "\t| {need} | {cell} |",
    "a block quote": "> {need} | {cell}",
    "a block quote with no space": ">{need} | {cell}",
    "a heading": "# {need}",
    "a dash list item": "- {need}",
    "a plus list item": "+ {need}",
    "a star list item": "* {need}",
    "an ordered list item": "1. {need}",
    "an ordered list item with a parenthesis": "1) {need}",
    "a backtick fence": "```",
    "a tilde fence": "~~~",
    "an HTML block": "<div>{need}</div>",
    "an HTML comment": "<!-- {need} -->",
    "a thematic break of stars": "***",
    "a thematic break of dashes": "---",
    "a lone pipe": "|",
    "a pipe after a space": " |",
}

TABLE_STARTS = {  # (header, delimiter, is it a table)
    "a header and a delimiter of two cells": ("| Need | Source |", "| --- | --- |", True),
    "a delimiter of single hyphens": ("| Need | Source |", "| - | - |", True),
    "a delimiter with alignment colons": ("| Need | Source |", "| :-- | --: |", True),
    "a delimiter indented three spaces": ("| Need | Source |", "   | --- | --- |", True),
    "a delimiter indented four spaces": ("| Need | Source |", "    | --- | --- |", False),
    "a header and a delimiter with no outer pipes": ("Need | Source", "--- | ---", True),
    "a one-column table": ("| Need |", "| - |", True),
    "a header of three cells over a delimiter of two": ("| Need | Source | More |", "| --- | --- |", False),
    "a delimiter of two cells with a cell of no hyphen": ("| Need | Source |", "| --- | |", False),
    "a header indented four spaces": ("    | Need | Source |", "| --- | --- |", False),
    "a header that is a block quote": ("> Need | Source", "--- | ---", False),
    "a header and a delimiter with no pipe at all": ("Need", "---", False),
}


def indent(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip(" "))


def row_parts(line: str) -> list[str]:
    """The cells of a row: the first pipe and the closing pipe are not separators, and neither is an escaped pipe."""
    body = line.strip(SPACES)
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return re.split(r"(?<!\\)\|", body)


def split_row(line: str) -> tuple[str, str]:
    """A row as (its first cell, the rest of the row): the first cell is the need, the rest is the source cell as written."""
    parts = row_parts(line)
    return parts[0].strip(SPACES), "|".join(parts[1:]).strip(SPACES)


def starts_table(header: str, delimiter: str) -> bool:
    return (DELIMITER.fullmatch(delimiter.expandtabs(4)) is not None and "|" in header + delimiter and header.strip(SPACES) != "" and indent(header) < 4
            and OTHER_BLOCK.match(header.expandtabs(4)) is None and len(row_parts(header)) == len(row_parts(delimiter)))


def ends_table(line: str) -> bool:
    """The table is broken at a blank line, a lone pipe (a row of no cells) or the beginning of another block-level structure; four columns of indent make a code block."""
    expanded = line.expandtabs(4)
    return not expanded.strip(SPACES) or expanded.strip(SPACES) == "|" or indent(line) >= 4 or OTHER_BLOCK.match(expanded) is not None


def table_rows(text: str) -> list[tuple[str, str]]:
    """The rows of every table in `text` as (need, cell) in page order, duplicates kept. A line that starts with a pipe outside any table comes back with OUTSIDE before its need (GitHub renders it as text)."""
    lines = LINE_ENDING.split(text)
    rows, i = [], 0
    while i < len(lines):
        if i + 1 < len(lines) and starts_table(lines[i], lines[i + 1]):
            i += 2
            while i < len(lines) and not ends_table(lines[i]):
                rows.append(split_row(lines[i]))
                i += 1
            continue
        if ROW_LIKE.match(lines[i].expandtabs(4)):
            need, cell = split_row(lines[i])
            rows.append((OUTSIDE + need, cell))
        i += 1
    return rows


def unfixed_rows(text: str) -> list[tuple[str, str]]:
    """The reading of be54c82e and before, kept to show what it missed: the physical lines of the sources part that start with "| "."""
    rows = []
    for line in text.split("Claude column sources", 1)[1].splitlines():
        if line.startswith("| ") and not line.startswith(("| Need", "| ---")):
            need, cell = (part.strip() for part in line.strip().strip("|").split("|", 1))
            rows.append((need, cell))
    return rows


def page_rows(text: str | None = None) -> tuple[list[str], list[tuple[str, str]]]:
    """The needs of the mechanism table, and the rows of the Claude source table as (need, cell) in the order they are written, duplicates kept (a mapping keyed by need let a later row replace an
    earlier one before any check saw it: the GPT micro of #986 at f085a62b, P2). Both tables are read as GitHub reads a table (`table_rows`): the Claude micro of #986 at be54c82e, P2."""
    text = PAGE.read_text(encoding="utf-8") if text is None else text
    mechanism = text.split("## Native mechanism per client", 1)[1].split("Claude column sources", 1)[0]
    return [need for need, _ in table_rows(mechanism)], table_rows(text.split("Claude column sources", 1)[1])


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
    """The recorded hash of a line: the sha256 of its bytes followed by a newline, lines counted by newline. For a line that is followed by a newline in the capture (each recorded line is),
    `sed -n '<number>p' <capture> | sha256sum` prints the same; a final line without a newline is hashed with one added, which sed does not print (the Claude micro of #986 at be54c82e, P3)."""
    return hashlib.sha256(capture.split(b"\n")[number - 1] + b"\n").hexdigest()


def split_cell(cell: str) -> list[str]:
    """The citations of a cell as written: each starts at a link, and the text between two links belongs to the citation before it."""
    return SEPARATOR.split(cell.strip(SPACES))


def violations(cells, needs: list, captures: dict, lines: dict | None = None) -> list:
    """`cells` is the rows of the source table as (need, cell) pairs in page order, or a dict need -> cell. A need written twice is a violation and every row is checked, not only the last one."""
    rows = list(cells.items()) if isinstance(cells, dict) else list(cells)
    lines = recorded_lines() if lines is None else lines
    names = [need for need, _ in rows]
    found = [f"more than one source row for {need!r}" for need in dict.fromkeys(names) if names.count(need) > 1]
    found += [f"no source cell for {need!r}" for need in needs if need not in names]
    found += [f"a source cell for {need!r}, which is not a need of the mechanism table" for need in dict.fromkeys(names) if need not in needs and not need.startswith(OUTSIDE)]
    found += [f"a row-like line outside any table (the table ends before it): {need[len(OUTSIDE):]!r}" for need in names if need.startswith(OUTSIDE)]
    found += [f"no expected citations for {need!r}" for need in needs if need not in EXPECTED]
    found += [f"expected citations for {need!r}, which is not a need of the mechanism table" for need in EXPECTED if need not in needs]
    for need, cell in rows:
        if need.startswith(OUTSIDE):
            continue
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
        self.assertEqual(line_digest(capture, 3), hashlib.sha256(b"third\n").hexdigest(), "the last line without a newline is hashed with one added (sed does not print one)")

    @unittest.skipUnless(os.environ.get("CLAUDE_DOCS_CAPTURES"), "set CLAUDE_DOCS_CAPTURES to the directory that holds the captured documentation pages (<page>.md)")
    def test_the_recorded_line_hashes_match_the_captures_where_they_are_available(self):
        directory = Path(os.environ["CLAUDE_DOCS_CAPTURES"])
        for (url, number), (sha, _fetched, digest) in recorded_lines().items():
            with self.subTest(line=(url, number)):
                capture = (directory / (url.rsplit("/", 1)[1])).read_bytes()
                self.assertEqual(hashlib.sha256(capture).hexdigest(), sha)
                self.assertLessEqual(number, capture.count(b"\n"), "the line is followed by a newline, so `sed -n '<number>p' | sha256sum` prints the recorded hash")
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


class SourceTableReadingTests(unittest.TestCase):
    """The Claude micro of #986 at be54c82e (P2, P3-1, P3-2): the table is read the way GitHub reads it, and what the texts say about the artifacts is what the artifacts hold."""

    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")
        cls.needs, cls.rows = page_rows(cls.text)
        cls.captures = recorded_captures()
        cls.head, cls.sources = cls.text.split("Claude column sources", 1)
        cls.lines = LINE_ENDING.split(cls.sources)
        cls.gate = next(i for i, line in enumerate(cls.lines) if line.startswith("| Completion gate |"))
        cls.last = max(i for i, line in enumerate(cls.lines) if line.startswith("| "))
        cls.need, cls.cell = split_row(cls.lines[cls.gate])
        cls.names = [need for need, _ in cls.rows]

    def page_with(self, line: str, where: str) -> str:
        position = {"before": self.gate, "after": self.gate + 1, "at the end": self.last + 1}[where]
        return self.head + "Claude column sources" + "\n".join(self.lines[:position] + [line] + self.lines[position:])

    def test_the_page_as_written_is_one_table_of_seven_rows_and_one_of_seven_needs(self):
        self.assertEqual(sorted(self.names), sorted(self.needs))
        self.assertEqual(len(self.rows), 7)
        self.assertEqual(violations(self.rows, self.needs, self.captures), [])

    def test_a_corrupt_source_row_in_any_spelling_github_renders_as_a_row_is_caught_in_either_order(self):
        corruptions = {"a wrong host": self.cell.replace("code.claude.com", "invalid.example", 1), "trailing prose": self.cell + " (extra prose)"}
        for label, template in ROW_SHAPES.items():
            for corruption, bad_cell in corruptions.items():
                line = template.format(need=self.need, cell=bad_cell)
                for where in ("before", "after"):
                    with self.subTest(spelling=label, corruption=corruption, placed=where):
                        page = self.page_with(line, where)
                        needs, rows = page_rows(page)
                        self.assertEqual(len(rows), len(self.rows) + 1)
                        found = violations(rows, needs, self.captures)
                        self.assertIn(f"more than one source row for {self.need!r}", found)
                        self.assertGreater(len(found), 1, "the corrupt row is checked on its own")
                        if not line.startswith("| "):
                            self.assertEqual(len(unfixed_rows(page)), len(self.rows), "the physical-line reading of be54c82e does not see this row")

    def test_lines_that_only_look_like_something_else_stay_rows(self):
        for label, template in ODD_ROWS.items():
            for where in ("before", "after"):
                with self.subTest(line=label, placed=where):
                    needs, rows = page_rows(self.page_with(template.format(need=self.need, cell=self.cell), where))
                    self.assertEqual(len([row for row in rows if not row[0].startswith(OUTSIDE)]), len(self.rows) + 1)
                    self.assertNotEqual(violations(rows, needs, self.captures), [])

    def test_a_line_that_ends_the_table_takes_the_rows_after_it_out_of_the_table(self):
        gate = self.names.index(self.need)
        for label, template in BREAK_SHAPES.items():
            line = template.format(need=self.need, cell=self.cell)
            with self.subTest(line=label, placed="before the Completion gate row"):
                needs, rows = page_rows(self.page_with(line, "before"))
                self.assertEqual([n for n, _ in rows if not n.startswith(OUTSIDE)], self.names[:gate])
                found = violations(rows, needs, self.captures)
                self.assertIn(f"no source cell for {self.need!r}", found)
                self.assertTrue(any(f.startswith("a row-like line outside any table") for f in found))
            with self.subTest(line=label, placed="after the Completion gate row"):
                needs, rows = page_rows(self.page_with(line, "after"))
                self.assertEqual([n for n, _ in rows if not n.startswith(OUTSIDE)], self.names[:gate + 1])
                found = violations(rows, needs, self.captures)
                self.assertIn(f"no source cell for {self.names[-1]!r}", found)
            with self.subTest(line=label, placed="after the last row"):
                needs, rows = page_rows(self.page_with(line, "at the end"))
                self.assertEqual(violations(rows, needs, self.captures), [], "a block that starts under the last row ends the table where the table ends")

    def test_what_starts_a_table(self):
        row = self.lines[self.gate]
        for label, (header, delimiter, table) in TABLE_STARTS.items():
            with self.subTest(case=label):
                rows = table_rows("\n".join([header, delimiter, row]))
                tabled = [r for r in rows if not r[0].startswith(OUTSIDE)]
                strays = [r for r in rows if r[0].startswith(OUTSIDE)]
                if table:
                    self.assertEqual((len(tabled), len(strays)), (1, 0))
                else:
                    self.assertEqual(tabled, [])
                    self.assertTrue(strays, "the row of a text that is not a table is a line outside any table")

    def test_a_second_table_a_stray_row_and_a_table_that_lost_its_delimiter_are_caught(self):
        table = "\n".join(line for line in self.lines if line.startswith("| "))
        pages = {
            "the whole table written twice": self.text.rstrip("\n") + "\n\n" + table + "\n",
            "one row after a blank line": self.text.rstrip("\n") + "\n\n" + self.lines[self.gate] + "\n",
            "the delimiter row removed": self.head + "Claude column sources" + "\n".join(line for line in self.lines if not line.startswith("| --- |")),
        }
        for label, page in pages.items():
            with self.subTest(page=label):
                needs, rows = page_rows(page)
                found = violations(rows, needs, self.captures)
                self.assertNotEqual(found, [])
                if label == "the delimiter row removed":
                    self.assertTrue(any(f.startswith("a row-like line outside any table") for f in found))
                else:
                    self.assertTrue(any(f.startswith("more than one source row") or f.startswith("a row-like line outside any table") for f in found))

    def test_a_character_that_python_but_not_markdown_cuts_a_line_at_does_not_hide_what_follows_it(self):
        for separator in ("\u2028", "\u0085", "\x0b", "\x0c", "\x1c"):
            with self.subTest(separator=repr(separator)):
                row = self.lines[self.gate].rstrip(" |") + separator + "tail |"
                page = self.head + "Claude column sources" + "\n".join(self.lines[:self.gate] + [row] + self.lines[self.gate + 1:])
                needs, rows = page_rows(page)
                self.assertEqual(len(rows), len(self.rows))
                self.assertNotEqual(violations(rows, needs, self.captures), [], "the text after the separator is part of the cell")
                self.assertEqual(violations(unfixed_rows(page), needs, self.captures), [], "the reading of be54c82e cut the row at the separator and checked the first part only")

    def test_an_extra_cell_the_renderer_drops_is_still_read(self):
        # GFM section 4.10, example 204: "If there are greater, the excess is ignored", so text in a third cell is not on the rendered page; it is in the file, and the guard reads it as part of the source cell.
        row = self.lines[self.gate].rstrip(" |") + " | extra prose |"
        page = self.head + "Claude column sources" + "\n".join(self.lines[:self.gate] + [row] + self.lines[self.gate + 1:])
        needs, rows = page_rows(page)
        self.assertEqual(len(rows), len(self.rows))
        self.assertNotEqual(violations(rows, needs, self.captures), [])

    def test_text_that_is_not_a_space_or_a_tab_stays_in_the_cell(self):
        # the GFM specification trims "spaces" between pipes and cell content; a no-break space is content, and the cell with it is not a citation
        for character in ("\u00a0", "\u200b", "\x0b"):
            with self.subTest(character=repr(character)):
                row = self.lines[self.gate].rstrip(" |") + character + " |"
                page = self.head + "Claude column sources" + "\n".join(self.lines[:self.gate] + [row] + self.lines[self.gate + 1:])
                needs, rows = page_rows(page)
                self.assertEqual(len(rows), len(self.rows))
                self.assertNotEqual(violations(rows, needs, self.captures), [])

    def test_a_blank_line_is_only_spaces_and_tabs(self):
        # the GFM specification, section 2.1: "A line containing no characters, or a line containing only spaces (U+0020) or tabs (U+0009), is called a blank line"
        for blank, ends in (("", True), ("  ", True), ("\t", True), ("\u00a0", False), ("\x0b", False)):
            with self.subTest(line=repr(blank)):
                self.assertEqual(ends_table(blank), ends)

    @staticmethod
    def locator_counts(claims: dict) -> tuple[int, int, int]:
        found = [locator for claim in claims["claims"] for locator in claim.get("locators", []) if locator.get("type") == "url" and locator.get("url", "").startswith(BASE)]
        return len(found), sum("capture_sha256" in locator for locator in found), sum("lines" in locator for locator in found)

    def test_the_locator_counts_the_module_states_are_the_counts_of_the_blob_it_names(self):
        # The Claude micro of #986 at be54c82e, P3: the text said 256 documentation locators; claims.json at f085a62b holds 257 (256 with a capture hash, 253 with lines).
        blob = "cb0fe6c39497d0f5c6261cd97315d1117acc3a86"
        shown = subprocess.run(["git", "-C", str(ROOT), "cat-file", "blob", blob], capture_output=True)
        if shown.returncode != 0:
            self.skipTest(f"the history of this checkout does not hold blob {blob}")
        counts = self.locator_counts(json.loads(shown.stdout))
        stated = re.search(r"holds (\d+) documentation locators \(type `url`, code\.claude\.com\), (\d+) of them with a capture hash .*? and (\d+) of them\s+carry a `lines` field", __doc__, re.S)
        self.assertIsNotNone(stated, "the module states the three counts")
        self.assertEqual(tuple(int(n) for n in stated.groups()), counts)
        self.assertEqual(counts, (257, 256, 253))

    def test_sed_prints_the_recorded_hash_of_a_line_followed_by_a_newline(self):
        # P3: the parity holds for a line followed by a newline; the texts that claim it say so
        if shutil.which("sed") is None:
            self.skipTest("sed is not on the PATH")
        capture = b"first\nsecond\nthird"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.md"
            path.write_bytes(capture)
            for number in (1, 2):
                printed = subprocess.run(["sed", "-n", f"{number}p", str(path)], capture_output=True, check=True).stdout
                self.assertEqual(hashlib.sha256(printed).hexdigest(), line_digest(capture, number))
        note = json.loads(LINES.read_text(encoding="utf-8"))["note"]
        for where, text in {"the page": self.sources.split("\n\n", 1)[0], "the lines artifact": note, "line_digest": line_digest.__doc__}.items():
            with self.subTest(text=where):
                self.assertIn("a line that is followed by a newline", text)

    @unittest.skipUnless(os.environ.get("GFM_RENDER_CHECK"), "set GFM_RENDER_CHECK=1 to compare the reading with GitHub's renderer (needs the gh CLI, a login and network)")
    def test_the_reading_agrees_with_the_rows_github_renders(self):
        def rendered(markdown: str) -> int:
            html = subprocess.run(["gh", "api", "markdown", "-f", "mode=gfm", "-f", f"text={markdown}", "-H", "Accept: application/vnd.github+json"], capture_output=True, check=True, text=True).stdout
            body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
            return len(re.findall(r"<tr>", body.group(1))) if body else 0

        header, delimiter = "| Need | Claude Code source |", "| --- | --- |"
        valid = self.lines[self.gate]
        shapes = {**ROW_SHAPES, **ODD_ROWS, **BREAK_SHAPES}
        for label, template in shapes.items():
            line = template.format(need=self.need, cell=self.cell)
            for where, body in (("before", [line, valid]), ("after", [valid, line])):
                with self.subTest(line=label, placed=where):
                    markdown = "\n".join([header, delimiter, *body]) + "\n"
                    read = [row for row in table_rows(markdown) if not row[0].startswith(OUTSIDE)]
                    self.assertEqual(len(read), rendered(markdown))
        for label, (head_row, delimiter_row, table) in TABLE_STARTS.items():
            with self.subTest(case=label):
                markdown = "\n".join([head_row, delimiter_row, valid]) + "\n"
                self.assertEqual(len([row for row in table_rows(markdown) if not row[0].startswith(OUTSIDE)]), rendered(markdown))


if __name__ == "__main__":
    unittest.main()
