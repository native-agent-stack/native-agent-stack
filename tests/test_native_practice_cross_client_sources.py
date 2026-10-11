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
(each spelling placed before the valid row: 11 tests, OK). The sixth version copied the GFM specification's rules for a table (https://github.github.com/gfm/, version 0.29-gfm of 2019-04-06, section 4.10, fetched
2026-10-11T09:47:16Z, sha256 b153d814fdfc8624bb6da7449162c1cd707a637f7d1c1b636eb44b9cf63fa220) and one pattern for the block structure around a table, and checked them against `gh api markdown`. It caught the six spellings and still
disagreed with GitHub in both directions on 13 of 29 shapes (the command center's Claude micro at 18227acd, and the Codex review of the same head, P2 twice): a line that starts with an inline tag, an autolink, a backtick fence whose info
string holds a backtick, or `<! ` is a row for GitHub (section 4.5: the info string "may not contain any backtick characters"; section 4.6, condition 7: a complete tag "followed only by whitespace or the end of the line") and was
dropped as the start of a block; a table inside a block quote (5.1), a list item (5.2), a fenced block, an HTML comment or a second table is not the published source table and was counted as it.

The seventh version does not emulate a renderer (the command center's ruling at 18227acd, option 1: fail closed on the page's canonical structure). The two tables of the page are maintained data, so the page has exactly one shape and every other
line of its two sections is a violation (`read_page()`): the heading "## Native mechanism per client", a blank line, the header, the delimiter, the rows, a blank line; then the paragraph that begins "Claude column sources:" (plain text: no
line of it starts a quote, a heading, a list, a fence, raw HTML, a table row or a rule), a blank line, the header, the delimiter, and the rows to the end of the file. A row is "| <need> | <cell> |" (three cells in the mechanism table):
cells trimmed, a single space around each pipe, no pipe inside a cell, the line starting in the first column. The page has newline line endings only. Nothing before the mechanism heading starts a fence or raw HTML (an unclosed one would hide
both tables), and a line that looks like a delimiter row or a header row anywhere else in the file (HTML, comments, fences, quotes, list items, a second table) is a violation too. GitHub's renderer stays the oracle:
`test_the_canonical_page_renders_exactly_the_two_expected_tables` (enabled by GFM_RENDER_CHECK) renders the page with `gh api markdown` and checks the tables, their rows and their first cells, and
`test_a_page_that_hides_or_adds_a_source_row_renders_differently` shows that for each dangerous regression page GitHub shows something other than those tables (the renders: gfm-render-regression-pages.json, sha256
25c749ce1a94429716d7a486c787eaedb57589532b09e6abc69952b324dabdfb; 39 line shapes measured before: gfm-render-measurement.json, sha256 a6e5a13dae945734eac60beba901e28f33b4659cf436a4b2f86509dc3bf3e4ba). Fails before, passes after: the module of 18227acd reports nothing on 12 of the 16 regression
pages of `CanonicalStructureTests` that GitHub renders differently (the source row moved to a second table, a fenced block or a tilde fence, the whole source table in a comment, a quoted copy of the table with a wrong-host row, and
the rows that begin with an inline tag, an autolink, a backtick-fence line or `<! `) and the new tests fail on it; the other four (the source row moved into a comment, a quoted table or a list item, and a list-item copy) it rejects
for other reasons, and the two invisible pages it passes (the table of the pages, with the counts: fail-before-canonical-structure.txt, retained beside gfm-render-regression-pages.json).

The eighth version closes three bypasses that the command center's Claude micro of #986 found at 23fa8ef7a (P2-1 to P2-3), each a page that GitHub renders differently and the guard passed: a table without outer pipes inside the source
paragraph (the paragraph lines skipped the sweep; the specification calls the leading and trailing pipe only "recommended", section 4.10, so a header line, a delimiter row and a row are a third table); a delimiter row spaced with a
vertical tab or a form feed (whitespace to the renderer, section 2.1, and invisible to the space and tab classes of the patterns: the page now rejects both characters); and an HTML table tag anywhere (section 6.10: raw HTML "will be
rendered in HTML without escaping"). Nine pages join the regression pages (27 in all; GitHub renders 24 of them differently and 3 are invisible; the renders: gfm-render-regression-pages-v2.json, sha256
4d130c8063339eb3685275a3de82eaa7d06086a3fde474eb799e09d5f800a427; the first file, 18 pages, is kept). Fails before, passes after: the guard of 23fa8ef7a passes 8 of the new pages with no violation (fail-before-wave.txt, retained beside the
renders).
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


# The page is data, not prose, and the guard does not emulate a renderer (the command center's ruling on #986 at 18227acd, option 1: fail closed on the page's canonical structure; see the seventh version above).
# The two sections of the page have exactly this shape, and every other line of them is a violation:
#   ## Native mechanism per client / blank / header / delimiter / rows / blank / "Claude column sources: ..." (one paragraph of plain text) / blank / header / delimiter / rows to the end of the file.
MECHANISM_HEADING = "## Native mechanism per client"
SOURCES_MARKER = "Claude column sources:"
CELL = r"[^|\s](?:[^|]*[^|\s])?"
MECHANISM_HEADER = re.compile(r"\| Need \| Claude Code [0-9.]+ \| Codex [0-9.]+ \|")
MECHANISM_DELIMITER = "| --- | --- | --- |"
MECHANISM_ROW = re.compile(rf"\| ({CELL}) \| {CELL} \| {CELL} \|")
SOURCE_HEADER = "| Need | Claude Code source |"
SOURCE_DELIMITER = "| --- | --- |"
SOURCE_ROW = re.compile(rf"\| ({CELL}) \| ({CELL}) \|")
# What looks like a delimiter row or a header row, also behind a block quote or list marker, is not allowed anywhere but at its place in the two tables.
DELIMITER_SHAPED = re.compile(r"[ \t>*+0-9.)-]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*")
HEADER_SHAPED = re.compile(r"[ \t>*+0-9.)-]*\|?[ \t]*Need[ \t]*\|")
# A fence or raw HTML before the tables could hide them (an unclosed fence or comment runs to the end of the document), so none is allowed before the second section's header; a line that breaks the source paragraph is not plain text.
SWALLOWING = re.compile(r" {0,3}(?:`{3,}|~{3,}|<)")
PARAGRAPH_BREAKER = re.compile(r" {0,3}(?:>|#{1,6}(?:[ \t]|$)|[-+*](?:[ \t]|$)|\d{1,9}[.)](?:[ \t]|$)|`{3,}|~{3,}|<|\||([-*_])(?:[ \t]*\1){2,}[ \t]*$|[=-]+[ \t]*$)")
# A raw HTML table tag anywhere (a line of prose, a cell) is a table to the renderer: "Text between < and > that looks like an HTML tag is parsed as a raw HTML tag and will be rendered in HTML without escaping"
# (GFM 0.29-gfm section 6.10, sha256 b153d814...).
HTML_TABLE = re.compile(r"(?i)<\s*/?\s*(?:table|thead|tbody|tfoot|tr|th|td)\b")
SPACES = " \t"
OUTSIDE = "the page is not canonical: "


def table_shaped(line: str) -> bool:
    """A header- or delimiter-shaped line is never a row, whatever its cells say."""
    return HEADER_SHAPED.match(line) is not None or ("|" in line and DELIMITER_SHAPED.fullmatch(line) is not None)


def read_page(text: str) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    """(the needs of the mechanism table, the rows of the source table as (need, cell) in page order with duplicates kept, the findings): a finding is any line or place that the canonical structure does not have."""
    findings = []
    if "\r" in text:
        findings.append("a carriage return: the canonical page has newline line endings only")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    for index, line in enumerate(lines):
        if "\x0b" in line or "\x0c" in line:
            findings.append(f"line {index + 1}: a vertical tab or a form feed, which is whitespace to the renderer (GFM 0.29-gfm section 2.1) and can space a delimiter row: {line!r}")
        if HTML_TABLE.search(line):
            findings.append(f"line {index + 1}: an HTML table tag, which the renderer shows as a table (GFM 0.29-gfm section 6.10): {line!r}")
    headings = [i for i, line in enumerate(lines) if line == MECHANISM_HEADING]
    markers = [i for i, line in enumerate(lines) if line.startswith(SOURCES_MARKER)]
    if len(headings) != 1 or len(markers) != 1 or headings[0] > markers[0]:
        return [], [], findings + [f"{len(headings)} mechanism headings and {len(markers)} source paragraphs: the page has one of each, in that order"]
    heading, marker = headings[0], markers[0]
    shaped = set()
    needs, rows = [], []

    def expect(index: int, wanted, what: str) -> None:
        line = lines[index] if 0 <= index < len(lines) else None
        if line is not None and (wanted.fullmatch(line) if hasattr(wanted, "fullmatch") else line == wanted):
            shaped.add(index)
        else:
            findings.append(f"line {index + 1}: {what} is expected here, found {line!r}")

    for index in range(0, heading):
        if SWALLOWING.match(lines[index]):
            findings.append(f"line {index + 1}: a fence or raw HTML before the tables could hide them: {lines[index]!r}")
    expect(heading + 1, "", "a blank line after the mechanism heading")
    expect(heading + 2, MECHANISM_HEADER, "the mechanism table's header")
    expect(heading + 3, MECHANISM_DELIMITER, "the mechanism table's delimiter")
    expect(marker - 1, "", "a blank line before the source paragraph")
    ended = False
    for index in range(heading + 4, marker - 1):
        match = None if ended else MECHANISM_ROW.fullmatch(lines[index])
        if match and not table_shaped(lines[index]):
            shaped.add(index)
            needs.append(match.group(1))
        else:
            ended = True  # a table ends at the first line that is not a row; what follows is not a row of it, whatever it looks like
            findings.append(f"line {index + 1}: not a row of the mechanism table, '| <need> | <Claude Code> | <Codex> |': {lines[index]!r}")
    blank = next((index for index in range(marker, len(lines)) if lines[index].strip(SPACES) == ""), None)
    for index in range(marker, len(lines) if blank is None else blank):
        shaped.add(index)
        if index > marker and (PARAGRAPH_BREAKER.match(lines[index]) or DELIMITER_SHAPED.fullmatch(lines[index]) or HEADER_SHAPED.match(lines[index])):
            findings.append(f"line {index + 1}: a line that is not plain text inside the source paragraph: {lines[index]!r}")
    if blank is None:
        findings.append("the source paragraph is not followed by a blank line and the source table")
        return needs, rows, findings
    expect(blank, "", "a blank line after the source paragraph")
    expect(blank + 1, SOURCE_HEADER, "the source table's header")
    expect(blank + 2, SOURCE_DELIMITER, "the source table's delimiter")
    ended = False
    for index in range(blank + 3, len(lines)):
        match = None if ended else SOURCE_ROW.fullmatch(lines[index])
        if match and not table_shaped(lines[index]):
            shaped.add(index)
            rows.append((match.group(1), match.group(2)))
        else:
            ended = True
            findings.append(f"line {index + 1}: not a row of the source table, '| <need> | <cell> |', to the end of the file: {lines[index]!r}")
    for index, line in enumerate(lines):
        if index not in shaped and ("|" in line and DELIMITER_SHAPED.fullmatch(line) or HEADER_SHAPED.match(line)):
            findings.append(f"line {index + 1}: a delimiter-shaped or header-shaped line outside the two tables: {line!r}")
    return needs, rows, list(dict.fromkeys(findings))


def page_rows(text: str | None = None) -> tuple[list[str], list[tuple[str, str]]]:
    """The needs of the mechanism table, and the rows of the Claude source table as (need, cell) in the order they are written, duplicates kept (a mapping keyed by need let a later row replace an earlier one before any check
    saw it: the GPT micro of #986 at f085a62b, P2). Every line the canonical page does not have comes back as a row with OUTSIDE before its text, and `violations()` reports it."""
    needs, rows, findings = read_page(PAGE.read_text(encoding="utf-8") if text is None else text)
    return needs, rows + [(OUTSIDE + finding, "") for finding in findings]


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
    found += [need for need in names if need.startswith(OUTSIDE)]
    found += [f"more than one mechanism row for {need!r}" for need in dict.fromkeys(needs) if needs.count(need) > 1]
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


class CanonicalStructureTests(unittest.TestCase):
    """The command center's Claude micro of #986 at 18227acd and the Codex review of the same head (P2 twice): the page has one canonical structure and every other line of its two sections is a violation; what the texts say about
    the artifacts is what the artifacts hold."""

    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")
        cls.needs, cls.rows, cls.findings = read_page(cls.text)
        cls.captures = recorded_captures()
        cls.lines = cls.text.split("\n")
        cls.marker = next(i for i, line in enumerate(cls.lines) if line.startswith(SOURCES_MARKER))
        cls.mechanism_end = cls.marker - 1  # the blank line before the source paragraph
        cls.mechanism_header = cls.lines.index(MECHANISM_HEADING) + 2
        cls.source_header = cls.lines.index(SOURCE_HEADER)
        cls.gate = next(i for i, line in enumerate(cls.lines) if i > cls.source_header and line.startswith("| Completion gate |"))
        cls.last = max(i for i, line in enumerate(cls.lines) if line.startswith("| "))
        cls.need, cls.cell = cls.rows[1]

    def page(self, lines: list[str]) -> str:
        return "\n".join(lines)

    def violations_of(self, text: str) -> list[str]:
        needs, rows = page_rows(text)
        return violations(rows, needs, self.captures)

    def inserted(self, index: int, extra: list[str]) -> str:
        return self.page(self.lines[:index] + extra + self.lines[index:])

    def positions(self) -> dict[str, int]:
        """Where a line can be put: each is an index into the lines, the new lines go before it."""
        return {"inside the mechanism table": self.mechanism_header + 3, "after the last mechanism row": self.mechanism_end, "inside the source paragraph": self.marker + 1,
                "between the paragraph and the source table": self.source_header, "between the source header and its delimiter": self.source_header + 1, "before the Completion gate row": self.gate,
                "after the Completion gate row": self.gate + 1, "after the last source row": self.last + 1}

    def test_the_page_as_written_has_the_canonical_structure(self):
        self.assertEqual(self.findings, [])
        self.assertEqual(len(self.needs), 7)
        self.assertEqual(len(self.rows), 7)
        self.assertEqual([need for need, _ in self.rows], self.needs)
        self.assertEqual(self.violations_of(self.text), [])

    def test_every_line_the_canonical_page_does_not_have_is_a_violation_wherever_it_is_put(self):
        # The Claude micro of #986 at 18227acd (P2-1): a row led by an inline tag, an autolink, a backtick fence whose info string holds a backtick or `<! ` is a row for GitHub and was dropped as the start of a block;
        # the earlier readings also took some lines for rows that GitHub does not render as rows. None of these lines is in the canonical structure (in the source paragraph, plain text is).
        need, bad = self.need, self.cell.replace("code.claude.com", "invalid.example", 1)
        lines = {"a wrong-host row led by <b>": f"<b>{need}</b> | {bad} |", "a wrong-host row led by <span>": f"<span>{need}</span> | {bad} |", "a wrong-host row led by </b>": f"</b>{need} | {bad} |",
                 "an autolink-led row": f"<https://example.invalid> | {bad} |", "a backtick fence whose info string holds a backtick": f"```{need}`x | {bad}", "a line led by <! ": f"<! {need} | {bad}",
                 "a row for a new need that has no source": "| A need nobody cited | a mechanism | a mechanism |", "a block quote": f"> {need} | {bad}", "a heading": "# a heading", "a list item": "- an item",
                 "an HTML comment": "<!-- x -->", "an empty line": "", "a line of spaces": "   ", "a lone pipe": "|", "four leading spaces": f"    | {need} | {bad} |",
                 "one leading space": f" | {need} | {bad} |", "three leading spaces": f"   | {need} | {bad} |", "no space after the leading pipe": f"|{need} | {bad} |", "a tab after the leading pipe": f"|\t{need} | {bad} |",
                 "no trailing pipe": f"| {need} | {bad}", "no leading pipe": f"{need} | {bad} |", "no outer pipes": f"{need} | {bad}", "a third cell": f"| {need} | {bad} | extra |",
                 "a row ending in an escaped pipe": f"| {need} | {bad} \\|", "a row with doubled spaces": f"|  {need}  |  {bad}  |", "a plain line of text": "Completion gate", "a thematic break": "***"}
        for where, index in self.positions().items():
            for label, line in lines.items():
                with self.subTest(line=label, placed=where):
                    found = self.violations_of(self.inserted(index, [line]))
                    if where == "inside the source paragraph" and line.strip() and not PARAGRAPH_BREAKER.match(line):
                        self.assertEqual(found, [], "a plain line of the paragraph is text")
                    elif where in ("inside the mechanism table", "after the last mechanism row") and label == "a row for a new need that has no source":
                        self.assertIn("no source cell for 'A need nobody cited'", found)
                    else:
                        self.assertNotEqual(found, [])
        # the one line that is canonical, the same row again, is a duplicate and reported as one
        found = self.violations_of(self.inserted(self.last + 1, [f"| {need} | {bad} |"]))
        self.assertIn(f"more than one source row for {need!r}", found)

    def test_a_fence_or_raw_html_before_the_tables_is_a_violation_because_an_unclosed_one_hides_them(self):
        for text in ("```", "```text", "~~~", "<!--", "<div>", "<script>", "<pre>", "   ```", "<?php", "<![CDATA["):
            with self.subTest(line=text):
                page = self.inserted(3, [text])
                self.assertTrue(any("could hide them" in f for f in self.violations_of(page)))

    def test_the_whole_source_table_in_a_comment_leaves_no_source_table(self):
        # The Claude micro of #986 at 18227acd (P2-2): GitHub renders only the mechanism table, and the whole module passed.
        table = self.lines[self.source_header:self.last + 1]
        page = self.page(self.lines[:self.source_header] + ["<!--", ""] + table + ["", "-->"])
        found = self.violations_of(page)
        self.assertTrue(any("source table's header" in f for f in found))
        self.assertIn(f"no source cell for {self.need!r}", found, "nothing after the comment counts as a row of the table")

    def test_a_source_row_moved_out_of_the_table_is_reported_wherever_it_goes(self):
        # The Codex review of #986 at 18227acd (P2) and the Claude micro (P2-2): the six pages on which GitHub does not show the row in the published source table and the guard found it.
        row = self.lines[self.gate]
        remaining = self.lines[:self.gate] + self.lines[self.gate + 1:]
        header, delimiter = self.lines[self.source_header], self.lines[self.source_header + 1]
        blocks = {"a second table": [header, delimiter, row], "a fenced block": ["```", header, delimiter, row, "```"], "a fenced block in tildes": ["~~~~", header, delimiter, row, "~~~~"],
                  "an HTML comment": ["<!--", header, delimiter, row, "-->"], "a block quote": [f"> {header}", f"> {delimiter}", f"> {row}"],
                  "a list item": [f"- {header}", f"  {delimiter}", f"  {row}"], "bare rows after a blank line": [row]}
        for label, extra in blocks.items():
            with self.subTest(moved_to=label):
                found = self.violations_of(self.page(remaining + [""] + extra))
                self.assertIn(f"no source cell for {self.need!r}", found)
                self.assertTrue(any(f.startswith(OUTSIDE) for f in found))

    def test_a_quoted_or_list_item_copy_of_the_table_is_a_violation(self):
        # Samples of the Claude micro of #986 at 18227acd (container tables, GFM 5.1 and 5.2): GitHub renders a third table and the guard said nothing.
        table = self.lines[self.source_header:self.last + 1]
        quoted = ["> " + line for line in table]
        listed = ["- " + table[0]] + ["  " + line for line in table[1:]]
        for label, copy in {"a block quote": quoted, "a list item": listed, "a block quote with a wrong-host row": quoted[:3] + [quoted[3].replace("code.claude.com", "invalid.example")] + quoted[4:]}.items():
            with self.subTest(copy=label):
                found = self.violations_of(self.page(self.lines + [""] + copy))
                self.assertTrue(any(f.startswith(OUTSIDE) for f in found))

    def test_a_delimiter_or_header_shaped_line_anywhere_else_in_the_file_is_a_violation(self):
        shaped = ["| --- | --- |", "|---|---|", "| :-- | --: |", "--- | ---", "> | --- | --- |", "- | --- | --- |", "| Need | Claude Code source |", "Need | Claude Code source", "> | Need | x |"]
        for label, line in {"before the mechanism heading": 3, "after the last source row": self.last + 1}.items():
            for text in shaped:
                with self.subTest(placed=label, line=text):
                    self.assertNotEqual(self.violations_of(self.inserted(line, [text])), [])

    def test_a_header_or_delimiter_that_is_not_the_canonical_one_is_a_violation(self):
        variants = {"single hyphens": "| - | - |", "alignment colons": "| :-- | --: |", "three leading spaces": "   | --- | --- |", "no outer pipes": "--- | ---", "four hyphens": "| ---- | ---- |", "a third cell": "| --- | --- | --- |"}
        for label, delimiter in variants.items():
            with self.subTest(delimiter=label):
                lines = list(self.lines)
                lines[self.source_header + 1] = delimiter
                self.assertNotEqual(self.violations_of(self.page(lines)), [])
        headers = {"another first cell": "| Needs | Claude Code source |", "another second cell": "| Need | Source |", "no outer pipes": "Need | Claude Code source", "a leading space": " | Need | Claude Code source |"}
        for label, header in headers.items():
            with self.subTest(header=label):
                lines = list(self.lines)
                lines[self.source_header] = header
                self.assertNotEqual(self.violations_of(self.page(lines)), [])
        for label, change in {"the blank line before the header removed": (self.source_header - 1, None), "a second blank line before the header": (self.source_header, ""),
                              "a blank line before the mechanism header removed": (self.mechanism_header - 1, None)}.items():
            with self.subTest(structure=label):
                lines = list(self.lines)
                index, value = change
                if value is None:
                    del lines[index]
                else:
                    lines.insert(index, value)
                self.assertNotEqual(self.violations_of(self.page(lines)), [])

    def test_a_carriage_return_a_three_space_indent_and_a_row_ending_in_an_escaped_pipe_are_violations(self):
        # The Claude micro of #986 at 18227acd (P3-2): the survivors of the reading's single-edit mutants, now in the structure: a lone carriage return, an indented row, a row that ends in an escaped pipe.
        row = self.lines[self.gate]
        replaced = lambda bad: self.page(self.lines[:self.gate] + [bad] + self.lines[self.gate + 1:])  # noqa: E731
        pages = {"a lone carriage return inside a row": replaced(row.replace(" | ", " |\r", 1)), "a lone carriage return at the end of a row": replaced(row + "\r"),
                 "a carriage return and a newline for every line": self.text.replace("\n", "\r\n"), "a three-space-indented row": replaced("   " + row),
                 "a row ending in an escaped pipe": replaced(row[:-2] + " \\|"), "a row with a no-break space before the closing pipe": replaced(row[:-2] + "\u00a0|")}
        for label, page in pages.items():
            with self.subTest(case=label):
                self.assertNotEqual(self.violations_of(page), [])

    def test_a_character_that_python_but_not_markdown_cuts_a_line_at_does_not_hide_what_follows_it(self):
        for separator in ("\u2028", "\u0085", "\x0b", "\x0c", "\x1c"):
            with self.subTest(separator=repr(separator)):
                row = self.lines[self.gate].rstrip(" |") + separator + "tail |"
                found = self.violations_of(self.page(self.lines[:self.gate] + [row] + self.lines[self.gate + 1:]))
                self.assertNotEqual(found, [], "the text after the separator is part of the cell")

    def test_text_that_is_not_a_space_or_a_tab_stays_in_the_cell(self):
        # the GFM specification trims "spaces" between pipes and cell content; a no-break space is content, and the cell with it is not a citation
        for character in ("\u00a0", "\u200b", "\x0b"):
            with self.subTest(character=repr(character)):
                row = self.lines[self.gate].rstrip(" |") + character + " |"
                self.assertNotEqual(self.violations_of(self.page(self.lines[:self.gate] + [row] + self.lines[self.gate + 1:])), [])

    def test_the_findings_name_what_is_missing_from_the_structure(self):
        def findings_of(lines):
            return read_page(self.page(lines))[2]

        def without(index):
            return self.lines[:index] + self.lines[index + 1:]

        heading = self.lines.index(MECHANISM_HEADING)
        cases = {"the blank line after the mechanism heading": (without(heading + 1), "blank line after the mechanism heading"),
                 "the blank line before the source paragraph": (without(self.marker - 1), "blank line before the source paragraph"),
                 "a blank line after the paragraph that has spaces in it": (self.lines[:self.source_header - 1] + ["  "] + self.lines[self.source_header:], "blank line after the source paragraph"),
                 "the mechanism header with another first cell": (self.lines[:heading + 2] + [self.lines[heading + 2].replace("Need", "Needs", 1)] + self.lines[heading + 3:], "mechanism table's header"),
                 "the mechanism header without the Codex cell": (self.lines[:heading + 2] + ["| Need | Claude Code 2.1.295 |"] + self.lines[heading + 3:], "mechanism table's header"),
                 "the mechanism delimiter": (self.lines[:heading + 3] + ["| - | - | - |"] + self.lines[heading + 4:], "mechanism table's delimiter"),
                 "the mechanism heading": ([("## Native mechanism" if line == MECHANISM_HEADING else line) for line in self.lines], "mechanism headings"),
                 "a second source paragraph": (self.lines + ["", SOURCES_MARKER + " again"], "source paragraphs")}
        for label, (lines, wanted) in cases.items():
            with self.subTest(case=label):
                self.assertTrue(any(wanted in f for f in findings_of(lines)), findings_of(lines))
        self.assertTrue(any("mechanism headings" in f for f in violations(*reversed(page_rows(self.page(cases["the mechanism heading"][0]))), self.captures)))

    def test_a_table_ends_at_the_first_line_that_is_not_a_row_in_both_tables(self):
        # what follows a line that is not a row is not a row of the table, whatever it looks like: GitHub ends the table there
        needs, rows, findings = read_page(self.inserted(self.mechanism_header + 3, ["<b>x</b> | y"]))
        self.assertEqual((len(needs), len(rows)), (1, 7))
        self.assertEqual(sum("mechanism table" in f for f in findings), 7)
        needs, rows, findings = read_page(self.inserted(self.gate + 1, ["<b>x</b> | y"]))
        self.assertEqual((len(needs), len(rows)), (7, 2))
        self.assertEqual(sum("source table" in f for f in findings), 6)

    def test_a_header_or_delimiter_copy_inside_a_table_is_reported_as_what_it_is(self):
        for label, line, index in (("a delimiter copy among the mechanism rows", MECHANISM_DELIMITER, self.mechanism_header + 3), ("a header copy among the mechanism rows", self.lines[self.mechanism_header], self.mechanism_header + 3),
                                   ("a delimiter copy among the source rows", SOURCE_DELIMITER, self.gate), ("a header copy among the source rows", SOURCE_HEADER, self.gate)):
            with self.subTest(copy=label):
                self.assertTrue(any("not a row of the" in f for f in read_page(self.inserted(index, [line]))[2]))

    def test_the_row_shapes_are_exact(self):
        need, cell = "Completion gate", "[hooks](https://code.claude.com/docs/en/hooks.md) line 1"
        self.assertIsNotNone(SOURCE_ROW.fullmatch(f"| {need} | {cell} |"))
        for label, line in {"leading spaces inside a cell": f"|  {need} | {cell} |", "trailing spaces inside a cell": f"| {need}  | {cell} |", "an empty cell": f"| {need} |  |", "a third cell": f"| {need} | {cell} | x |",
                            "a tab for a space": f"|\t{need} | {cell} |", "a pipe inside the cell": f"| {need} | a | b |", "a leading space": f" | {need} | {cell} |", "a missing closing pipe": f"| {need} | {cell}"}.items():
            with self.subTest(source_row=label):
                self.assertIsNone(SOURCE_ROW.fullmatch(line))
        three = "| Need | a | b |"
        self.assertIsNotNone(MECHANISM_ROW.fullmatch(three))
        for label, line in {"two cells": "| Need | a |", "four cells": "| Need | a | b | c |", "doubled spaces": "|  Need | a | b |"}.items():
            with self.subTest(mechanism_row=label):
                self.assertIsNone(MECHANISM_ROW.fullmatch(line))

    def test_a_table_without_outer_pipes_a_control_space_and_an_html_table_tag_are_reported_where_they_stand(self):
        # The command center's Claude micro of #986 at 23fa8ef7a (P2-1 to P2-3): the paragraph lines skipped the sweep, so a table without outer pipes (GFM 0.29-gfm section 4.10: the leading and trailing pipe are only
        # "recommended") passed; a vertical tab and a form feed are whitespace to the renderer (section 2.1) and space a delimiter row; raw HTML is rendered as written (section 6.10).
        end = self.source_header - 1
        cases = {"a table without outer pipes in the paragraph": (self.inserted(end, ["Need | Claude Code source", "--- | ---", "Completion gate | x"]), "not plain text inside the source paragraph"),
                 "a header-shaped line in the paragraph": (self.inserted(end, ["Need | Claude Code source"]), "not plain text inside the source paragraph"),
                 "a delimiter spaced with a vertical tab": (self.inserted(end, ["a | b", "---\x0b|\x0b---"]), "a vertical tab or a form feed"),
                 "a delimiter spaced with a form feed": (self.inserted(end, ["a | b", "---\x0c|\x0c---"]), "a vertical tab or a form feed"),
                 "an HTML table in the paragraph": (self.page(self.lines[:self.marker] + [self.lines[self.marker] + " <table><tr><td>x</td></tr></table>"] + self.lines[self.marker + 1:]), "an HTML table tag"),
                 "an uppercase HTML table tag with spaces": (self.inserted(end, ["x < TD > y"]), "an HTML table tag")}
        for label, (page, wanted) in cases.items():
            with self.subTest(case=label):
                self.assertTrue(any(wanted in finding for finding in read_page(page)[2]), read_page(page)[2])
        self.assertEqual(HTML_TABLE.search("a < b and c > d"), None, "a comparison is not a tag")
        self.assertEqual(read_page(self.text)[2], [], "the canonical page has none of them")

    def test_a_carriage_return_in_the_prose_hides_no_table_line(self):
        # GitHub ends a line at a lone carriage return too, so a table line can start after one inside a line that this reading sees as plain text
        for where, index in (("the head", 3), ("the source paragraph", self.marker + 1)):
            with self.subTest(placed=where):
                self.assertNotEqual(self.violations_of(self.inserted(index, ["plain text\r| Need | Claude Code source |\r| --- | --- |\r| x | y |"])), [])

    def test_the_source_of_this_module_spells_its_invisible_characters_as_escapes(self):
        # A literal no-break space, zero-width space or line separator cannot be seen in a review, and U+2028 is a line boundary for str.splitlines() (Python 3.13, Built-in Types, str.splitlines: the boundaries
        # include \x0b, \x0c, \x1c to \x1e, \x85, U+2028 and U+2029), the very boundary the reading under test is careful about. The cases of this class write such a character as an escape; this module is printable ASCII.
        source = Path(__file__).read_text(encoding="utf-8")
        hidden = sorted({f"U+{ord(c):04X}" for c in source if c != "\n" and not (c.isascii() and c.isprintable())})
        self.assertEqual(hidden, [], "write an invisible or non-ASCII character of this module as an escape")

    def test_the_cell_of_a_row_keeps_every_character_that_is_not_a_space_or_a_tab(self):
        self.assertEqual(split_cell(" \u00a0x ")[0], "\u00a0x")
        self.assertEqual(split_cell("\x0bx\t")[0], "\x0bx")

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
        paragraph = "\n".join(self.lines[self.marker:self.source_header - 1])
        for where, text in {"the page": paragraph, "the lines artifact": note, "line_digest": line_digest.__doc__}.items():
            with self.subTest(text=where):
                self.assertIn("a line that is followed by a newline", text)

    def regression_pages(self) -> dict[str, tuple[str, bool]]:
        """Pages the guard rejects, each with whether GitHub's renderer shows something other than the two canonical tables (a hidden or an added source row, a missing table)."""
        row, header, delimiter = self.lines[self.gate], self.lines[self.source_header], self.lines[self.source_header + 1]
        bad = row.replace("code.claude.com", "invalid.example", 1)
        table = self.lines[self.source_header:self.last + 1]
        remaining = self.lines[:self.gate] + self.lines[self.gate + 1:]
        para_end = self.source_header - 1  # the blank line after the source paragraph: lines inserted here end the paragraph
        return {
            "a wrong-host row led by <b> under the last source row": (self.inserted(self.last + 1, [bad.replace("| Completion gate |", "<b>Completion gate</b> |", 1)]), True),
            "a wrong-host row led by <span> under the last source row": (self.inserted(self.last + 1, [bad.replace("| Completion gate |", "<span>Completion gate</span> |", 1)]), True),
            "a wrong-host row led by </b> under the last source row": (self.inserted(self.last + 1, [bad.replace("| Completion gate |", "</b>Completion gate |", 1)]), True),
            "an autolink-led row under the last source row": (self.inserted(self.last + 1, [bad.replace("| Completion gate |", "<https://example.invalid> |", 1)]), True),
            "a backtick-fence line with a backtick in its info string, as a row": (self.inserted(self.last + 1, [bad.replace("| Completion gate |", "```Completion gate`x |", 1)]), True),
            "a line led by <! , as a row": (self.inserted(self.last + 1, [bad.replace("| Completion gate |", "<! Completion gate |", 1)]), True),
            "a <b> row for a new need under the mechanism table": (self.inserted(self.mechanism_end, ["<b>A need nobody cited</b> | a mechanism | a mechanism |"]), True),
            "the whole source table in an HTML comment": (self.page(self.lines[:self.source_header] + ["<!--", ""] + table + ["", "-->"]), True),
            "the Completion gate row moved to a second table": (self.page(remaining + ["", header, delimiter, row]), True),
            "the Completion gate row moved into a fenced block": (self.page(remaining + ["", "```", header, delimiter, row, "```"]), True),
            "the Completion gate row moved into a tilde fence": (self.page(remaining + ["", "~~~~", header, delimiter, row, "~~~~"]), True),
            "the Completion gate row moved into an HTML comment": (self.page(remaining + ["", "<!--", header, delimiter, row, "-->"]), True),
            "the Completion gate row moved into a block quote table": (self.page(remaining + ["", f"> {header}", f"> {delimiter}", f"> {row}"]), True),
            "the Completion gate row moved into a list item table": (self.page(remaining + ["", f"- {header}", f"  {delimiter}", f"  {row}"]), True),
            "a quoted copy of the source table with a wrong-host row": (self.page(self.lines + [""] + ["> " + line.replace(row, bad) for line in table]), True),
            "a list-item copy of the source table with a wrong-host row": (self.page(self.lines + [""] + ["- " + table[0]] + ["  " + line.replace(row, bad) for line in table[1:]]), True),
            "a pipe-less table (header, delimiter, row) at the end of the source paragraph": (self.inserted(para_end, ["Need | Claude Code source", "--- | ---", "Completion gate | [hooks](https://invalid.example/x) line 2587"]), True),
            "a pipe-less table with another header at the end of the source paragraph": (self.inserted(para_end, ["Gate | Source", "--- | ---", "Completion gate | x"]), True),
            "a pipe-less table with alignment colons at the end of the source paragraph": (self.inserted(para_end, ["Need | Claude Code source", ":---: | ---:", "Completion gate | x"]), True),
            "a pipe-less table after two more lines of prose in the source paragraph": (self.inserted(para_end, ["More prose.", "Even more prose.", "Need | Claude Code source", "--- | ---", "Completion gate | x"]), True),
            "a delimiter row spaced with a vertical tab in the source paragraph": (self.inserted(para_end, ["Need | Claude Code source", "---\x0b|\x0b---", "Completion gate | x"]), True),
            "a delimiter row spaced with a form feed in the source paragraph": (self.inserted(para_end, ["Need | Claude Code source", "---\x0c|\x0c---", "Completion gate | x"]), True),
            "an inline HTML table in the source paragraph": (self.page(self.lines[:self.marker] + [self.lines[self.marker] + " <table><tr><td>Completion gate</td><td>x</td></tr></table>"] + self.lines[self.marker + 1:]), True),
            "an uppercase HTML table inside a cell of the mechanism table": (self.page(self.lines[:self.mechanism_header + 2] + [self.lines[self.mechanism_header + 2][:-2] + " <TABLE><TR><TD>x</TD></TR></TABLE> |"] + self.lines[self.mechanism_header + 3:]), True),
            "a source-header copy inside the source paragraph (invisible, still not canonical)": (self.inserted(para_end, ["Need | Claude Code source"]), False),
            "an HTML comment under the last source row (invisible, still not canonical)": (self.inserted(self.last + 1, ["<!-- x -->"]), False),
            "one more blank line at the end of the page (invisible, still not canonical)": (self.text + "\n", False),
        }

    def test_every_regression_page_is_rejected_and_names_a_line_or_a_place_the_canonical_page_does_not_have(self):
        for label, (page, _dangerous) in self.regression_pages().items():
            with self.subTest(page=label):
                found = self.violations_of(page)
                self.assertNotEqual(found, [])
                self.assertTrue(any(f.startswith(OUTSIDE) or f.startswith("no source cell") or f.startswith("more than one") for f in found))

    @staticmethod
    def rendered_tables(markdown: str) -> list[dict]:
        """The tables GitHub's renderer shows for `markdown` (gh api markdown, mode gfm): per table its header cells and its body rows."""
        import html.parser

        class Reader(html.parser.HTMLParser):
            def __init__(self):
                super().__init__()
                self.tables, self.row, self.cell, self.head = [], None, None, False

            def handle_starttag(self, tag, attrs):
                if tag == "table":
                    self.tables.append({"header": [], "rows": []})
                elif tag == "thead":
                    self.head = True
                elif tag == "tbody":
                    self.head = False
                elif tag == "tr":
                    self.row = []
                elif tag in ("th", "td"):
                    self.cell = []

            def handle_data(self, data):
                if self.cell is not None:
                    self.cell.append(data)

            def handle_endtag(self, tag):
                if tag in ("th", "td") and self.cell is not None:
                    self.row.append("".join(self.cell).strip())
                    self.cell = None
                elif tag == "tr" and self.row is not None:
                    if self.head:
                        self.tables[-1]["header"] = self.row
                    else:
                        self.tables[-1]["rows"].append(self.row)
                    self.row = None

        reader = Reader()
        reader.feed(subprocess.run(["gh", "api", "markdown", "-f", "mode=gfm", "-f", f"text={markdown}", "-H", "Accept: application/vnd.github+json"], capture_output=True, check=True, text=True).stdout)
        return reader.tables

    @unittest.skipUnless(os.environ.get("GFM_RENDER_CHECK"), "set GFM_RENDER_CHECK=1 to render the page with GitHub's renderer (needs the gh CLI, a login and network)")
    def test_the_canonical_page_renders_exactly_the_two_expected_tables(self):
        tables = self.rendered_tables(self.text)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["header"][0], "Need")
        self.assertEqual(len(tables[0]["header"]), 3)
        self.assertEqual(tables[1]["header"], ["Need", "Claude Code source"])
        for table, width in zip(tables, (3, 2)):
            self.assertEqual([row[0] for row in table["rows"]], self.needs)
            self.assertTrue(all(len(row) == width for row in table["rows"]))

    @unittest.skipUnless(os.environ.get("GFM_RENDER_CHECK"), "set GFM_RENDER_CHECK=1 to render the page with GitHub's renderer (needs the gh CLI, a login and network)")
    def test_a_page_that_hides_or_adds_a_source_row_renders_differently(self):
        expected = self.rendered_tables(self.text)
        for label, (page, dangerous) in self.regression_pages().items():
            with self.subTest(page=label):
                if dangerous:
                    self.assertNotEqual(self.rendered_tables(page), expected, "GitHub shows something other than the two canonical tables, so the guard has to reject it")
                else:
                    self.assertEqual(self.rendered_tables(page), expected, "invisible on GitHub; the guard still rejects it as not canonical")


if __name__ == "__main__":
    unittest.main()
