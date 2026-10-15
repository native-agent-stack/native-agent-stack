"""Owner chat is paraphrased on publication, never quoted: every tracked text file is checked.

The no-owner-quote rule of 2026-10-14 supersedes the round-2 resolution to quote the owner exactly. The command center's
FULL read of #1161 at c95453a1 (2026-10-15) found owner sentences still quoted in files outside the three the earlier check
read, and ruled a tree-wide scanner with a ratchet: tests/fixtures/owner-quote-baseline.json lists, by path, how many
owner-attribution hits each file still holds (names and counts only, never text) for the burn-down PRs. A file the
baseline does not list must be clean, and a listed count may not change unless the baseline changes with it, so a fixed
file lowers its count in the same commit and a new quotation fails here. The check is structural: it holds no owner text,
and its messages give path:line locators only.
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
# The owner and a speech word close together, then a quote mark, or a closing quote mark followed by them, within one line.
ATTRIBUTED = re.compile(rf"(?:{OWNER}{GAP}{{0,80}}?{SPEECH}|{SPEECH}{GAP}{{0,80}}?{OWNER}){GAP}{{0,160}}?[\"“”]"
                        rf"|[\"“”]{GAP}{{0,30}}?{OWNER}{GAP}{{0,30}}?{SPEECH}", re.IGNORECASE)
# A line that calls the owner's text verbatim.
VERBATIM_CLAIM = re.compile(rf"{OWNER}[^\n.]{{0,80}}verbatim|verbatim[^\n.]{{0,80}}{OWNER}", re.IGNORECASE)
# A field that holds the owner's words.
WORDS_KEY = re.compile(r'"(?:owner_words|owner_verbatim|owner_quote|owner_quotation)"\s*:\s*"[^"]')
# A verbatim field in a file that records owner decisions.
VERBATIM_KEY = re.compile(r'"verbatim"\s*:\s*"[^"]')
OWNER_RECORD = re.compile(r'"(?:owner_decision|owner_decisions)"')
# A block quote introduced by a line that attributes it to the owner.
BLOCK_INTRO = re.compile(rf"{OWNER}[^\n]{{0,160}}(?:verbatim|quoted|said|wrote|asked|answer(?:ed)?|order|words)[^\n]{{0,80}}:\s*$",
                         re.IGNORECASE)


JSON_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


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


def line_hits(text, as_json=False):
    """1-based line numbers of owner-attribution hits in a text, never the text itself."""
    lines = text.splitlines()
    owner_record = bool(OWNER_RECORD.search(text))
    found = []
    for number, line in enumerate(lines, 1):
        hit = (any(ATTRIBUTED.search(part) or VERBATIM_CLAIM.search(part) for part in prose(line, as_json))
               or WORDS_KEY.search(line) or (owner_record and VERBATIM_KEY.search(line)))
        if not hit and line.lstrip().startswith(">") and not PARAPHRASE.match(line):
            before = next((lines[index] for index in range(number - 2, max(-1, number - 5), -1) if lines[index].strip()), "")
            hit = BLOCK_INTRO.search(before)
        if hit:
            found.append(number)
    return found


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
        lines = line_hits(text, as_json=name.endswith((".json", ".jsonl")))
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
                  "block": "The owner wrote at 10:00Z:\n\n> light every fixture lane now"}
        for label, text in quoted.items():
            with self.subTest(case=label):
                self.assertTrue(line_hits(text))
        self.assertTrue(line_hits('{"kind": "owner_decision", "verbatim": "light every fixture lane now"}', as_json=True))
        self.assertTrue(line_hits('{"note": "The owner asked: \\"light every fixture lane now\\"."}', as_json=True))
        self.assertEqual(line_hits('{"paraphrase": "the owner, 2026-10-15 (paraphrased): they asked for lit lanes"}',
                                   as_json=True), [])
        passing = {"paraphrase": "the owner, 2026-10-15 (paraphrased): they asked for every fixture lane to be lit.",
                   "protocol": 'The contract counts "delivered" runs.',
                   "slot": 'the memory-owner row quotes the release notes: "fixture notes"',
                   "verbatim elsewhere": '{"verbatim": "a test needle"}'}
        for label, text in passing.items():
            with self.subTest(case=label):
                self.assertEqual(line_hits(text), [])

    def test_the_baseline_holds_names_and_counts_only(self):
        document = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(set(document), {"schema", "rule", "files"})
        self.assertTrue(all(isinstance(name, str) and isinstance(count, int) and count > 0
                            for name, count in document["files"].items()))


if __name__ == "__main__":
    unittest.main()
