"""Publication privacy for adoption/new-wsl/client-config-map.json: no string value quotes the owner.

A2 audit finding G8-A01: two values carried the owner's dated directive in quotation marks, and one referred to
the owner with a gendered pronoun. The rule (AGENTS.md, the owner-chat-unquoted rule) is that the owner's chat
words are never quoted on a publication surface and the owner is "the owner", never he or she. These checks walk
every string in the committed map, report counts and locations only, and never print a matched value. The
fixtures below are built from synthetic words.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "adoption" / "new-wsl" / "client-config-map.json"

# A dated directive, decision or request followed straight away by an opening quotation mark: "directive of
# 2026-01-01 ("...". A date that closes a citation, as in "read 2026-10-04)", or a quoted setting value, as in
# = "accept", does not match.
DATED_QUOTE = re.compile(
    r"\b(directive|instruction|request|words|decision|answer|ask|asked|said|wrote|message|prompt)\b"
    r"[^.;\"“‘]{0,40}?\b\d{4}-\d{2}-\d{2}\b\s*[(:,]?\s*[\"“‘]",
    re.IGNORECASE,
)
# The owner's (or user's) decision, directive, answer or the like, then an opening quotation mark before the clause
# ends: 'The owner's decision of 2001-02-03 (a tool, about 01:02Z): "...'.
ATTRIBUTED_QUOTE = re.compile(
    r"\b(owner|user)(?:'s|’s)?\s+(?:own\s+)?"
    r"(directive|instruction|request|words|decision|answer|ask|reply|message|prompt|yes)\b"
    r"[^.;\"“‘]{0,80}[\"“‘]",
    re.IGNORECASE,
)
GENDERED = re.compile(r"\b(he|him|his|himself|she|her|hers|herself)\b", re.IGNORECASE)


def strings(value, path="$"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, f"{path}[{index}]")


class ClientConfigMapOwnerWordsTests(unittest.TestCase):
    def test_patterns_on_synthetic_fixtures(self):
        flagged = 'Set on the owner\'s directive of 2001-02-03 ("alpha beta gamma delta epsilon zeta").'
        self.assertIsNotNone(DATED_QUOTE.search(flagged))
        self.assertIsNotNone(DATED_QUOTE.search("their request of 2001-02-03: “alpha beta”"))
        self.assertIsNotNone(ATTRIBUTED_QUOTE.search(
            'The owner\'s decision of 2001-02-03 (a tool, about 01:02Z): "alpha beta gamma delta"'))
        for clean in (
            'Claude Code crossSessionInbound = "accept" (settings reference, read 2026-10-04), which it carries.',
            "on the owner's directive of 2001-02-03 to enable every current feature on the new distribution",
            "the other sessions; there is no hero here",
        ):
            self.assertIsNone(DATED_QUOTE.search(clean))
            self.assertIsNone(ATTRIBUTED_QUOTE.search(clean))
            self.assertIsNone(GENDERED.search(clean))
        self.assertIsNotNone(GENDERED.search("and his yes on the posture"))

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


if __name__ == "__main__":
    unittest.main()
