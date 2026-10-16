"""Owner chat is paraphrased on publication, never quoted: every tracked text file up to MAX_BYTES is checked, within
the bounds below.

The no-owner-quote rule of 2026-10-14 supersedes the round-2 resolution to quote the owner exactly. The command center's
FULL read of #1161 at c95453a1 (2026-10-15) found owner sentences still quoted in files outside the three the earlier check
read, and ruled a tree-wide scanner with a ratchet: tests/fixtures/owner-quote-baseline.json lists, by path, how many
owner-attribution hits each file still holds (names and counts only, never text) for the burn-down PRs. A file the
baseline does not list must be clean, and a listed count may not change unless the baseline changes with it, so a fixed
file lowers its count in the same commit, and a new quotation on a line or paragraph with no counted hit fails here. The
check is structural: it holds no owner text, and its messages give path:line locators only.

Bounds (the command center's adjudication of #1161 at 9bcb8133, 2026-10-15); each is a Follow-up in #1161's body:
- a file over MAX_BYTES (8 MB) is not scanned (the scanner's size bound);
- several attributions in one line or one paragraph count once, so a quotation added beside a counted one leaves the
  count unchanged (C1: the detector's restructure);
- a block quote is attributed by the paragraph or list item just above it, read whole, when that names the owner and ends
  with a colon (the ruling of 2026-10-16 at 768d9cc0, which also closed C3, an introduction wrapped across lines); an
  introduction further away is not read (a CommonMark parser stays a PROPOSAL routed to the layer-resolution protocol).
"""
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "fixtures" / "owner-quote-baseline.json"
MAX_BYTES = 8_000_000

# The owner, or the user as these records also call the owner; a slot or setting named after them (memory-owner) is not
# a speaker.
OWNER = r"(?<![\w-])(?:owner|user)(?:'s|’s)?(?![\w-])"
# A block quote that is itself a dated paraphrase is not a quotation.
PARAPHRASE = re.compile(r"^\s*>\s*the (?:owner|user), \d{4}-\d{2}-\d{2} \(paraphrased\)", re.IGNORECASE)
SPEECH = (r"(?<![\w-])(?:ask(?:s|ed|ing)?|answer(?:s|ed)?|request(?:s|ed)?|said|says|told|wrote|words|"
          r"quot(?:e|es|ed|ing)|verbatim)(?![\w-])")
GAP = "[^\"“”|]"
# An opening quote mark: a double quote, an opening typographic single quote, or a straight or typographic single quote
# that opens a word (not an apostrophe inside or after one, as in the team’s or it’s).
QUOTE = "(?:[\"“”‘]|(?<![\\w])['’](?=\\w))"
# A closing quote mark: a double quote, or a single quote that ends a word or its punctuation.
CLOSE = "(?:[\"“”]|(?<=[\\w.,!?])['’](?!\\w))"
# The owner and a speech word close together, then a quote mark, or a closing quote mark followed by them, within one
# sentence.
ATTRIBUTED = re.compile(rf"(?:{OWNER}{GAP}{{0,80}}?{SPEECH}|{SPEECH}{GAP}{{0,80}}?{OWNER}){GAP}{{0,160}}?{QUOTE}"
                        rf"|{CLOSE}{GAP}{{0,30}}?{OWNER}{GAP}{{0,30}}?{SPEECH}", re.IGNORECASE)
# An attribution without a speech word: the owner, then within a short span a colon and a quote mark ("The user to this
# session: ..."). The command center's adjudication of #1161 at 9371e2ad (P2-2).
INTRODUCED = re.compile(rf"{OWNER}{GAP}{{0,60}}?:\s*{QUOTE}", re.IGNORECASE)
# An attribution by possessive: the owner's (or the user's) words, direction or requirement, then within a short span a
# quoted phrase of two or more words, with no speech word or colon. The command center's adjudication of #1161 at
# e21a7b61 (P1). The phrase must open on a letter and close on the line, so a string literal's closing delimiter in code
# ("the user's home directory") is not a quotation, nor is a quoted dated-paraphrase prefix.
DATED = r"(?!the (?:owner|user), \d{4}-\d{2}-\d{2} \(paraphrased\))"
QUOTED_PHRASE = (rf"(?:[\"“‘]{DATED}[^\W\d_][^\"“”‘’\n]{{0,200}}?\s[^\"“”‘’\n]{{0,200}}?[\"”’]"
                 rf"|(?<!\w)'{DATED}[^\W\d_][^'\n]{{0,200}}?\s[^'\n]{{0,200}}?'(?!\w))")
