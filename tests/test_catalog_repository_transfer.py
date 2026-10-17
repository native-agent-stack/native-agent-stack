"""Our own catalog rows name this repository under its current owner only.

Follow-up to #1073's finding P2-3, on the command center's rulings of
2026-10-16. build_manifest copies baseline rows from engines-strategies.json
and reconciliations-20260922.json into each dated manifest; #1073's record
named four former-owner pointers in them
(docs/decisions/2026-10-13-sweep-wave1-publication.md:84-92 at 1e5ceb91). A
fifth sits in the sources of the same engines catalog entry, and a sixth in
that entry's coverage.json row, which must name the entry's repository
(scripts/validate_catalogs.py:315-339 at 5bab6323).

Mechanism: GitHub redirects every link to a transferred repository's previous
location, and permanently deletes those redirects once a repository or fork is
created there (github/docs@cb051611377a0d2904411e6157154e9b4953d870
content/repositories/creating-and-managing-repositories/transferring-a-repository.md:62,68-69),
so a row relying on the redirect could resolve to another account's repository.
#1073 recorded GET repos/<former-owner>/native-agent-stack resolving to
native-agent-stack/native-agent-stack on 2026-10-13. The detector copies the
patterns of #1073's normalize_repository_urls verbatim
(tools/sota-convergence/landscape-sweep/convert.py:770-789 at 1e5ceb91, patterns
at :779-782): this repository's GitHub web or REST API URL and its pinned-locator
or bare-slug spelling under the former owner, case-insensitively. Another owner,
a similarly named repository, a non-GitHub host and the former owner's own
account links are not this repository and stay untouched. It reads every JSON
string, values and keys, as the converter's rewrite does, and reports JSON
pointers, never the matched text. The cases follow #1073's converter tests
(tests/test_landscape_sweep_harness.py:3954-4049 at 1e5ceb91).
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# Scope, per the 2026-10-16 rulings: the three files these rows live in.
CATALOGS = (
    "catalogs/us-equities/coverage.json",
    "catalogs/us-equities/engines-strategies.json",
    "tools/sota-convergence/reconciliations-20260922.json",
)
FORMER_OWNER = "seathatflowsinourveins"
CURRENT = "native-agent-stack/native-agent-stack"
URL = re.compile(r"(https?://(?:github\.com/|api\.github\.com/repos/))" + re.escape(FORMER_OWNER)
                 + r"/native-agent-stack(\.git)?(?=$|[^A-Za-z0-9_.-])", re.I)
LOCATOR = re.compile(r"(?<![\w/.-])" + re.escape(FORMER_OWNER)
                     + r"/native-agent-stack(?=@|$|[)\],;:!?\s])", re.I)


def names_former_owner(text: str) -> bool:
    return bool(URL.search(text) or LOCATOR.search(text))


def former_owner_pointers(value, pointer: str = ""):
    """Yield the RFC 6901 pointer of each string spelling this repository under the former owner.

    A matching key is reported by position, so no output repeats the spelling.
    """
    if isinstance(value, dict):
        for index, (key, item) in enumerate(value.items()):
            child = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            if names_former_owner(key):
                child = f"{pointer}/<key-{index}>"
                yield child
            yield from former_owner_pointers(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from former_owner_pointers(item, f"{pointer}/{index}")
    elif isinstance(value, str) and names_former_owner(value):
        yield pointer


class DetectorTests(unittest.TestCase):
    former = FORMER_OWNER + "/native-agent-stack"
    pin = "a" * 40

    def test_each_former_owner_spelling_of_this_repository_is_flagged(self):
        for text in (
            "https://github.com/" + self.former,
            "https://github.com/" + self.former + ".git",
            "https://github.com/" + self.former + "/blob/" + self.pin + "/README.md?plain=1#run-it",
            "HTTP://GITHUB.COM/" + self.former.upper(),
            "https://api.github.com/repos/" + self.former + "/contents/README.md?ref=" + self.pin + "#L12",
            self.former + "@" + self.pin + ":tools/sota-convergence/README.md:12",
            self.former,
            "source (" + self.former + ")",
        ):
            with self.subTest(text=text):
                self.assertTrue(names_former_owner(text))

    def test_current_owner_other_owners_similar_names_and_account_links_are_kept(self):
        for text in (
            "https://github.com/" + CURRENT,
            "https://github.com/" + CURRENT + "/blob/" + self.pin + "/README.md",
            "https://api.github.com/repos/" + CURRENT + "/contents/README.md",
            CURRENT + "@" + self.pin + ":README.md:1",
            "https://github.com/" + self.former + "-tools",
            "https://github.com/fixture-owner/native-agent-stack",
            "prefix-" + self.former,
            "other/" + self.former,
            "https://example.test/repos/" + self.former,
            "https://github.com/" + FORMER_OWNER,
            "https://api.github.com/users/" + FORMER_OWNER + "/starred?per_page=100",
        ):
            with self.subTest(text=text):
                self.assertFalse(names_former_owner(text))

    def test_walk_reports_value_and_key_pointers_without_the_spelling(self):
        url = "https://github.com/" + self.former
        document = {
            "entries": [{"repository": url,
                         "sources": ["https://github.com/" + CURRENT, url + "/blob/" + self.pin + "/README.md"]}],
            "notes": {url: "keyed by the former location", "kept": "https://github.com/" + CURRENT},
        }
        found = list(former_owner_pointers(document))
        self.assertEqual(found, ["/entries/0/repository", "/entries/0/sources/1", "/notes/<key-0>"])
        self.assertFalse(any(FORMER_OWNER in pointer for pointer in found))


class CatalogTests(unittest.TestCase):
    def test_baseline_catalogs_name_this_repository_under_its_current_owner_only(self):
        findings = []
        for relative in CATALOGS:
            document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            findings.extend(relative + "#" + pointer for pointer in former_owner_pointers(document))
        self.assertEqual(findings, [], "former-owner spellings of this repository at these JSON pointers")


if __name__ == "__main__":
    unittest.main()
