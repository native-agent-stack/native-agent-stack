"""tools/landscape/screen_generic.py is the retained G5 generic list screen with only its path constants edited.

It is this project's own G5 tool, not an upstream's, so landing it forks nothing. The original file's sha256 is the
one native-agent-stack/native-agent-stack@c8a29c3ee9b4337564165d9e588b3fe81e8ba817:catalogs/landscape/
grand-catalog-20261008.json:340 records: the commit that added that line, which still holds it (the parser of the 14
generic lists' populations). The release v2026.10.08 that was to carry the G5 archive was never published, so the
committed record is the binding. The original named host paths on lines 19-24 and 427-428; this module edits only
those lines. Restoring them as /home/<user>/ must give REDACTED_SHA256, which anyone can recompute from the committed
bytes. Where the retained original is present (the host that ran G5), the landed bytes with those lines restored
from it must give the recorded hash; elsewhere that test is skipped, an untested boundary. One mutated byte fails
both bindings.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "landscape" / "screen_generic.py"
GRAND = ROOT / "catalogs" / "landscape" / "grand-catalog-20261008.json"
PARSER_LINE = 340
ANCHOR_COMMIT = "c8a29c3ee9b4337564165d9e588b3fe81e8ba817"  # added line 340 (git blame), PR #878
MUTATED_LINE = 100  # a line outside the edited ones
REDACTED_SHA256 = "8b042c8810ad6e16f0cc4c23e0583d0d7e3d04717f579a6d9cf60dcb4f52580e"
RETAINED = "native-agent-stack/research/coverage-gap-20261008/landscape-stars/generic/screen_generic.py"
STATE = "/home/<user>/.local/state/native-agent-stack"
ORIGINAL_LINES = {
    19: "ROOT = Path('/home/<user>/code/native-agent-stack-ns2604-landscape-stars')",
    20: f"BASE = Path('{STATE}/research/coverage-gap-20261008/AE/generic/clones')",
    21: f"OUT = Path('{STATE}/research/coverage-gap-20261008/landscape-stars/generic')",
    22: f"GAP = Path('{STATE}/coordination/command-center/cc-tools/gaps/gaps.json')",
    23: f"BOARD = Path('{STATE}/coordination/ns2604-coop/readiness-20261005/jobs/BOARD-CLOSE-20261007T190934Z/"
        "board-revision-20261008T100346Z.json')",
    24: f"AMEND = Path('{STATE}/coordination/e2e-truth-20261006/s4-disposition-20261008T0400Z.amend-1017Z.md')",
    427: f"    methodology['reference_implementation']={{'path':'{STATE}/research/coverage-gap-20261008/AE/core/"
         "extract_lists.py',",
    428: f"                                             'sha256':hashlib.sha256(Path('{STATE}/research/"
         "coverage-gap-20261008/AE/core/extract_lists.py').read_bytes()).hexdigest(),",
}
LANDED_LINES = {
    19: "ROOT = Path(__file__).resolve().parents[2]  # this checkout (tools/landscape/screen_generic.py); "
        "a caller may reassign it",
    20: "BASE = None  # caller-set Path: one <owner>__<repo> clone per list, each checked out at its pin "
        "(extract, external_resources)",
    21: "OUT = None  # caller-set Path: run() reads OUT/'native-survivor-review.json'; artifacts() names its "
        "outputs under OUT",
    22: "GAP = None  # caller-set Path: run() reads the gap file's updated_utc",
    23: "BOARD = None  # caller-set Path: definitions() reads the readiness board's 'slots' list",
    24: "AMEND = REFERENCE = None  # caller-set Paths: run() records the S4 amendment and the reference "
        "implementation it names",
    427: "    methodology['reference_implementation']={'path':str(REFERENCE),",
    428: "                                             'sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),",
}
FIXTURE_README = """# Awesome Fixture

## Agents