POSSESSED = re.compile(rf"(?<![\w-])(?:owner|user)(?:'s|’s)(?![\w-]){GAP}{{0,80}}?{QUOTED_PHRASE}", re.IGNORECASE)
# A line that calls the owner's text verbatim.
VERBATIM_CLAIM = re.compile(rf"{OWNER}[^\n.]{{0,80}}verbatim|verbatim[^\n.]{{0,80}}{OWNER}", re.IGNORECASE)
# A field that holds the owner's words.
WORDS_KEY = re.compile(r'"(?:owner_words|owner_verbatim|owner_quote|owner_quotation)"\s*:\s*"[^"]')
# A verbatim field in a file that records owner decisions.
VERBATIM_KEY = re.compile(r'"verbatim"\s*:\s*"[^"]')
OWNER_RECORD = re.compile(r'"(?:owner_decision|owner_decisions)"')
# A block quote introduced by a sentence that names the owner and ends with a colon, with or without a speech word. The
# command center's ruling of 2026-10-16 on #1161 at 768d9cc0 (a count read found real block quotes introduced without one).
BLOCK_INTRO = re.compile(rf"{OWNER}[^\n]{{0,600}}:\s*$", re.IGNORECASE)


JSON_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
# Markdown wraps prose across physical lines: a paragraph runs on until a blank line or a line that opens a
# new block (a list item, heading, table row or code fence); block-quote lines join only each other. The command
# center's adjudication of #1161 at e21a7b61 (the GPT read's and the local review's P2s, line boundaries).
# Plain-text files here are mostly captures, logs and code copies, read line by line.
WRAPPED = (".md", ".markdown", ".rst")
BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#|\||```|~~~)")
FENCE = re.compile(r"^\s*(?:```|~~~)")
# A sentence ends at . ! or ? and whitespace before a capital letter; an attribution never reaches into the next one.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def prose(line, as_json):
    """The texts of a line to check: the line itself, or in JSON each string value decoded on its own, so a value's
    delimiting quote marks are not read as quotation and an escaped quote inside it is."""
    if not as_json:
        return [line]
    texts = []
    for match in JSON_STRING.finditer(line):
        try:
            texts.append(json.loads(f'"{match.group(1)}"'))
        except ValueError:
            texts.append(match.group(1))
    return texts


def units(lines, as_json, wrapped):
    """(text, starts) for each unit of prose, where starts maps offsets in the text to the 1-based lines joined into it:
    each physical line (each JSON string value on its own), or in wrapped text each paragraph, list item or block quote."""
    if as_json or not wrapped:
        for number, line in enumerate(lines, 1):
            for part in prose(line, as_json):
                yield part, [(0, number)]
        return
    text, starts, quoted, fenced = "", [], False, False
    for number, line in enumerate(lines, 1):
        stripped = line.lstrip()
        is_quote = not fenced and stripped.startswith(">")
        body = stripped[1:].strip() if is_quote else line.strip()
        alone = fenced or FENCE.match(line) or (BLOCK_START.match(body) and body[:1] in "#|")
        if FENCE.match(line):
            fenced = not fenced
        if alone or not body or not text or is_quote != quoted or BLOCK_START.match(body):
            if text:
                yield text, starts
            text, starts, quoted = "", [], is_quote
            if alone:
                yield line, [(0, number)]
                continue
            if not body:
                continue
        else:
            text += " "
        starts.append((len(text), number))
        text += body
    if text:
        yield text, starts


def sentences(text):
    """(offset, sentence) for each sentence of a unit."""
    begin = 0
    for end in SENTENCE_END.finditer(text):
        yield begin, text[begin:end.start()]
        begin = end.end()
    yield begin, text[begin:]


def introduction(lines, number, wrapped):
    """The text that introduces a block quote whose first line is the 1-based `number`: the nearest line with content
    within three lines above it, and in wrapped text the whole paragraph or list item that line ends, joined, since the
    attribution can sit in an earlier sentence of it. The command center's ruling of 2026-10-16 on #1161 at 768d9cc0."""
    index = next((i for i in range(number - 2, max(-1, number - 5), -1) if lines[i].strip().lstrip(">").strip()), None)
    if index is None:
        return ""
    if not wrapped or lines[index].lstrip().startswith(">"):
        return lines[index]
    start = index
    while start > 0 and not BLOCK_START.match(lines[start].strip()):
        above = lines[start - 1]
        if not above.strip() or above.lstrip().startswith(">") or FENCE.match(above):
            break
        start -= 1
    return " ".join(line.strip() for line in lines[start:index + 1])


