"""The 2026-10-09 exports say which revision they describe, and the reading's local locators resolve there.

claude-native-slot-manifest.json was built from reference/slots.json as merged in #923, before the follow-up extended it,
and primary-source-reading.json cites the skill's reference pages by page and line as the readers saw them. Both are
baseline records: each names the revision (and, for the manifest, the hash) it describes, and the manifest names the
current decision source and the fields in which that source now differs: the exported fields slot by slot, and in its
note the other fields by name. The label checks read repository files only.
The checks that read the baseline revision from Git skip where the history lacks it (an archive without .git); CI checks
out the full history.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "evidence/artifacts/claude-native-practice-20261009"
MANIFEST = ARTIFACTS / "claude-native-slot-manifest.json"
READING = ARTIFACTS / "primary-source-reading.json"
SLOTS_REL = ".claude/skills/claude-native-practice/reference/slots.json"
REFERENCE_DIR = ".claude/skills/claude-native-practice/reference/"
BASELINE_REVISION = "a30c2188e4423f05a7448e5f7a3bcfd858e0f5b8"  # main with #923 merged
BASELINE_SLOTS_SHA256 = "a7d87f9a30f1654761f93f4edbde6735998a6dfd48b31549dfd5ad0e1dacdb95"
# A quoted phrase directly followed by a locator into one of the skill's reference pages: the form that lets a locator be
# checked without knowing what the sentence around it claims.
QUOTED_LOCATOR = re.compile(
    r"'([^']{12,}?)' \((?:<pr-checkout>/\.claude/skills/claude-native-practice/reference/|)"
    r"((?:slots|workers|token-efficiency|native-clients|instructions-skills|observation-inference|mcp-surfaces)\.md)"
    r":(\d+)(?:-(\d+))?\)")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def strings_of(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from strings_of(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_of(item)
    elif isinstance(value, str):
        yield value


def git_show(revision: str, path: str):
    shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{revision}:{path}"], capture_output=True)
    return shown.stdout if shown.returncode == 0 else None


def has_revision(revision: str) -> bool:
    try:
        probe = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{revision}^{{commit}}"], capture_output=True)
    except OSError:
        return False
    return probe.returncode == 0


def manifest_fields(row: dict) -> dict:
    """The fields the manifest carries for a slot, as a manifest row has them."""
    return {"status": row["status"], "default": row["default"], "layer_id": row["layer_id"], "route": row["route"],
            "alternatives": [alt["text"] for alt in row["alternatives"]], "rejections": row["rejections"],
            "overturn_when": row["overturn_when"], "evidence": row["evidence"]}


def slot_fields(slot: dict) -> dict:
    """The same fields, as a slot of reference/slots.json has them."""
    return {"status": slot["status"], "default": slot["default"], "layer_id": slot.get("layer_id"), "route": slot.get("route"),
            "alternatives": slot.get("alternatives") or [], "rejections": len(slot.get("rejections") or []),
            "overturn_when": slot.get("overturn_when"), "evidence": slot.get("evidence")}


def listing(items: list) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def unexported_difference_sentence(baseline: dict, current: dict) -> str:
    """The note's sentence on what differs outside the exported fields: the slot fields by name (no per-slot list, so an
    edit to one more slot's notes keeps it true) and the top-level keys."""
    then = {slot["id"]: slot for slot in baseline["slots"]}
    exported = {"id", *slot_fields({"status": None, "default": None})}  # the keys the manifest rows carry
    fields = sorted({key for slot in current["slots"] for key in set(slot) | set(then.get(slot["id"], {}))
                     if key not in exported and slot.get(key) != then.get(slot["id"], {}).get(key)})
    retired = [slot["id"] for slot in current["slots"] if slot.get("retired") != then.get(slot["id"], {}).get("retired")]
    named = [field for field in fields if field != "retired"] + [f"{slot_id}'s retired block" for slot_id in retired]
    top = sorted(key for key in set(baseline) | set(current) if key != "slots" and baseline.get(key) != current.get(key))
    return f"Slot fields this export does not carry also differ ({listing(named)}), and so do the top-level {listing(top)}."


class SnapshotLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.reading = json.loads(READING.read_text(encoding="utf-8"))
        cls.slots_raw = (ROOT / SLOTS_REL).read_bytes()
        cls.slots = {slot["id"]: slot for slot in json.loads(cls.slots_raw)["slots"]}
        cls.snapshot = cls.manifest["snapshot"]
        cls.current = cls.snapshot["current_decision_source"]
        cls.rows = {row["slot"]: row for row in cls.manifest["slots"]}

    def test_the_manifest_names_the_baseline_it_was_built_from(self):
        self.assertEqual(self.snapshot["kind"], "baseline")
        self.assertEqual(self.snapshot["revision"], BASELINE_REVISION)
        self.assertEqual(self.snapshot["slots_json_sha256"], BASELINE_SLOTS_SHA256)
        self.assertEqual(self.manifest["sources"]["slots.json"], BASELINE_SLOTS_SHA256)

    def test_the_reading_binds_its_local_locators_to_the_same_revision(self):
        self.assertEqual(self.reading["local_references"]["revision"], self.snapshot["revision"])

    def test_the_current_decision_source_is_named_and_is_the_file_the_skill_ships(self):
        self.assertEqual(self.current["path"], SLOTS_REL)
        self.assertRegex(self.current["sha256_when_labeled"], r"^[0-9a-f]{64}$")
        self.assertEqual(list(self.rows), list(self.slots))

    def test_each_listed_difference_holds_in_the_current_source(self):
        listed = self.current["differs_from_this_snapshot_in"]
        self.assertEqual(sorted(listed), ["alternatives", "default", "evidence", "overturn_when", "rejections", "route", "status"])
        for field, slot_ids in listed.items():
            for slot_id in slot_ids:
                with self.subTest(field=field, slot=slot_id):
                    self.assertNotEqual(manifest_fields(self.rows[slot_id])[field], slot_fields(self.slots[slot_id])[field])

    def test_the_label_names_the_shipped_slots_file(self):
        # A label on other bytes used to make the exact-difference test below skip without a failure: the forward commit of #1001 edited the selection_rule after the manifest was labeled, and the
        # check the description says runs was skipped (OK, skipped=1). A change to the slots file now has to carry its label.
        self.assertEqual(sha256(self.slots_raw), self.current["sha256_when_labeled"],
                         "reference/slots.json changed after the snapshot was labeled: set current_decision_source.sha256_when_labeled to its sha256 and make "
                         "differs_from_this_snapshot_in the differences the next test reports, then run scripts/evidence_manifest.py --write and register the changed files with scripts/host_receipts.register_file "
                         "(validate.py checks both)")

    def test_no_other_exported_field_differs(self):
        listed = {(field, slot_id) for field, slot_ids in self.current["differs_from_this_snapshot_in"].items()
                  for slot_id in slot_ids}
        actual = set()
        for slot_id, row in self.rows.items():
            then, now = manifest_fields(row), slot_fields(self.slots[slot_id])
            actual |= {(field, slot_id) for field in then if then[field] != now[field]}
        self.assertEqual(actual, listed)


class BaselineHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reading = json.loads(READING.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.revision = cls.reading["local_references"]["revision"]
        if not has_revision(cls.revision) or not has_revision(BASELINE_REVISION):
            raise unittest.SkipTest(f"the history of this checkout does not hold {cls.revision} and {BASELINE_REVISION}")

    def test_the_recorded_baseline_slots_file_has_the_recorded_hash(self):
        self.assertEqual(sha256(git_show(BASELINE_REVISION, SLOTS_REL)), BASELINE_SLOTS_SHA256)

    def test_the_manifest_rows_are_the_baseline_rows(self):
        baseline = {slot["id"]: slot for slot in json.loads(git_show(BASELINE_REVISION, SLOTS_REL))["slots"]}
        self.assertEqual([row["slot"] for row in self.manifest["slots"]], list(baseline))
        for row in self.manifest["slots"]:
            with self.subTest(slot=row["slot"]):
                self.assertEqual(manifest_fields(row), slot_fields(baseline[row["slot"]]))

    def test_the_note_names_what_differs_beyond_the_exported_fields(self):
        # The CC's read of #1234 at 1af2052c (P3): the note listed six slots whose notes differ from this snapshot when 21
        # did, and three of the five top-level keys that differ. It now names the fields instead of the slots; a field or
        # top-level key that starts or stops differing fails here, with the sentence to write.
        baseline = json.loads(git_show(BASELINE_REVISION, SLOTS_REL))
        current = json.loads((ROOT / SLOTS_REL).read_text(encoding="utf-8"))
        expected = unexported_difference_sentence(baseline, current)
        note = self.manifest["snapshot"]["current_decision_source"]["note"]
        self.assertIn(expected, note, f"set the note's sentence to: {expected}")

    def test_quoted_locators_resolve_at_the_bound_revision(self):
        found = [match.groups() for text in strings_of(self.reading["sources"]) for match in QUOTED_LOCATOR.finditer(text)]
        self.assertGreaterEqual(len(found), 6)  # the six the reading carries; fewer means the pattern stopped matching
        for phrase, page, first, last in found:
            with self.subTest(page=page, line=first):
                lines = git_show(self.revision, REFERENCE_DIR + page).decode("utf-8").split("\n")
                window = alnum(" ".join(lines[int(first) - 1:int(last or first)]))
                self.assertIn(alnum(phrase), window)


if __name__ == "__main__":
    unittest.main()