- [agent-x](https://github.com/owner-a/agent-x) - A multi-agent framework for coding agents.
- [tracker](https://github.com/owner-b/repo-b/issues) - Issue tracker for agent-x.
- [Topic](https://github.com/topics/agents) - Topic page.
- [recipes](https://github.com/owner-c/recipes-app) - A cooking recipes manager.
- [ref-tool][r1] - Sandbox runtime for untrusted code.
- <a href="https://github.com/owner-e/tool-e">Tool E</a> - Vector database for retrieval augmented generation.
- https://github.com/owner-f/tool-f - backup and restore with restic.

## Lists

- [awesome-testing](https://github.com/owner-g/awesome-testing) - Awesome list of testing tools.
- [dashboard](https://example.org/tool) - Observability dashboard with Grafana.
- [badge](https://img.shields.io/badge/fixture-yes-green.svg)

[r1]: https://github.com/owner-d/tool-d
"""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def recorded_hash() -> str:
    line = GRAND.read_text(encoding="utf-8").splitlines()[PARSER_LINE - 1]
    match = re.search(r'"parser": "screen_generic\.py@([0-9a-f]{64}):', line)
    if match is None:
        raise AssertionError(f"{GRAND.name}:{PARSER_LINE} no longer names the screen_generic.py parser hash")
    return match.group(1)


def landed_lines() -> list[str]:
    return MODULE.read_bytes().decode("utf-8").split("\n")


def restored(lines: list[str], originals: dict[int, str]) -> bytes:
    """The landed lines with the edited ones put back."""
    rebuilt = list(lines)
    for number, text in originals.items():
        rebuilt[number - 1] = text
    return "\n".join(rebuilt).encode("utf-8")


def mutated(lines: list[str]) -> list[str]:
    """The same lines with one byte changed on a line outside the edited ones."""
    changed = list(lines)
    text = changed[MUTATED_LINE - 1]
    changed[MUTATED_LINE - 1] = text[:-1] + ("x" if text[-1:] != "x" else "y")
    return changed


def retained_path() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / RETAINED


def load_module():
    spec = importlib.util.spec_from_file_location("landscape_screen_generic_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LandedBytesTests(unittest.TestCase):
    def test_only_the_named_path_lines_differ_from_the_hashed_original(self):
        lines = landed_lines()
        self.assertEqual(len(lines), 508)  # 507 lines and the final newline
        for number, text in LANDED_LINES.items():
            with self.subTest(line=number):
                self.assertEqual(lines[number - 1], text)
        self.assertEqual(sha256(restored(lines, ORIGINAL_LINES)), REDACTED_SHA256)

    def test_one_mutated_byte_fails_the_redacted_binding(self):
        self.assertNotIn(MUTATED_LINE, LANDED_LINES)
        self.assertNotEqual(sha256(restored(mutated(landed_lines()), ORIGINAL_LINES)), REDACTED_SHA256)

    def test_the_anchor_commit_added_the_recorded_parser_hash(self):
        def show(revision):
            done = subprocess.run(["git", "-C", str(ROOT), "show", f"{revision}:{GRAND.relative_to(ROOT).as_posix()}"],
                                  capture_output=True, text=True)
            return done.stdout if done.returncode == 0 else None

        if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", ANCHOR_COMMIT + "^{commit}"],
                          capture_output=True).returncode:
            self.skipTest(f"{ANCHOR_COMMIT} is not in this clone (shallow?); the binding below still holds")
        at_anchor = show(ANCHOR_COMMIT).splitlines()
        self.assertIn(f"screen_generic.py@{recorded_hash()}:", at_anchor[PARSER_LINE - 1])
        self.assertEqual(at_anchor[PARSER_LINE - 1], GRAND.read_text(encoding="utf-8").splitlines()[PARSER_LINE - 1])
        before = show(ANCHOR_COMMIT + "^")
        self.assertTrue(before is None or recorded_hash() not in before)

    def test_the_landed_module_names_no_host_path(self):
        self.assertIsNone(re.search(r"/home/(?!<user>)[^/\s'\"]+/", MODULE.read_text(encoding="utf-8")))

    def test_the_recorded_parser_hash_binds_every_generic_list_population(self):
        import json
        grand = json.loads(GRAND.read_text(encoding="utf-8"))
        parsers = {item["parser"].split(";")[0] for item in grand["coverage"]["list_populations"]
                   if item["parser"].startswith("screen_generic.py@")}
        self.assertEqual(parsers, {f"screen_generic.py@{recorded_hash()}:extract/external_resources"})

    @unittest.skipUnless(retained_path().is_file(), "the retained G5 original is not on this host (untested boundary)")
    def test_the_retained_original_is_the_recorded_bytes(self):
        raw = retained_path().read_bytes()
        self.assertEqual(sha256(raw), recorded_hash())
        self.assertNotEqual(sha256(raw[:-2] + bytes([raw[-2] ^ 1]) + raw[-1:]), recorded_hash())  # one mutated byte
        original = raw.decode("utf-8").split("\n")
        landed = landed_lines()
        self.assertEqual(len(original), len(landed))
        self.assertEqual([index + 1 for index, (a, b) in enumerate(zip(original, landed)) if a != b],
                         sorted(LANDED_LINES))
        self.assertEqual(sha256(re.sub(rb"/home/[^/]+/", b"/home/<user>/", raw)), REDACTED_SHA256)

    @unittest.skipUnless(retained_path().is_file(), "the retained G5 original is not on this host (untested boundary)")
    def test_the_landed_bytes_with_the_path_lines_restored_are_the_recorded_hash(self):
        original = retained_path().read_bytes().decode("utf-8").split("\n")
        put_back = {number: original[number - 1] for number in LANDED_LINES}
        self.assertEqual(sha256(restored(landed_lines(), put_back)), recorded_hash())
        self.assertNotEqual(sha256(restored(mutated(landed_lines()), put_back)), recorded_hash())


class SyntheticListTests(unittest.TestCase):
    """extract() and external_resources() on a committed synthetic list: no upstream bytes, no network."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        clone = base / "fixture-owner__awesome-fixture"
        clone.mkdir()
        (clone / "README.md").write_text(FIXTURE_README, encoding="utf-8")
        (clone / "CONTRIBUTING.md").write_text("- [x](https://github.com/owner-z/ignored)\n", encoding="utf-8")
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_AUTHOR_NAME="fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                           GIT_COMMITTER_NAME="fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--no-gpg-sign", "-m", "fixture"]):
            subprocess.run(["git", "-C", str(clone), *args], check=True, env=environment, capture_output=True)
        cls.head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], check=True, capture_output=True,
                                  text=True, env=environment).stdout.strip()
        module = load_module()
        csv.field_size_limit(8_000_000)
        module.BASE, module.REPOS = base, ["fixture-owner/awesome-fixture"]
        cls.summary, cls.rows = module.extract("fixture-owner/awesome-fixture", {}, [])
        cls.external, cls.ignored = module.external_resources({}, [])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_census_counts(self):
        self.assertEqual(self.summary["pin"], self.head)
        self.assertEqual((self.summary["document_files_scanned"], self.summary["entries_extracted"],
                          self.summary["unique_repository_links"]), (1, 8, 7))
        self.assertEqual(self.summary["counts_by_disposition"], {"WATCH": 4, "OUT-OF-SCOPE": 3, "NO-GAP": 1})
        self.assertEqual(self.summary["counts_by_kind"], {"github-reference": 7, "administrative-reference": 1})
        self.assertEqual(self.summary["excluded_files"]["administrative_markdown"], ["CONTRIBUTING.md"])

    def test_each_occurrence_keeps_the_g5_rules(self):
        observed = [(row["repository"], row["line"], row["kind"], row["disposition"], row["layer_ids"],
                     row["lifecycle_fields"]) for row in self.rows]
        self.assertEqual(observed, [
            ("owner-a/agent-x", 5, "github-reference", "WATCH", ["workers", "agent-sdks"], []),
            ("owner-b/repo-b", 6, "administrative-reference", "OUT-OF-SCOPE", [], []),
            ("owner-c/recipes-app", 8, "github-reference", "OUT-OF-SCOPE", [], []),
            ("owner-d/tool-d", 9, "github-reference", "WATCH", ["isolation", "security-supply-chain"], []),
            ("owner-e/tool-e", 10, "github-reference", "WATCH", ["semantic-rag", "storage-compute"], []),
            ("owner-f/tool-f", 11, "github-reference", "WATCH", ["recovery-portability", "observability-hosting"], []),
            ("owner-g/awesome-testing", 15, "github-reference", "NO-GAP", ["quality-evaluation"], ["skills-test"]),
            ("owner-d/tool-d", 19, "github-reference", "OUT-OF-SCOPE", [], []),
        ])
        self.assertTrue(all(row["citation"] == f"fixture-owner/awesome-fixture@{self.head}:README.md:{row['line']}"
                            for row in self.rows))

    def test_external_references_and_ignored_badges(self):
        self.assertEqual([(row["target"], row["line"], row["disposition"]) for row in self.external],
                         [("https://example.org/tool", 16, "WATCH")])
        self.assertEqual(self.ignored, {"badges-images-sponsors": 1})


if __name__ == "__main__":
    unittest.main()