def line_hits(text, as_json=False, wrapped=True):
    """1-based line numbers of owner-attribution hits in a text, never the text itself: each attribution is matched
    within one sentence and located at the line where it starts. Text is read as wrapped prose unless it is JSON or the
    caller says otherwise (scan() wraps only Markdown and reStructuredText)."""
    lines = text.splitlines()
    owner_record = bool(OWNER_RECORD.search(text))
    found = set()
    for unit, starts in units(lines, as_json, wrapped):
        for begin, sentence in sentences(unit):
            for detector in (ATTRIBUTED, INTRODUCED, POSSESSED, VERBATIM_CLAIM):
                match = detector.search(sentence)
                if match:
                    found.add(max(number for at, number in starts if at <= begin + match.start()))
    for number, line in enumerate(lines, 1):
        hit = WORDS_KEY.search(line) or (owner_record and VERBATIM_KEY.search(line))
        if not hit and line.lstrip().startswith(">") and line.strip().lstrip(">").strip() and not PARAPHRASE.match(line):
            hit = BLOCK_INTRO.search(introduction(lines, number, wrapped and not as_json))
        if hit:
            found.add(number)
    return sorted(found)


def tracked_files(root=ROOT):
    """The repository's tracked files (git ls-files), or every file under the root outside .git in an export."""
    try:
        listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True, timeout=120,
                                check=True).stdout.split("\0")
        return sorted(name for name in listed if name)
    except (OSError, subprocess.SubprocessError):
        names = []
        for directory, subdirectories, files in os.walk(root):
            subdirectories[:] = [name for name in subdirectories if name != ".git"]
            names += [str(Path(directory, name).relative_to(root)) for name in files]
        return sorted(names)


def scan(root=ROOT):
    """{path: [line numbers]} for every tracked text file with an owner-attribution hit."""
    found = {}
    for name in tracked_files(root):
        path = root / name
        try:
            if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = line_hits(text, as_json=name.endswith((".json", ".jsonl")), wrapped=name.endswith(WRAPPED))
        if lines:
            found[name] = lines
    return found


