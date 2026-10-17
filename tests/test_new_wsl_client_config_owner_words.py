"""Publication privacy for adoption/new-wsl/client-config-map.json: no string value quotes the owner.

A2 audit finding G8-A01: at 90471d63 three values (entries[29] source at line 306, entries[33] note at line 345 and
entries[46] source at line 488) quoted the owner's words in quotation marks, and two of them (lines 306 and 345)
referred to the owner with a gendered pronoun. The repository's own publication form for the owner's words is a
dated, attributed paraphrase using they/them, never a quotation: docs/new-wsl-handbook.json:852 ("Owner (they/them),
paraphrased"), docs/decisions/2026-10-12-converged-candidates-only.md:56 ("paraphrased, not quoted") and
evidence/artifacts/new-wsl-install-plan-20261002/NO_START_PORTS.md:498-506, whose guard checks fields and counts in
memory without keeping the quoted text. These checks follow that form: they walk every string in the map, report
counts and locations only, and never print a matched value. The fixtures below are built from synthetic words.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_REL = "adoption/new-wsl/client-config-map.json"
MAP = ROOT / MAP_REL
BASE = "90471d63f20918efa3a63ef949caffd8c012656c"  # the head that still carried the quotations
REMOVED_AT_BASE = 4  # quotations: two in entries[29], one each in entries[33] and entries[46]

OPEN = "\"“‘"
# A directive, decision or request dated by a date or by "the same day", then straight away an opening quotation
# mark: 'directive of 2001-02-03 ("...' or 'directive of the same day ("...'. A date that closes a citation, as in
# "read 2026-10-04)", or a quoted setting value, as in = "accept", does not match.
DATED_QUOTE = re.compile(
    r"\b(directive|instruction|request|words|decision|answer|ask|asked|said|wrote|message|prompt)\b"
    rf"[^.;{OPEN}]{{0,40}}?(\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b(the|that) same day\b|\b(that day|today|yesterday)\b)"
    rf"\s*[(:,]?\s*[{OPEN}]",
    re.IGNORECASE,
)
# The owner's (or user's) decision, directive, answer or the like, then an opening quotation mark before the clause
# ends: 'The owner's decision of 2001-02-03 (a tool, about 01:02Z): "...'.
ATTRIBUTED_QUOTE = re.compile(
    r"\b(owner|user)(?:'s|’s)?\s+(?:own\s+)?"
    r"(directive|instruction|request|words|decision|answer|ask|reply|message|prompt|yes)\b"
    rf"[^.;{OPEN}]{{0,80}}[{OPEN}]",
    re.IGNORECASE,
)
QUOTE_PATTERNS = (DATED_QUOTE, ATTRIBUTED_QUOTE)
GENDERED = re.compile(r"\b(he|him|his|himself|she|her|hers|herself)\b", re.IGNORECASE)
# A quoted passage of prose (five words or more), as opposed to a quoted setting value such as "accept".
QUOTATION = re.compile(r"[\"“]([^\"”]*)[\"”]")


def strings(value, path="$"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, f"{path}[{index}]")


def quotations(text):
    """(offset of the opening mark, quoted text) for every quoted passage of five words or more."""
    return [(m.start(), m.group(1)) for m in QUOTATION.finditer(text) if len(m.group(1).split()) >= 5]


def flagged_by_a_quote_pattern(text, opening):
    """True when one quote pattern, on its own, ends exactly at this opening quotation mark."""
    return any(m.end() - 1 == opening for pattern in QUOTE_PATTERNS for m in pattern.finditer(text))


class ClientConfigMapOwnerWordsTests(unittest.TestCase):
    def test_patterns_on_synthetic_fixtures(self):
        for flagged in (
            'Set on the owner\'s directive of 2001-02-03 ("alpha beta gamma delta epsilon zeta").',
            "their request of 2001-02-03: “alpha beta gamma delta epsilon”",
            'kept on a directive of the same day ("alpha beta gamma delta epsilon").',
        ):
            self.assertIsNotNone(DATED_QUOTE.search(flagged))
            (opening, _), = quotations(flagged)
            self.assertTrue(flagged_by_a_quote_pattern(flagged, opening))
        attributed = 'The owner\'s decision of 2001-02-03 (a tool, about 01:02Z): "alpha beta gamma delta epsilon"'
        self.assertIsNotNone(ATTRIBUTED_QUOTE.search(attributed))
        (opening, _), = quotations(attributed)
        self.assertTrue(flagged_by_a_quote_pattern(attributed, opening))
        for clean in (
            'Claude Code crossSessionInbound = "accept" (settings reference, read 2026-10-04), which it carries.',
            "on the owner's directive of 2001-02-03 to enable every current feature on the new distribution",
            "on a directive of the same day to keep alpha beta gamma",
            "the other sessions; there is no hero here",
        ):
            self.assertIsNone(DATED_QUOTE.search(clean))
            self.assertIsNone(ATTRIBUTED_QUOTE.search(clean))
            self.assertIsNone(GENDERED.search(clean))
        self.assertIsNotNone(GENDERED.search("the reviewer said she would retry the alpha run"))

    def test_no_string_quotes_a_dated_directive(self):
        data = json.loads(MAP.read_text(encoding="utf-8"))
        hits = [path for path, text in strings(data) if DATED_QUOTE.search(text)]
        self.assertEqual(hits, [], f"{len(hits)} value(s) quote a dated directive (locations only)")

    def test_no_string_quotes_an_attributed_owner_decision(self):
        data = json.loads(MAP.read_text(encoding="utf-8"))
        hits = [path for path, text in strings(data) if ATTRIBUTED_QUOTE.search(text)]
        self.assertEqual(hits, [], f"{len(hits)} value(s) quote an owner decision (locations only)")

    def test_no_string_uses_a_gendered_pronoun(self):
        data = json.loads(MAP.read_text(encoding="utf-8"))
        hits = [path for path, text in strings(data) if GENDERED.search(text)]
        self.assertEqual(hits, [], f"{len(hits)} value(s) use a gendered pronoun (locations only)")

    def test_every_quotation_removed_since_the_base_matches_a_quote_pattern_on_its_own(self):
        # The base's quoted text is read from git into memory and compared there; only locations are reported.
        present = subprocess.run(["git", "cat-file", "-e", f"{BASE}^{{commit}}"], cwd=ROOT, capture_output=True)
        if present.returncode != 0:
            self.skipTest(f"{BASE} is not present as a commit object in this clone (likely a shallow clone)")
        base_raw = subprocess.run(["git", "show", f"{BASE}:{MAP_REL}"], cwd=ROOT, capture_output=True, check=True)
        base = json.loads(base_raw.stdout.decode("utf-8"))
        head = MAP.read_text(encoding="utf-8")
        head_values = [text for _, text in strings(json.loads(head))]
        removed = [
            (path, opening, text)
            for path, text in strings(base)
            for opening, quoted in quotations(text)
            if not any(quoted in value for value in head_values)
        ]
        self.assertEqual(len(removed), REMOVED_AT_BASE, "quotations removed since the base (count only)")
        unflagged = [f"{path}@{opening}" for path, opening, text in removed
                     if not flagged_by_a_quote_pattern(text, opening)]
        self.assertEqual(unflagged, [], f"{len(unflagged)} removed quotation(s) no quote pattern flags (locations only)")


if __name__ == "__main__":
    unittest.main()