class OwnerQuotePublication(unittest.TestCase):
    def test_every_tracked_file_matches_the_ratchet_baseline(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["files"]
        found = scan()
        new = {name: lines for name, lines in found.items() if name not in baseline}
        changed = {name: (baseline[name], len(found.get(name, []))) for name in baseline
                   if baseline[name] != len(found.get(name, []))}
        self.assertEqual(new, {}, "owner text is paraphrased with its date ('the owner, <date> (paraphrased): they ...'), "
                                  "never quoted; these files are not in tests/fixtures/owner-quote-baseline.json")
        self.assertEqual(changed, {}, "(baseline, now) per file: a fixed file lowers its baseline count in the same commit, "
                                      "and a count may never rise")

    def test_the_detector_finds_attributed_owner_text_and_passes_paraphrases(self):
        quoted = {"attributed": 'The owner asked: "light every fixture lane now".',
                  "verbatim": "The owner's order, verbatim, as relayed:",
                  "field": '{"owner_words": "light every fixture lane now"}',
                  "block": "The owner wrote at 10:00Z:\n\n> light every fixture lane now",
                  "no speech word": 'The user to this session: "light every fixture lane now".',
                  "single quotes": "the record keeps the owner's words 'light every fixture lane now'",
                  "possessive": "The user's recorded direction is 'light every fixture lane now'.",
                  "single quotes before the speaker": "'light every fixture lane now,' the owner said.",
                  "typographic quotes before the speaker": "‘light every fixture lane now,’ the owner said."}
        for label, text in quoted.items():
            with self.subTest(case=label):
                self.assertTrue(line_hits(text))
        # Wrapped prose: the attribution and its quotation on separate physical lines of one paragraph or list item,
        # located at the attribution's line; a code fence and a separate paragraph do not join.
        wrapped = {"wrapped after the attribution": ("Notes\n\nThe owner asked:\n\"light every fixture lane now\"", [3]),
                   "wrapped list item": ("- The owner asked on 2026-10-04\n  for this: \"light every fixture lane now\"", [1]),
                   "wrapped block quote": ("> The owner asked on 2026-10-04\n> for this: \"light every fixture lane now\"", [1])}
        for label, (text, lines) in wrapped.items():
            with self.subTest(case=label):
                self.assertEqual(line_hits(text, wrapped=True), lines)
        for label, text in {"separate paragraphs": 'The owner asked for lit lanes.\n\n"Delivered" runs count.',
                            "code fence": 'The owner asked:\n```\n"light every fixture lane now"\n```'}.items():
            with self.subTest(case=label):
                self.assertEqual(line_hits(text, wrapped=True), [])
        self.assertTrue(line_hits('{"kind": "owner_decision", "verbatim": "light every fixture lane now"}', as_json=True))
        self.assertTrue(line_hits('{"note": "The owner asked: \\"light every fixture lane now\\"."}', as_json=True))
        self.assertEqual(line_hits('{"paraphrase": "the owner, 2026-10-15 (paraphrased): they asked for lit lanes"}',
                                   as_json=True), [])
        passing = {"paraphrase": "the owner, 2026-10-15 (paraphrased): they asked for every fixture lane to be lit.",
                   "protocol": 'The contract counts "delivered" runs.',
                   "slot": 'the memory-owner row quotes the release notes: "fixture notes"',
                   "verbatim elsewhere": '{"verbatim": "a test needle"}',
                   "apostrophes": "the owner's decision and the user's rule stand; it's the lane's call",
                   "string literal": 'help="the user\'s home directory", default="~"',
                   "format string": 'raise SystemExit(f"the owner\'s outcome: {identifier}")',
                   "paraphrase prefix": "the owner's paraphrase begins 'the owner, 2026-10-04 (paraphrased): '",
                   "typographic apostrophes": "the owner, 2026-10-15 (paraphrased): they asked to respect the team’s "
                                              "defaults; it’s the lane’s call",
                   "a separate quoted sentence": "the owner, 2026-10-15 (paraphrased): they asked for every fixture lane "
                                                 "to be lit. The contract counts \"delivered\" runs."}
        for label, text in passing.items():
            with self.subTest(case=label):
                self.assertEqual(line_hits(text), [])

    def test_a_block_quote_introduced_by_a_wrapped_sentence_is_found(self):
        """The command center's ruling of 2026-10-16 on #1161 at 768d9cc0: a count read found real block quotes whose
        introduction the check at BLOCK_INTRO missed, the class its adjudication at 9bcb8133 recorded as C3 (an
        introduction wrapped across lines). The introduction is the last sentence of the paragraph above the quote, read
        whole. Synthetic text only."""
        found = {"wrapped introduction": ("Notes.\n\nOn 2026-01-02 the owner wrote this to the fixture\nlane, in their "
                                          "own words:\n\n> keep the lanterns lit on every shelf", [6]),
                 "wrapped, no blank line": ("On 2026-01-02 the owner wrote this to the fixture\nlane, in their own "
                                            "words:\n> keep the lanterns lit on every shelf", [3]),
                 "one line, as before": ("The owner wrote at 10:00Z:\n\n> keep the lanterns lit on every shelf", [3]),
                 "no speech word": ("The owner's 2026-01-02 decision sets the shelf rule; its wording\nfollows the "
                                    "owner's line:\n\n> keep the lanterns lit on every shelf", [4]),
                 "inside a block quote": ("> The owner's notes for the next unit:\n>\n> - keep the lanterns lit on "
                                          "every shelf", [3]),
                 "the owner in an earlier sentence": ("The owner's 2026-01-02 decision sets the shelf rule. Its wording\n"
                                                      "follows:\n\n> keep the lanterns lit on every shelf", [4]),
                 "the owner in a list item's label": ("1. **The owner** (2026-01-02). Their first position:\n   > keep "
                                                      "the lanterns lit on every shelf", [2])}
        for label, (text, lines) in found.items():
            with self.subTest(case=label):
                self.assertEqual(line_hits(text, wrapped=True), lines)
        passing = {"no owner in the introduction": ("On 2026-01-02 the lead wrote this to the fixture\nlane, in their "
                                                    "own words:\n\n> keep the lanterns lit on every shelf"),
                   "a dated paraphrase under it": ("On 2026-01-02 the owner wrote this to the fixture\nlane, in their own "
                                                   "words:\n\n> the owner, 2026-01-02 (paraphrased): they asked that "
                                                   "every shelf stay lit"),
                   "a separate paragraph between": ("The owner wrote these words:\n\nThe lead then asked for a list.\n\n> "
                                                    "keep the lanterns lit on every shelf"),
                   "a role owner": "The handoffs to the component owners:\n\n> - keep the lanterns lit on every shelf",
                   "a hyphenated role": "The memory-owner row lists:\n\n> keep the lanterns lit on every shelf",
                   "no colon": "The owner set the shelf rule on 2026-01-02.\n\n> keep the lanterns lit on every shelf"}
        for label, text in passing.items():
            with self.subTest(case=label):
                self.assertEqual(line_hits(text, wrapped=True), [])

    def test_the_baseline_holds_names_and_counts_only(self):
        document = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(set(document), {"schema", "rule", "files"})
        self.assertTrue(all(isinstance(name, str) and isinstance(count, int) and count > 0
                            for name, count in document["files"].items()))


if __name__ == "__main__":
    unittest.main()
